#!/usr/bin/env python3
# ruff: noqa: DTZ007
"""모의투자 실시간 자동매매 — ACTIVE_STRATEGY 분기 (cross_momentum / multi_regime / short_swing).

스크리닝 통과 종목을 장중 실시간 감시하며 조건 충족 시 매수/매도한다.
ActiveStrategy enum으로 전략을 선택:
  - cross_momentum: 월말 리밸런싱 기반 전략 (WebSocket, polling 불가)
  - multi_regime: 레짐별 복수 전략 병행 (WebSocket 기본 + polling 60초 폴백)
  - short_swing: 단기 스윙 (09:20~13:00 진입, 09:20~15:10 청산, 15:20 미체결 취소)
  - none: 전략 없이 종료 (테스트용)

사용법:
    python scripts/live_trader.py --auto                          # cross_momentum (WebSocket 기본)
    python scripts/live_trader.py --auto --mode polling           # multi_regime 전용 60초 폴링 모드
    python scripts/live_trader.py --auto --strategy momentum      # multi_regime: 모멘텀만
    python scripts/live_trader.py --auto --strategy mean_reversion # multi_regime: 평균회귀만
    python scripts/live_trader.py --symbols 005930,000660

필수 환경변수:
    KIWOOM_MOCK_APP_KEY, KIWOOM_MOCK_APP_SECRET
    KIWOOM_MOCK_ACCOUNT: 모의투자 계좌번호 (잔고 조회용)

동작:
    ws 모드 (기본):
    1. 거래일 일봉 데이터 로드 (스크리닝/모멘텀 계산용)
    2. WebSocket 구독 → 실시간 틱 수신 → 전략별 진입/청산 신호 체크
    3. 동적 포지션 사이징 (ATR 기반) + 드로우다운 킬스위치
    4. 조건 충족 시 시장가 주문 실행
    5. 15:15 미청산 포지션 강제 청산
    6. 15:35 자동 종료
    7. WebSocket 연결 실패 시 폴링 모드로 자동 폴백 (multi_regime 한정)

    polling 모드 (multi_regime 전용):
    1~6 동일, 2번만 60초 주기 REST 폴링으로 처리
    cross_momentum/none 모드는 polling 진입 시 자동 차단
"""

import argparse
import asyncio
import glob as glob_mod
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.trading.cross_momentum_rebalance import (
        CrossMomentumRebalanceAdapter,
    )

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.screen_symbols import get_sector
from src.ai.signal.position_sizer import StrategyBudget, calc_atr, calc_dynamic_position_size
from src.backtest.strategy import MomentumParams
from src.broker.constants import MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.realtime import KiwoomWebSocket
from src.broker.schemas import DailyPrice, OrderRequest, OrderSideEnum, OrderTypeEnum, RealtimeTick
from src.config.active_strategy import ActiveStrategy, get_active_strategy
from src.config.database import async_session_factory
from src.notification.commands import parse_command
from src.notification.executor import TradingContext, execute_command
from src.notification.handler import TelegramHandler
from src.notification.telegram import TelegramNotifier
from src.strategy import MeanReversionParams, MeanReversionStrategy, MomentumStrategy
from src.strategy.base import Strategy
from src.strategy.flow_signal import FlowSignal
from src.strategy.indicators import VolatilityClass, classify_volatility
from src.strategy.theme_detector import ThemeDetector
from src.trading.drawdown_guard import DrawdownAction, update_drawdown
from src.trading.live_order_persist import (
    get_is_mock,
    persist_order_submitted,
    resolve_live_trader_user_id,
)
from src.trading.market_context import MarketContext
from src.trading.market_regime import MarketRegime, RegimeConfig, detect_regime
from src.utils.secret_masking import SecretMaskingFilter
from src.utils.time import now_kst

# ── 설정 ───────────────────────────────────────────────

_TRADER_USER_ID: uuid.UUID = uuid.uuid4()  # kill_switch용 세션 고정 ID
RESULTS_DIR = Path("docs/backtest-results")
POLL_INTERVAL_SEC = 60  # 1분 (WS fallback 시)
MARKET_CLOSE_HHMM = "1535"  # 이 시각 이후 루프 종료
DEFAULT_INVEST_PER_TRADE = 500_000  # 1회 투자금 (원)
DEFAULT_ACCOUNT_BALANCE = 10_000_000  # 기본 계좌 잔고 (1천만원)
FORCE_CLOSE_HHMM = (
    "1515"  # 미청산 포지션 강제 청산 시각 (마감 모멘텀 캡처 + 동시호가 5분 안전 마진)
)
RESCREEN_TIMES = ("1000", "1100")  # 장중 재스크리닝 실행 시각
OVERNIGHT_PATH = "data/overnight_positions.json"  # 스윙 포지션 overnight 저장 경로
GAP_RISK_THRESHOLD = -0.03  # 갭 하락 손절 기준 (-3%)
MAX_HOLDING_DAYS = 5  # 최대 보유 거래일

# ── ATR 동적 손절 파라미터 ─────────────────────────────
MIN_ATR_PCT = 0.0020  # 0.20% 미만이면 진입 스킵 (대형주 진입 허용)
ATR_STOP_MULT = 1.2  # 손절 = ATR의 1.2배
ATR_TP_MULT = 3.0  # 익절 = ATR의 3.0배 (R:R = 1:2)

# ── 마이크로구조 개선 (ADR-015) ─────────────────────────
# 지정가 주문 기본 전환: 왕복 슬리피지 0.85% → 0.30%
LIMIT_ORDER_TIMEOUT_SEC = 30  # 미체결 지정가 취소 후 시장가 전환 대기 시간(초)

# 진입 차단 시간대: (시작HHMM, 종료HHMM) 리스트.
# 점심 저유동성(11:30~13:00)에서 실패가 집중되므로 진입 차단.
ENTRY_BLOCKED_WINDOWS: list[tuple[str, str]] = [("1130", "1300")]

# True이면 09:00~09:30 시초가 변동성 구간 신규 진입 차단.
BLOCK_OPEN_VOLATILITY: bool = False

# 긴급 시장가 청산 사유 — 해당 reason이면 호가 조회 없이 즉시 시장가 매도.
_MARKET_SELL_REASONS: frozenset[str] = frozenset(
    {"stop_loss", "force_close", "gap_risk", "holding_limit", "kill_switch", "end_of_day"}
)
MIN_STOP_PCT = 0.005  # 바닥: 최소 0.5% 손절폭 (Kevin Davey floor 패턴)

# ── FlowSignal 진입 필터 (feature flag 기반, design-009 PR B) ──
# 기본 비활성. USE_FLOW_SIGNAL=true 설정 시 FlowSignal로 강한 매도 압력 모멘텀 진입 차단.
FLOW_SIGNAL_BEARISH_THRESHOLD = -0.2  # score 이하면 bearish 판정(진입 차단)

# ── ThemeDetector 진입 필터 (feature flag 기반, design-009 PR C) ──
# 기본 비활성. USE_THEME_BOOST=true 설정 시 차가운 테마 종목의 모멘텀 진입 차단.
# 핫 테마(>= 0.6)는 허용(기존 경로, 사실상 '가산' 효과). 테마 미분류(score 0.0)도 차단 대상.
THEME_COLD_THRESHOLD = 0.3  # get_theme_score() < 이 값이면 cold → 진입 차단

# ── 웹 제어 파일 경로 (프로젝트 루트 기준 절대 경로) ──────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
KILL_SWITCH_FILE = _PROJECT_ROOT / "data" / ".kill_switch"
PID_FILE = _PROJECT_ROOT / "data" / ".trader.pid"

log = logging.getLogger("live_trader")


def _is_flow_signal_enabled() -> bool:
    """USE_FLOW_SIGNAL 환경변수 활성 여부를 반환한다.

    Returns:
        True이면 FlowSignal 진입 필터 활성(기본 False).
    """
    return os.environ.get("USE_FLOW_SIGNAL", "false").lower() in ("true", "1", "yes")


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _compute_volume_ratio_override(
    base_volume_ratio: float,
    market_value_ratio: float,
    *,
    clamp_low: float = 0.5,
    clamp_high: float = 1.5,
) -> float:
    """시장 거래대금 비율을 반영한 동적 volume_ratio_override (Design 013).

    시장 전체 거래대금이 평균 대비 낮으면 종목 거래량 임계치도 완화,
    높으면 강화한다. 극단값 방지를 위해 [clamp_low, clamp_high]로 제한.

    Args:
        base_volume_ratio: 전략의 기본 volume_ratio (params.volume_ratio)
        market_value_ratio: today / 5d_avg (1.0 = 평균)
        clamp_low: 거래대금 비율 하한 (기본 0.5)
        clamp_high: 거래대금 비율 상한 (기본 1.5)

    Returns:
        effective volume_ratio = base * clamp(market_value_ratio, low, high)
    """
    scale = _clamp(market_value_ratio, clamp_low, clamp_high)
    return base_volume_ratio * scale


def _load_market_style(market_ctx: "MarketContext | None") -> "object | None":
    """MarketContext에서 데이터 읽어 현재 MarketStyle을 판단 (Design 013).

    MarketContext가 None이거나 필요한 데이터가 부족하면 None 반환.
    호출자(flag 체크 완료 후)는 None일 때 스타일 기반 분배를 건너뛴다.

    Args:
        market_ctx: MarketContext 인스턴스. None 허용.

    Returns:
        MarketStyle 또는 None (판단 불가 시).
    """
    if market_ctx is None:
        return None
    # lazy import — MarketContext는 상단에서 이미 import됨, style만 추가 지연 로드
    from src.trading.market_style import detect_style

    if not isinstance(market_ctx, MarketContext):
        return None

    # KOSPI close/MA 및 market_value_ratio는 MarketContext 캐시에서.
    # kospi_close/ma12 페이로드는 _apply_kospi_regime에서 'above_ma12'만 반영되므로
    # 실제 값 접근은 내부 속성으로만 가능 — detect_style은 수치를 원하므로
    # MarketContext에 전용 getter가 추가되기 전까지 근사치로 ratio 기반 판단만.
    #
    # 근사 판단: above_ma12 상승/하락 방향 + market_value_ratio로 대략적 분류.
    above = market_ctx.get_kospi_above_ma12()
    ratio = market_ctx.get_market_value_ratio()

    # detect_style이 KOSPI close/MA 수치를 요구하므로 대체 호출:
    # kospi_close=1.0, kospi_ma=1.0 (같으므로 gap=0) → band 안이라 RANGE 후보
    # 이를 피하고자 above_ma12에 따라 close에 약간의 offset 부여.
    # ATR% 미상 → 보수적으로 0.02 (RANGE 후보 탈락 방향)
    if above:
        kospi_close = 1.02
        kospi_ma = 1.00
    else:
        kospi_close = 0.98
        kospi_ma = 1.00
    atr_pct = (
        0.02  # RANGE 기준(0.015) 초과 → 기본적으로 RANGE 탈락, bull 방향이면 STRONG/QUIET 분기
    )

    return detect_style(
        kospi_close=kospi_close,
        kospi_ma=kospi_ma,
        kospi_adx=None,
        market_value_ratio=ratio,
        atr_pct=atr_pct,
    )


# 변동성 버킷 → 적합 전략 집합 (Design 013 PR9)
_HIGH_VOL_STRATEGIES: frozenset[str] = frozenset({"momentum", "pullback"})
_LOW_VOL_STRATEGIES: frozenset[str] = frozenset({"mean_reversion", "range_trade"})


def _distribute_strategies(
    syms: list[str],
    weights: dict[str, float],
    out: dict[str, str],
) -> None:
    """종목 리스트를 가중치 비례로 전략에 할당한다 (in-place).

    종목은 ticker 순 정렬로 결정론적 분배. 마지막 전략에 나머지 전부 할당.

    Args:
        syms: 분배 대상 종목 코드 리스트
        weights: {전략명: 가중치} (합 <= 1.0)
        out: 결과를 저장할 dict
    """
    if not syms or not weights:
        return
    total = sum(weights.values())
    n = len(syms)
    sorted_syms = sorted(syms)
    sorted_strats = sorted(weights.items(), key=lambda x: -x[1])
    idx = 0
    for i, (strat_name, w) in enumerate(sorted_strats):
        count = n - idx if i == len(sorted_strats) - 1 else round(n * w / total)
        for sym in sorted_syms[idx : idx + count]:
            out[sym] = strat_name
        idx += count
        if idx >= n:
            break


def _assign_symbol_strategies(
    daily_prices: dict[str, list["DailyPrice"]],
    market_style: object | None,
) -> dict[str, str]:
    """종목별 전략 분배 (Design 013 PR9).

    get_active_strategy() != ActiveStrategy.MULTI_REGIME 또는 market_style 없음:
      classify_volatility → MEAN_REVERSION → "mean_reversion", 나머지 → "momentum"

    get_active_strategy() == ActiveStrategy.MULTI_REGIME + market_style 있음:
      REGIME_STRATEGY_WEIGHTS 가중치에 따라 비례 분배.
      - 고변동(CONSERVATIVE/MOMENTUM) 종목 → momentum/pullback 풀
      - 저변동(MEAN_REVERSION) 종목 → mean_reversion/range_trade 풀
      - 풀에 해당 전략 가중치 없으면 기본값(momentum/mean_reversion) 폴백.

    Args:
        daily_prices: {symbol: 일봉 데이터} 맵
        market_style: MarketStyle 인스턴스 또는 None

    Returns:
        {symbol: 전략명} 맵
    """
    result: dict[str, str] = {}

    if get_active_strategy() != ActiveStrategy.MULTI_REGIME or market_style is None:
        for sym, daily in daily_prices.items():
            vol = classify_volatility(daily)
            result[sym] = "mean_reversion" if vol == VolatilityClass.MEAN_REVERSION else "momentum"
        return result

    from src.trading.regime_strategy_map import get_strategy_weights

    weights = get_strategy_weights(market_style)  # type: ignore[arg-type]
    if not weights:
        for sym, daily in daily_prices.items():
            vol = classify_volatility(daily)
            result[sym] = "mean_reversion" if vol == VolatilityClass.MEAN_REVERSION else "momentum"
        return result

    high_vol: list[str] = []
    low_vol: list[str] = []
    for sym, daily in daily_prices.items():
        vol = classify_volatility(daily)
        if vol == VolatilityClass.MEAN_REVERSION:
            low_vol.append(sym)
        else:
            high_vol.append(sym)

    high_weights = {k: v for k, v in weights.items() if k in _HIGH_VOL_STRATEGIES}
    low_weights = {k: v for k, v in weights.items() if k in _LOW_VOL_STRATEGIES}

    if high_vol:
        if high_weights:
            _distribute_strategies(high_vol, high_weights, result)
        else:
            for sym in high_vol:
                result[sym] = "momentum"

    if low_vol:
        if low_weights:
            _distribute_strategies(low_vol, low_weights, result)
        else:
            for sym in low_vol:
                result[sym] = "mean_reversion"

    return result


def _log_strategy_distribution(symbol_strategies: dict[str, str]) -> None:
    """전략 분배 결과를 INFO 레벨로 로그한다 (Design 013 PR9 runtime 증거).

    Args:
        symbol_strategies: {symbol: 전략명} 맵
    """
    counts: dict[str, int] = {}
    for strat in symbol_strategies.values():
        counts[strat] = counts.get(strat, 0) + 1
    parts = [f"{s} {n}개" for s, n in sorted(counts.items())]
    log.info(
        "종목 전략 분배 완료 (멀티레짐 %s): %s",
        "on" if get_active_strategy() == ActiveStrategy.MULTI_REGIME else "off",
        ", ".join(parts) if parts else "없음",
    )
    if counts.get("pullback", 0):
        log.info("pullback 종목 %d개", counts["pullback"])
    if counts.get("range_trade", 0):
        log.info("range 종목 %d개", counts["range_trade"])


def _should_block_by_flow_signal(
    market_ctx: MarketContext | None,
    symbol: str,
) -> bool:
    """FlowSignal 판정으로 모멘텀 신규 진입을 차단해야 하는지 검사한다.

    feature flag `USE_FLOW_SIGNAL`가 false면 항상 False(차단 안 함) — 기존 경로 100% 유지.
    활성화된 경우 MarketContext 수급을 기반으로 `FlowSignal.score()`를 계산하고,
    `FLOW_SIGNAL_BEARISH_THRESHOLD` 이하이면 True를 반환한다.

    Args:
        market_ctx: 시장 컨텍스트(None이면 차단하지 않음).
        symbol: 대상 종목코드.

    Returns:
        True이면 bearish 수급으로 진입 차단 필요. False이면 기존 경로 유지.
    """
    if not _is_flow_signal_enabled():
        return False
    if market_ctx is None:
        return False
    try:
        market_flow = market_ctx.get_investor_flow()
        stock_flows = market_ctx.get_stock_investor_flows()
    except Exception:
        log.debug("FlowSignal 데이터 조회 실패 — 차단하지 않음", exc_info=True)
        return False
    if not market_flow:
        # 데이터 부재 시 기존 동작 유지(차단 안 함)
        return False
    flow = FlowSignal(market_flow=market_flow, stock_flows=stock_flows)
    score = flow.score(symbol)
    blocked = score <= FLOW_SIGNAL_BEARISH_THRESHOLD
    log.info(
        "[%s] FlowSignal score=%.2f (flag ON, %s)",
        symbol,
        score,
        "진입 차단" if blocked else "진입 허용",
    )
    return blocked


def _is_theme_boost_enabled() -> bool:
    """USE_THEME_BOOST 환경변수 활성 여부를 반환한다.

    Returns:
        True이면 ThemeDetector 진입 필터 활성(기본 False).
    """
    return os.environ.get("USE_THEME_BOOST", "false").lower() in ("true", "1", "yes")


def _build_sector_map(symbols: list[str]) -> dict[str, list[str]]:
    """symbol→sector을 ThemeDetector 입력 형식(sector→[symbols])으로 역변환한다.

    Args:
        symbols: 대상 종목 리스트(현재 감시 유니버스).

    Returns:
        테마→[종목코드] 딕셔너리. 분류 없는 종목은 '기타' 섹터로 집계.
    """
    # scripts.screen_symbols.get_sector()를 활용해 각 symbol의 섹터 조회
    # lazy import: 순환 참조 회피는 불필요(이미 live_trader가 screen_symbols에 의존)
    sector_to_symbols: dict[str, list[str]] = {}
    for sym in symbols:
        sector = get_sector(sym)
        sector_to_symbols.setdefault(sector, []).append(sym)
    return sector_to_symbols


def _should_block_by_theme(
    market_ctx: MarketContext | None,
    symbol: str,
    symbols: list[str],
) -> bool:
    """ThemeDetector 판정으로 모멘텀 신규 진입을 차단해야 하는지 검사한다.

    feature flag `USE_THEME_BOOST`가 false면 항상 False(차단 안 함) — 기존 경로 100%.
    활성 시 종목 테마 점수가 `THEME_COLD_THRESHOLD` 미만이면 True(차단).
    핫 테마/중립 테마는 기존 경로 유지.

    Args:
        market_ctx: 시장 컨텍스트(None이면 차단 안 함).
        symbol: 대상 종목코드.
        symbols: 감시 유니버스(sector_map 구성용).

    Returns:
        True이면 cold 테마로 진입 차단 필요. False이면 기존 경로 유지.
    """
    if not _is_theme_boost_enabled():
        return False
    if market_ctx is None:
        return False
    try:
        theme_scores = market_ctx.get_theme_scores()
    except Exception:
        log.debug("ThemeDetector 데이터 조회 실패 — 차단하지 않음", exc_info=True)
        return False
    if not theme_scores:
        # 테마 점수 미존재 → 기존 동작 유지
        return False
    # LLM 테마 어휘를 CANONICAL_SECTORS로 정규화 (예: "기술주"→"반도체")
    from scripts.screen_symbols import canonicalize_theme

    normalized_scores: dict[str, float] = {}
    for raw_theme, score in theme_scores.items():
        canonical = canonicalize_theme(raw_theme)
        # 같은 canonical로 매핑되는 여러 원본 테마는 max 점수 채택
        if canonical not in normalized_scores or score > normalized_scores[canonical]:
            normalized_scores[canonical] = score
    sector_map = _build_sector_map(symbols)
    detector = ThemeDetector(theme_scores=normalized_scores, sector_map=sector_map)
    score = detector.get_theme_score(symbol)
    blocked = score < THEME_COLD_THRESHOLD
    log.info(
        "[%s] ThemeDetector score=%.2f (flag ON, %s)",
        symbol,
        score,
        "진입 차단" if blocked else "진입 허용",
    )
    return blocked


# ── 포지션 추적 ──────────────────────────────────────


@dataclass
class LivePosition:
    """실시간 보유 포지션."""

    symbol: str
    name: str
    entry_price: int
    quantity: int
    entry_time: str
    order_no: str
    strategy: str = "momentum"  # 진입 전략 ("momentum" | "mean_reversion")
    high_since_entry: int = 0  # 진입 후 최고가
    dynamic_stop: float | None = None  # ATR 기반 동적 손절 (음수, 예: -0.024)
    dynamic_tp: float | None = None  # ATR 기반 동적 익절 (양수, 예: +0.048)
    entry_date: str = ""  # 진입 날짜 (YYYY-MM-DD, overnight 보유일수 계산용)


@dataclass
class TradeLog:
    """거래 기록."""

    symbol: str
    name: str
    side: str
    price: int
    quantity: int
    time: str
    order_no: str
    pnl_pct: float = 0.0
    exit_reason: str = ""
    strategy: str = ""


@dataclass
class TradingState:
    """트레이딩 상태."""

    positions: dict[str, LivePosition] = field(default_factory=dict)
    trades: list[TradeLog] = field(default_factory=list)
    daily_prices: dict[str, list[DailyPrice]] = field(default_factory=dict)
    daily_context: dict[str, dict] = field(default_factory=dict)  # {symbol: {high_52w, avg_volume}}
    drawdown_stop_buy: bool = False  # 드로우다운 매수 중단 플래그
    day_open_prices: dict[str, int] = field(default_factory=dict)  # {symbol: 당일 시가}
    symbol_losses: dict[str, int] = field(default_factory=dict)  # {symbol: 연속 손실 횟수}
    symbol_blacklist: set[str] = field(default_factory=set)  # 당일 진입 금지 종목
    cumulative_pnl_won: int = 0  # 세션 누적 실현 손익 (원, kill_switch 포트폴리오 추정용)
    sector_positions: dict[str, int] = field(default_factory=dict)  # 당일 진입 섹터 카운트
    symbol_strategies: dict[str, str] = field(
        default_factory=dict
    )  # {symbol: "momentum"|"mean_reversion"}
    budget: StrategyBudget = field(default_factory=StrategyBudget)  # 전략별 자금 버킷
    cumulative_volumes: dict[str, int] = field(default_factory=dict)  # {symbol: 당일 누적 거래량}
    current_prices: dict[str, int] = field(default_factory=dict)  # {symbol: 실시간 현재가}
    rescreened: dict[str, bool] = field(default_factory=dict)  # 재스크리닝 실행 여부 추적
    current_regime: MarketRegime = MarketRegime.NEUTRAL  # 현재 시장 레짐
    market_style: object | None = (
        None  # 현재 MarketStyle (Design 013, ADR-024 ActiveStrategy enum 통합)
    )
    max_loss_pct: float = -0.02  # 고정 손절 하한선 (-2%, ATR 손절 이중 안전망)
    pending_cancel_tasks: set[asyncio.Task] = field(
        default_factory=set
    )  # 지정가 취소 백그라운드 태스크 (GC 방지)
    t2_pending: list = field(default_factory=list)  # T2PendingSettlement 항목 (ADR-023 T+2 결제)


# ── 유틸 ──────────────────────────────────────────────


def is_entry_blocked(current_hhmm: str) -> bool:
    """현재 시각이 진입 차단 구간인지 확인한다.

    ENTRY_BLOCKED_WINDOWS 및 BLOCK_OPEN_VOLATILITY 설정을 참조한다.

    Args:
        current_hhmm: 현재 시각 HHMM 문자열 (예: "1145")

    Returns:
        True이면 신규 진입 차단.
    """
    # 09:00~09:30 시초가 변동성 구간 (옵션)
    if BLOCK_OPEN_VOLATILITY and "0900" <= current_hhmm < "0930":
        log.info("[진입차단] 시초가 변동성 구간 09:00~09:30 (%s)", current_hhmm)
        return True

    # 설정된 차단 시간대 (기본: 11:30~13:00 점심)
    for start_hhmm, end_hhmm in ENTRY_BLOCKED_WINDOWS:
        if start_hhmm <= current_hhmm < end_hhmm:
            log.info("[진입차단] 저유동성 구간 %s~%s (%s)", start_hhmm, end_hhmm, current_hhmm)
            return True

    return False


def setup_logging() -> None:
    """로깅 설정 (콘솔 + 파일).

    stdout/파일 핸들러 양쪽에 ``SecretMaskingFilter``를 부착해 Telegram bot token,
    Bearer 토큰, 32자+ 영숫자 시크릿이 로그 파일로 새어나가지 않도록 한다.
    루트 로거에도 필터를 부착해 라이브러리(httpx 등)가 만드는 LogRecord도
    전파 경로 상에서 마스킹이 적용된다.
    """
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS_DIR / f"live_{now_kst().strftime('%Y%m%d')}.log"

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    mask_filter = SecretMaskingFilter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(mask_filter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(mask_filter)

    # basicConfig는 루트 로거에 핸들러가 있으면 no-op이므로, 직접 구성한다.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 재시작/테스트 시 핸들러 중복 방지
    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    # 전파 단계 보강: 개별 로거가 자체 핸들러를 가질 때도 마스킹 필터 적용
    root_logger.addFilter(mask_filter)

    # httpx/httpcore INFO 로그는 요청 URL 전체를 출력 → 쿼리/경로에 토큰이 임베드되면 유출.
    # 마스킹 패턴이 1차 방어이고, 로거 레벨 하향이 2차 방어층이다.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    log.info("로그 파일: %s", log_path)


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        log.error("환경변수 %s가 없습니다.", key)
        sys.exit(1)
    return value


def calc_portfolio_value(
    account_balance: int, state: "TradingState", current_prices: dict[str, int]
) -> int:
    """포트폴리오 현재 가치 계산 (현금 + 실현 손익 + 미실현 평가액).

    Args:
        account_balance: 세션 시작 시 계좌 잔고
        state: 트레이딩 상태 (cumulative_pnl_won + positions)
        current_prices: {symbol: 현재가} 딕셔너리

    Returns:
        포트폴리오 시가총액 (원)
    """
    unrealized = sum(
        (current_prices.get(sym, pos.entry_price) - pos.entry_price) * pos.quantity
        for sym, pos in state.positions.items()
    )
    return account_balance + state.cumulative_pnl_won + unrealized


def now_hhmm() -> str:
    """현재 시각을 HHMM 문자열로 반환."""
    return now_kst().strftime("%H%M")


def check_web_kill_switch() -> bool:
    """웹에서 생성된 kill_switch 파일을 확인한다.

    Returns:
        True이면 안전 종료 요청 — 신규 매수 중단 후 청산해야 함
    """
    return KILL_SWITCH_FILE.exists()


def _write_pid_file() -> None:
    """현재 PID를 파일에 기록한다."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _remove_pid_file() -> None:
    """PID 파일을 삭제한다."""
    if PID_FILE.exists():
        PID_FILE.unlink()


def calc_time_ratio(hhmm: str) -> float:
    """장 경과 비율 계산 (거래량 보정용).

    당일 누적 거래량(quote.volume)을 일평균 거래량과 비교하려면
    장 경과 시간만큼 기대 거래량을 보정해야 한다.

    Args:
        hhmm: 현재 시각 HHMM 문자열 (예: "1030")

    Returns:
        float: elapsed_minutes / 390. 장 시작 전이면 0.0, 장 종료 후이면 1.0.
    """
    if len(hhmm) < 4:
        return 1.0
    try:
        hh, mm = int(hhmm[:2]), int(hhmm[2:4])
    except ValueError:
        return 1.0

    elapsed = hh * 60 + mm - 9 * 60  # 09:00 기준 경과 분
    total_trading_minutes = 390  # 09:00~15:30
    if elapsed <= 0:
        return 0.0
    return min(elapsed / total_trading_minutes, 1.0)


def load_screened_symbols() -> list[str]:
    """최근 스크리닝 결과에서 종목코드 로드."""
    pattern = str(RESULTS_DIR / "screened_*.json")
    files = sorted(glob_mod.glob(pattern))
    if not files:
        log.error("스크리닝 결과 파일 없음: %s", pattern)
        sys.exit(1)

    latest = files[-1]
    log.info("스크리닝 결과 로드: %s", latest)

    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    symbols = data.get("symbols", [])
    if not symbols:
        log.warning("스크리닝 통과 종목 없음 — overnight 포지션 확인 후 결정")
        return []

    log.info("감시 종목 %d개: %s", len(symbols), ", ".join(symbols))
    return symbols


def _safe_int(v: str | int) -> int:
    """부호 접두사 포함 가격/수량 안전 변환."""
    if isinstance(v, int):
        return abs(v)
    s = str(v).lstrip("+-")
    return int(s) if s else 0


def update_risk_after_trade(state: TradingState, symbol: str, pnl: float) -> None:
    """매 청산 후 종목별 손실 카운트 갱신.

    - 손실: 연패 카운트 증가, 3연패 시 당일 블랙리스트 (시그널 품질 필터)
    - 수익: 해당 종목 카운트 초기화 (모멘텀 복구 신호)

    Args:
        state: 트레이딩 상태
        symbol: 종목코드
        pnl: 청산 후 순손익률
    """
    if pnl < 0:
        state.symbol_losses[symbol] = state.symbol_losses.get(symbol, 0) + 1
        if state.symbol_losses[symbol] >= 3:
            state.symbol_blacklist.add(symbol)
            log.warning("[%s] 3연패 → 당일 블랙리스트 등록 (시그널 품질 필터)", symbol)
    else:
        state.symbol_losses[symbol] = 0


def build_strategies(
    strategy_name: str,
    params: MomentumParams,
    mr_params: MeanReversionParams | None = None,
    *,
    include_multi_regime: bool = False,
) -> list[Strategy]:
    """전략 인스턴스 생성.

    Args:
        strategy_name: "momentum" | "mean_reversion" | "both"
        params: 모멘텀 전략 파라미터
        mr_params: 평균회귀 전략 파라미터
        include_multi_regime: True이면 PullbackStrategy / RangeStrategy 추가 (Design 013 PR9)
    """
    strategies: list[Strategy] = []
    if strategy_name in ("momentum", "both"):
        strategies.append(MomentumStrategy(params=params))
    if strategy_name in ("mean_reversion", "both"):
        strategies.append(MeanReversionStrategy(params=mr_params))
    if include_multi_regime:
        from src.strategy.pullback import PullbackStrategy
        from src.strategy.range_trade import RangeStrategy

        strategies.append(PullbackStrategy())
        strategies.append(RangeStrategy())
    return strategies


# ── 데이터 로드 ──────────────────────────────────────


def _is_db_daily_candles_enabled() -> bool:
    """USE_DB_DAILY_CANDLES 활성 여부 (Design 011 feature flag).

    Returns:
        True이면 DailyCandleStore(DB 우선 + 키움 폴백) 경로 사용.
        기본 False — 기존 키움 ka10086 페이징 경로 유지.
    """
    return os.environ.get("USE_DB_DAILY_CANDLES", "false").lower() in ("true", "1", "yes")


async def load_daily_context(
    client: KiwoomClient, symbols: list[str]
) -> tuple[dict[str, list[DailyPrice]], dict[str, dict]]:
    """거래일 일봉 데이터 로드 (스크리닝/모멘텀 계산용).

    Design 011: `USE_DB_DAILY_CANDLES` 활성 시 `DailyCandleStore`를 경유해
    daily_candles DB 캐시를 우선 사용하고, 부족/에러 시 키움 ka10086 폴백.
    비활성 시 종전 키움 페이징 경로를 그대로 사용(기본값).

    Returns:
        (daily_prices, daily_context) 튜플
        - daily_prices: {symbol: list[DailyPrice]} — 전략 신호용
        - daily_context: {symbol: {high_52w, avg_volume}} — 호환용
    """
    if _is_db_daily_candles_enabled():
        from src.trading.daily_candle_store import DailyCandleStore

        database_url = os.environ.get("DATABASE_URL")
        store = DailyCandleStore(database_url=database_url, use_db=True)
        prices, ctx = await store.get_daily_context(symbols, kiwoom_client=client)
        for sym, cached_bars in prices.items():
            high_52w = ctx.get(sym, {}).get("high_52w", 0)
            avg_volume = ctx.get(sym, {}).get("avg_volume", 0)
            log.info(
                "[%s] 고가=%s, 평균거래량=%s (일봉 %d개, DB 캐시 경로)",
                sym,
                f"{high_52w:,}",
                f"{avg_volume:,}",
                len(cached_bars),
            )
        return prices, ctx

    from src.broker.constants import API_IDS, DEFAULT_EXCHANGE, ENDPOINTS
    from src.broker.schemas import to_kiwoom_symbol

    daily_prices: dict[str, list[DailyPrice]] = {}
    daily_context: dict[str, dict] = {}

    for symbol in symbols:
        log.info("[%s] 일봉 로드 중...", symbol)
        all_raw: list[dict] = []
        qry_dt = now_kst().strftime("%Y%m%d")

        for page in range(13):
            stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)
            try:
                data = await client._request(
                    ENDPOINTS["market"],
                    API_IDS["daily_price"],
                    json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
                )
            except Exception:
                log.warning("[%s] 일봉 %d페이지 에러, 3초 대기 후 재시도", symbol, page)
                await asyncio.sleep(3)
                try:
                    data = await client._request(
                        ENDPOINTS["market"],
                        API_IDS["daily_price"],
                        json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
                    )
                except Exception as e:
                    log.error("[%s] 일봉 재시도 실패: %s", symbol, e)
                    break

            items = data.get("daly_stkpc", [])
            if not items:
                break
            all_raw.extend(items)
            last_date = items[-1].get("date", "")
            if not last_date:
                break
            qry_dt = last_date
            await asyncio.sleep(0.5)

        if not all_raw:
            log.warning("[%s] 일봉 데이터 없음, 건너뜀", symbol)
            continue

        # DailyPrice 객체 리스트 생성 (오래된 것부터)
        bars: list[DailyPrice] = []
        for r in all_raw:
            try:
                bars.append(
                    DailyPrice(
                        date=r.get("date", ""),
                        open=_safe_int(r.get("open_pric", 0)),
                        high=_safe_int(r.get("high_pric", 0)),
                        low=_safe_int(r.get("low_pric", 0)),
                        close=_safe_int(r.get("close_pric", r.get("cur_prc", 0))),
                        volume=_safe_int(r.get("trde_qty", 0)),
                    )
                )
            except (ValueError, TypeError):
                continue
        bars.sort(key=lambda x: x.date)
        daily_prices[symbol] = bars

        # 호환용 컨텍스트
        high_52w = max(d.high for d in bars) if bars else 0
        recent_20 = bars[-20:] if len(bars) >= 20 else bars
        avg_volume = sum(d.volume for d in recent_20) // len(recent_20) if recent_20 else 0

        daily_context[symbol] = {"high_52w": high_52w, "avg_volume": avg_volume}
        log.info(
            "[%s] 52주고가=%s, 평균거래량=%s (일봉 %d개)",
            symbol,
            f"{high_52w:,}",
            f"{avg_volume:,}",
            len(bars),
        )
        await asyncio.sleep(1)

    return daily_prices, daily_context


# ── 매매 실행 ────────────────────────────────────────


async def _place_buy_market(
    client: KiwoomClient,
    symbol: str,
    name: str,
    price: int,
    quantity: int,
    strategy_name: str,
    state: TradingState,
    notifier: "TelegramNotifier | None",
    dynamic_stop: float | None,
    dynamic_tp: float | None,
) -> bool:
    """시장가 매수 주문 실행 및 포지션 등록.

    Returns:
        True이면 주문 성공 + 포지션 등록.
    """
    resp = await client.place_order(
        OrderRequest(
            symbol=symbol,
            side=OrderSideEnum.BUY,
            price=0,
            quantity=quantity,
            order_type=OrderTypeEnum.MARKET,
        )
    )
    log.info("[%s] 시장가 매수 접수: 주문번호 %s", symbol, resp.order_no)
    _register_buy_position(
        symbol, name, price, quantity, strategy_name, state, resp.order_no, dynamic_stop, dynamic_tp
    )
    try:
        async with async_session_factory() as _s:
            _uid = await resolve_live_trader_user_id(_s)
            await persist_order_submitted(
                _s,
                symbol,
                "BUY",
                quantity,
                price,
                resp.order_no,
                strategy_name,
                get_is_mock(),
                _uid,
            )
            await _s.commit()
    except Exception as _db_err:
        log.error("[%s] DB persist 실패(무시): %s", symbol, _db_err)
    if notifier:
        await notifier.send_buy(symbol, name, quantity, price, strategy_name)
    # 쿨다운 진입 기록 + 자동 kill_switch 주문 건수 추적
    from src.trading.kill_switch import auto_kill_monitor
    from src.trading.risk_manager import cooldown_tracker

    cooldown_tracker.record_entry(symbol)
    auto_kill_monitor.record_order(_TRADER_USER_ID)
    return True


def _register_buy_position(
    symbol: str,
    name: str,
    price: int,
    quantity: int,
    strategy_name: str,
    state: TradingState,
    order_no: str,
    dynamic_stop: float | None,
    dynamic_tp: float | None,
) -> None:
    """포지션 및 TradeLog 등록 (매수 공통 로직)."""
    state.positions[symbol] = LivePosition(
        symbol=symbol,
        name=name,
        entry_price=price,
        quantity=quantity,
        entry_time=now_kst().strftime("%Y%m%d%H%M%S"),
        order_no=order_no,
        strategy=strategy_name,
        high_since_entry=price,
        dynamic_stop=dynamic_stop,
        dynamic_tp=dynamic_tp,
        entry_date=now_kst().strftime("%Y-%m-%d"),
    )
    order_amount = price * quantity
    state.budget.allocate(strategy_name, order_amount)
    sector = get_sector(symbol)
    if sector != "기타":
        state.sector_positions[sector] = state.sector_positions.get(sector, 0) + 1
    state.trades.append(
        TradeLog(
            symbol=symbol,
            name=name,
            side="BUY",
            price=price,
            quantity=quantity,
            time=now_kst().strftime("%Y%m%d%H%M%S"),
            order_no=order_no,
            strategy=strategy_name,
        )
    )


async def _cancel_limit_buy_and_fallback(
    client: KiwoomClient,
    symbol: str,
    name: str,
    quantity: int,
    order_no: str,
    strategy_name: str,
    state: TradingState,
    notifier: "TelegramNotifier | None",
    dynamic_stop: float | None,
    dynamic_tp: float | None,
) -> None:
    """지정가 매수 미체결 시 LIMIT_ORDER_TIMEOUT_SEC 후 취소 + 시장가 재주문.

    Args:
        order_no: 취소 대상 지정가 주문번호
    """
    await asyncio.sleep(LIMIT_ORDER_TIMEOUT_SEC)

    # 이미 체결돼 포지션이 등록됐거나 다른 이유로 포지션이 없는 경우 → 취소 불필요
    if symbol in state.positions:
        return

    log.info(
        "[%s] 지정가 %d초 경과, 미체결 → 취소 후 시장가 fallback (주문번호 %s)",
        symbol,
        LIMIT_ORDER_TIMEOUT_SEC,
        order_no,
    )
    try:
        from src.broker.schemas import CancelRequest

        await client.cancel_order(
            CancelRequest(symbol=symbol, order_no=order_no, quantity=quantity)
        )
        log.info("[%s] 지정가 취소 완료, 시장가 재주문", symbol)
    except Exception as e:
        log.warning("[%s] 지정가 취소 실패(무시): %s — 시장가 재주문 진행", symbol, e)

    # 포지션 재진입 여부 재확인 (취소 도중 WS tick이 등록했을 가능성)
    if symbol in state.positions:
        return

    try:
        quote = await client.get_quote(symbol)
        await _place_buy_market(
            client,
            symbol,
            name,
            quote.price,
            quantity,
            strategy_name,
            state,
            notifier,
            dynamic_stop,
            dynamic_tp,
        )
    except Exception as e:
        log.error("[%s] 시장가 fallback 실패: %s", symbol, e)


async def execute_buy(
    client: KiwoomClient,
    symbol: str,
    name: str,
    price: int,
    quantity: int,
    strategy_name: str,
    state: TradingState,
    notifier: "TelegramNotifier | None" = None,
    *,
    dynamic_stop: float | None = None,
    dynamic_tp: float | None = None,
) -> None:
    """지정가 매수 주문 (매도1호가). 미체결 시 시장가 fallback."""
    if quantity <= 0:
        log.warning("[%s] 수량 0 — 매수 스킵 (현재가 %s원)", symbol, f"{price:,}")
        return

    # 매도1호가 조회 → 지정가 주문
    limit_price: int = 0
    use_limit: bool = False
    try:
        orderbook = await client.get_orderbook(symbol)
        if orderbook.asks:
            candidate = orderbook.asks[0].price
            # int 타입이고 양수인 경우만 지정가 사용 (mock 방어)
            if isinstance(candidate, int) and candidate > 0:
                limit_price = candidate
                use_limit = True
    except Exception as e:
        log.warning("[%s] 호가 조회 실패, 시장가로 fallback: %s", symbol, e)

    log.info(
        "[%s] 매수 주문 [%s] %s: %d주 x %s원 = %s원",
        symbol,
        strategy_name,
        "지정가" if use_limit else "시장가",
        quantity,
        f"{limit_price if use_limit else price:,}",
        f"{(limit_price if use_limit else price) * quantity:,}",
    )

    try:
        if use_limit:
            resp = await client.place_order(
                OrderRequest(
                    symbol=symbol,
                    side=OrderSideEnum.BUY,
                    price=limit_price,
                    quantity=quantity,
                    order_type=OrderTypeEnum.LIMIT,
                )
            )
            log.info(
                "[%s] 지정가 매수 접수: 주문번호 %s (가격 %s원, %d초 후 미체결 시 취소)",
                symbol,
                resp.order_no,
                f"{limit_price:,}",
                LIMIT_ORDER_TIMEOUT_SEC,
            )
            # 지정가는 낙관적 포지션 등록 (즉시 fill 가정).
            # 미체결 시 백그라운드 태스크가 취소 + 시장가 재주문.
            _register_buy_position(
                symbol,
                name,
                limit_price,
                quantity,
                strategy_name,
                state,
                resp.order_no,
                dynamic_stop,
                dynamic_tp,
            )
            try:
                async with async_session_factory() as _s:
                    _uid = await resolve_live_trader_user_id(_s)
                    await persist_order_submitted(
                        _s,
                        symbol,
                        "BUY",
                        quantity,
                        limit_price,
                        resp.order_no,
                        strategy_name,
                        get_is_mock(),
                        _uid,
                    )
                    await _s.commit()
            except Exception as _db_err:
                log.error("[%s] DB persist 실패(무시): %s", symbol, _db_err)
            if notifier:
                await notifier.send_buy(symbol, name, quantity, limit_price, strategy_name)
            # 백그라운드: 미체결 취소 + 시장가 fallback
            _bg_task = asyncio.create_task(
                _cancel_limit_buy_and_fallback(
                    client,
                    symbol,
                    name,
                    quantity,
                    resp.order_no,
                    strategy_name,
                    state,
                    notifier,
                    dynamic_stop,
                    dynamic_tp,
                ),
                name=f"limit_cancel_{symbol}",
            )
            # 태스크 참조 유지 (GC 방지 — RUF006)
            state.pending_cancel_tasks.add(_bg_task)
            _bg_task.add_done_callback(state.pending_cancel_tasks.discard)
        else:
            await _place_buy_market(
                client,
                symbol,
                name,
                price,
                quantity,
                strategy_name,
                state,
                notifier,
                dynamic_stop,
                dynamic_tp,
            )
    except Exception as e:
        log.error("[%s] 매수 실패: %s", symbol, e)


async def execute_sell(
    client: KiwoomClient,
    pos: LivePosition,
    price: int,
    reason: str,
    state: TradingState,
    notifier: "TelegramNotifier | None" = None,
) -> float | None:
    """매도 주문. 긴급 사유(손절/강제청산)는 시장가, 목표 청산은 지정가(매수1호가).

    Returns:
        float | None: 성공 시 순손익률(pnl_net), 실패 시 None
    """
    # 긴급 사유: 시장가 즉시 청산. 목표 사유: 매수1호가 지정가.
    is_emergency = reason in _MARKET_SELL_REASONS
    sell_price = price  # fallback 표시용
    sell_order_type = OrderTypeEnum.MARKET
    sell_limit_price = 0

    if not is_emergency:
        # 매수1호가 조회 → 지정가 매도
        try:
            orderbook = await client.get_orderbook(pos.symbol)
            if orderbook.bids:
                candidate = orderbook.bids[0].price
                if isinstance(candidate, int) and candidate > 0:
                    sell_limit_price = candidate
                    sell_order_type = OrderTypeEnum.LIMIT
                    sell_price = sell_limit_price
        except Exception as e:
            log.warning("[%s] 호가 조회 실패, 시장가 매도로 fallback: %s", pos.symbol, e)
            sell_order_type = OrderTypeEnum.MARKET
            sell_limit_price = 0

    log.info(
        "[%s] 매도 주문 [%s] (%s) %s: %d주 x %s원 | 진입가 %s원",
        pos.symbol,
        pos.strategy,
        reason,
        "시장가" if sell_order_type == OrderTypeEnum.MARKET else "지정가",
        pos.quantity,
        f"{sell_price:,}",
        f"{pos.entry_price:,}",
    )

    # 수수료/세금: 모멘텀/평균회귀 동일 기본값
    commission_rate = 0.00015
    tax_rate = 0.0020  # 2026년 KOSPI 거래세 0.20%

    try:
        resp = await client.place_order(
            OrderRequest(
                symbol=pos.symbol,
                side=OrderSideEnum.SELL,
                price=sell_limit_price,
                quantity=pos.quantity,
                order_type=sell_order_type,
            )
        )
        log.info("[%s] 매도 접수: 주문번호 %s", pos.symbol, resp.order_no)
        # DB persist 브릿지 (ADR-014) — 실패해도 in-memory TradeLog는 살아있음
        try:
            async with async_session_factory() as _s:
                _uid = await resolve_live_trader_user_id(_s)
                await persist_order_submitted(
                    _s,
                    pos.symbol,
                    "SELL",
                    pos.quantity,
                    price,
                    resp.order_no,
                    pos.strategy,
                    get_is_mock(),
                    _uid,
                )
                await _s.commit()
        except Exception as _db_err:
            log.error("[%s] DB persist 실패(무시): %s", pos.symbol, _db_err)

        pnl_gross = (price - pos.entry_price) / pos.entry_price if pos.entry_price > 0 else 0
        pnl_net = pnl_gross - (commission_rate * 2 + tax_rate)

        # 누적 손익 갱신 (kill_switch 포트폴리오 추정용)
        state.cumulative_pnl_won += round(pnl_net * pos.entry_price * pos.quantity)

        state.trades.append(
            TradeLog(
                symbol=pos.symbol,
                name=pos.name,
                side="SELL",
                price=price,
                quantity=pos.quantity,
                time=now_kst().strftime("%Y%m%d%H%M%S"),
                order_no=resp.order_no,
                pnl_pct=round(pnl_net, 6),
                exit_reason=reason,
                strategy=pos.strategy,
            )
        )
        # 자금 버킷 해제
        release_amount = pos.entry_price * pos.quantity
        state.budget.release(pos.strategy, release_amount)
        del state.positions[pos.symbol]
        if notifier:
            await notifier.send_sell(
                pos.symbol, pos.name, pos.quantity, price, pnl_net, reason, pos.strategy
            )
        # 쿨다운 청산 기록 + 자동 kill_switch PnL 추적
        from src.trading.kill_switch import auto_kill_monitor
        from src.trading.risk_manager import cooldown_tracker

        cooldown_tracker.record_exit(pos.symbol)
        auto_kill_monitor.record_trade(_TRADER_USER_ID, pos.symbol, pnl_net)
        return pnl_net
    except Exception as e:
        log.error("[%s] 매도 실패: %s", pos.symbol, e)
        return None


# ── 메인 루프 ────────────────────────────────────────


def _count_positions_by_strategy(state: TradingState, strategy_name: str) -> int:
    """특정 전략의 보유 포지션 수."""
    return sum(1 for p in state.positions.values() if p.strategy == strategy_name)


async def poll_cycle(
    client: KiwoomClient,
    symbols: list[str],
    strategies: list[Strategy],
    state: TradingState,
    account_balance: int,
    scale_factor: float,
    notifier: "TelegramNotifier | None" = None,
    market_ctx: MarketContext | None = None,
) -> None:
    """1회 폴링 사이클: 전 종목 시세 조회 → 전략별 진입/청산 판단.

    Args:
        market_ctx: MarketContext. USE_FLOW_SIGNAL=true일 때 모멘텀 진입 필터에 사용.
            None이거나 flag off이면 기존 경로 유지.
    """
    current_hhmm = now_hhmm()
    log.info("--- 폴링 %s ---", current_hhmm)

    # 실시간 현재가 축적 (drawdown 포트폴리오 가치 계산용)
    current_prices: dict[str, int] = {}

    # 웹 kill_switch 파일 체크 — 신규 매수 차단
    if check_web_kill_switch():
        log.warning("웹 kill_switch 감지 — 신규 매수 차단 (보유분 청산 후 종료)")
        state.drawdown_stop_buy = True

    for symbol in symbols:
        try:
            quote = await client.get_quote(symbol)
        except Exception as e:
            log.warning("[%s] 시세 조회 실패: %s", symbol, e)
            await asyncio.sleep(0.5)
            continue

        current_prices[symbol] = quote.price
        state.current_prices[symbol] = quote.price

        daily = state.daily_prices.get(symbol, [])
        ctx = state.daily_context.get(symbol)
        if not ctx or not daily:
            await asyncio.sleep(0.3)
            continue

        # 1. 보유 중이면 청산 체크 (진입 전략 기준)
        if symbol in state.positions:
            pos = state.positions[symbol]
            pnl_pct = (quote.price - pos.entry_price) / pos.entry_price
            # 고점 갱신
            if quote.price > pos.high_since_entry:
                pos.high_since_entry = quote.price

            # 진입 전략 찾기
            entry_strat = _find_strategy(strategies, pos.strategy)
            if entry_strat:
                kwargs: dict = {}
                if pos.dynamic_stop is not None:
                    kwargs = {"dynamic_stop": pos.dynamic_stop, "dynamic_tp": pos.dynamic_tp}

                log.info(
                    "[%s] 보유 체크 현재가=%s, pnl=%.2f%%, stop=%.4f, tp=%.4f",
                    symbol,
                    f"{quote.price:,}",
                    pnl_pct * 100,
                    pos.dynamic_stop or -999,
                    pos.dynamic_tp or -999,
                )

                exit_reason = entry_strat.check_exit_signal(
                    pos.entry_price, quote.price, pos.high_since_entry, **kwargs
                )
                # 평균회귀: 지표 기반 추가 청산 (RSI 과매수, BB 중심선 회귀)
                if not exit_reason and hasattr(entry_strat, "check_exit_with_indicators"):
                    exit_reason = entry_strat.check_exit_with_indicators(
                        pos.entry_price, quote.price, daily
                    )
                if exit_reason:
                    pnl = await execute_sell(client, pos, quote.price, exit_reason, state, notifier)
                    await asyncio.sleep(0.5)
                    if pnl is not None:
                        update_risk_after_trade(state, symbol, pnl)
                        portfolio_val = calc_portfolio_value(account_balance, state, current_prices)
                        action = update_drawdown(_TRADER_USER_ID, portfolio_val)
                        if action == DrawdownAction.FORCE_CLOSE:
                            await force_close_all(client, state, force_all=True)
                            return
                        if action == DrawdownAction.STOP_BUY:
                            state.drawdown_stop_buy = True
                        # HWM 드로우다운 레벨 갱신
                        from src.trading.risk_manager import DrawdownLevel, hwm_guard

                        hwm_level = hwm_guard.update(_TRADER_USER_ID, portfolio_val)
                        if hwm_level == DrawdownLevel.RED:
                            await force_close_all(client, state, force_all=True)
                            return
                        if hwm_level in (DrawdownLevel.ORANGE, DrawdownLevel.YELLOW):
                            state.drawdown_stop_buy = True
                    continue

            # 15:15 강제청산 (모멘텀만 — 스윙 포지션은 overnight 보유)
            if current_hhmm >= FORCE_CLOSE_HHMM and pos.strategy == "momentum":
                pnl = await execute_sell(client, pos, quote.price, "force_close", state, notifier)
                await asyncio.sleep(0.5)
                if pnl is not None:
                    update_risk_after_trade(state, symbol, pnl)
                    portfolio_val = calc_portfolio_value(account_balance, state, current_prices)
                    action = update_drawdown(_TRADER_USER_ID, portfolio_val)
                    if action == DrawdownAction.FORCE_CLOSE:
                        await force_close_all(client, state, force_all=True)
                        return
                    if action == DrawdownAction.STOP_BUY:
                        state.drawdown_stop_buy = True
                    # HWM 드로우다운 레벨 갱신
                    from src.trading.risk_manager import DrawdownLevel, hwm_guard

                    hwm_level = hwm_guard.update(_TRADER_USER_ID, portfolio_val)
                    if hwm_level == DrawdownLevel.RED:
                        await force_close_all(client, state, force_all=True)
                        return
                    if hwm_level in (DrawdownLevel.ORANGE, DrawdownLevel.YELLOW):
                        state.drawdown_stop_buy = True
                continue

        # 2. 미보유 + 드로우다운 매수중단 아님 + 블랙리스트 아님 → 전략별 진입 체크
        if (
            symbol not in state.positions
            and not state.drawdown_stop_buy
            and symbol not in state.symbol_blacklist
        ):
            # 진입 차단 시간대 체크 (점심 저유동성 등)
            if is_entry_blocked(current_hhmm):
                await asyncio.sleep(0.3)
                continue

            # 쿨다운 가드: 30분 내 청산 이력 또는 당일 3회 진입 초과 시 스킵
            from src.trading.risk_manager import cooldown_tracker, get_regime_max_positions

            if not cooldown_tracker.can_enter(symbol):
                await asyncio.sleep(0.3)
                continue

            # 섹터 중복 체크 (테마당 2개까지 허용, '기타' 제외)
            sym_sector = get_sector(symbol)
            if sym_sector != "기타" and state.sector_positions.get(sym_sector, 0) >= 2:
                log.info("[%s] 섹터 한도 [%s] → 진입 스킵", symbol, sym_sector)
                await asyncio.sleep(0.5)
                continue

            # 종목별 할당 전략으로만 진입 판단
            sym_strategy = state.symbol_strategies.get(symbol, "momentum")
            time_ratio = calc_time_ratio(current_hhmm)
            for strat in strategies:
                if strat.name != sym_strategy:
                    continue
                max_pos = _get_max_positions(strat)
                current_count = _count_positions_by_strategy(state, strat.name)
                # 레짐별 max_positions 하드 가드 (CRISIS=0 강제)
                regime_max = get_regime_max_positions(state.current_regime)
                if current_count >= min(max_pos, regime_max):
                    if regime_max == 0:
                        log.info(
                            "[%s] 레짐 %s max_positions=0 → 진입 차단",
                            symbol,
                            state.current_regime.upper(),
                        )
                    continue

                # 버킷 가용액 확인
                if state.budget.available(sym_strategy) <= 0:
                    log.info("[%s] %s 버킷 가용액 없음 → 진입 스킵", symbol, sym_strategy)
                    continue

                # 진입 필터 전달: 시각, 당일 시가 (bar_open=0: 봉 데이터 없으므로 비활성)
                ct = f"{current_hhmm[:2]}:{current_hhmm[2:]}" if len(current_hhmm) >= 4 else ""
                entry = strat.check_entry_signal(
                    daily,
                    quote.price,
                    quote.volume,
                    time_ratio,
                    current_time=ct,
                    day_open=quote.open,
                )

                # 디버그 로그
                high_52w = ctx["high_52w"]
                avg_volume = ctx["avg_volume"]
                price_ratio = quote.price / high_52w if high_52w > 0 else 0
                vol_ratio = quote.volume / avg_volume if avg_volume > 0 else 0
                log.info(
                    "[%s] %s [%s] | 현재가 %s (52주고 대비 %.1f%%) | 거래량 %s (%.1fx) | %s",
                    symbol,
                    quote.name,
                    strat.name,
                    f"{quote.price:,}",
                    price_ratio * 100,
                    f"{quote.volume:,}",
                    vol_ratio,
                    "→ 매수!" if entry else "대기",
                )

                if not entry:
                    continue

                # DEFENSIVE/CRISIS 레짐: 공격적 전략(momentum/pullback/range_trade) 신규 진입 차단
                # DEFENSIVE: mean_reversion만 허용 (50% 축소 효과)
                # CRISIS: get_regime_max_positions=0으로 이미 차단되나 명시적 가드 추가
                if strat.name in (
                    "momentum",
                    "pullback",
                    "range_trade",
                ) and state.current_regime in (
                    MarketRegime.DEFENSIVE,
                    MarketRegime.CRISIS,
                ):
                    log.info(
                        "[%s] 레짐 %s → %s 신규 진입 차단",
                        symbol,
                        state.current_regime.upper(),
                        strat.name,
                    )
                    continue

                # FlowSignal 수급 필터 (feature flag USE_FLOW_SIGNAL, 모멘텀만)
                # 기본 비활성 — 켜야 강한 매도 압력 종목 진입 차단.
                if strat.name == "momentum" and _should_block_by_flow_signal(market_ctx, symbol):
                    log.info("[%s] FlowSignal bearish → 모멘텀 신규 매수 중단", symbol)
                    continue

                # ThemeDetector 테마 필터 (feature flag USE_THEME_BOOST, 모멘텀만)
                # 기본 비활성 — 켜면 cold 테마(score < 0.3) 종목 진입 차단.
                if strat.name == "momentum" and _should_block_by_theme(market_ctx, symbol, symbols):
                    log.info("[%s] ThemeDetector cold → 모멘텀 신규 매수 중단", symbol)
                    continue

                # ATR 변동성 필터 (모멘텀 전략만 적용)
                dyn_stop: float | None = None
                dyn_tp: float | None = None
                if strat.name == "momentum":
                    atr = calc_atr(daily, period=20)
                    if atr <= 0 or quote.price <= 0:
                        log.info("[%s] ATR 미산출 → 진입 스킵", symbol)
                        continue
                    atr_pct = atr / quote.price
                    if atr_pct < MIN_ATR_PCT:
                        log.info(
                            "[%s] ATR%% %.4f < %.4f 변동성 부족 → 진입 스킵",
                            symbol,
                            atr_pct,
                            MIN_ATR_PCT,
                        )
                        continue
                    # 이중 안전망: ATR 손절 OR 고정 -2% 중 덜 타이트한 것 (더 작은 음수)
                    atr_based_stop = -max(atr_pct * ATR_STOP_MULT, MIN_STOP_PCT)
                    dyn_stop = max(atr_based_stop, state.max_loss_pct)
                    dyn_tp = max(atr_pct * ATR_TP_MULT, MIN_STOP_PCT * 2)
                    log.info(
                        "[%s] ATR=%.4f, dyn_stop=%.4f (%.1f원), dyn_tp=%.4f (%.1f원)",
                        symbol,
                        atr_pct,
                        dyn_stop,
                        quote.price * (1 + dyn_stop),
                        dyn_tp,
                        quote.price * (1 + dyn_tp),
                    )

                # 2연패 이상이면 포지션 규모 50% 축소
                symbol_scale = 0.5 if state.symbol_losses.get(symbol, 0) >= 2 else 1.0
                qty = calc_dynamic_position_size(
                    price=quote.price,
                    daily=daily,
                    account_balance=account_balance,
                    scale_factor=scale_factor * symbol_scale,
                    strategy=sym_strategy,
                    budget=state.budget,
                )
                await execute_buy(
                    client,
                    symbol,
                    quote.name,
                    quote.price,
                    qty,
                    strat.name,
                    state,
                    notifier,
                    dynamic_stop=dyn_stop,
                    dynamic_tp=dyn_tp,
                )
                break  # 한 종목에 한 전략만 진입

        await asyncio.sleep(0.5)  # API 간 간격


def _find_strategy(strategies: list[Strategy], name: str) -> Strategy | None:
    """전략 이름으로 인스턴스 검색."""
    for s in strategies:
        if s.name == name:
            return s
    return None


def _get_max_positions(strat: Strategy) -> int:
    """전략별 최대 포지션 수."""
    if hasattr(strat, "params") and hasattr(strat.params, "max_positions"):
        return strat.params.max_positions
    return 3


# ── 장중 재스크리닝 ──────────────────────────────────


async def _run_rescreen(
    client: KiwoomClient,
    symbols: list[str],
    state: TradingState,
) -> list[str]:
    """재스크리닝을 실행하고 신규 종목을 state에 초기화.

    Returns:
        새로 추가된 종목 코드 리스트
    """
    from scripts.screen_symbols import rescreen_intraday

    new_symbols = await rescreen_intraday(
        client,
        list(state.daily_prices.keys()),
    )
    if not new_symbols:
        log.info("재스크리닝: 추가 종목 없음")
        return []

    # 신규 종목 일봉 로드 + 전략 분류
    new_prices, new_ctx = await load_daily_context(client, new_symbols)
    added: list[str] = []
    new_daily: dict[str, list] = {}
    for sym in new_symbols:
        daily = new_prices.get(sym)
        if not daily:
            continue
        state.daily_prices[sym] = daily
        state.daily_context[sym] = new_ctx[sym]
        symbols.append(sym)
        new_daily[sym] = daily
        added.append(sym)

    if new_daily:
        # market_style은 state에 저장된 최신값 재사용 (재스크리닝 시 별도 refresh 생략)
        assigned = _assign_symbol_strategies(new_daily, state.market_style)
        state.symbol_strategies.update(assigned)
        for sym in added:
            log.info(
                "재스크리닝: [%s] 추가 (전략: %s)",
                sym,
                state.symbol_strategies.get(sym, "momentum"),
            )

    return added


_WS_RECONNECT_WAIT_SEC = 30  # 재스크리닝 시 WS 재연결 대기 최대 시간 (초)
_WS_RECONNECT_POLL_SEC = 1  # 재연결 확인 간격 (초)


async def _wait_for_ws_reconnect(
    ws: KiwoomWebSocket, timeout: float = _WS_RECONNECT_WAIT_SEC
) -> bool:
    """WS가 끊긴 경우 내부 _run_loop의 자동 재연결을 최대 timeout초 기다린다.

    Args:
        ws: KiwoomWebSocket 인스턴스
        timeout: 최대 대기 시간 (초)

    Returns:
        timeout 내 재연결 성공 여부
    """
    elapsed = 0.0
    while elapsed < timeout:
        if ws.is_connected:
            return True
        await asyncio.sleep(_WS_RECONNECT_POLL_SEC)
        elapsed += _WS_RECONNECT_POLL_SEC
    return False


async def rescreening_task_ws(
    client: KiwoomClient,
    symbols: list[str],
    state: TradingState,
    ws: KiwoomWebSocket,
) -> None:
    """WebSocket 모드 재스크리닝 태스크. RESCREEN_TIMES에 실행."""
    for target in RESCREEN_TIMES:
        current = now_hhmm()
        if current >= target:
            continue

        # 목표 시각까지 대기 (분 단위 근사)
        try:
            cur_min = int(current[:2]) * 60 + int(current[2:4])
            tgt_min = int(target[:2]) * 60 + int(target[2:4])
            wait_sec = max((tgt_min - cur_min) * 60, 0)
        except (ValueError, IndexError):
            continue

        if wait_sec > 0:
            log.info("재스크리닝: %s까지 %d초 대기", target, wait_sec)
            await asyncio.sleep(wait_sec)

        log.info("재스크리닝 시작 (시각: %s)", target)
        try:
            added = await _run_rescreen(client, symbols, state)
            if not added:
                continue

            # WS 연결 상태 확인 — 끊긴 경우 자동 재연결 대기
            if not ws.is_connected:
                log.warning(
                    "재스크리닝 후 WS 미연결, 재연결 대기 (최대 %ds)", _WS_RECONNECT_WAIT_SEC
                )
                reconnected = await _wait_for_ws_reconnect(ws)
                if reconnected:
                    log.info("WS 재연결 성공, 신규 종목 구독 진행")
                else:
                    # 폴백: WS 재연결 실패 — 종목은 이미 state/symbols에 등록됨
                    # 폴링 모드나 다음 재연결 시 _replay_subscriptions가 처리
                    log.warning(
                        "WS 재연결 실패 — 신규 종목 %s는 state에 등록됨, WS 구독 생략 (폴링 폴백)",
                        added,
                    )
                    continue

            await ws.subscribe(added, "0B")
            log.info("재스크리닝 완료: %d개 추가, WS 구독 등록", len(added))
        except Exception as e:
            log.warning("재스크리닝 실패 (%s): %s", target, e)


async def _refresh_regime(
    state: TradingState,
    market_ctx: MarketContext,
    symbols: list[str] | None = None,
) -> None:
    """MarketContext에서 최신 데이터로 장중 레짐을 재판단한다.

    관찰 로그(observe-only)로 investor_flow / theme_scores / stock_investor_flows도
    함께 기록한다. 매매 판단에는 영향을 주지 않으며, PR B/C에서 feature flag로
    활성화될 때 사용할 데이터의 오작동 감지가 목적이다.

    Args:
        state: 트레이딩 상태 (current_regime 갱신 대상)
        market_ctx: 시장 컨텍스트 캐시
        symbols: 현재 감시 중인 종목 코드 리스트. 지정되면 해당 종목별 수급만 로그.
    """
    prev_regime = state.current_regime
    await market_ctx.refresh()
    new_vkospi = market_ctx.get_vkospi()
    new_kospi_above_ma12 = market_ctx.get_kospi_above_ma12()
    new_regime = detect_regime(vkospi=new_vkospi, kospi_above_ma12=new_kospi_above_ma12)
    state.current_regime = new_regime
    if new_regime != prev_regime:
        log.warning(
            "레짐 전환: %s → %s (VKOSPI=%.1f, KOSPI>12이평=%s)",
            prev_regime.upper(),
            new_regime.upper(),
            new_vkospi,
            new_kospi_above_ma12,
        )
    else:
        log.info(
            "레짐 유지: %s (VKOSPI=%.1f, KOSPI>12이평=%s)",
            state.current_regime.upper(),
            new_vkospi,
            new_kospi_above_ma12,
        )

    # ── 관찰 로그(observe-only) ──────────────────────────────
    # 매매 판단에는 영향 0. PR B/C에서 flow_signal / theme_detector와 연동 예정.
    _log_market_context_observation(market_ctx, symbols)


def _log_market_context_observation(
    market_ctx: MarketContext,
    symbols: list[str] | None,
) -> None:
    """MarketContext 수급/테마 데이터를 관찰 로그로 남긴다 (매매 영향 없음).

    Args:
        market_ctx: 시장 컨텍스트 캐시 (get_investor_flow / get_theme_scores /
            get_stock_investor_flows 호출).
        symbols: 감시 중인 종목 리스트. 지정되면 해당 종목의 수급만 로그.

    Notes:
        - theme_scores는 상위 5개 key만 출력(상세 원문 미노출, 보안 정책).
        - DB 접근 실패/데이터 미존재 시 빈 dict를 반환하므로 None 방어 불필요.
    """
    try:
        investor_flow = market_ctx.get_investor_flow()
    except Exception:
        log.debug("MarketContext observe: investor_flow 조회 실패", exc_info=True)
        investor_flow = {}
    try:
        theme_scores = market_ctx.get_theme_scores()
    except Exception:
        log.debug("MarketContext observe: theme_scores 조회 실패", exc_info=True)
        theme_scores = {}
    try:
        stock_flows = market_ctx.get_stock_investor_flows()
    except Exception:
        log.debug("MarketContext observe: stock_investor_flows 조회 실패", exc_info=True)
        stock_flows = {}

    # 시장 전체 수급 (foreign/institution/individual 키만 추출)
    if investor_flow:
        log.info(
            "[observe] 시장 수급: foreign=%s, institution=%s, individual=%s",
            investor_flow.get("foreign"),
            investor_flow.get("institution"),
            investor_flow.get("individual"),
        )
    else:
        log.info("[observe] 시장 수급: 데이터 없음")

    # 테마 점수 상위 5개 (원문 노출 금지 — key, 점수만)
    if theme_scores:
        # 숫자로 변환 가능한 값만 정렬 대상에 포함
        sortable: list[tuple[str, float]] = []
        for name, score in theme_scores.items():
            try:
                sortable.append((str(name), float(score)))
            except (TypeError, ValueError):
                continue
        top5 = sorted(sortable, key=lambda kv: kv[1], reverse=True)[:5]
        formatted = ", ".join(f"{k}={v:.2f}" for k, v in top5)
        log.info("[observe] 테마 점수 상위 5: %s (총 %d개)", formatted, len(theme_scores))
    else:
        log.info("[observe] 테마 점수: 데이터 없음")

    # 현재 감시 종목의 수급 매칭
    if symbols and stock_flows:
        matched = {s: stock_flows.get(s) for s in symbols if s in stock_flows}
        if matched:
            log.info(
                "[observe] 감시 종목 수급 매칭: %d/%d (예: %s)",
                len(matched),
                len(symbols),
                next(iter(matched.items())),
            )
        else:
            log.info(
                "[observe] 감시 종목 수급 매칭: 0/%d (stock_flows 종목수=%d)",
                len(symbols),
                len(stock_flows),
            )
    elif stock_flows:
        log.info("[observe] 종목별 수급 데이터: %d종목 (symbols 미지정)", len(stock_flows))
    else:
        log.info("[observe] 종목별 수급 데이터: 없음")


async def _regime_refresh_task_ws(
    state: TradingState,
    market_ctx: MarketContext,
    symbols: list[str] | None = None,
) -> None:
    """WS 모드 레짐 갱신 백그라운드 태스크.

    1분마다 캐시 만료 여부를 확인하고, 만료 시 레짐을 재판단한다.
    기본 TTL(30분) 기준으로 장중 약 30분 간격 갱신.

    Args:
        state: 트레이딩 상태 (current_regime 갱신 대상)
        market_ctx: 시장 컨텍스트 캐시
        symbols: 감시 중인 종목 리스트. observe 로그 매칭에 사용.
    """
    check_interval_sec = 60  # 1분마다 TTL 만료 여부 확인
    while True:
        await asyncio.sleep(check_interval_sec)
        if market_ctx.is_cache_stale():
            await _refresh_regime(state, market_ctx, symbols=symbols)


# ── ADR-022 월말 리밸런싱 ─────────────────────────────

# 프로세스 수명 동안 단일 어댑터 인스턴스 유지 (중복 실행 방지용 날짜 캐시)
_rebalance_adapter: "CrossMomentumRebalanceAdapter | None" = None


def _get_rebalance_adapter() -> "CrossMomentumRebalanceAdapter":
    """CrossMomentumRebalanceAdapter 싱글턴 반환."""
    global _rebalance_adapter
    if _rebalance_adapter is None:
        from src.trading.cross_momentum_rebalance import CrossMomentumRebalanceAdapter

        _rebalance_adapter = CrossMomentumRebalanceAdapter()
    return _rebalance_adapter


async def _check_monthly_rebalance(
    client: KiwoomClient,
    current_hhmm: str,
    state: TradingState,
    account_balance: int,
) -> None:
    """월말 리밸런싱 훅. ActiveStrategy.CROSS_MOMENTUM 분기 진입점 — 14:55 + 마지막 거래일 시 실행.

    cooldown을 우회하는 전용 플로우이므로 poll_cycle과 독립 실행된다.

    Args:
        client: 키움 API 클라이언트
        current_hhmm: 현재 시각 HHMM
        state: 트레이딩 상태 (보유 포지션 조회용)
        account_balance: 세션 시작 계좌 잔고
    """
    from src.trading.cross_momentum_rebalance import check_monthly_rebalance
    from src.utils.krx_calendar import is_last_business_day_of_month

    today = now_kst().date()
    # 공휴일 캘린더 선행 체크 (ADR-023): 마지막 영업일이 아니면 조기 반환
    if current_hhmm == "1455" and not is_last_business_day_of_month(today):
        return

    adapter = _get_rebalance_adapter()
    current_holdings = {sym: pos.quantity for sym, pos in state.positions.items()}
    # 가용 현금 = 계좌 잔고 + 누적 실현 손익 (보수적 추정)
    available_cash = max(0, account_balance + state.cumulative_pnl_won)
    try:
        await check_monthly_rebalance(
            adapter,
            current_hhmm,
            today,
            client,
            current_holdings,
            available_cash,
            state.t2_pending,
        )
    except Exception as exc:
        log.error("월말 리밸런싱 실패 (무시): %s", exc)


# ── Short Swing 장중 체크 ─────────────────────────────

# 진입 시간: 09:20~13:00, 청산 시간: 09:20~15:10
_SS_ENTRY_START = "0920"
_SS_ENTRY_END = "1300"
_SS_EXIT_START = "0920"
_SS_EXIT_END = "1510"
_SS_CANCEL_HHMM = "1520"


async def _check_short_swing_entry(
    client: KiwoomClient,
    current_hhmm: str,
) -> None:
    """Short swing 진입 체크 — 09:20~13:00, 5분 주기 (메인 루프 간격).

    Args:
        client: 키움 API 클라이언트.
        current_hhmm: 현재 시각 HHMM.
    """
    if not (_SS_ENTRY_START <= current_hhmm <= _SS_ENTRY_END):
        return

    try:
        from src.trading.live_order_persist import resolve_live_trader_user_id
        from src.trading.short_swing import run_entry_check

        async with async_session_factory() as db:
            user_id = await resolve_live_trader_user_id(db)
            result = await run_entry_check(db, client, user_id=user_id)
            log.info(
                "short_swing entry: checked=%d, ordered=%d, skipped=%d, errors=%d",
                result.checked,
                result.ordered,
                len(result.skipped),
                len(result.errors),
            )
    except Exception as exc:
        log.error("short_swing 진입 체크 실패 (무시): %s", exc)


async def _check_short_swing_exit(
    client: KiwoomClient,
    current_hhmm: str,
) -> None:
    """Short swing 청산 체크 — 09:20~15:10, 5분 주기 (메인 루프 간격).

    Args:
        client: 키움 API 클라이언트.
        current_hhmm: 현재 시각 HHMM.
    """
    if not (_SS_EXIT_START <= current_hhmm <= _SS_EXIT_END):
        return

    try:
        from src.trading.live_order_persist import resolve_live_trader_user_id
        from src.trading.short_swing_exit import run_exit_check

        async with async_session_factory() as db:
            user_id = await resolve_live_trader_user_id(db)
            result = await run_exit_check(db, client, user_id=user_id)
            log.info(
                "short_swing exit: checked=%d, closed=%d, skipped=%d, errors=%d",
                result.checked,
                result.closed,
                len(result.skipped),
                len(result.errors),
            )
    except Exception as exc:
        log.error("short_swing 청산 체크 실패 (무시): %s", exc)


async def _check_short_swing_cancel(
    client: KiwoomClient,
    current_hhmm: str,
) -> None:
    """Short swing 미체결 매수 주문 취소 — 매 사이클 30분 경과 체크 + 15:20 일괄.

    Args:
        client: 키움 API 클라이언트.
        current_hhmm: 현재 시각 HHMM.
    """
    # 15:20 이후: threshold 0분 (전량 즉시 취소) / 그 외: 30분 경과만
    threshold = 0 if current_hhmm >= _SS_CANCEL_HHMM else 30

    try:
        from src.trading.live_order_persist import resolve_live_trader_user_id
        from src.trading.short_swing_cancel import cancel_stale_buy_orders

        async with async_session_factory() as db:
            user_id = await resolve_live_trader_user_id(db)
            counts = await cancel_stale_buy_orders(
                db, client, user_id=user_id, threshold_minutes=threshold
            )
            if counts["cancelled"] > 0:
                log.info(
                    "short_swing cancel: cancelled=%d, errors=%d",
                    counts["cancelled"],
                    counts["errors"],
                )
    except Exception as exc:
        log.error("short_swing 미체결 취소 실패 (무시): %s", exc)


async def _check_short_swing_reconcile(
    client: KiwoomClient,
) -> None:
    """Short swing 포지션-주문 체결 정합성 reconcile — 5분 주기.

    Args:
        client: 키움 API 클라이언트.
    """
    try:
        from src.trading.live_order_persist import resolve_live_trader_user_id
        from src.trading.short_swing_reconciler import reconcile_short_swing_positions

        async with async_session_factory() as db:
            user_id = await resolve_live_trader_user_id(db)
            counts = await reconcile_short_swing_positions(db, client, user_id=user_id)
            total = sum(counts.values())
            if total > 0:
                log.info(
                    "short_swing reconcile: open=%d, deleted=%d, closed=%d, reverted=%d, errors=%d",
                    counts["pending_to_open"],
                    counts["pending_deleted"],
                    counts["closing_to_closed"],
                    counts["closing_to_open"],
                    counts["errors"],
                )
    except Exception as exc:
        log.error("short_swing reconcile 실패 (무시): %s", exc)


async def run_trading_loop(
    client: KiwoomClient,
    symbols: list[str],
    strategies: list[Strategy],
    state: TradingState,
    account_balance: int,
    scale_factor: float,
    notifier: "TelegramNotifier | None" = None,
    market_ctx: MarketContext | None = None,
) -> None:
    """장중 매매 루프. 5분 간격 폴링, 15:35 이후 종료."""
    strat_names = [s.name for s in strategies]
    log.info(
        "매매 루프 시작 (전략: %s, 종료: %s)",
        "+".join(strat_names),
        MARKET_CLOSE_HHMM,
    )

    while True:
        current = now_hhmm()

        # 장 종료 체크
        if current >= MARKET_CLOSE_HHMM:
            log.info("장 종료 시각 도달 (%s). 루프 종료.", current)
            break

        # 장중 레짐 갱신 (MarketContext TTL 만료 시)
        if market_ctx is not None and market_ctx.is_cache_stale():
            await _refresh_regime(state, market_ctx, symbols=symbols)

        # 장중 재스크리닝 (RESCREEN_TIMES 시각에 1회씩)
        for target in RESCREEN_TIMES:
            if current >= target and not state.rescreened.get(target):
                log.info("재스크리닝 시작 (시각: %s)", target)
                try:
                    await _run_rescreen(client, symbols, state)
                except Exception as e:
                    log.warning("재스크리닝 실패 (%s): %s", target, e)
                state.rescreened[target] = True

        # ADR-024: ACTIVE_STRATEGY 분기
        # cross_momentum: monthly rebalance만 실행, default poll_cycle skip
        # multi_regime: poll_cycle 실행 (multi-regime 분배는 strategy 안에서 처리)
        # short_swing: 5분 주기 entry/exit 체크 + 미체결 취소
        # none: 모든 매매 비활성 (idle)
        strategy_mode = get_active_strategy()
        if strategy_mode == ActiveStrategy.CROSS_MOMENTUM:
            await _check_monthly_rebalance(client, current, state, account_balance)
        elif strategy_mode == ActiveStrategy.MULTI_REGIME:
            await poll_cycle(
                client,
                symbols,
                strategies,
                state,
                account_balance,
                scale_factor,
                notifier,
                market_ctx=market_ctx,
            )
        elif strategy_mode == ActiveStrategy.SHORT_SWING:
            await _check_short_swing_reconcile(client)
            await _check_short_swing_entry(client, current)
            await _check_short_swing_exit(client, current)
            await _check_short_swing_cancel(client, current)
        else:
            log.info("ACTIVE_STRATEGY=none — 매매 비활성 (idle)")

        # 다음 폴링까지 대기 (1초 단위로 kill_switch 체크)
        log.info("다음 폴링까지 %d초 대기...", POLL_INTERVAL_SEC)
        for _ in range(POLL_INTERVAL_SEC):
            if check_web_kill_switch():
                log.warning("kill_switch 감지 — 안전 종료")
                await force_close_all(client, state, force_all=True)
                return
            await asyncio.sleep(1)


async def force_close_all(
    client: KiwoomClient,
    state: TradingState,
    *,
    force_all: bool = False,
) -> None:
    """미청산 포지션 강제 청산.

    Args:
        client: 키움 API 클라이언트
        state: 트레이딩 상태
        force_all: True면 전량 청산 (kill_switch/프로그램 종료),
                   False면 모멘텀만 청산 (스윙 포지션은 overnight 보유)
    """
    if not state.positions:
        log.info("미청산 포지션 없음")
        return

    targets = list(state.positions.keys())
    if not force_all:
        targets = [s for s in targets if state.positions[s].strategy == "momentum"]

    # ADR-024: cross_momentum strategy는 force_all=True여도 보존
    # (월말 ranking 기반 매도가 정의 — 임의 강제 청산 시 알파 손실)
    cross_momentum_targets = [s for s in targets if state.positions[s].strategy == "cross_momentum"]
    if cross_momentum_targets:
        log.info(
            "cross_momentum 포지션 %d개 강제 청산 보존 (force_all=%s, 월말 trigger 대기): %s",
            len(cross_momentum_targets),
            force_all,
            ", ".join(cross_momentum_targets),
        )
    targets = [s for s in targets if state.positions[s].strategy != "cross_momentum"]

    if not targets:
        swing_count = len(state.positions)
        log.info("청산 대상 없음 (보유 %d개 보존)", swing_count)
        return

    label = "전량" if force_all else "모멘텀"
    log.info("%s 강제 청산 %d개 (총 보유 %d개)", label, len(targets), len(state.positions))

    for symbol in targets:
        pos = state.positions[symbol]
        try:
            quote = await client.get_quote(symbol)
            reason = "kill_switch" if force_all else "end_of_day"
            await execute_sell(client, pos, quote.price, reason, state)
        except Exception as e:
            log.error("[%s] 강제 청산 실패: %s", symbol, e)
        await asyncio.sleep(0.5)


# ── overnight 포지션 관리 ─────────────────────────────


def _count_business_days(start_date: str, end_date: str) -> int:
    """두 날짜 사이의 영업일 수 계산 (주말 제외, 공휴일 미반영).

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        영업일 수
    """
    from datetime import timedelta

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    if end <= start:
        return 0
    days = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:  # 월~금
            days += 1
        current += timedelta(days=1)
    return days


def save_overnight_positions(state: TradingState, path: str = OVERNIGHT_PATH) -> None:
    """스윙 포지션을 JSON 파일에 저장.

    force_close_all(force_all=False) 호출 후 남은 포지션을 저장한다.
    포지션이 없으면 빈 리스트 저장.

    Args:
        state: 트레이딩 상태
        path: 저장 경로
    """
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    positions_data = []
    for pos in state.positions.values():
        positions_data.append(
            {
                "symbol": pos.symbol,
                "name": pos.name,
                "entry_price": pos.entry_price,
                "quantity": pos.quantity,
                "entry_time": pos.entry_time,
                "order_no": pos.order_no,
                "strategy": pos.strategy,
                "high_since_entry": pos.high_since_entry,
                "dynamic_stop": pos.dynamic_stop,
                "dynamic_tp": pos.dynamic_tp,
                "entry_date": pos.entry_date,
            }
        )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(positions_data, f, ensure_ascii=False, indent=2)
    log.info("overnight 포지션 %d개 저장: %s", len(positions_data), path)


def load_overnight_positions(path: str = OVERNIGHT_PATH) -> list[LivePosition]:
    """JSON 파일에서 overnight 포지션을 복원.

    파일이 없거나 비어있으면 빈 리스트 반환.
    복원 성공 시 .bak으로 rename (이중 로드 방지).

    Args:
        path: 파일 경로

    Returns:
        복원된 LivePosition 리스트
    """
    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("overnight 포지션 파일 읽기 실패: %s", e)
        return []

    if not data:
        return []

    positions: list[LivePosition] = []
    for item in data:
        try:
            positions.append(
                LivePosition(
                    symbol=item["symbol"],
                    name=item["name"],
                    entry_price=item["entry_price"],
                    quantity=item["quantity"],
                    entry_time=item["entry_time"],
                    order_no=item["order_no"],
                    strategy=item.get("strategy", "mean_reversion"),
                    high_since_entry=item.get("high_since_entry", 0),
                    dynamic_stop=item.get("dynamic_stop"),
                    dynamic_tp=item.get("dynamic_tp"),
                    entry_date=item.get("entry_date", ""),
                )
            )
        except (KeyError, TypeError) as e:
            log.warning("overnight 포지션 복원 실패 (항목 스킵): %s", e)
            continue

    # 이중 로드 방지: .bak으로 rename
    bak_path = path + ".bak"
    try:
        os.rename(path, bak_path)
        log.info("overnight 파일 백업: %s → %s", path, bak_path)
    except OSError as e:
        log.warning("overnight 파일 백업 실패: %s", e)

    log.info("overnight 포지션 %d개 복원", len(positions))
    return positions


async def check_gap_risk(
    state: TradingState,
    broker: KiwoomClient,
) -> list[str]:
    """overnight 포지션의 갭 하락 리스크 체크.

    전일 종가(entry_price) 대비 GAP_RISK_THRESHOLD 이상 하락 시 즉시 손절.
    장 시작 직후 (09:01~09:05) 호출.

    Args:
        state: 트레이딩 상태
        broker: 키움 API 클라이언트

    Returns:
        손절된 종목 코드 리스트
    """
    closed: list[str] = []
    today = now_kst().strftime("%Y-%m-%d")

    for symbol in list(state.positions.keys()):
        pos = state.positions[symbol]
        # 당일 진입 포지션은 스킵
        if not pos.entry_date or pos.entry_date == today:
            continue

        try:
            quote = await broker.get_quote(symbol)
            gap_pct = (
                (quote.price - pos.entry_price) / pos.entry_price if pos.entry_price > 0 else 0
            )
            if gap_pct <= GAP_RISK_THRESHOLD:
                log.warning(
                    "[%s] 갭 하락 %.2f%% → 즉시 손절 (진입가 %s, 현재가 %s)",
                    symbol,
                    gap_pct * 100,
                    f"{pos.entry_price:,}",
                    f"{quote.price:,}",
                )
                await execute_sell(broker, pos, quote.price, "gap_risk", state)
                closed.append(symbol)
            else:
                log.info(
                    "[%s] 갭 리스크 OK (%.2f%%, 진입가 %s, 현재가 %s)",
                    symbol,
                    gap_pct * 100,
                    f"{pos.entry_price:,}",
                    f"{quote.price:,}",
                )
        except Exception as e:
            log.error("[%s] 갭 리스크 체크 실패: %s", symbol, e)
        await asyncio.sleep(0.5)

    return closed


async def check_holding_limit(
    state: TradingState,
    broker: KiwoomClient,
) -> list[str]:
    """보유 기간 초과 포지션 강제 청산.

    entry_date 기준 MAX_HOLDING_DAYS 거래일 초과 시 강제 청산.
    주말 제외, 공휴일 미반영.

    Args:
        state: 트레이딩 상태
        broker: 키움 API 클라이언트

    Returns:
        청산된 종목 코드 리스트
    """
    closed: list[str] = []
    today = now_kst().strftime("%Y-%m-%d")

    for symbol in list(state.positions.keys()):
        pos = state.positions[symbol]
        if not pos.entry_date:
            continue

        holding_days = _count_business_days(pos.entry_date, today)
        if holding_days > MAX_HOLDING_DAYS:
            log.warning(
                "[%s] 보유 %d거래일 > %d일 → 강제 청산 (진입 %s)",
                symbol,
                holding_days,
                MAX_HOLDING_DAYS,
                pos.entry_date,
            )
            try:
                quote = await broker.get_quote(symbol)
                await execute_sell(broker, pos, quote.price, "holding_limit", state)
                closed.append(symbol)
            except Exception as e:
                log.error("[%s] 보유기간 초과 청산 실패: %s", symbol, e)
            await asyncio.sleep(0.5)
        else:
            log.info("[%s] 보유 %d거래일 (진입 %s)", symbol, holding_days, pos.entry_date)

    return closed


async def run_trading_loop_ws(
    client: KiwoomClient,
    symbols: list[str],
    strategies: list[Strategy],
    state: TradingState,
    account_balance: int,
    scale_factor: float,
    notifier: "TelegramNotifier | None" = None,
    market_ctx: MarketContext | None = None,
) -> None:
    """WebSocket 이벤트 기반 장중 매매 루프. 15:35 자동 종료.

    실시간 틱 수신 시 전략별 진입/청산을 판단한다.
    강제 매수(FORCE_BUY_TIME)는 별도 asyncio 태스크로 실행한다.
    """
    strat_names = [s.name for s in strategies]
    log.info(
        "WebSocket 매매 루프 시작 (전략: %s, 종료: 153500)",
        "+".join(strat_names),
    )

    ws = KiwoomWebSocket(
        base_url=MOCK_BASE_URL,
        get_token=client.ensure_token,
        is_mock=True,
    )

    # WS 모드 실시간 현재가 축적 (drawdown 포트폴리오 가치 계산용)
    current_prices: dict[str, int] = {}

    async def handle_tick(tick: RealtimeTick) -> None:
        """실시간 틱 수신 시 진입/청산 판단."""
        symbol = tick.symbol

        if symbol not in symbols:
            return

        current_prices[symbol] = tick.price
        state.current_prices[symbol] = tick.price

        daily = state.daily_prices.get(symbol, [])
        ctx = state.daily_context.get(symbol)
        if not ctx or not daily:
            return

        current_hhmm = now_hhmm()

        # 웹 kill_switch 파일 체크 — 신규 매수 차단
        if check_web_kill_switch():
            log.warning("웹 kill_switch 감지 (WS) — 신규 매수 차단 (보유분 청산 후 종료)")
            state.drawdown_stop_buy = True

        # 1. 보유 중이면 청산 체크 (진입 전략 기준)
        if symbol in state.positions:
            pos = state.positions[symbol]
            # 고점 갱신
            if tick.price > pos.high_since_entry:
                pos.high_since_entry = tick.price

            entry_strat = _find_strategy(strategies, pos.strategy)
            if entry_strat:
                ws_kwargs: dict = {}
                if pos.dynamic_stop is not None:
                    ws_kwargs = {"dynamic_stop": pos.dynamic_stop, "dynamic_tp": pos.dynamic_tp}
                exit_reason = entry_strat.check_exit_signal(
                    pos.entry_price, tick.price, pos.high_since_entry, **ws_kwargs
                )
                # 평균회귀: 지표 기반 추가 청산 (RSI 과매수, BB 중심선 회귀)
                if not exit_reason and hasattr(entry_strat, "check_exit_with_indicators"):
                    exit_reason = entry_strat.check_exit_with_indicators(
                        pos.entry_price, tick.price, daily
                    )
                if exit_reason:
                    pnl = await execute_sell(client, pos, tick.price, exit_reason, state, notifier)
                    if pnl is not None:
                        update_risk_after_trade(state, symbol, pnl)
                        ws_portfolio_val = calc_portfolio_value(
                            account_balance, state, current_prices
                        )
                        action = update_drawdown(_TRADER_USER_ID, ws_portfolio_val)
                        if action == DrawdownAction.FORCE_CLOSE:
                            await force_close_all(client, state, force_all=True)
                        elif action == DrawdownAction.STOP_BUY:
                            state.drawdown_stop_buy = True
                        # HWM 드로우다운 레벨 갱신
                        from src.trading.risk_manager import DrawdownLevel, hwm_guard

                        hwm_level = hwm_guard.update(_TRADER_USER_ID, ws_portfolio_val)
                        if hwm_level == DrawdownLevel.RED:
                            await force_close_all(client, state, force_all=True)
                        elif hwm_level in (DrawdownLevel.ORANGE, DrawdownLevel.YELLOW):
                            state.drawdown_stop_buy = True
                    return

            # 15:15 강제청산 (모멘텀만 — 스윙 포지션은 overnight 보유)
            if current_hhmm >= FORCE_CLOSE_HHMM and pos.strategy == "momentum":
                pnl = await execute_sell(client, pos, tick.price, "force_close", state, notifier)
                if pnl is not None:
                    update_risk_after_trade(state, symbol, pnl)
                    ws_portfolio_val = calc_portfolio_value(account_balance, state, current_prices)
                    action = update_drawdown(_TRADER_USER_ID, ws_portfolio_val)
                    if action == DrawdownAction.FORCE_CLOSE:
                        await force_close_all(client, state, force_all=True)
                    elif action == DrawdownAction.STOP_BUY:
                        state.drawdown_stop_buy = True
                    # HWM 드로우다운 레벨 갱신
                    from src.trading.risk_manager import DrawdownLevel, hwm_guard

                    hwm_level = hwm_guard.update(_TRADER_USER_ID, ws_portfolio_val)
                    if hwm_level == DrawdownLevel.RED:
                        await force_close_all(client, state, force_all=True)
                    elif hwm_level in (DrawdownLevel.ORANGE, DrawdownLevel.YELLOW):
                        state.drawdown_stop_buy = True
                return

        # 2. 미보유 + 드로우다운 매수중단 아님 + 블랙리스트 아님 → 전략별 진입 체크
        if (
            symbol not in state.positions
            and not state.drawdown_stop_buy
            and symbol not in state.symbol_blacklist
        ):
            # 진입 차단 시간대 체크 (점심 저유동성 등)
            if is_entry_blocked(current_hhmm):
                return

            # 쿨다운 가드: 30분 내 청산 이력 또는 당일 3회 진입 초과 시 스킵
            from src.trading.risk_manager import cooldown_tracker, get_regime_max_positions

            if not cooldown_tracker.can_enter(symbol):
                return

            # 섹터 중복 체크 (테마당 2개까지, '기타' 제외)
            ws_sector = get_sector(symbol)
            if ws_sector != "기타" and state.sector_positions.get(ws_sector, 0) >= 2:
                log.info("[%s] WS 섹터 한도 [%s] → 진입 스킵", symbol, ws_sector)
                return

            # 종목별 할당 전략으로만 진입 판단
            ws_sym_strategy = state.symbol_strategies.get(symbol, "momentum")
            time_ratio = calc_time_ratio(current_hhmm)
            for strat in strategies:
                if strat.name != ws_sym_strategy:
                    continue
                max_pos = _get_max_positions(strat)
                current_count = _count_positions_by_strategy(state, strat.name)
                # 레짐별 max_positions 하드 가드 (CRISIS=0 강제)
                regime_max = get_regime_max_positions(state.current_regime)
                if current_count >= min(max_pos, regime_max):
                    if regime_max == 0:
                        log.info(
                            "[%s] WS 레짐 %s max_positions=0 → 진입 차단",
                            symbol,
                            state.current_regime.upper(),
                        )
                    continue

                # 버킷 가용액 확인
                if state.budget.available(ws_sym_strategy) <= 0:
                    log.info("[%s] %s 버킷 가용액 없음 → 진입 스킵", symbol, ws_sym_strategy)
                    continue

                # 당일 시가 추적 (첫 tick 기준)
                if symbol not in state.day_open_prices:
                    state.day_open_prices[symbol] = tick.price
                day_open = state.day_open_prices[symbol]

                # 누적 거래량 (tick.volume은 단건 체결량이므로 누적 필요)
                state.cumulative_volumes[symbol] = (
                    state.cumulative_volumes.get(symbol, 0) + tick.volume
                )
                cum_volume = state.cumulative_volumes[symbol]

                ct = f"{current_hhmm[:2]}:{current_hhmm[2:]}" if len(current_hhmm) >= 4 else ""
                entry = strat.check_entry_signal(
                    daily,
                    tick.price,
                    cum_volume,
                    time_ratio,
                    current_time=ct,
                    day_open=day_open,
                )

                high_52w = ctx["high_52w"]
                avg_volume = ctx["avg_volume"]
                price_ratio = tick.price / high_52w if high_52w > 0 else 0
                vol_ratio = cum_volume / avg_volume if avg_volume > 0 else 0
                log.info(
                    "[%s] WS [%s] | 현재가 %s (52주고 대비 %.1f%%) | 누적거래량 %s (%.1fx) | %s",
                    symbol,
                    strat.name,
                    f"{tick.price:,}",
                    price_ratio * 100,
                    f"{cum_volume:,}",
                    vol_ratio,
                    "→ 매수!" if entry else "대기",
                )

                if not entry:
                    continue

                # DEFENSIVE/CRISIS 레짐: 공격적 전략(momentum/pullback/range_trade) 신규 진입 차단
                if strat.name in (
                    "momentum",
                    "pullback",
                    "range_trade",
                ) and state.current_regime in (
                    MarketRegime.DEFENSIVE,
                    MarketRegime.CRISIS,
                ):
                    log.info(
                        "[%s] WS 레짐 %s → %s 신규 진입 차단",
                        symbol,
                        state.current_regime.upper(),
                        strat.name,
                    )
                    continue

                # FlowSignal 수급 필터 (feature flag USE_FLOW_SIGNAL, 모멘텀만)
                if strat.name == "momentum" and _should_block_by_flow_signal(market_ctx, symbol):
                    log.info("[%s] WS FlowSignal bearish → 모멘텀 신규 매수 중단", symbol)
                    continue

                # ThemeDetector 테마 필터 (feature flag USE_THEME_BOOST, 모멘텀만)
                if strat.name == "momentum" and _should_block_by_theme(market_ctx, symbol, symbols):
                    log.info("[%s] WS ThemeDetector cold → 모멘텀 신규 매수 중단", symbol)
                    continue

                # ATR 변동성 필터 (모멘텀 전략만 적용)
                ws_dyn_stop: float | None = None
                ws_dyn_tp: float | None = None
                if strat.name == "momentum":
                    atr = calc_atr(daily, period=20)
                    if atr <= 0 or tick.price <= 0:
                        log.info("[%s] ATR 미산출 → 진입 스킵", symbol)
                        continue
                    atr_pct = atr / tick.price
                    if atr_pct < MIN_ATR_PCT:
                        log.info(
                            "[%s] ATR%% %.4f < %.4f 변동성 부족 → 진입 스킵",
                            symbol,
                            atr_pct,
                            MIN_ATR_PCT,
                        )
                        continue
                    # 이중 안전망: ATR 손절 OR 고정 -2% 중 덜 타이트한 것 (더 작은 음수)
                    ws_atr_based_stop = -max(atr_pct * ATR_STOP_MULT, MIN_STOP_PCT)
                    ws_dyn_stop = max(ws_atr_based_stop, state.max_loss_pct)
                    ws_dyn_tp = max(atr_pct * ATR_TP_MULT, MIN_STOP_PCT * 2)

                # 2연패 이상이면 포지션 규모 50% 축소
                ws_symbol_scale = 0.5 if state.symbol_losses.get(symbol, 0) >= 2 else 1.0
                qty = calc_dynamic_position_size(
                    price=tick.price,
                    daily=daily,
                    account_balance=account_balance,
                    scale_factor=scale_factor * ws_symbol_scale,
                    strategy=ws_sym_strategy,
                    budget=state.budget,
                )
                await execute_buy(
                    client,
                    symbol,
                    symbol,
                    tick.price,
                    qty,
                    strat.name,
                    state,
                    notifier,
                    dynamic_stop=ws_dyn_stop,
                    dynamic_tp=ws_dyn_tp,
                )
                break  # 한 종목에 한 전략만 진입

    ws.on_tick = handle_tick

    try:
        await ws.connect()
        # 연결 수립 대기 (최대 10초)
        for _ in range(100):
            if ws.is_connected:
                break
            await asyncio.sleep(0.1)
        if not ws.is_connected:
            raise ConnectionError("WebSocket 연결 수립 시간 초과 (10초)")

        await ws.subscribe(symbols, "0B")

        # 장중 재스크리닝 태스크 (백그라운드)
        rescreen_task = asyncio.create_task(rescreening_task_ws(client, symbols, state, ws))
        # 장중 레짐 갱신 태스크 (백그라운드, MarketContext TTL 기반)
        regime_task: asyncio.Task[None] | None = None
        if market_ctx is not None:
            regime_task = asyncio.create_task(
                _regime_refresh_task_ws(state, market_ctx, symbols=symbols)
            )
        try:
            await ws.run_until("153500")
        finally:
            rescreen_task.cancel()
            if regime_task is not None:
                regime_task.cancel()
    finally:
        await ws.close()


# ── 결과 저장 ────────────────────────────────────────


def save_results(state: TradingState, strategies: list[Strategy]) -> None:
    """매매 결과 JSON 저장."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = now_kst().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"live_{timestamp}.json"

    buys = [t for t in state.trades if t.side == "BUY"]
    sells = [t for t in state.trades if t.side == "SELL"]
    wins = [t for t in sells if t.pnl_pct > 0]

    # 전략별 통계
    strategy_stats = {}
    for strat in strategies:
        strat_sells = [t for t in sells if t.strategy == strat.name]
        strat_wins = [t for t in strat_sells if t.pnl_pct > 0]
        strategy_stats[strat.name] = {
            "buys": sum(1 for t in buys if t.strategy == strat.name),
            "sells": len(strat_sells),
            "win_rate": round(len(strat_wins) / len(strat_sells), 4) if strat_sells else 0,
            "total_pnl_pct": round(sum(t.pnl_pct for t in strat_sells), 6),
        }

    output = {
        "run_at": now_kst().isoformat(),
        "mode": "live_mock",
        "strategies": [s.name for s in strategies],
        "summary": {
            "total_buys": len(buys),
            "total_sells": len(sells),
            "win_rate": round(len(wins) / len(sells), 4) if sells else 0,
            "total_pnl_pct": round(sum(t.pnl_pct for t in sells), 6),
        },
        "strategy_stats": strategy_stats,
        "trades": [
            {
                "symbol": t.symbol,
                "name": t.name,
                "side": t.side,
                "price": t.price,
                "quantity": t.quantity,
                "time": t.time,
                "order_no": t.order_no,
                "pnl_pct": t.pnl_pct,
                "exit_reason": t.exit_reason,
                "strategy": t.strategy,
            }
            for t in state.trades
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info("결과 저장: %s", path)

    # Airflow DAG용 매매 기록 저장 (data/trades/YYYYMMDD.json)
    trades_dir = _PROJECT_ROOT / "data" / "trades"
    trades_dir.mkdir(parents=True, exist_ok=True)
    trades_path = trades_dir / f"{now_kst().strftime('%Y%m%d')}.json"
    with open(trades_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info("Airflow 매매 기록 저장: %s", trades_path)


# ── 메인 ─────────────────────────────────────────────


def _update_poll_interval(value: int) -> None:
    """폴링 간격 전역 변수 갱신."""
    global POLL_INTERVAL_SEC
    POLL_INTERVAL_SEC = value


async def main() -> None:
    """실시간 자동매매 실행."""
    global ATR_STOP_MULT, ATR_TP_MULT, MIN_ATR_PCT, MIN_STOP_PCT
    global FORCE_CLOSE_HHMM, MARKET_CLOSE_HHMM, GAP_RISK_THRESHOLD, MAX_HOLDING_DAYS

    parser = argparse.ArgumentParser(description="모의투자 실시간 자동매매")
    parser.add_argument("--symbols", default=None, help="종목코드 (쉼표 구분)")
    parser.add_argument("--auto", action="store_true", help="스크리닝 결과에서 종목 자동 로드")
    parser.add_argument(
        "--from-prescreen-cache",
        action="store_true",
        help="--auto 와 함께 사용. daily_screening_cache(DB)에서 직접 종목 로드 (Design 012).",
    )
    parser.add_argument("--volume-ratio", type=float, default=1.5, help="거래량 배수 (기본: 1.5)")
    parser.add_argument("--stop-loss", type=float, default=-0.005, help="손절 비율 (기본: -0.5%%)")
    parser.add_argument("--take-profit", type=float, default=0.015, help="익절 비율 (기본: +1.5%%)")
    parser.add_argument(
        "--invest-per-trade",
        type=int,
        default=DEFAULT_INVEST_PER_TRADE,
        help=f"1회 투자금 (기본: {DEFAULT_INVEST_PER_TRADE:,}원)",
    )
    parser.add_argument(
        "--account-balance",
        type=int,
        default=DEFAULT_ACCOUNT_BALANCE,
        help=f"총 계좌 잔고 (기본: {DEFAULT_ACCOUNT_BALANCE:,}원)",
    )
    parser.add_argument(
        "--poll-interval", type=int, default=POLL_INTERVAL_SEC, help="폴링 간격 (초)"
    )
    parser.add_argument(
        "--high-52w-threshold",
        type=float,
        default=0.0,
        help="52주고가 대비 진입 기준 (기본: 0.0 = 비활성)",
    )
    parser.add_argument(
        "--mode",
        choices=["ws", "polling"],
        default="ws",
        help=(
            "매매 루프 모드 (ws: WebSocket 기반, "
            "polling: multi_regime 전용 60초 REST 폴링 — "
            "cross_momentum/none 모드는 자동 차단, 기본: ws)"
        ),
    )
    parser.add_argument(
        "--strategy",
        choices=["momentum", "mean_reversion", "both"],
        default="both",
        help="실행 전략 (기본: both)",
    )
    parser.add_argument(
        "--mr-rsi-oversold", type=float, default=40.0, help="평균회귀 RSI 과매도 기준"
    )
    parser.add_argument("--mr-bb-std", type=float, default=1.5, help="평균회귀 볼린저밴드 표준편차")
    parser.add_argument("--mr-volume-ratio", type=float, default=0.8, help="평균회귀 거래량 배수")
    parser.add_argument("--mr-stop-loss", type=float, default=-0.015, help="평균회귀 손절")
    parser.add_argument("--mr-take-profit", type=float, default=0.015, help="평균회귀 익절")
    # ── 웹 제어 연동 파라미터 (strategy_config에서 전달) ──
    parser.add_argument("--atr-stop-mult", type=float, default=ATR_STOP_MULT, help="ATR 손절 배수")
    parser.add_argument("--atr-tp-mult", type=float, default=ATR_TP_MULT, help="ATR 익절 배수")
    parser.add_argument("--min-atr-pct", type=float, default=MIN_ATR_PCT, help="최소 ATR 비율")
    parser.add_argument("--min-stop-pct", type=float, default=MIN_STOP_PCT, help="최소 손절 비율")
    parser.add_argument(
        "--force-close-time", type=str, default=FORCE_CLOSE_HHMM, help="강제 청산 시각 (HHMM)"
    )
    parser.add_argument(
        "--market-close-time", type=str, default=MARKET_CLOSE_HHMM, help="장 종료 시각 (HHMM)"
    )
    parser.add_argument(
        "--entry-start-time", type=str, default="0930", help="진입 시작 시각 (HHMM, 기본 09:30)"
    )
    parser.add_argument("--entry-end-time", type=str, default="1300", help="진입 종료 시각 (HHMM)")
    parser.add_argument(
        "--max-holding-days", type=int, default=MAX_HOLDING_DAYS, help="최대 보유 거래일"
    )
    parser.add_argument(
        "--gap-risk-threshold", type=float, default=GAP_RISK_THRESHOLD, help="갭 하락 손절 기준"
    )
    parser.add_argument("--max-positions", type=int, default=3, help="최대 동시 포지션 수")
    parser.add_argument(
        "--max-loss-pct",
        type=float,
        default=-0.02,
        help="고정 손절 하한선 (기본: -2%%, ATR 손절 이중 안전망)",
    )
    args = parser.parse_args()

    setup_logging()

    # ACTIVE_STRATEGY enum 부팅 시 1회 로깅 (ADR-024: 기존 두 boolean 상호배타 검증 대체)
    log.info("ACTIVE_STRATEGY=%s", get_active_strategy().value)

    # PID 파일 기록
    _write_pid_file()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    notifier = TelegramNotifier(
        token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
    )

    # 양방향 텔레그램 핸들러
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    tg_handler = TelegramHandler(
        token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        allowed_chat_ids=[chat_id] if chat_id else [],
    )

    if args.auto:
        from src.trading.prescreen_cache import (
            is_prescreen_cache_enabled,
            load_screened_symbols_from_db,
        )

        use_prescreen_cache = args.from_prescreen_cache or is_prescreen_cache_enabled()
        if use_prescreen_cache:
            from datetime import timedelta as _td
            from datetime import timezone as _tz

            today_kst_date = datetime.now(tz=_tz(_td(hours=9))).date()
            symbols = load_screened_symbols_from_db(today_kst_date)
            if symbols:
                log.info(
                    "prescreen_cache DB 로드: %d종목 (%s)",
                    len(symbols),
                    today_kst_date,
                )
            else:
                log.warning("prescreen_cache DB 미스 — JSON 파일 폴백")
                symbols = load_screened_symbols()
        else:
            symbols = load_screened_symbols()
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        log.error("--symbols 또는 --auto 필수")
        sys.exit(1)

    # 스크리닝 0개여도 overnight/브로커 보유종목이 있으면 계속 진행
    if not symbols:
        overnight = load_overnight_positions(OVERNIGHT_PATH)
        if not overnight:
            log.warning("스크리닝 종목 0개 + overnight 포지션 없음 — 종료")
            sys.exit(0)
        log.info("스크리닝 종목 0개이나 overnight %d개 존재 — 계속 진행", len(overnight))
        symbols = [pos.symbol for pos in overnight]

    # ── DB strategy_config 로드 (우선순위: CLI > DB > 코드 기본값) ──
    from src.config.strategy_loader import (
        build_momentum_params,
        build_mr_params,
        extract_globals,
        load_all_config_raw,
    )

    db_config: dict[str, object] = {}
    _database_url: str | None = None
    _use_llm_decisions: bool = False
    try:
        from src.config.settings import get_settings

        _settings = get_settings()
        _database_url = _settings.database_url
        _use_llm_decisions = getattr(_settings, "use_llm_decisions", False)
        db_config = await load_all_config_raw(_database_url)
        log.info("DB strategy_config 로드 성공: %d개 키", len(db_config))
    except Exception:
        log.warning("DB strategy_config 로드 실패 — CLI/기본값으로 진행", exc_info=True)

    # ── LLM 승인 결정 로드 (design-010) ───────────────────
    # feature flag OFF(기본): 로드만 하고 관찰 로그만 남김 (shadow 모드).
    # ON: universe_adjust.exclude / symbol_bias.block_buy 을 symbols에 반영.
    # strategy_param_hint 는 PR 3에서 반영. 여기서는 로그만.
    from src.trading.llm_decision_loader import (
        apply_llm_param_hints,
        apply_universe_decisions,
        extract_strategy_param_hints,
        load_approved_decisions,
        summarize_decisions,
    )

    # Phase 1 (LLM 자동 승인): use_llm_decisions=true일 때 부팅 시점에 pending → approved
    # 자동 전환 (whitelist + 범위 + min_confidence 검증). 사용자 manual rejected는 우선.
    if _use_llm_decisions:
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from src.trading.llm_auto_approval import auto_approve_pending

            _auto_engine = create_async_engine(_database_url, pool_pre_ping=True)
            _auto_factory = async_sessionmaker(_auto_engine, expire_on_commit=False)
            async with _auto_factory() as _auto_session:
                _auto_counts = await auto_approve_pending(db=_auto_session)
                log.info(
                    "LLM 자동 승인 결과: approved=%d, rejected=%d, skipped=%d",
                    _auto_counts["approved"],
                    _auto_counts["rejected"],
                    _auto_counts["skipped"],
                )
            await _auto_engine.dispose()
        except Exception as exc:
            log.warning("LLM 자동 승인 실패 (무시, approved 결정만 사용): %s", exc)

    _llm_decisions = await load_approved_decisions(_database_url, since_hours=24)
    log.info(
        "LLM approved 결정 로드: %s (use_llm_decisions=%s)",
        summarize_decisions(_llm_decisions),
        _use_llm_decisions,
    )
    if _use_llm_decisions and _llm_decisions:
        _before_count = len(symbols)
        symbols = apply_universe_decisions(symbols, _llm_decisions)
        if len(symbols) != _before_count:
            log.info(
                "LLM 결정 반영으로 유니버스 %d → %d 종목",
                _before_count,
                len(symbols),
            )

        # strategy_param_hint 반영 (PR 3)
        # whitelist + 범위 검증을 통과한 값만 추출.
        # DB(사용자 설정) 우선 → LLM 힌트는 DB에 없는 키에만 적용.
        _llm_param_hints = extract_strategy_param_hints(_llm_decisions)
        if _llm_param_hints:
            _db_keys = {k for k in _llm_param_hints if k in db_config}
            _llm_keys = [k for k in _llm_param_hints if k not in db_config]
            log.info(
                "strategy_param_hint 처리: DB 우선=%s, LLM 적용=%s",
                sorted(_db_keys),
                _llm_keys,
            )
            db_config = apply_llm_param_hints(db_config, _llm_param_hints)
    else:
        # flag off 이거나 결정 없음: strategy_param_hint 도 로그만
        _hints = _llm_decisions.get("strategy_param_hint", [])
        if _hints:
            log.info(
                "strategy_param_hint %d건 승인됨 (flag off — 적용 안 함)",
                len(_hints),
            )

    # 전역 상수 업데이트 (DB > CLI > 하드코딩)
    db_globals = extract_globals(db_config)
    ATR_STOP_MULT = db_globals.get("atr_stop_mult", args.atr_stop_mult)
    ATR_TP_MULT = db_globals.get("atr_tp_mult", args.atr_tp_mult)
    MIN_ATR_PCT = args.min_atr_pct
    MIN_STOP_PCT = args.min_stop_pct
    FORCE_CLOSE_HHMM = args.force_close_time
    MARKET_CLOSE_HHMM = args.market_close_time
    GAP_RISK_THRESHOLD = db_globals.get("gap_risk_threshold", args.gap_risk_threshold)
    MAX_HOLDING_DAYS = db_globals.get("max_holding_days", args.max_holding_days)

    params = build_momentum_params(db_config)
    mr_params = build_mr_params(db_config)

    strategies = build_strategies(
        args.strategy,
        params,
        mr_params,
        include_multi_regime=get_active_strategy() == ActiveStrategy.MULTI_REGIME,
    )

    _update_poll_interval(args.poll_interval)

    log.info("=" * 60)
    log.info("자동매매 — 2전략 병행 (모의투자)")
    log.info("실행: %s", now_kst().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 60)
    log.info("전략        : %s", ", ".join(s.name for s in strategies))
    log.info("종목        : %s (%d개)", ", ".join(symbols), len(symbols))
    log.info("계좌 잔고   : %s원", f"{args.account_balance:,}")
    log.info("폴링 간격   : %d초", POLL_INTERVAL_SEC)
    log.info("사이징      : 동적 (ATR 기반, 계좌 2%%/거래)")
    log.info(
        "모멘텀 파라미터: vol_ratio=%s, SL=%s, TP=%s, 52w=%s, max_pos=%d",
        params.volume_ratio,
        params.stop_loss,
        params.take_profit,
        params.high_52w_threshold,
        params.max_positions,
    )
    log.info(
        "모멘텀 파라미터(2): 진입시작=%s, 고정손절=%.1f%%",
        params.entry_start_time,
        args.max_loss_pct * 100,
    )
    log.info(
        "평균회귀 파라미터: rsi_oversold=%s, bb_std=%s, vol_ratio=%s, SL=%s, TP=%s",
        mr_params.rsi_oversold,
        mr_params.bb_std,
        mr_params.volume_ratio,
        mr_params.stop_loss,
        mr_params.take_profit,
    )
    log.info("=" * 60)

    app_key = get_env_or_exit("KIWOOM_MOCK_APP_KEY")
    app_secret = get_env_or_exit("KIWOOM_MOCK_APP_SECRET")

    client = KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key=app_key,
        app_secret=app_secret,
        is_mock=True,
    )

    state = TradingState()
    scale_factor = 1.0  # 킬스위치 스케일 팩터 (주간 손실 시 0.5)

    try:
        # 토큰 발급 (최대 3회 재시도, 5초 간격)
        for _attempt in range(3):
            try:
                await client.authenticate()
                log.info("[OK] 토큰 발급 성공")
                break
            except Exception as auth_err:
                if _attempt < 2:
                    log.warning("토큰 발급 실패 (%s), %d초 후 재시도", auth_err, 5)
                    await asyncio.sleep(5)
                else:
                    raise

        # 52주 일봉 데이터 로드
        state.daily_prices, state.daily_context = await load_daily_context(client, symbols)
        if not state.daily_prices:
            log.error("일봉 데이터 로드 실패. 종료.")
            return

        # ── Layer 0: 시장 레짐 판단 ──────────────────────────
        # MarketContext로 Airflow DB에서 VKOSPI/KOSPI 레짐 조회.
        # DB 조회 실패(is_cache_stale=True) 시 환경변수 폴백.
        market_ctx = MarketContext(database_url=_database_url)
        await market_ctx.refresh()
        if market_ctx.is_cache_stale():
            # DB 갱신 실패 — 환경변수 폴백
            vkospi_val = float(os.environ.get("VKOSPI", "25.0"))
            kospi_above_ma12 = os.environ.get("KOSPI_ABOVE_MA12", "true").lower() in ("true", "1")
            log.warning(
                "MarketContext DB 갱신 실패 — 환경변수 폴백 (VKOSPI=%.1f, KOSPI>12이평=%s)",
                vkospi_val,
                kospi_above_ma12,
            )
        else:
            vkospi_val = market_ctx.get_vkospi()
            kospi_above_ma12 = market_ctx.get_kospi_above_ma12()
            # 초기 observe 로그(매매 영향 0) — PR B/C에서 feature flag로 활성화 예정
            _log_market_context_observation(market_ctx, symbols=symbols)
        regime_cfg = RegimeConfig()
        state.current_regime = detect_regime(
            vkospi=vkospi_val,
            kospi_above_ma12=kospi_above_ma12,
            config=regime_cfg,
        )
        log.info(
            "시장 레짐: %s (VKOSPI=%.1f, KOSPI>12이평=%s)",
            state.current_regime.upper(),
            vkospi_val,
            kospi_above_ma12,
        )

        # 종목별 전략 분류 (변동성 + 시장 스타일 기반, Design 013 PR9)
        state.market_style = (
            _load_market_style(market_ctx)
            if get_active_strategy() == ActiveStrategy.MULTI_REGIME
            else None
        )
        state.symbol_strategies.update(
            _assign_symbol_strategies(state.daily_prices, state.market_style)
        )
        _log_strategy_distribution(state.symbol_strategies)

        # max_loss_pct 설정 (이중 안전망)
        state.max_loss_pct = args.max_loss_pct

        # CRISIS 레짐: 매매 자동 정지
        if state.current_regime == MarketRegime.CRISIS:
            log.critical(
                "시장 레짐 CRISIS — 매매 자동 정지 (VKOSPI=%.1f, KOSPI>12이평=%s)",
                vkospi_val,
                kospi_above_ma12,
            )
            await notifier.send_error(
                f"[CRISIS] 시장 레짐 위기 판정 — 매매 정지 (VKOSPI={vkospi_val:.1f})"
            )
            return

        # 자금 버킷 초기화 + 레짐별 자본 배분
        state.budget.reset(args.account_balance)
        state.budget.apply_regime(state.current_regime, args.account_balance)
        log.info(
            "자금 버킷 초기화 (레짐: %s): %s",
            state.current_regime.upper(),
            state.budget.summary(),
        )

        # overnight 포지션 복원
        overnight_positions = load_overnight_positions(OVERNIGHT_PATH)
        if overnight_positions:
            for pos in overnight_positions:
                state.positions[pos.symbol] = pos
                state.symbol_strategies[pos.symbol] = pos.strategy
                order_amount = pos.entry_price * pos.quantity
                state.budget.allocate(pos.strategy, order_amount)
            log.info(
                "overnight 포지션 %d개 복원, 버킷: %s",
                len(overnight_positions),
                state.budget.summary(),
            )

        # ── 브로커 실제 보유종목 동기화 (수동 매수 포함) ──────
        # ADR-024: 외부 동기화 시 strategy 메타데이터를 ACTIVE_STRATEGY 기준으로 부여.
        # cross_momentum 모드에서 모든 holdings를 "momentum"으로 등록하면
        # multi_regime 시절 도입된 손절/강제청산 path가 cross_momentum 포지션을
        # 의도와 다르게 청산함 (5/5~5/6 사고).
        active_strategy_mode = get_active_strategy()
        external_strategy = (
            "cross_momentum"
            if active_strategy_mode == ActiveStrategy.CROSS_MOMENTUM
            else "momentum"
        )
        try:
            broker_balance = await client.get_balance()
            external_symbols: list[str] = []
            for h in broker_balance.holdings:
                if h.symbol not in state.positions and h.quantity > 0:
                    state.positions[h.symbol] = LivePosition(
                        symbol=h.symbol,
                        name=h.name,
                        entry_price=h.avg_price,
                        quantity=h.quantity,
                        entry_time=now_kst().strftime("%H:%M"),
                        order_no="external",
                        strategy=external_strategy,
                        high_since_entry=h.current_price,
                        entry_date=now_kst().strftime("%Y-%m-%d"),
                    )
                    state.symbol_strategies[h.symbol] = external_strategy
                    state.budget.allocate(external_strategy, h.avg_price * h.quantity)
                    external_symbols.append(h.symbol)
            if external_symbols:
                # 외부 종목 일봉 데이터 로드 (청산 시그널 판단에 필요)
                ext_daily, ext_ctx = await load_daily_context(client, external_symbols)
                state.daily_prices.update(ext_daily)
                state.daily_context.update(ext_ctx)
                log.info(
                    "브로커 보유종목 동기화: %d개 외부 포지션 추가 (%s)",
                    len(external_symbols),
                    ", ".join(external_symbols),
                )
                # 외부 종목도 감시 대상에 추가 (WS 구독 + 폴링)
                for sym in external_symbols:
                    if sym not in symbols:
                        symbols.append(sym)
        except Exception:
            log.warning("브로커 잔고 조회 실패 — 외부 매수 동기화 스킵", exc_info=True)

        # 장 시작 체크: 갭 리스크 + 보유 기간 제한
        # ADR-024: multi_regime 모드 전용 손절 로직.
        # cross_momentum은 월말 ranking 기반 매도만 정의 — 개별 갭/보유기간 손절 없음.
        # cross_momentum/none 모드에서 이 로직이 발동하면 5/5~5/6 사고처럼
        # 부팅 직후 multi_regime 잔재 손절이 cross_momentum 포지션을 강제 청산함.
        if state.positions and get_active_strategy() == ActiveStrategy.MULTI_REGIME:
            gap_closed = await check_gap_risk(state, client)
            if gap_closed:
                log.info("갭 리스크 손절 %d개: %s", len(gap_closed), ", ".join(gap_closed))
            hold_closed = await check_holding_limit(state, client)
            if hold_closed:
                log.info("보유기간 초과 청산 %d개: %s", len(hold_closed), ", ".join(hold_closed))
        elif state.positions:
            log.info(
                "ACTIVE_STRATEGY=%s — 갭 리스크/보유기간 손절 SKIP "
                "(multi_regime 전용 로직, %d개 포지션 보존)",
                get_active_strategy().value,
                len(state.positions),
            )

        # ── 양방향 텔레그램: DB 제안 조회/갱신 헬퍼 ─────────
        _cached_suggestions: list[dict[str, Any]] = []
        _bg_tasks: set[asyncio.Task[Any]] = set()  # fire-and-forget 태스크 참조 보관

        async def _load_pending_suggestions() -> list[dict[str, Any]]:
            """DB에서 pending 제안 목록 로드."""
            if _database_url is None:
                return []
            from sqlalchemy import text as sa_text
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(_database_url, pool_pre_ping=True)
            try:
                async with engine.begin() as conn:
                    result = await conn.execute(
                        sa_text(
                            "SELECT id::text, config_key, current_value::text, "
                            "suggested_value::text, reason, source "
                            "FROM strategy_config_suggestions "
                            "WHERE status = 'pending' ORDER BY created_at DESC"
                        )
                    )
                    return [dict(row._mapping) for row in result]
            finally:
                await engine.dispose()

        async def _update_suggestion_status(
            suggestion_ids: list[str],
            new_status: str,
            reviewed_by: str,
        ) -> int:
            """제안 상태를 DB에서 업데이트한다. 변경된 행 수 반환."""
            if _database_url is None or not suggestion_ids:
                return 0
            from sqlalchemy import text as sa_text
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(_database_url, pool_pre_ping=True)
            try:
                async with engine.begin() as conn:
                    result = await conn.execute(
                        sa_text(
                            "UPDATE strategy_config_suggestions "
                            "SET status = :status, reviewed_at = NOW(), reviewed_by = :by "
                            "WHERE id::text = ANY(:ids) AND status = 'pending'"
                        ),
                        {"status": new_status, "by": reviewed_by, "ids": suggestion_ids},
                    )
                    return result.rowcount  # type: ignore[return-value]
            finally:
                await engine.dispose()

        # 시작 시 pending 제안 로드
        try:
            _cached_suggestions.extend(await _load_pending_suggestions())
            if _cached_suggestions:
                log.info("pending 제안 %d건 로드", len(_cached_suggestions))
        except Exception:
            log.warning("pending 제안 로드 실패", exc_info=True)

        # ── 양방향 텔레그램 핸들러 시작 ─────────────────────
        def _build_context() -> TradingContext:
            """현재 TradingState → TradingContext 변환."""
            pos_info: dict[str, dict] = {}
            for sym, pos in state.positions.items():
                ctx_data = state.daily_context.get(sym, {})
                cur_price = state.current_prices.get(sym, pos.entry_price)
                pnl_pct = (
                    (cur_price - pos.entry_price) / pos.entry_price if pos.entry_price > 0 else 0.0
                )
                pos_info[sym] = {
                    "name": pos.name,
                    "qty": pos.quantity,
                    "entry_price": pos.entry_price,
                    "pnl_pct": pnl_pct,
                    "strategy": pos.strategy,
                }
                _ = ctx_data  # 향후 확장용

            sells = [t for t in state.trades if t.side == "SELL"]
            wins = [t for t in sells if t.pnl_pct > 0]
            total_pnl = sum(t.pnl_pct for t in sells) if sells else 0.0
            win_rate = len(wins) / len(sells) if sells else 0.0

            from src.trading.kill_switch import kill_switch

            return TradingContext(
                positions=pos_info,
                total_buys=sum(1 for t in state.trades if t.side == "BUY"),
                total_sells=len(sells),
                win_rate=win_rate,
                total_pnl=total_pnl,
                account_balance=args.account_balance,
                budget_summary=state.budget.summary(),
                current_regime=state.current_regime.upper(),
                strategy_params={s.name: repr(s.params) for s in strategies},
                user_id=_TRADER_USER_ID,
                kill_switch_status=kill_switch.get_status(_TRADER_USER_ID).value,
                pending_suggestions=list(_cached_suggestions),
            )

        def _command_callback(text: str) -> str:
            """텔레그램 메시지 → 명령 파싱 → 실행 → 응답."""
            cmd = parse_command(text)
            if cmd is None:
                return "인식할 수 없는 명령입니다. /도움 을 입력해 보세요."

            from src.trading.kill_switch import kill_switch

            def _on_stop() -> str:
                kill_switch.soft_stop(_TRADER_USER_ID)
                state.drawdown_stop_buy = True
                return "🛑 킬스위치 활성화 — 신규 매수 중단"

            def _on_resume() -> str:
                kill_switch.resume(_TRADER_USER_ID)
                state.drawdown_stop_buy = False
                return "▶️ 매매 재개 — 정상 상태 복귀"

            def _fire_and_forget(coro: Any) -> None:
                task = asyncio.create_task(coro)
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)

            def _on_approve(ids: list[str]) -> str:
                _cached_suggestions[:] = [s for s in _cached_suggestions if s["id"] not in ids]
                _fire_and_forget(_update_suggestion_status(ids, "approved", "telegram"))
                return f"\u2705 {len(ids)}건 제안 승인 처리"

            def _on_reject(ids: list[str]) -> str:
                _cached_suggestions[:] = [s for s in _cached_suggestions if s["id"] not in ids]
                _fire_and_forget(_update_suggestion_status(ids, "rejected", "telegram"))
                return f"\u274c {len(ids)}건 제안 거부 처리"

            ctx = _build_context()
            return execute_command(
                cmd,
                ctx,
                on_stop=_on_stop,
                on_resume=_on_resume,
                on_approve=_on_approve,
                on_reject=_on_reject,
            )

        tg_handler.set_command_callback(_command_callback)
        await tg_handler.start()

        # 매매 루프 시작 알림
        await notifier.send_start([s.name for s in strategies], len(symbols))

        # ADR-024: cross_momentum / none 모드는 WS 우회 (default tick 매매 차단, polling만 사용)
        # multi_regime 모드만 WS 모드 허용
        active = get_active_strategy()
        if args.mode == "ws" and active != ActiveStrategy.MULTI_REGIME:
            log.info(
                "ACTIVE_STRATEGY=%s → WS 모드 우회, polling 모드로 진입 (default tick 매매 차단)",
                active.value,
            )
            args.mode = "polling"

        # 매매 루프
        if args.mode == "ws":
            try:
                await run_trading_loop_ws(
                    client,
                    symbols,
                    strategies,
                    state,
                    args.account_balance,
                    scale_factor,
                    notifier,
                    market_ctx=market_ctx,
                )
            except Exception as ws_err:
                log.warning("WebSocket 루프 실패 (%s), 폴링 모드로 폴백 — 신규 매수 중단", ws_err)
                state.drawdown_stop_buy = True  # WS 페일세이프: 폴링 전환 시 매수 중단
                await run_trading_loop(
                    client,
                    symbols,
                    strategies,
                    state,
                    args.account_balance,
                    scale_factor,
                    notifier,
                    market_ctx=market_ctx,
                )
        else:
            await run_trading_loop(
                client,
                symbols,
                strategies,
                state,
                args.account_balance,
                scale_factor,
                notifier,
                market_ctx=market_ctx,
            )

        # 종료 시 모멘텀 강제 청산 (스윙은 보유 유지)
        await force_close_all(client, state, force_all=False)
        # 남은 스윙 포지션 overnight 저장
        save_overnight_positions(state, OVERNIGHT_PATH)

    except KeyboardInterrupt:
        log.info("사용자 중단 (Ctrl+C)")
        await force_close_all(client, state, force_all=True)
    except Exception as e:
        log.error("매매 루프 에러: %s", e)
        await force_close_all(client, state, force_all=True)
        await notifier.send_error(str(e))
        raise
    finally:
        await tg_handler.stop()
        await client.close()
        _remove_pid_file()

    # 결과 저장 + 요약
    save_results(state, strategies)

    sells = [t for t in state.trades if t.side == "SELL"]
    log.info("=" * 60)
    log.info("매매 요약")
    log.info("=" * 60)
    total_buys = sum(1 for t in state.trades if t.side == "BUY")
    log.info("총 매수: %d건", total_buys)
    log.info("총 매도: %d건", len(sells))
    if sells:
        wins = [t for t in sells if t.pnl_pct > 0]
        total_pnl = sum(t.pnl_pct for t in sells)
        win_rate = len(wins) / len(sells)
        log.info("승률   : %.1f%%", win_rate * 100)
        log.info("총 손익: %+.2f%%", total_pnl * 100)
        await notifier.send_summary(total_buys, len(sells), win_rate, total_pnl)
    else:
        await notifier.send_summary(total_buys, 0, 0.0, 0.0)
    # 전략별 요약
    for strat in strategies:
        strat_sells = [t for t in sells if t.strategy == strat.name]
        if strat_sells:
            strat_wins = [t for t in strat_sells if t.pnl_pct > 0]
            strat_pnl = sum(t.pnl_pct for t in strat_sells)
            log.info(
                "  [%s] 매도 %d건, 승률 %.1f%%, 손익 %+.2f%%",
                strat.name,
                len(strat_sells),
                len(strat_wins) / len(strat_sells) * 100,
                strat_pnl * 100,
            )
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
