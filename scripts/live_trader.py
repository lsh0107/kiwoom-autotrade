#!/usr/bin/env python3
# ruff: noqa: DTZ005, DTZ007
"""모의투자 실시간 자동매매 — 2전략 병행 (모멘텀 + 평균회귀).

스크리닝 통과 종목을 장중 실시간 감시하며 조건 충족 시 매수/매도한다.

사용법:
    python scripts/live_trader.py --auto                          # 2전략 병행 (WebSocket 기본)
    python scripts/live_trader.py --auto --mode polling           # 5분 폴링 모드
    python scripts/live_trader.py --auto --strategy momentum      # 모멘텀만
    python scripts/live_trader.py --auto --strategy mean_reversion # 평균회귀만
    python scripts/live_trader.py --symbols 005930,000660

필수 환경변수:
    KIWOOM_MOCK_APP_KEY, KIWOOM_MOCK_APP_SECRET
    KIWOOM_MOCK_ACCOUNT: 모의투자 계좌번호 (잔고 조회용)

동작:
    ws 모드 (기본):
    1. 종목별 52주 일봉 데이터 로드 (DailyPrice 객체)
    2. WebSocket 구독 → 실시간 틱 수신 → 전략별 진입/청산 신호 체크
    3. 동적 포지션 사이징 (ATR 기반) + 드로우다운 킬스위치
    4. 조건 충족 시 시장가 주문 실행
    5. 15:15 미청산 포지션 강제 청산
    6. 15:35 자동 종료
    7. WebSocket 연결 실패 시 폴링 모드로 자동 폴백

    polling 모드:
    1~6 동일, 2번만 5분 주기 REST 폴링으로 처리
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

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.screen_symbols import get_sector
from src.ai.signal.position_sizer import StrategyBudget, calc_atr, calc_dynamic_position_size
from src.backtest.strategy import MomentumParams
from src.broker.constants import MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.realtime import KiwoomWebSocket
from src.broker.schemas import DailyPrice, OrderRequest, OrderSideEnum, OrderTypeEnum, RealtimeTick
from src.notification.telegram import TelegramNotifier
from src.strategy import MeanReversionParams, MeanReversionStrategy, MomentumStrategy
from src.strategy.base import Strategy
from src.strategy.indicators import VolatilityClass, classify_volatility
from src.trading.drawdown_guard import DrawdownAction, update_drawdown

# ── 설정 ───────────────────────────────────────────────

_TRADER_USER_ID: uuid.UUID = uuid.uuid4()  # kill_switch용 세션 고정 ID
RESULTS_DIR = Path("docs/backtest-results")
POLL_INTERVAL_SEC = 300  # 5분
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
MIN_ATR_PCT = 0.0035  # 0.35% 미만이면 진입 스킵 (거래비용 손익분기 미달)
ATR_STOP_MULT = 1.5  # 손절 = ATR의 1.5배
ATR_TP_MULT = 3.0  # 익절 = ATR의 3.0배 (R:R = 1:2)
MIN_STOP_PCT = 0.005  # 바닥: 최소 0.5% 손절폭 (Kevin Davey floor 패턴)

# ── 웹 제어 파일 경로 ─────────────────────────────────
KILL_SWITCH_FILE = Path("data/.kill_switch")  # 웹에서 생성 시 안전 종료
PID_FILE = Path("data/.trader.pid")  # 프로세스 PID 기록

log = logging.getLogger("live_trader")


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
    sector_positions: set[str] = field(default_factory=set)  # 당일 진입한 섹터 (테마당 1개)
    symbol_strategies: dict[str, str] = field(
        default_factory=dict
    )  # {symbol: "momentum"|"mean_reversion"}
    budget: StrategyBudget = field(default_factory=StrategyBudget)  # 전략별 자금 버킷
    rescreened: dict[str, bool] = field(default_factory=dict)  # 재스크리닝 실행 여부 추적


# ── 유틸 ──────────────────────────────────────────────


def setup_logging() -> None:
    """로깅 설정 (콘솔 + 파일)."""
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS_DIR / f"live_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    log.info("로그 파일: %s", log_path)


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        log.error("환경변수 %s가 없습니다.", key)
        sys.exit(1)
    return value


def now_hhmm() -> str:
    """현재 시각을 HHMM 문자열로 반환."""
    return datetime.now().strftime("%H%M")


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
        log.warning("스크리닝 통과 종목 없음")
        sys.exit(0)

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
) -> list[Strategy]:
    """전략 인스턴스 생성."""
    strategies: list[Strategy] = []
    if strategy_name in ("momentum", "both"):
        strategies.append(MomentumStrategy(params=params))
    if strategy_name in ("mean_reversion", "both"):
        strategies.append(MeanReversionStrategy(params=mr_params))
    return strategies


# ── 데이터 로드 ──────────────────────────────────────


async def load_daily_context(
    client: KiwoomClient, symbols: list[str]
) -> tuple[dict[str, list[DailyPrice]], dict[str, dict]]:
    """종목별 52주 일봉 데이터 로드.

    Returns:
        (daily_prices, daily_context) 튜플
        - daily_prices: {symbol: list[DailyPrice]} — 전략 신호용
        - daily_context: {symbol: {high_52w, avg_volume}} — 호환용
    """
    from src.broker.constants import API_IDS, DEFAULT_EXCHANGE, ENDPOINTS
    from src.broker.schemas import to_kiwoom_symbol

    daily_prices: dict[str, list[DailyPrice]] = {}
    daily_context: dict[str, dict] = {}

    for symbol in symbols:
        log.info("[%s] 일봉 로드 중...", symbol)
        all_raw: list[dict] = []
        qry_dt = datetime.now().strftime("%Y%m%d")

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
    """시장가 매수 주문."""
    if quantity <= 0:
        log.warning("[%s] 수량 0 — 매수 스킵 (현재가 %s원)", symbol, f"{price:,}")
        return

    log.info(
        "[%s] 매수 주문 [%s]: %d주 x %s원 = %s원",
        symbol,
        strategy_name,
        quantity,
        f"{price:,}",
        f"{price * quantity:,}",
    )

    try:
        resp = await client.place_order(
            OrderRequest(
                symbol=symbol,
                side=OrderSideEnum.BUY,
                price=0,  # 시장가
                quantity=quantity,
                order_type=OrderTypeEnum.MARKET,
            )
        )
        log.info("[%s] 매수 접수: 주문번호 %s", symbol, resp.order_no)

        state.positions[symbol] = LivePosition(
            symbol=symbol,
            name=name,
            entry_price=price,
            quantity=quantity,
            entry_time=datetime.now().strftime("%Y%m%d%H%M%S"),
            order_no=resp.order_no,
            strategy=strategy_name,
            high_since_entry=price,
            dynamic_stop=dynamic_stop,
            dynamic_tp=dynamic_tp,
            entry_date=datetime.now().strftime("%Y-%m-%d"),
        )
        # 자금 버킷 할당
        order_amount = price * quantity
        state.budget.allocate(strategy_name, order_amount)
        # 섹터 점유 기록 (당일 재진입 방지)
        sector = get_sector(symbol)
        if sector != "기타":
            state.sector_positions.add(sector)
        state.trades.append(
            TradeLog(
                symbol=symbol,
                name=name,
                side="BUY",
                price=price,
                quantity=quantity,
                time=datetime.now().strftime("%Y%m%d%H%M%S"),
                order_no=resp.order_no,
                strategy=strategy_name,
            )
        )
        if notifier:
            await notifier.send_buy(symbol, name, quantity, price, strategy_name)
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
    """시장가 매도 주문.

    Returns:
        float | None: 성공 시 순손익률(pnl_net), 실패 시 None
    """
    log.info(
        "[%s] 매도 주문 [%s] (%s): %d주 x %s원 | 진입가 %s원",
        pos.symbol,
        pos.strategy,
        reason,
        pos.quantity,
        f"{price:,}",
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
                price=0,
                quantity=pos.quantity,
                order_type=OrderTypeEnum.MARKET,
            )
        )
        log.info("[%s] 매도 접수: 주문번호 %s", pos.symbol, resp.order_no)

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
                time=datetime.now().strftime("%Y%m%d%H%M%S"),
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
) -> None:
    """1회 폴링 사이클: 전 종목 시세 조회 → 전략별 진입/청산 판단."""
    current_hhmm = now_hhmm()
    log.info("--- 폴링 %s ---", current_hhmm)

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

        daily = state.daily_prices.get(symbol, [])
        ctx = state.daily_context.get(symbol)
        if not ctx or not daily:
            await asyncio.sleep(0.3)
            continue

        # 1. 보유 중이면 청산 체크 (진입 전략 기준)
        if symbol in state.positions:
            pos = state.positions[symbol]
            # 고점 갱신
            if quote.price > pos.high_since_entry:
                pos.high_since_entry = quote.price

            # 진입 전략 찾기
            entry_strat = _find_strategy(strategies, pos.strategy)
            if entry_strat:
                kwargs: dict = {}
                if pos.dynamic_stop is not None:
                    kwargs = {"dynamic_stop": pos.dynamic_stop, "dynamic_tp": pos.dynamic_tp}
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
                        action = update_drawdown(
                            _TRADER_USER_ID, account_balance + state.cumulative_pnl_won
                        )
                        if action == DrawdownAction.FORCE_CLOSE:
                            await force_close_all(client, state, force_all=True)
                            return
                        if action == DrawdownAction.STOP_BUY:
                            state.drawdown_stop_buy = True
                    continue

            # 15:15 강제청산 (모멘텀만 — 스윙 포지션은 overnight 보유)
            if current_hhmm >= FORCE_CLOSE_HHMM and pos.strategy == "momentum":
                pnl = await execute_sell(client, pos, quote.price, "force_close", state, notifier)
                await asyncio.sleep(0.5)
                if pnl is not None:
                    update_risk_after_trade(state, symbol, pnl)
                    action = update_drawdown(
                        _TRADER_USER_ID, account_balance + state.cumulative_pnl_won
                    )
                    if action == DrawdownAction.FORCE_CLOSE:
                        await force_close_all(client, state, force_all=True)
                        return
                    if action == DrawdownAction.STOP_BUY:
                        state.drawdown_stop_buy = True
                continue

        # 2. 미보유 + 드로우다운 매수중단 아님 + 블랙리스트 아님 → 전략별 진입 체크
        if (
            symbol not in state.positions
            and not state.drawdown_stop_buy
            and symbol not in state.symbol_blacklist
        ):
            # 섹터 중복 체크 (테마당 1개, '기타' 제외)
            sym_sector = get_sector(symbol)
            if sym_sector != "기타" and sym_sector in state.sector_positions:
                log.info("[%s] 섹터 중복 [%s] → 진입 스킵", symbol, sym_sector)
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
                if current_count >= max_pos:
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
                    dyn_stop = -max(atr_pct * ATR_STOP_MULT, MIN_STOP_PCT)
                    dyn_tp = max(atr_pct * ATR_TP_MULT, MIN_STOP_PCT * 2)

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
    for sym in new_symbols:
        daily = new_prices.get(sym)
        if not daily:
            continue
        state.daily_prices[sym] = daily
        state.daily_context[sym] = new_ctx[sym]
        symbols.append(sym)

        vol_class = classify_volatility(daily)
        if vol_class == VolatilityClass.MEAN_REVERSION:
            state.symbol_strategies[sym] = "mean_reversion"
        else:
            state.symbol_strategies[sym] = "momentum"
        added.append(sym)
        log.info(
            "재스크리닝: [%s] 추가 (전략: %s)",
            sym,
            state.symbol_strategies[sym],
        )

    return added


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
            if added:
                await ws.subscribe(added, "0B")
                log.info("재스크리닝 완료: %d개 추가, WS 구독 등록", len(added))
        except Exception as e:
            log.warning("재스크리닝 실패 (%s): %s", target, e)


async def run_trading_loop(
    client: KiwoomClient,
    symbols: list[str],
    strategies: list[Strategy],
    state: TradingState,
    account_balance: int,
    scale_factor: float,
    notifier: "TelegramNotifier | None" = None,
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

        # 장중 재스크리닝 (RESCREEN_TIMES 시각에 1회씩)
        for target in RESCREEN_TIMES:
            if current >= target and not state.rescreened.get(target):
                log.info("재스크리닝 시작 (시각: %s)", target)
                try:
                    await _run_rescreen(client, symbols, state)
                except Exception as e:
                    log.warning("재스크리닝 실패 (%s): %s", target, e)
                state.rescreened[target] = True

        await poll_cycle(
            client, symbols, strategies, state, account_balance, scale_factor, notifier
        )

        # 다음 폴링까지 대기
        log.info("다음 폴링까지 %d초 대기...", POLL_INTERVAL_SEC)
        await asyncio.sleep(POLL_INTERVAL_SEC)


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

    if not targets:
        swing_count = len(state.positions)
        log.info("청산 대상 없음 (스윙 %d개 보유 유지)", swing_count)
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
    today = datetime.now().strftime("%Y-%m-%d")

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
    today = datetime.now().strftime("%Y-%m-%d")

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
        get_token=client._ensure_token,
        is_mock=True,
    )

    async def handle_tick(tick: RealtimeTick) -> None:
        """실시간 틱 수신 시 진입/청산 판단."""
        symbol = tick.symbol

        if symbol not in symbols:
            return

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
                        action = update_drawdown(
                            _TRADER_USER_ID, account_balance + state.cumulative_pnl_won
                        )
                        if action == DrawdownAction.FORCE_CLOSE:
                            await force_close_all(client, state, force_all=True)
                        elif action == DrawdownAction.STOP_BUY:
                            state.drawdown_stop_buy = True
                    return

            # 15:15 강제청산 (모멘텀만 — 스윙 포지션은 overnight 보유)
            if current_hhmm >= FORCE_CLOSE_HHMM and pos.strategy == "momentum":
                pnl = await execute_sell(client, pos, tick.price, "force_close", state, notifier)
                if pnl is not None:
                    update_risk_after_trade(state, symbol, pnl)
                    action = update_drawdown(
                        _TRADER_USER_ID, account_balance + state.cumulative_pnl_won
                    )
                    if action == DrawdownAction.FORCE_CLOSE:
                        await force_close_all(client, state, force_all=True)
                    elif action == DrawdownAction.STOP_BUY:
                        state.drawdown_stop_buy = True
                return

        # 2. 미보유 + 드로우다운 매수중단 아님 + 블랙리스트 아님 → 전략별 진입 체크
        if (
            symbol not in state.positions
            and not state.drawdown_stop_buy
            and symbol not in state.symbol_blacklist
        ):
            # 섹터 중복 체크 (테마당 1개, '기타' 제외)
            ws_sector = get_sector(symbol)
            if ws_sector != "기타" and ws_sector in state.sector_positions:
                log.info("[%s] WS 섹터 중복 [%s] → 진입 스킵", symbol, ws_sector)
                return

            # 종목별 할당 전략으로만 진입 판단
            ws_sym_strategy = state.symbol_strategies.get(symbol, "momentum")
            time_ratio = calc_time_ratio(current_hhmm)
            for strat in strategies:
                if strat.name != ws_sym_strategy:
                    continue
                max_pos = _get_max_positions(strat)
                current_count = _count_positions_by_strategy(state, strat.name)
                if current_count >= max_pos:
                    continue

                # 버킷 가용액 확인
                if state.budget.available(ws_sym_strategy) <= 0:
                    log.info("[%s] %s 버킷 가용액 없음 → 진입 스킵", symbol, ws_sym_strategy)
                    continue

                # 당일 시가 추적 (첫 tick 기준)
                if symbol not in state.day_open_prices:
                    state.day_open_prices[symbol] = tick.price
                day_open = state.day_open_prices[symbol]
                ct = f"{current_hhmm[:2]}:{current_hhmm[2:]}" if len(current_hhmm) >= 4 else ""
                entry = strat.check_entry_signal(
                    daily,
                    tick.price,
                    tick.volume,
                    time_ratio,
                    current_time=ct,
                    day_open=day_open,
                )

                high_52w = ctx["high_52w"]
                avg_volume = ctx["avg_volume"]
                price_ratio = tick.price / high_52w if high_52w > 0 else 0
                vol_ratio = tick.volume / avg_volume if avg_volume > 0 else 0
                log.info(
                    "[%s] WS [%s] | 현재가 %s (52주고 대비 %.1f%%) | 거래량 %s (%.1fx) | %s",
                    symbol,
                    strat.name,
                    f"{tick.price:,}",
                    price_ratio * 100,
                    f"{tick.volume:,}",
                    vol_ratio,
                    "→ 매수!" if entry else "대기",
                )

                if not entry:
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
                    ws_dyn_stop = -max(atr_pct * ATR_STOP_MULT, MIN_STOP_PCT)
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
        try:
            await ws.run_until("153500")
        finally:
            rescreen_task.cancel()
    finally:
        await ws.close()


# ── 결과 저장 ────────────────────────────────────────


def save_results(state: TradingState, strategies: list[Strategy]) -> None:
    """매매 결과 JSON 저장."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        "run_at": datetime.now().isoformat(),
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
        help="매매 루프 모드 (ws: WebSocket 기반, polling: 5분 REST 폴링, 기본: ws)",
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
        "--entry-start-time", type=str, default="0905", help="진입 시작 시각 (HHMM)"
    )
    parser.add_argument("--entry-end-time", type=str, default="1300", help="진입 종료 시각 (HHMM)")
    parser.add_argument(
        "--max-holding-days", type=int, default=MAX_HOLDING_DAYS, help="최대 보유 거래일"
    )
    parser.add_argument(
        "--gap-risk-threshold", type=float, default=GAP_RISK_THRESHOLD, help="갭 하락 손절 기준"
    )
    parser.add_argument("--max-positions", type=int, default=3, help="최대 동시 포지션 수")
    args = parser.parse_args()

    # argparse 값으로 전역 상수 덮어쓰기
    ATR_STOP_MULT = args.atr_stop_mult
    ATR_TP_MULT = args.atr_tp_mult
    MIN_ATR_PCT = args.min_atr_pct
    MIN_STOP_PCT = args.min_stop_pct
    FORCE_CLOSE_HHMM = args.force_close_time
    MARKET_CLOSE_HHMM = args.market_close_time
    GAP_RISK_THRESHOLD = args.gap_risk_threshold
    MAX_HOLDING_DAYS = args.max_holding_days

    setup_logging()

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

    if args.auto:
        symbols = load_screened_symbols()
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        log.error("--symbols 또는 --auto 필수")
        sys.exit(1)

    params = MomentumParams(
        volume_ratio=args.volume_ratio,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
        high_52w_threshold=args.high_52w_threshold,
    )

    mr_params = MeanReversionParams(
        rsi_oversold=args.mr_rsi_oversold,
        bb_std=args.mr_bb_std,
        volume_ratio=args.mr_volume_ratio,
        stop_loss=args.mr_stop_loss,
        take_profit=args.mr_take_profit,
    )

    strategies = build_strategies(args.strategy, params, mr_params)

    _update_poll_interval(args.poll_interval)

    log.info("=" * 60)
    log.info("자동매매 — 2전략 병행 (모의투자)")
    log.info("실행: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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
        await client.authenticate()
        log.info("[OK] 토큰 발급 성공")

        # 52주 일봉 데이터 로드
        state.daily_prices, state.daily_context = await load_daily_context(client, symbols)
        if not state.daily_prices:
            log.error("일봉 데이터 로드 실패. 종료.")
            return

        # 종목별 전략 분류 (변동성 + 추세 강도 기반)
        for symbol, daily in state.daily_prices.items():
            vol_class = classify_volatility(daily)
            if vol_class == VolatilityClass.MEAN_REVERSION:
                state.symbol_strategies[symbol] = "mean_reversion"
            else:
                # CONSERVATIVE + MOMENTUM → 모멘텀 전략
                state.symbol_strategies[symbol] = "momentum"
        mom_count = sum(1 for s in state.symbol_strategies.values() if s == "momentum")
        mr_count = sum(1 for s in state.symbol_strategies.values() if s == "mean_reversion")
        log.info("종목 전략 분류 완료: 모멘텀 %d개, 평균회귀 %d개", mom_count, mr_count)

        # 자금 버킷 초기화
        state.budget.reset(args.account_balance)
        log.info("자금 버킷 초기화: %s", state.budget.summary())

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

        # 장 시작 체크: 갭 리스크 + 보유 기간 제한
        if state.positions:
            gap_closed = await check_gap_risk(state, client)
            if gap_closed:
                log.info("갭 리스크 손절 %d개: %s", len(gap_closed), ", ".join(gap_closed))
            hold_closed = await check_holding_limit(state, client)
            if hold_closed:
                log.info("보유기간 초과 청산 %d개: %s", len(hold_closed), ", ".join(hold_closed))

        # 매매 루프 시작 알림
        await notifier.send_start([s.name for s in strategies], len(symbols))

        # 매매 루프
        if args.mode == "ws":
            try:
                await run_trading_loop_ws(
                    client, symbols, strategies, state, args.account_balance, scale_factor, notifier
                )
            except Exception as ws_err:
                log.warning("WebSocket 루프 실패 (%s), 폴링 모드로 폴백", ws_err)
                await run_trading_loop(
                    client, symbols, strategies, state, args.account_balance, scale_factor, notifier
                )
        else:
            await run_trading_loop(
                client, symbols, strategies, state, args.account_balance, scale_factor, notifier
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
