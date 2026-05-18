"""ADR-022: Cross-sectional momentum monthly rebalance 어댑터.

ADR-021 PASS 조합(top20pct_novol_notrend)을 모의투자 환경에서 실행하는 어댑터.
live_trader.py와 분리된 독립 모듈로, 매월 마지막 거래일 14:30 신호 산정 →
14:55 주문 실행 흐름을 담당한다.

설계 결정 (ADR-022):
  - 유니버스: KOSPI100 + KOSDAQ100 동결 리스트 (ADR-021 기준)
  - best combo: top 20%, vol_filter=OFF, trend_filter=OFF
  - sizing: equal weight (가용현금 x (1-cash_buffer) / n_positions), 1주 미만 SKIP
  - 안전장치: min/max_order_amount, 09:00~15:30 외 SKIP
  - 강제 모의투자: is_mock_trading=True 고정

ADR-023 견고화:
  - pykrx rate limit: DB 캐시 우선 조회 + backoff 재시도
  - T+2 결제 현금흐름: T2PendingSettlement 추적 (실전용)
  - KRX 공휴일: krx_calendar 사용 (pykrx 의존 제거)
"""

from __future__ import annotations

import asyncio
import contextlib
import json as _json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    pass

log = logging.getLogger("cross_momentum_rebalance")
_slog = structlog.get_logger("cross_momentum_rebalance")

# ── 상수 ─────────────────────────────────────────────────────────────────────

# best combo 파라미터 (ADR-021 PASS: top20pct_novol_notrend)
_FORMATION_MONTHS: int = 12
_SKIP_MONTHS: int = 1
_TOP_PCT: float = 0.20

# 안전장치
MAX_ORDER_AMOUNT_KRW: int = 5_000_000  # 종목당 최대 주문금액 (레거시, 호환용)

# 공통 리스크 게이트(run_all_checks)용 cross_momentum 임계값
# multi_regime의 1.5M보다 큼 — cross_momentum은 monthly 1회 large-position 매수
# 자본 50억 / 35종목 ≈ 14M 가정 + 여유로 50M 기준
_CROSS_MOMENTUM_GATE_MAX_AMOUNT: int = 50_000_000  # Level 1: 1회 주문 한도
_CROSS_MOMENTUM_GATE_MAX_INVESTMENT: int = 50_000_000  # Level 2: 누적 한도 (per call)

# 시장 운영시간 (HHMM)
_MARKET_OPEN = "0900"
_MARKET_CLOSE = "1530"

# 리밸런싱 트리거 시각
REBALANCE_SIGNAL_HHMM = "1430"  # 신호 산정 (ranking)
REBALANCE_ORDER_HHMM = "1455"  # 주문 실행

# 월 거래일 수 추정값 (momentum score 계산용)
_TRADING_DAYS_PER_MONTH: int = 21


# ── 데이터 클래스 ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RebalanceParams:
    """리밸런싱 파라미터.

    strategy_config DB에서 로드하거나 기본값 사용.
    best combo: top20pct_novol_notrend (ADR-021 PASS)
    """

    formation_months: int = _FORMATION_MONTHS
    skip_months: int = _SKIP_MONTHS
    top_pct: float | None = _TOP_PCT
    use_vol_filter: bool = False  # novol — OFF
    use_trend_filter: bool = False  # notrend — OFF
    n_positions: int = 5  # 사용자 요구: 계좌 규모(~1,152만) 대비 적정 분산
    t2_settlement: bool = False  # T+2 결제 시뮬레이션 (모의 기본 False, 실전 True)
    rebalance_freq: str = "monthly"  # monthly | weekly
    min_order_amount: int = 500_000  # 최소 주문금액 (원)
    max_order_amount_pct: float = 0.20  # 가용현금 대비 종목당 최대 주문 비율
    cash_buffer_pct: float = 0.10  # 현금 버퍼 비율 (매수에 사용하지 않는 비율)

    @property
    def effective_top_pct(self) -> float:
        """n_positions 우선, top_pct는 fallback."""
        return self.top_pct if self.top_pct is not None else _TOP_PCT


async def load_rebalance_params(db: AsyncSession) -> RebalanceParams:
    """strategy_config에서 cross_momentum.* 키를 읽어 RebalanceParams 인스턴스화.

    누락 키는 데이터클래스 기본값 그대로. DB 조회 실패 시에도 기본값 반환.

    Args:
        db: AsyncSession 인스턴스

    Returns:
        RebalanceParams: DB 값이 반영된 파라미터
    """
    from sqlalchemy import text

    defaults = RebalanceParams()
    _prefix = "cross_momentum."
    _keys = [
        "rebalance_freq",
        "n_positions",
        "top_pct",
        "use_vol_filter",
        "use_trend_filter",
        "min_order_amount",
        "max_order_amount_pct",
        "cash_buffer_pct",
    ]

    try:
        result = await db.execute(
            text("SELECT key, value FROM strategy_config WHERE key LIKE 'cross_momentum.%'"),
        )
        rows = result.fetchall()
        config: dict[str, Any] = {}
        for row in rows:
            short_key = row[0].removeprefix(_prefix)
            val = row[1]
            # JSONB → Python 자동 변환되지만, 일부 드라이버는 raw JSON 문자열 반환
            if isinstance(val, str):
                with contextlib.suppress(ValueError, TypeError):
                    val = _json.loads(val)
            config[short_key] = val

        return RebalanceParams(
            formation_months=defaults.formation_months,
            skip_months=defaults.skip_months,
            top_pct=config.get("top_pct", defaults.top_pct),
            use_vol_filter=config.get("use_vol_filter", defaults.use_vol_filter),
            use_trend_filter=config.get("use_trend_filter", defaults.use_trend_filter),
            n_positions=config.get("n_positions", defaults.n_positions),
            t2_settlement=defaults.t2_settlement,
            rebalance_freq=config.get("rebalance_freq", defaults.rebalance_freq),
            min_order_amount=config.get("min_order_amount", defaults.min_order_amount),
            max_order_amount_pct=config.get("max_order_amount_pct", defaults.max_order_amount_pct),
            cash_buffer_pct=config.get("cash_buffer_pct", defaults.cash_buffer_pct),
        )
    except Exception as exc:
        log.warning("strategy_config 로드 실패, 기본값 사용: %s", exc)
        return defaults


@dataclass
class T2PendingSettlement:
    """T+2 결제 대기 항목 (ADR-023).

    매도 체결 후 결제일(T+2)까지 미수령 현금을 추적한다.

    Attributes:
        symbol: 종목코드
        sell_amount: 매도 예상금액 (원)
        sell_date: 매도 체결일
        settle_date: 결제일 (sell_date + 2 영업일)
    """

    symbol: str
    sell_amount: int
    sell_date: date
    settle_date: date


@dataclass
class RebalanceOrders:
    """리밸런싱 주문 명세 (equal-weight 완전화).

    Attributes:
        sells: 전량 매도 종목코드 리스트 (현재 보유 중이나 타깃에 없음)
        buys: 매수 종목코드 리스트 (타깃이나 현재 미보유)
        adjust_sells: 비중 축소 매도 (target 안이지만 초과 보유)
        adjust_buys: 비중 확대 매수 (target 안이지만 부족 보유)
        target_symbols: 이번 달 목표 포트폴리오 종목 코드
        cash_per_position: 종목당 목표 배정 현금 (원)
        sell_amounts: 종목별 매도 금액 (비중 조정용)
        buy_amounts: 종목별 매수 금액 (비중 조정용)
    """

    sells: list[str] = field(default_factory=list)
    buys: list[str] = field(default_factory=list)
    adjust_sells: list[str] = field(default_factory=list)
    adjust_buys: list[str] = field(default_factory=list)
    target_symbols: list[str] = field(default_factory=list)
    cash_per_position: int = 0
    sell_amounts: dict[str, int] = field(default_factory=dict)
    buy_amounts: dict[str, int] = field(default_factory=dict)


# ── pykrx backoff wrapper ──────────────────────────────────────────────────────


async def _fetch_pykrx_with_backoff(
    symbol: str,
    start: str,
    end: str,
    retries: int = 3,
    base_delay: float = 0.5,
) -> Any:
    """pykrx rate limit 대응 backoff 재시도 래퍼 (ADR-023).

    Args:
        symbol: 종목코드 (6자리)
        start: 조회 시작일 (YYYYMMDD)
        end: 조회 종료일 (YYYYMMDD)
        retries: 최대 재시도 횟수 (기본 3)
        base_delay: 초기 대기 시간(초). 지수 증가: base_delay * 2^attempt

    Returns:
        pykrx OHLCV DataFrame.

    Raises:
        Exception: retries 소진 후에도 실패 시 마지막 예외를 다시 발생.
    """
    from pykrx import stock as pykrx_stock  # lazy import

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return pykrx_stock.get_market_ohlcv_by_date(start, end, symbol)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                await asyncio.sleep(base_delay * (2**attempt))
    raise last_exc  # type: ignore[misc]


# ── 마지막 거래일 판정 (레거시 fallback) ──────────────────────────────────────
# check_monthly_rebalance 훅은 krx_calendar.is_last_business_day_of_month를 사용한다.
# 이 함수는 하위 호환 및 단위 테스트 검증용으로 유지한다.


def _is_last_trading_day_of_month(today: date) -> bool:
    """오늘이 이번 달의 마지막 거래일인지 판정한다.

    pykrx를 이용해 다음 거래일을 조회하고, 다음 거래일이 다음 달이면 True.
    pykrx 실패 시 주말 기반 단순 판정으로 fallback.

    Args:
        today: 판정 기준일 (KST date)

    Returns:
        True이면 이번 달 마지막 거래일.
    """
    try:
        from pykrx import stock as pykrx_stock  # lazy import

        today_str = today.strftime("%Y%m%d")
        # 다음 영업일 조회
        next_biz = pykrx_stock.get_nearest_business_day_in_a_week(
            date=(today + timedelta(days=1)).strftime("%Y%m%d")
        )
        if next_biz:
            next_date = date(int(next_biz[:4]), int(next_biz[4:6]), int(next_biz[6:8]))
            return next_date.month != today.month
        # 조회 실패 → fallback
        log.debug("pykrx 다음 거래일 조회 결과 없음 (%s), fallback 사용", today_str)
    except Exception as exc:
        log.debug("pykrx 거래일 조회 실패, fallback 사용: %s", exc)

    # Fallback: 이번 달 마지막 날에서 가장 가까운 평일이 오늘인지 확인
    # 다음 달 1일의 전날 = 이번 달 말일
    first_of_next = date(today.year + (1 if today.month == 12 else 0), today.month % 12 + 1, 1)
    last_of_month = first_of_next - timedelta(days=1)
    # 말일이 주말이면 그 전 평일이 마지막 거래일
    while last_of_month.weekday() >= 5:  # 5=토, 6=일
        last_of_month -= timedelta(days=1)
    return today == last_of_month


# ── 어댑터 ────────────────────────────────────────────────────────────────────


class CrossMomentumRebalanceAdapter:
    """Cross-sectional momentum monthly rebalance 어댑터 (ADR-022).

    모의투자 전용. is_mock_trading=True 강제.
    """

    def __init__(
        self,
        params: RebalanceParams | None = None,
        *,
        database_url: str | None = None,
    ) -> None:
        self.params = params or RebalanceParams()
        # 리밸런싱 실행 여부 추적 (당일 중복 실행 방지)
        self._last_rebalance_date: date | None = None

        # DB 캐시 (ADR-023 rate limit 대응)
        if database_url is None:
            database_url = os.environ.get("DATABASE_URL")
        from src.trading.daily_candle_store import DailyCandleStore

        self._candle_store = DailyCandleStore(database_url=database_url)

    # ── 신호 계산 ────────────────────────────────────────────────────────────

    async def compute_target_portfolio(self, today: date) -> list[str]:
        """오늘 기준 12-1 momentum 신호로 목표 포트폴리오 산정.

        DB 캐시를 우선 조회하고, 데이터 부족 시 pykrx를 backoff 재시도로 fetch한다.
        best combo(top20pct_novol_notrend): vol_filter, trend_filter 둘 다 OFF.

        Args:
            today: 신호 기준일 (리밸런싱 실행일)

        Returns:
            list[str]: 선택된 종목코드 리스트 (momentum 내림차순, 최대 40종목)
        """
        from src.broker.schemas import DailyPrice
        from src.strategy.cross_momentum_universe import get_universe

        # 데이터 수집 기간: 12개월 formation + 1개월 skip + 여유 2개월
        history_months = self.params.formation_months + self.params.skip_months + 2
        lookback_days = history_months * 31  # 캘린더일 기준 넉넉한 버퍼
        start_date = (date(today.year - (history_months // 12 + 1), today.month, 1)).strftime(
            "%Y%m%d"
        )
        end_date = today.strftime("%Y%m%d")

        # DB 캐시 활성화 시 최소 필요 봉 수 (formation + skip 월 x 21일/월)
        min_required_bars = (
            self.params.formation_months + self.params.skip_months
        ) * _TRADING_DAYS_PER_MONTH

        universe = get_universe()
        universe_data: dict[str, list[DailyPrice]] = {}

        for symbol in universe:
            # 1. DB 캐시 우선 조회 (kiwoom_client=None → pykrx fallback은 아래에서)
            db_bars = await self._candle_store.get_daily_prices(
                symbol,
                lookback_days=lookback_days,
                kiwoom_client=None,
            )
            if len(db_bars) >= min_required_bars:
                universe_data[symbol] = db_bars
                continue

            # 2. DB 데이터 부족 → pykrx backoff fetch
            try:
                df = await _fetch_pykrx_with_backoff(symbol, start_date, end_date)
                if df is None or df.empty:
                    continue
                bars: list[DailyPrice] = []
                for idx, row in df.iterrows():
                    date_str = str(idx).replace("-", "")[:8]
                    bars.append(
                        DailyPrice(
                            date=date_str,
                            open=int(row.get("시가", row.get("Open", 0))),
                            high=int(row.get("고가", row.get("High", 0))),
                            low=int(row.get("저가", row.get("Low", 0))),
                            close=int(row.get("종가", row.get("Close", 0))),
                            volume=int(row.get("거래량", row.get("Volume", 0))),
                        )
                    )
                bars.sort(key=lambda x: x.date)
                if bars:
                    universe_data[symbol] = bars
            except Exception as exc:
                log.debug("[%s] 일봉 수집 실패 (스킵): %s", symbol, exc)

        log.info("일봉 수집 완료: %d/%d종목", len(universe_data), len(universe))

        return self._score_and_select(universe_data)

    def _score_and_select(
        self,
        universe_data: dict[str, list],
    ) -> list[str]:
        """universe_data에서 momentum score를 계산하고 상위 종목 선택.

        n_positions가 설정되면 상위 n_positions개, 아니면 top_pct% 선택.
        pykrx 의존 없이 순수 로직만 담당 — 단위 테스트에서 직접 호출 가능.

        Args:
            universe_data: {종목코드: list[DailyPrice]} 딕셔너리

        Returns:
            list[str]: momentum 내림차순 상위 종목 리스트
        """
        from src.strategy.cross_momentum import (
            CrossMomentumParams,
            compute_momentum_score,
            select_portfolio,
        )

        effective_top_pct = self.params.effective_top_pct

        cm_params = CrossMomentumParams(
            formation_months=self.params.formation_months,
            skip_months=self.params.skip_months,
            top_decile=effective_top_pct,
            use_vol_filter=self.params.use_vol_filter,
            use_trend_filter=self.params.use_trend_filter,
        )

        scores: dict[str, float] = {}
        for symbol, daily in universe_data.items():
            score = compute_momentum_score(daily, cm_params)
            if score is not None:
                scores[symbol] = score

        if not scores:
            log.warning("momentum score 계산 가능 종목 없음")
            return []

        candidates = list(scores.keys())
        selected = select_portfolio(candidates, scores, cm_params)

        # n_positions 우선: select_portfolio 결과를 n_positions로 잘라냄
        n_pos = self.params.n_positions
        if n_pos and len(selected) > n_pos:
            selected = selected[:n_pos]

        log.info(
            "목표 포트폴리오 산정: %d종목 (후보 %d개, n_positions=%s, top_pct=%s)",
            len(selected),
            len(scores),
            n_pos,
            effective_top_pct,
        )
        return selected

    # ── 주문 명세 계산 ────────────────────────────────────────────────────────

    def compute_rebalance_orders(
        self,
        target_symbols: list[str],
        current_holdings: dict[str, int],
        total_cash: int,
        t2_pending: list[T2PendingSettlement] | None = None,
        current_prices: dict[str, int] | None = None,
    ) -> RebalanceOrders:
        """현재 보유 vs 타깃 포트폴리오의 equal-weight diff로 매도/매수 목록 산출.

        equal-weight 완전화:
          1. target 외 종목 → 전량 매도
          2. target 안 보유 종목 → 현재 평가금액 vs 목표 비중 비교 → 비중 조정
          3. target 안 미보유 종목 → 신규 매수
          4. min_order_amount 미만 주문은 SKIP
          5. max_order_amount = available_cash x max_order_amount_pct로 단일 주문 cap

        Args:
            target_symbols: 이번 달 목표 포트폴리오 종목코드
            current_holdings: 현재 보유 종목코드 → 수량 매핑 (symbol → quantity)
            total_cash: 총 사용 가능 현금 (원, T2 조정 전)
            t2_pending: T+2 미정산 항목 리스트 (실전 모드에서 전달)
            current_prices: 종목별 현재가 매핑 (비중 조정 계산용). None이면 비중 조정 SKIP.

        Returns:
            RebalanceOrders: 매도/매수 목록 및 종목당 현금
        """
        # T+2 결제 현금 잠금 처리
        if self.params.t2_settlement and t2_pending:
            locked = sum(p.sell_amount for p in t2_pending)
            available_cash = max(0, total_cash - locked)
            log.info(
                "T+2 미정산 잠금: %s원 → 가용현금 %s원",
                f"{locked:,}",
                f"{available_cash:,}",
            )
        else:
            available_cash = total_cash

        # 현금 버퍼 적용
        investable = int(available_cash * (1 - self.params.cash_buffer_pct))

        target_set = set(target_symbols)
        current_set = set(current_holdings.keys())
        prices = current_prices or {}

        # 종목당 목표 금액
        n = len(target_symbols) if target_symbols else 1
        cash_per_position = investable // n

        # max_order_amount: 가용현금 기준 동적 cap
        max_order_amount = int(available_cash * self.params.max_order_amount_pct)
        min_order_amount = self.params.min_order_amount

        # 1. target 외 종목 → 전량 매도
        sells: list[str] = [s for s in current_holdings if s not in target_set]

        # 2. target 안 미보유 → 신규 매수
        new_buys: list[str] = [s for s in target_symbols if s not in current_set]

        # 3. target 안 기존 보유 → 비중 조정
        adjust_sells: list[str] = []
        adjust_buys: list[str] = []
        sell_amounts: dict[str, int] = {}
        buy_amounts: dict[str, int] = {}

        for sym in target_symbols:
            if sym not in current_set:
                # 신규 매수 금액
                buy_amt = min(cash_per_position, max_order_amount)
                if buy_amt < min_order_amount:
                    log.info(
                        "[%s] 매수금액 %s원 < min %s원 — SKIP",
                        sym,
                        f"{buy_amt:,}",
                        f"{min_order_amount:,}",
                    )
                    continue
                buy_amounts[sym] = buy_amt
                continue

            # 기존 보유 종목 — 비중 조정 판단
            price = prices.get(sym)
            if not price or price <= 0:
                continue

            qty = current_holdings.get(sym, 0)
            current_eval = qty * price
            diff = cash_per_position - current_eval

            if abs(diff) < min_order_amount:
                log.info(
                    "[%s] 비중 차이 %s원 < min %s원 — 조정 SKIP",
                    sym,
                    f"{abs(diff):,}",
                    f"{min_order_amount:,}",
                )
                continue

            if diff > 0:
                # 부족 → 추가 매수
                buy_amt = min(diff, max_order_amount)
                if buy_amt < min_order_amount:
                    continue
                adjust_buys.append(sym)
                buy_amounts[sym] = buy_amt
            elif diff < 0:
                # 초과 → 부분 매도
                sell_amt = min(abs(diff), max_order_amount)
                if sell_amt < min_order_amount:
                    continue
                adjust_sells.append(sym)
                sell_amounts[sym] = sell_amt

        # 신규 매수에 금액 없는 종목 필터
        new_buys = [s for s in new_buys if s in buy_amounts]

        log.info(
            "리밸런싱 diff: 전량매도 %d개, 신규매수 %d개, 비중↓ %d개, 비중↑ %d개, "
            "종목당 목표 %s원 (max=%s, min=%s, buffer=%.0f%%)",
            len(sells),
            len(new_buys),
            len(adjust_sells),
            len(adjust_buys),
            f"{cash_per_position:,}",
            f"{max_order_amount:,}",
            f"{min_order_amount:,}",
            self.params.cash_buffer_pct * 100,
        )
        return RebalanceOrders(
            sells=sells,
            buys=new_buys,
            adjust_sells=adjust_sells,
            adjust_buys=adjust_buys,
            target_symbols=target_symbols,
            cash_per_position=cash_per_position,
            sell_amounts=sell_amounts,
            buy_amounts=buy_amounts,
        )

    # ── 실행 파이프라인 (4-phase) ──────────────────────────────────────────────

    async def _execute_sells(
        self,
        sell_symbols: list[str],
        client: object,
        current_holdings: dict[str, int],
        *,
        adjust_sells: list[str] | None = None,
        sell_amounts: dict[str, int] | None = None,
        db: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
    ) -> dict[str, tuple[int, str | None]]:
        """Phase 1: 매도 실행. 전량 매도 + 비중 축소 매도.

        Returns:
            sold: 매도 완료 종목 → (매도 수량, 브로커 주문번호)
        """
        sold: dict[str, tuple[int, str | None]] = {}
        _sell_amounts = sell_amounts or {}

        # 전량 매도
        for symbol in sell_symbols:
            try:
                qty = current_holdings.get(symbol, 0)
                placed_qty, order_no = await self._place_sell_order(
                    client, symbol, qty, db=db, user_id=user_id
                )
                if placed_qty > 0:
                    sold[symbol] = (placed_qty, order_no)
            except Exception as exc:
                log.error("[%s] 전량 매도 실패 (계속 진행): %s", symbol, exc)

        # 비중 축소 매도
        for symbol in adjust_sells or []:
            try:
                sell_amt = _sell_amounts.get(symbol, 0)
                if sell_amt <= 0:
                    continue
                quote = await client.get_quote(symbol)  # type: ignore[attr-defined]
                if quote.price <= 0:
                    continue
                qty = sell_amt // quote.price
                if qty < 1:
                    continue
                placed_qty, order_no = await self._place_sell_order(
                    client, symbol, qty, db=db, user_id=user_id
                )
                if placed_qty > 0:
                    sold[symbol] = (placed_qty, order_no)
            except Exception as exc:
                log.error("[%s] 비중 축소 매도 실패 (계속 진행): %s", symbol, exc)

        return sold

    async def _execute_buys(
        self,
        buy_symbols: list[str],
        client: object,
        _refreshed_cash: int,
        *,
        adjust_buys: list[str] | None = None,
        buy_amounts: dict[str, int] | None = None,
        db: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
    ) -> dict[str, tuple[int, int, str | None]]:
        """Phase 3: 매수 실행. 신규 매수 + 비중 확대 매수.

        _refreshed_cash: Phase 2에서 갱신된 잔고 (향후 동적 배분 확장용).

        Returns:
            bought: 매수 완료 종목 → (수량, 현재가, 브로커 주문번호)
        """
        bought: dict[str, tuple[int, int, str | None]] = {}
        _buy_amounts = buy_amounts or {}

        all_buys = list(buy_symbols) + list(adjust_buys or [])
        for symbol in all_buys:
            try:
                cash = _buy_amounts.get(symbol, 0)
                if cash <= 0:
                    continue
                ok, buy_qty, buy_price, order_no = await self._place_buy_order(
                    client, symbol, cash, db=db, user_id=user_id
                )
                if ok:
                    bought[symbol] = (buy_qty, buy_price, order_no)
            except Exception as exc:
                log.error("[%s] 매수 실패 (계속 진행): %s", symbol, exc)

        return bought

    def _compute_reconcile(
        self,
        target_symbols: list[str],
        final_balance: object,
        sold: dict[str, tuple[int, str | None]],
        bought: dict[str, tuple[int, int, str | None]],
    ) -> dict[str, Any]:
        """Phase 4: 리밸런스 후 target 대비 실제 보유 비중 차이 로그.

        Returns:
            reconcile_report: 구조화된 reconcile 결과
        """
        holdings_map: dict[str, int] = {}
        total_eval = 0
        try:
            for h in final_balance.holdings:  # type: ignore[attr-defined]
                holdings_map[h.symbol] = h.eval_amount
                total_eval += h.eval_amount
        except Exception as exc:
            log.debug("reconcile 잔고 파싱 실패: %s", exc)

        target_weight = 1.0 / len(target_symbols) if target_symbols else 0.0
        diffs: dict[str, float] = {}
        for sym in target_symbols:
            actual_eval = holdings_map.get(sym, 0)
            actual_weight = actual_eval / total_eval if total_eval > 0 else 0.0
            diffs[sym] = actual_weight - target_weight

        report = {
            "target_count": len(target_symbols),
            "sold_count": len(sold),
            "bought_count": len(bought),
            "total_eval": total_eval,
            "target_weight": round(target_weight, 4),
            "weight_diffs": {k: round(v, 4) for k, v in diffs.items()},
            "max_deviation": round(max(abs(v) for v in diffs.values()), 4) if diffs else 0.0,
        }

        _slog.info(
            "리밸런스 reconcile",
            **report,
        )
        return report

    async def execute_monthly_rebalance(
        self,
        today: date,
        client: object,
        current_holdings: dict[str, int],
        available_cash: int,
        t2_pending: list[T2PendingSettlement] | None = None,
    ) -> bool:
        """월말 리밸런싱 4-phase 파이프라인 실행.

        Phase 1: SELL (전량 매도 + 비중 축소)
        Phase 2: REFRESH BALANCE (매도 후 잔고 재조회)
        Phase 3: BUY (신규 매수 + 비중 확대, refreshed cash 기준)
        Phase 4: RECONCILE (target 대비 실제 보유 비중 차이 로그)

        Args:
            today: 리밸런싱 기준일 (KST)
            client: KiwoomClient 인스턴스
            current_holdings: 현재 보유 종목코드 → 수량 매핑 (symbol → quantity)
            available_cash: 사용 가능 현금 (원, T2 조정 전)
            t2_pending: T+2 미정산 항목 리스트. 실전 모드에서 매도 후 적재됨.

        Returns:
            True이면 실행 완료, False이면 스킵/실패
        """
        # 안전장치: 시장 운영시간 외 SKIP
        from src.utils.time import now_kst

        now = now_kst()
        current_hhmm = now.strftime("%H%M")
        if not (_MARKET_OPEN <= current_hhmm <= _MARKET_CLOSE):
            log.warning(
                "장 운영시간 외 리밸런싱 요청 스킵 (%s, 허용: %s~%s)",
                current_hhmm,
                _MARKET_OPEN,
                _MARKET_CLOSE,
            )
            return False

        # 당일 중복 실행 방지 — instance cache + DB 영속 둘 다 확인
        if self._last_rebalance_date == today:
            log.info("당일 리밸런싱 이미 실행 완료 (%s, 메모리 캐시) — 스킵", today)
            return False
        last_db = await self._get_last_rebalance_date_db()
        if last_db == today:
            self._last_rebalance_date = today
            log.info("당일 리밸런싱 이미 실행 완료 (%s, DB) — 스킵", today)
            return False

        # rebalance_freq 검증
        if self.params.rebalance_freq != "monthly":
            log.warning(
                "rebalance_freq=%s 는 현재 미지원, monthly fallback",
                self.params.rebalance_freq,
            )

        log.info("=" * 60)
        log.info("[ADR-022] 월말 리밸런싱 실행 시작 (%s, 모의투자)", today)
        log.info("=" * 60)

        # 목표 포트폴리오 산정
        target = await self.compute_target_portfolio(today)
        if not target:
            log.error("목표 포트폴리오 산정 실패 — 리밸런싱 중단")
            return False

        # 현재가 조회 (비중 조정용)
        current_prices: dict[str, int] = {}
        for sym in set(list(current_holdings.keys()) + target):
            try:
                quote = await client.get_quote(sym)  # type: ignore[attr-defined]
                current_prices[sym] = quote.price
            except Exception as exc:
                log.debug("[%s] 현재가 조회 실패 (비중 조정 스킵): %s", sym, exc)

        # diff 계산 (T2 현금 잠금 + 비중 조정 반영)
        orders = self.compute_rebalance_orders(
            target, current_holdings, available_cash, t2_pending, current_prices
        )

        # 공통 리스크 게이트용 db session + user_id
        gate_db: AsyncSession | None = None
        gate_user_id: uuid.UUID | None = None
        try:
            from src.config.database import async_session_factory
            from src.trading.live_order_persist import resolve_live_trader_user_id

            gate_db = async_session_factory()
            gate_user_id = await resolve_live_trader_user_id(gate_db)
        except Exception as exc:
            log.warning("리스크 게이트 비활성 (db/user_id 확보 실패): %s", exc)
            if gate_db is not None:
                await gate_db.close()
                gate_db = None

        try:
            # Phase 1: SELL
            sold = await self._execute_sells(
                orders.sells,
                client,
                current_holdings,
                adjust_sells=orders.adjust_sells,
                sell_amounts=orders.sell_amounts,
                db=gate_db,
                user_id=gate_user_id,
            )
            log.info("Phase 1 매도 완료: %d개", len(sold))

            # Phase 2: REFRESH BALANCE
            try:
                refreshed = await client.get_balance()  # type: ignore[attr-defined]
                new_cash = refreshed.available_cash
                log.info("Phase 2 잔고 재조회: 가용현금 %s원", f"{new_cash:,}")
            except Exception as exc:
                log.warning("잔고 재조회 실패, 기존 현금 사용: %s", exc)
                new_cash = available_cash

            # Phase 3: BUY (refreshed cash 기준)
            bought = await self._execute_buys(
                orders.buys,
                client,
                new_cash,
                adjust_buys=orders.adjust_buys,
                buy_amounts=orders.buy_amounts,
                db=gate_db,
                user_id=gate_user_id,
            )
            log.info("Phase 3 매수 완료: %d개", len(bought))

        finally:
            if gate_db is not None:
                await gate_db.close()

        # Phase 4: RECONCILE
        try:
            final_balance = await client.get_balance()  # type: ignore[attr-defined]
            self._compute_reconcile(target, final_balance, sold, bought)
        except Exception as exc:
            log.warning("Phase 4 reconcile 실패 (무시): %s", exc)

        # DB persist
        await self._persist_rebalance(sold, bought)

        # T+2 큐 적재 (실전만)
        if self.params.t2_settlement and t2_pending is not None:
            await self._enqueue_t2_pending(
                client, list(sold.keys()), current_holdings, today, t2_pending
            )

        self._last_rebalance_date = today
        await self._set_last_rebalance_date_db(today)
        log.info("[ADR-022] 월말 리밸런싱 완료 (매도 %d, 매수 %d)", len(sold), len(bought))
        return True

    # ── T+2 큐 적재 헬퍼 ────────────────────────────────────────────────────

    async def _enqueue_t2_pending(
        self,
        client: object,
        sold: list[str],
        current_holdings: dict[str, int],
        sell_date: date,
        t2_pending: list[T2PendingSettlement],
    ) -> None:
        """매도 체결 후 T+2 미정산 항목을 큐에 적재한다 (ADR-023).

        현재가 x 보유수량으로 매도금액을 추정한다.
        조회 실패 시 해당 종목은 스킵 (보수적 현금 추정).

        Args:
            client: KiwoomClient 인스턴스
            sold: 실제 매도 완료된 종목코드
            current_holdings: 매도 전 보유 수량 매핑
            sell_date: 매도 체결일 (KST)
            t2_pending: 적재 대상 큐 (in-place 수정)
        """
        from src.utils.krx_calendar import add_business_days

        settle_date = add_business_days(sell_date, 2)
        for symbol in sold:
            try:
                qty = current_holdings.get(symbol, 0)
                if qty <= 0:
                    continue
                quote = await client.get_quote(symbol)  # type: ignore[attr-defined]
                sell_amount = qty * quote.price
                t2_pending.append(
                    T2PendingSettlement(
                        symbol=symbol,
                        sell_amount=sell_amount,
                        sell_date=sell_date,
                        settle_date=settle_date,
                    )
                )
                log.debug(
                    "[%s] T+2 적재: %s원 (결제일 %s)",
                    symbol,
                    f"{sell_amount:,}",
                    settle_date,
                )
            except Exception as exc:
                log.warning("[%s] T+2 큐 적재 실패 (스킵): %s", symbol, exc)

    # ── 주문 실행 헬퍼 ──────────────────────────────────────────────────────

    async def _place_sell_order(
        self,
        client: object,
        symbol: str,
        quantity: int,
        *,
        db: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
    ) -> tuple[int, str | None]:
        """시장가 매도 주문 (모의투자).

        Args:
            client: KiwoomClient 인스턴스
            symbol: 종목코드
            quantity: 매도 수량 (보유 수량 전량)
            db: AsyncSession. 제공 시 공통 리스크 게이트(run_all_checks) 호출.
            user_id: 트레이더 user_id. db와 함께 제공돼야 게이트 활성.

        Returns:
            (실제 발주된 매도 수량, 브로커 주문번호). 스킵 시 (0, None).
        """
        from src.broker.schemas import OrderRequest, OrderSideEnum, OrderTypeEnum

        if quantity <= 0:
            log.warning("[%s] 매도 수량 0 이하 — 주문 스킵 (quantity=%d)", symbol, quantity)
            return (0, None)

        # 공통 리스크 게이트 (Codex 검토 #4): order_service.run_all_checks 호출
        # 시장가는 발주 시점 현재가로 게이트 검증
        if db is not None and user_id is not None:
            try:
                quote = await client.get_quote(symbol)  # type: ignore[attr-defined]
                from src.trading.drawdown_guard import run_all_checks

                await run_all_checks(
                    user_id=user_id,
                    symbol=symbol,
                    side="sell",
                    price=quote.price,
                    quantity=quantity,
                    db=db,
                    prev_close=quote.prev_close,
                    max_amount=_CROSS_MOMENTUM_GATE_MAX_AMOUNT,
                    max_investment=_CROSS_MOMENTUM_GATE_MAX_INVESTMENT,
                    max_daily_orders=200,  # cross_momentum: 35매도+35매수+추가 buffer
                )
            except Exception as exc:
                log.warning("[%s] 매도 게이트 차단: %s", symbol, exc)
                return (0, None)

        resp = await client.place_order(  # type: ignore[attr-defined]
            OrderRequest(
                symbol=symbol,
                side=OrderSideEnum.SELL,
                price=0,
                quantity=quantity,
                order_type=OrderTypeEnum.MARKET,
            )
        )
        log.info("[%s] 리밸런싱 매도 접수: %d주 (주문번호: %s)", symbol, quantity, resp.order_no)
        return (quantity, resp.order_no)

    async def _place_buy_order(
        self,
        client: object,
        symbol: str,
        cash_per_position: int,
        *,
        db: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
    ) -> tuple[bool, int, int, str | None]:
        """시장가 매수 주문 (모의투자). 1주 미만 수량이면 SKIP.

        Args:
            client: KiwoomClient 인스턴스
            symbol: 종목코드
            cash_per_position: 종목당 배정 현금 (원). compute_rebalance_orders에서 cap 적용 완료.

        Returns:
            (성공 여부, 매수 수량, 발주 시점 현재가, 브로커 주문번호).
            실패/SKIP 시 (False, 0, 0, None).
        """
        from src.broker.schemas import OrderRequest, OrderSideEnum, OrderTypeEnum

        # 현재가 조회 → 수량 계산
        try:
            quote = await client.get_quote(symbol)  # type: ignore[attr-defined]
            current_price = quote.price
        except Exception as exc:
            log.warning("[%s] 현재가 조회 실패, 매수 스킵: %s", symbol, exc)
            return (False, 0, 0, None)

        if current_price <= 0:
            log.warning("[%s] 현재가 0원 — 매수 스킵", symbol)
            return (False, 0, 0, None)

        quantity = cash_per_position // current_price
        if quantity < 1:
            log.info(
                "[%s] 수량 0주 (현재가 %s원, 배정금 %s원) — 매수 스킵",
                symbol,
                f"{current_price:,}",
                f"{cash_per_position:,}",
            )
            return (False, 0, current_price, None)

        # 공통 리스크 게이트
        if db is not None and user_id is not None:
            try:
                from src.trading.drawdown_guard import run_all_checks

                await run_all_checks(
                    user_id=user_id,
                    symbol=symbol,
                    side="buy",
                    price=current_price,
                    quantity=quantity,
                    db=db,
                    prev_close=quote.prev_close,
                    max_amount=_CROSS_MOMENTUM_GATE_MAX_AMOUNT,
                    max_investment=_CROSS_MOMENTUM_GATE_MAX_INVESTMENT,
                    max_daily_orders=200,
                )
            except Exception as exc:
                log.warning("[%s] 매수 게이트 차단: %s", symbol, exc)
                return (False, 0, current_price, None)

        resp = await client.place_order(  # type: ignore[attr-defined]
            OrderRequest(
                symbol=symbol,
                side=OrderSideEnum.BUY,
                price=0,
                quantity=quantity,
                order_type=OrderTypeEnum.MARKET,
            )
        )
        log.info(
            "[%s] 리밸런싱 매수 접수: %d주 x %s원 = %s원 (주문번호: %s)",
            symbol,
            quantity,
            f"{current_price:,}",
            f"{quantity * current_price:,}",
            resp.order_no,
        )
        return (True, quantity, current_price, resp.order_no)

    # ── _last_rebalance_date DB 영속화 (Codex follow-up) ────────────────────
    # strategy_config KV 테이블 재사용 (key=last_rebalance_date_cross_momentum)

    _LAST_REBAL_KEY = "last_rebalance_date_cross_momentum"

    async def _get_last_rebalance_date_db(self) -> date | None:
        """DB에서 마지막 리밸런스 일자 조회. 실패/없음 시 None."""
        try:
            import json

            from sqlalchemy import text

            from src.config.database import async_session_factory

            async with async_session_factory() as session:
                result = await session.execute(
                    text("SELECT value FROM strategy_config WHERE key = :k"),
                    {"k": self._LAST_REBAL_KEY},
                )
                row = result.first()
                if not row:
                    return None
                stored = row[0]
                if isinstance(stored, str):
                    stored = json.loads(stored)
                if isinstance(stored, str):
                    return date.fromisoformat(stored)
        except Exception as exc:
            log.warning("last_rebalance_date DB 조회 실패 (무시): %s", exc)
        return None

    async def _set_last_rebalance_date_db(self, today: date) -> None:
        """DB에 마지막 리밸런스 일자 upsert. 실패 무시 (운영 경로 보존)."""
        try:
            import json

            from sqlalchemy import text

            from src.config.database import async_session_factory

            async with async_session_factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO strategy_config "
                        "(id, key, value, description, updated_by, created_at, updated_at) "
                        "VALUES (gen_random_uuid(), :k, CAST(:v AS jsonb), :d, "
                        "'cross_momentum', NOW(), NOW()) "
                        "ON CONFLICT (key) DO UPDATE SET "
                        "value = EXCLUDED.value, updated_at = NOW()"
                    ),
                    {
                        "k": self._LAST_REBAL_KEY,
                        "v": json.dumps(today.isoformat()),
                        "d": "cross-momentum 마지막 리밸런스 일자 (ADR-022 중복 trigger 방지)",
                    },
                )
                await session.commit()
        except Exception as exc:
            log.warning("last_rebalance_date DB 저장 실패 (무시): %s", exc)

    async def _persist_rebalance(
        self,
        sold: dict[str, tuple[int, str | None]],
        bought: dict[str, tuple[int, int, str | None]],
    ) -> None:
        """리밸런싱 결과를 DB에 기록 (ADR-014 패턴, 실패 무시).

        broker_order_no가 None인 종목은 persist 스킵 + 경고 로그.
        cross_momentum은 시장가 주문이므로 order_type="market" 전달.

        Args:
            sold: 실제 매도 완료 종목 → (수량, 브로커 주문번호)
            bought: 실제 매수 완료 종목 → (수량, 발주 시점 현재가, 브로커 주문번호)
        """
        try:
            from src.config.database import async_session_factory
            from src.trading.live_order_persist import (
                get_is_mock,
                persist_order_submitted,
                resolve_live_trader_user_id,
            )

            persisted_sell = 0
            persisted_buy = 0

            async with async_session_factory() as session:
                user_id = await resolve_live_trader_user_id(session)
                is_mock = get_is_mock()

                for symbol, (qty, broker_order_no) in sold.items():
                    if broker_order_no is None:
                        log.error("[%s] broker_order_no 누락 — persist 스킵", symbol)
                        continue
                    await persist_order_submitted(
                        session,
                        symbol,
                        "SELL",
                        qty,
                        0,
                        broker_order_no,
                        "cross_momentum",
                        is_mock,
                        user_id,
                        order_type="market",
                    )
                    persisted_sell += 1
                for symbol, (qty, price, broker_order_no) in bought.items():
                    if broker_order_no is None:
                        log.error("[%s] broker_order_no 누락 — persist 스킵", symbol)
                        continue
                    await persist_order_submitted(
                        session,
                        symbol,
                        "BUY",
                        qty,
                        price,
                        broker_order_no,
                        "cross_momentum",
                        is_mock,
                        user_id,
                        order_type="market",
                    )
                    persisted_buy += 1
                await session.commit()
                log.info(
                    "리밸런싱 DB persist 완료 (매도 %d, 매수 %d)", persisted_sell, persisted_buy
                )
        except Exception as exc:
            log.error("리밸런싱 DB persist 실패 (무시): %s", exc)


# ── 스케줄러 훅 ──────────────────────────────────────────────────────────────


def _is_cross_momentum_enabled() -> bool:
    """ADR-024: ACTIVE_STRATEGY=cross_momentum 활성 여부."""
    from src.config.active_strategy import ActiveStrategy, get_active_strategy

    return get_active_strategy() == ActiveStrategy.CROSS_MOMENTUM


def _is_rebalance_trigger_date(today: date) -> bool:
    """오늘이 cross_momentum 리밸런스 trigger date인지 판정.

    env ``CROSS_MOMENTUM_REBALANCE_FREQ``:
      - ``monthly`` (디폴트): 매월 마지막 영업일
      - ``weekly``: 매주 금요일 (영업일 기준 — 5/15, 5/22 등)

    Args:
        today: KST date

    Returns:
        True이면 오늘 trigger.
    """
    from src.utils.krx_calendar import is_business_day, is_last_business_day_of_month

    freq = os.environ.get("CROSS_MOMENTUM_REBALANCE_FREQ", "monthly").strip().lower()
    if freq == "weekly":
        # 금요일(weekday=4) 영업일 = trigger
        # 금요일 휴장 시 직전 영업일(목요일)로 대체
        if today.weekday() == 4 and is_business_day(today):
            return True
        # 금요일이 휴장인 주: 목요일이 그 주의 마지막 영업일이면 trigger
        if today.weekday() == 3 and is_business_day(today):
            friday = today.replace(day=today.day) + timedelta(days=1)
            if not is_business_day(friday):
                return True
        return False
    # monthly mode (default)
    return is_last_business_day_of_month(today)


async def check_monthly_rebalance(
    adapter: CrossMomentumRebalanceAdapter,
    current_hhmm: str,
    today: date,
    client: object,
    current_holdings: dict[str, int],
    available_cash: int,
    t2_pending: list[T2PendingSettlement] | None = None,
) -> bool:
    """live_trader main loop에서 호출하는 리밸런싱 훅.

    조건:
      - ACTIVE_STRATEGY=cross_momentum (ADR-024)
      - current_hhmm == REBALANCE_ORDER_HHMM ("1455")
      - today가 trigger date (env CROSS_MOMENTUM_REBALANCE_FREQ 기준)
        - monthly (디폴트): 매월 마지막 영업일
        - weekly: 매주 금요일 영업일

    Args:
        adapter: CrossMomentumRebalanceAdapter 인스턴스
        current_hhmm: 현재 시각 (HHMM)
        today: 오늘 날짜 (KST date)
        client: KiwoomClient 인스턴스
        current_holdings: 현재 보유 종목코드 → 수량 매핑 (symbol → quantity)
        available_cash: 가용 현금 (원)
        t2_pending: T+2 미정산 항목 리스트 (실전 모드에서 전달)

    Returns:
        True이면 리밸런싱 실행됨.
    """
    if not _is_cross_momentum_enabled():
        return False

    if current_hhmm != REBALANCE_ORDER_HHMM:
        return False

    if not _is_rebalance_trigger_date(today):
        return False

    return await adapter.execute_monthly_rebalance(
        today, client, current_holdings, available_cash, t2_pending
    )
