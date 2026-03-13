#!/usr/bin/env python3
# ruff: noqa: DTZ005
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
    5. 14:30 미청산 포지션 강제 청산
    6. 15:35 자동 종료
    7. WebSocket 연결 실패 시 폴링 모드로 자동 폴백

    polling 모드:
    1~6 동일, 2번만 5분 주기 REST 폴링으로 처리
"""

import argparse
import asyncio
import contextlib
import glob as glob_mod
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.signal.position_sizer import calc_dynamic_position_size
from src.backtest.strategy import MomentumParams
from src.broker.constants import MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.realtime import KiwoomWebSocket
from src.broker.schemas import DailyPrice, OrderRequest, OrderSideEnum, OrderTypeEnum, RealtimeTick
from src.notification.telegram import TelegramNotifier
from src.strategy import MeanReversionParams, MeanReversionStrategy, MomentumStrategy
from src.strategy.base import Strategy

# ── 설정 ───────────────────────────────────────────────

RESULTS_DIR = Path("docs/backtest-results")
POLL_INTERVAL_SEC = 300  # 5분
MARKET_CLOSE_HHMM = "1535"  # 이 시각 이후 루프 종료
DEFAULT_INVEST_PER_TRADE = 500_000  # 1회 투자금 (원)
DEFAULT_ACCOUNT_BALANCE = 10_000_000  # 기본 계좌 잔고 (1천만원)

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
        )
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
) -> None:
    """시장가 매도 주문."""
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
    tax_rate = 0.0018

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
        del state.positions[pos.symbol]
        if notifier:
            await notifier.send_sell(
                pos.symbol, pos.name, pos.quantity, price, pnl_net, reason, pos.strategy
            )
    except Exception as e:
        log.error("[%s] 매도 실패: %s", pos.symbol, e)


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
                exit_reason = entry_strat.check_exit_signal(
                    pos.entry_price, quote.price, pos.high_since_entry
                )
                # 평균회귀: 지표 기반 추가 청산 (RSI 과매수, BB 중심선 회귀)
                if not exit_reason and hasattr(entry_strat, "check_exit_with_indicators"):
                    exit_reason = entry_strat.check_exit_with_indicators(
                        pos.entry_price, quote.price, daily
                    )
                if exit_reason:
                    await execute_sell(client, pos, quote.price, exit_reason, state, notifier)
                    await asyncio.sleep(0.5)
                    continue

            # 14:30 강제청산 (전략 무관)
            if current_hhmm >= "1430":
                await execute_sell(client, pos, quote.price, "force_close", state, notifier)
                await asyncio.sleep(0.5)
                continue

        # 2. 미보유 + 드로우다운 매수중단 아님 → 전략별 진입 체크
        if symbol not in state.positions and not state.drawdown_stop_buy:
            time_ratio = calc_time_ratio(current_hhmm)
            for strat in strategies:
                max_pos = _get_max_positions(strat)
                current_count = _count_positions_by_strategy(state, strat.name)
                if current_count >= max_pos:
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

                if entry:
                    qty = calc_dynamic_position_size(
                        price=quote.price,
                        daily=daily,
                        account_balance=account_balance,
                        scale_factor=scale_factor,
                    )
                    await execute_buy(
                        client, symbol, quote.name, quote.price, qty, strat.name, state, notifier
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


async def force_buy_best(
    client: KiwoomClient,
    symbols: list[str],
    state: TradingState,
    account_balance: int,
    scale_factor: float,
    notifier: "TelegramNotifier | None" = None,
) -> None:
    """가장 유망한 종목 1개 강제 매수 (매매 0건 방지)."""
    if state.trades or state.positions:
        return  # 이미 매매 이력 있으면 패스

    log.info("=== 강제 매수 발동: 매매 0건 → 최적 종목 탐색 ===")

    best_symbol = None
    best_name = ""
    best_price = 0
    best_score = -1.0

    for symbol in symbols:
        if symbol in state.positions:
            continue
        ctx = state.daily_context.get(symbol)
        if not ctx:
            continue

        try:
            quote = await client.get_quote(symbol)
        except Exception:
            await asyncio.sleep(0.5)
            continue

        high_52w = ctx["high_52w"]
        avg_volume = ctx["avg_volume"]
        price_ratio = quote.price / high_52w if high_52w > 0 else 0
        vol_ratio = quote.volume / avg_volume if avg_volume > 0 else 0

        # 점수: 52주고가 근접도 + 거래량 활성도
        score = price_ratio * 0.6 + min(vol_ratio, 3.0) / 3.0 * 0.4
        log.info(
            "[%s] %s | score=%.3f (price=%.1f%%, vol=%.1fx)",
            symbol,
            quote.name,
            score,
            price_ratio * 100,
            vol_ratio,
        )

        if score > best_score:
            best_score = score
            best_symbol = symbol
            best_name = quote.name
            best_price = quote.price

        await asyncio.sleep(0.5)

    if best_symbol and best_price > 0:
        daily = state.daily_prices.get(best_symbol, [])
        qty = calc_dynamic_position_size(
            price=best_price,
            daily=daily,
            account_balance=account_balance,
            scale_factor=scale_factor,
        )
        log.info(
            "=== 강제 매수 대상: %s %s (score=%.3f, %d주 x %s원) ===",
            best_symbol,
            best_name,
            best_score,
            qty,
            f"{best_price:,}",
        )
        await execute_buy(
            client, best_symbol, best_name, best_price, qty, "momentum", state, notifier
        )
    else:
        log.warning("강제 매수 대상 없음")


FORCE_BUY_TIME = "1300"  # 이 시각까지 매매 0건이면 강제 매수


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
        "매매 루프 시작 (전략: %s, 종료: %s, 강제매수: %s)",
        "+".join(strat_names),
        MARKET_CLOSE_HHMM,
        FORCE_BUY_TIME,
    )
    force_buy_done = False

    while True:
        current = now_hhmm()

        # 장 종료 체크
        if current >= MARKET_CLOSE_HHMM:
            log.info("장 종료 시각 도달 (%s). 루프 종료.", current)
            break

        await poll_cycle(
            client, symbols, strategies, state, account_balance, scale_factor, notifier
        )

        # 강제 매수: 지정 시각까지 매매 0건이면 최적 종목 1개 매수
        if not force_buy_done and current >= FORCE_BUY_TIME:
            await force_buy_best(client, symbols, state, account_balance, scale_factor, notifier)
            force_buy_done = True

        # 다음 폴링까지 대기
        log.info("다음 폴링까지 %d초 대기...", POLL_INTERVAL_SEC)
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def force_close_all(
    client: KiwoomClient,
    state: TradingState,
) -> None:
    """미청산 포지션 전량 강제 청산."""
    if not state.positions:
        log.info("미청산 포지션 없음")
        return

    log.info("미청산 포지션 %d개 강제 청산", len(state.positions))

    for symbol in list(state.positions.keys()):
        pos = state.positions[symbol]
        try:
            quote = await client.get_quote(symbol)
            await execute_sell(client, pos, quote.price, "end_of_day", state)
        except Exception as e:
            log.error("[%s] 강제 청산 실패: %s", symbol, e)
        await asyncio.sleep(0.5)


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
        "WebSocket 매매 루프 시작 (전략: %s, 종료: 153500, 강제매수: %s)",
        "+".join(strat_names),
        FORCE_BUY_TIME,
    )

    ws = KiwoomWebSocket(
        base_url=MOCK_BASE_URL,
        get_token=client._ensure_token,
        is_mock=True,
    )
    force_buy_done = False

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

        # 1. 보유 중이면 청산 체크 (진입 전략 기준)
        if symbol in state.positions:
            pos = state.positions[symbol]
            # 고점 갱신
            if tick.price > pos.high_since_entry:
                pos.high_since_entry = tick.price

            entry_strat = _find_strategy(strategies, pos.strategy)
            if entry_strat:
                exit_reason = entry_strat.check_exit_signal(
                    pos.entry_price, tick.price, pos.high_since_entry
                )
                # 평균회귀: 지표 기반 추가 청산 (RSI 과매수, BB 중심선 회귀)
                if not exit_reason and hasattr(entry_strat, "check_exit_with_indicators"):
                    exit_reason = entry_strat.check_exit_with_indicators(
                        pos.entry_price, tick.price, daily
                    )
                if exit_reason:
                    await execute_sell(client, pos, tick.price, exit_reason, state, notifier)
                    return

            # 14:30 강제청산 (전략 무관)
            if current_hhmm >= "1430":
                await execute_sell(client, pos, tick.price, "force_close", state, notifier)
                return

        # 2. 미보유 + 드로우다운 매수중단 아님 → 전략별 진입 체크
        if symbol not in state.positions and not state.drawdown_stop_buy:
            time_ratio = calc_time_ratio(current_hhmm)
            for strat in strategies:
                max_pos = _get_max_positions(strat)
                current_count = _count_positions_by_strategy(state, strat.name)
                if current_count >= max_pos:
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

                if entry:
                    qty = calc_dynamic_position_size(
                        price=tick.price,
                        daily=daily,
                        account_balance=account_balance,
                        scale_factor=scale_factor,
                    )
                    await execute_buy(
                        client, symbol, symbol, tick.price, qty, strat.name, state, notifier
                    )
                    break  # 한 종목에 한 전략만 진입

    ws.on_tick = handle_tick

    async def _force_buy_checker() -> None:
        """강제 매수 시각 도달 시 최적 종목 1개 강제 매수."""
        nonlocal force_buy_done
        while True:
            current = now_hhmm()
            if current >= MARKET_CLOSE_HHMM:
                break
            if not force_buy_done and current >= FORCE_BUY_TIME:
                await force_buy_best(
                    client, symbols, state, account_balance, scale_factor, notifier
                )
                force_buy_done = True
                break
            await asyncio.sleep(60)

    force_buy_task = asyncio.create_task(_force_buy_checker())

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
        await ws.run_until("153500")
    finally:
        force_buy_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await force_buy_task
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


def _update_force_buy_time(value: str) -> None:
    """강제 매수 시각 전역 변수 갱신."""
    global FORCE_BUY_TIME
    FORCE_BUY_TIME = value


async def main() -> None:
    """실시간 자동매매 실행."""
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
        "--force-buy-time",
        default="1300",
        help="매매 0건 시 강제 매수 시각 HHMM (기본: 1300)",
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
    args = parser.parse_args()

    setup_logging()

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
    _update_force_buy_time(args.force_buy_time)

    log.info("=" * 60)
    log.info("자동매매 — 2전략 병행 (모의투자)")
    log.info("실행: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 60)
    log.info("전략        : %s", ", ".join(s.name for s in strategies))
    log.info("종목        : %s (%d개)", ", ".join(symbols), len(symbols))
    log.info("계좌 잔고   : %s원", f"{args.account_balance:,}")
    log.info("폴링 간격   : %d초", POLL_INTERVAL_SEC)
    log.info("강제매수    : %s (매매 0건 시)", FORCE_BUY_TIME)
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

        # 종료 시 미청산 강제 청산
        await force_close_all(client, state)

    except KeyboardInterrupt:
        log.info("사용자 중단 (Ctrl+C)")
        await force_close_all(client, state)
    except Exception as e:
        log.error("매매 루프 에러: %s", e)
        await notifier.send_error(str(e))
        raise
    finally:
        await client.close()

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
