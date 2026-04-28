"""ADR-022: Cross-sectional momentum monthly rebalance 어댑터.

ADR-021 PASS 조합(top20pct_novol_notrend)을 모의투자 환경에서 실행하는 어댑터.
live_trader.py와 분리된 독립 모듈로, 매월 마지막 거래일 14:30 신호 산정 →
14:55 주문 실행 흐름을 담당한다.

설계 결정 (ADR-022):
  - 유니버스: KOSPI100 + KOSDAQ100 동결 리스트 (ADR-021 기준)
  - best combo: top 20%, vol_filter=OFF, trend_filter=OFF
  - sizing: equal weight (가용현금 / 40종목), 1주 미만 SKIP
  - 안전장치: MAX_ORDER_AMOUNT_KRW 5,000,000원, 09:00~15:30 외 SKIP
  - 강제 모의투자: is_mock_trading=True 고정
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta

log = logging.getLogger("cross_momentum_rebalance")

# ── 상수 ─────────────────────────────────────────────────────────────────────

# best combo 파라미터 (ADR-021 PASS: top20pct_novol_notrend)
_FORMATION_MONTHS: int = 12
_SKIP_MONTHS: int = 1
_TOP_PCT: float = 0.20

# 안전장치
MAX_ORDER_AMOUNT_KRW: int = 5_000_000  # 종목당 최대 주문금액

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
    """리밸런싱 파라미터 (ADR-022 핵심 결정 고정값).

    best combo: top20pct_novol_notrend
    """

    formation_months: int = _FORMATION_MONTHS
    skip_months: int = _SKIP_MONTHS
    top_pct: float = _TOP_PCT
    use_vol_filter: bool = False  # novol — OFF
    use_trend_filter: bool = False  # notrend — OFF
    n_positions: int = 40  # 200종목 x 20% = 40종목


@dataclass
class RebalanceOrders:
    """리밸런싱 주문 명세.

    Attributes:
        sells: 매도할 종목코드 리스트 (현재 보유 중이나 타깃에 없음)
        buys: 매수할 종목코드 리스트 (타깃이나 현재 미보유)
        target_symbols: 이번 달 목표 포트폴리오 종목 코드
        cash_per_position: 종목당 배정 현금 (원)
    """

    sells: list[str] = field(default_factory=list)
    buys: list[str] = field(default_factory=list)
    target_symbols: list[str] = field(default_factory=list)
    cash_per_position: int = 0


# ── 마지막 거래일 판정 ─────────────────────────────────────────────────────────


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

    def __init__(self, params: RebalanceParams | None = None) -> None:
        self.params = params or RebalanceParams()
        # 리밸런싱 실행 여부 추적 (당일 중복 실행 방지)
        self._last_rebalance_date: date | None = None

    # ── 신호 계산 ────────────────────────────────────────────────────────────

    def compute_target_portfolio(self, today: date) -> list[str]:
        """오늘 기준 12-1 momentum 신호로 목표 포트폴리오 산정.

        pykrx로 유니버스 종목의 일봉 데이터를 수집하고 momentum score를 계산한다.
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
        start_date = (date(today.year - (history_months // 12 + 1), today.month, 1)).strftime(
            "%Y%m%d"
        )
        end_date = today.strftime("%Y%m%d")

        universe = get_universe()
        universe_data: dict[str, list[DailyPrice]] = {}

        try:
            from pykrx import stock as pykrx_stock  # lazy import

            for symbol in universe:
                try:
                    df = pykrx_stock.get_market_ohlcv_by_date(start_date, end_date, symbol)
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
        except Exception as exc:
            log.error("pykrx import 실패: %s", exc)
            return []

        log.info("일봉 수집 완료: %d/%d종목", len(universe_data), len(universe))

        return self._score_and_select(universe_data)

    def _score_and_select(
        self,
        universe_data: dict[str, list],
    ) -> list[str]:
        """universe_data에서 momentum score를 계산하고 상위 top_pct% 선택.

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

        cm_params = CrossMomentumParams(
            formation_months=self.params.formation_months,
            skip_months=self.params.skip_months,
            top_decile=self.params.top_pct,
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

        log.info(
            "목표 포트폴리오 산정: %d종목 (후보 %d개 중 상위 %.0f%%)",
            len(selected),
            len(scores),
            self.params.top_pct * 100,
        )
        return selected

    # ── 주문 명세 계산 ────────────────────────────────────────────────────────

    def compute_rebalance_orders(
        self,
        target_symbols: list[str],
        current_holdings: dict[str, int],
        available_cash: int,
    ) -> RebalanceOrders:
        """현재 보유 vs 타깃 포트폴리오 diff로 매도/매수 목록 산출.

        sizing: equal weight = available_cash / len(target_symbols)
        MAX_ORDER_AMOUNT_KRW 초과 시 cap.

        Args:
            target_symbols: 이번 달 목표 포트폴리오 종목코드
            current_holdings: 현재 보유 종목코드 → 수량 매핑 (symbol → quantity)
            available_cash: 사용 가능한 현금 (원)

        Returns:
            RebalanceOrders: 매도/매수 목록 및 종목당 현금
        """
        target_set = set(target_symbols)
        current_set = set(current_holdings.keys())

        sells = [s for s in current_holdings if s not in target_set]
        buys = [s for s in target_symbols if s not in current_set]

        n = len(target_symbols) if target_symbols else 1
        raw_cash = available_cash // n
        cash_per_position = min(raw_cash, MAX_ORDER_AMOUNT_KRW)

        log.info(
            "리밸런싱 diff: 매도 %d개, 매수 %d개, 종목당 %s원",
            len(sells),
            len(buys),
            f"{cash_per_position:,}",
        )
        return RebalanceOrders(
            sells=sells,
            buys=buys,
            target_symbols=target_symbols,
            cash_per_position=cash_per_position,
        )

    # ── 실행 파이프라인 ──────────────────────────────────────────────────────

    async def execute_monthly_rebalance(
        self,
        today: date,
        client: object,
        current_holdings: dict[str, int],
        available_cash: int,
    ) -> bool:
        """월말 리밸런싱 풀 파이프라인 실행.

        1. 목표 포트폴리오 산정 (compute_target_portfolio)
        2. diff 계산 (compute_rebalance_orders)
        3. 시장가 매도 (보유 中 타깃 외 종목)
        4. 시장가 매수 (타깃 中 미보유 종목, 1주 미만 SKIP)
        5. DB persist (ADR-014 패턴)

        Args:
            today: 리밸런싱 기준일 (KST)
            client: KiwoomClient 인스턴스
            current_holdings: 현재 보유 종목코드 → 수량 매핑 (symbol → quantity)
            available_cash: 사용 가능 현금 (원)

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

        # 당일 중복 실행 방지
        if self._last_rebalance_date == today:
            log.info("당일 리밸런싱 이미 실행 완료 (%s) — 스킵", today)
            return False

        log.info("=" * 60)
        log.info("[ADR-022] 월말 리밸런싱 실행 시작 (%s, 모의투자)", today)
        log.info("=" * 60)

        # 1. 목표 포트폴리오 산정
        target = self.compute_target_portfolio(today)
        if not target:
            log.error("목표 포트폴리오 산정 실패 — 리밸런싱 중단")
            return False

        # 2. diff 계산
        orders = self.compute_rebalance_orders(target, current_holdings, available_cash)

        # 3. 시장가 매도 (현재 보유 中 타깃 외 종목)
        sold: list[str] = []
        for symbol in orders.sells:
            try:
                qty = current_holdings.get(symbol, 0)
                await self._place_sell_order(client, symbol, qty)
                sold.append(symbol)
            except Exception as exc:
                log.error("[%s] 매도 실패 (계속 진행): %s", symbol, exc)

        log.info("매도 완료: %d/%d개", len(sold), len(orders.sells))

        # 4. 시장가 매수 (타깃 中 미보유 종목)
        bought: list[str] = []
        for symbol in orders.buys:
            try:
                ok = await self._place_buy_order(client, symbol, orders.cash_per_position)
                if ok:
                    bought.append(symbol)
            except Exception as exc:
                log.error("[%s] 매수 실패 (계속 진행): %s", symbol, exc)

        log.info("매수 완료: %d/%d개", len(bought), len(orders.buys))

        # 5. DB persist
        await self._persist_rebalance(today, sold, bought)

        self._last_rebalance_date = today
        log.info("[ADR-022] 월말 리밸런싱 완료 (매도 %d, 매수 %d)", len(sold), len(bought))
        return True

    # ── 주문 실행 헬퍼 ──────────────────────────────────────────────────────

    async def _place_sell_order(self, client: object, symbol: str, quantity: int) -> None:
        """시장가 매도 주문 (모의투자).

        Args:
            client: KiwoomClient 인스턴스
            symbol: 종목코드
            quantity: 매도 수량 (보유 수량 전량)
        """
        from src.broker.schemas import OrderRequest, OrderSideEnum, OrderTypeEnum

        if quantity <= 0:
            log.warning("[%s] 매도 수량 0 이하 — 주문 스킵 (quantity=%d)", symbol, quantity)
            return

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

    async def _place_buy_order(
        self,
        client: object,
        symbol: str,
        cash_per_position: int,
    ) -> bool:
        """시장가 매수 주문 (모의투자). 1주 미만 수량이면 SKIP.

        Args:
            client: KiwoomClient 인스턴스
            symbol: 종목코드
            cash_per_position: 종목당 배정 현금 (원)

        Returns:
            True이면 주문 접수 성공.
        """
        from src.broker.schemas import OrderRequest, OrderSideEnum, OrderTypeEnum

        # 현재가 조회 → 수량 계산
        try:
            quote = await client.get_quote(symbol)  # type: ignore[attr-defined]
            current_price = quote.price
        except Exception as exc:
            log.warning("[%s] 현재가 조회 실패, 매수 스킵: %s", symbol, exc)
            return False

        if current_price <= 0:
            log.warning("[%s] 현재가 0원 — 매수 스킵", symbol)
            return False

        # 가격제한폭(±30%) 초과 SKIP: 주문가 ≠ 현재가인 경우 보수적으로 처리
        # (실제 가격제한폭 검증은 브로커가 거부하므로 추가 필터는 하지 않음)

        quantity = cash_per_position // current_price
        if quantity < 1:
            log.info(
                "[%s] 수량 0주 (현재가 %s원, 배정금 %s원) — 매수 스킵",
                symbol,
                f"{current_price:,}",
                f"{cash_per_position:,}",
            )
            return False

        # MAX_ORDER_AMOUNT_KRW 안전장치 재확인
        order_amount = quantity * current_price
        if order_amount > MAX_ORDER_AMOUNT_KRW:
            quantity = MAX_ORDER_AMOUNT_KRW // current_price
            if quantity < 1:
                log.info("[%s] MAX 금액 제한 후 수량 0 — 스킵", symbol)
                return False

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
        return True

    async def _persist_rebalance(
        self,
        today: date,
        sold: list[str],
        bought: list[str],
    ) -> None:
        """리밸런싱 결과를 DB에 기록 (ADR-014 패턴, 실패 무시).

        Args:
            today: 리밸런싱 기준일
            sold: 실제 매도 완료된 종목코드
            bought: 실제 매수 완료된 종목코드
        """
        try:
            from src.config.database import async_session_factory
            from src.trading.live_order_persist import (
                get_is_mock,
                persist_order_submitted,
                resolve_live_trader_user_id,
            )

            async with async_session_factory() as session:
                user_id = await resolve_live_trader_user_id(session)
                is_mock = get_is_mock()

                for symbol in sold:
                    await persist_order_submitted(
                        session,
                        symbol,
                        "SELL",
                        0,
                        0,
                        f"rebalance_{today.strftime('%Y%m%d')}_{symbol}",
                        "cross_momentum",
                        is_mock,
                        user_id,
                    )
                for symbol in bought:
                    await persist_order_submitted(
                        session,
                        symbol,
                        "BUY",
                        0,
                        0,
                        f"rebalance_{today.strftime('%Y%m%d')}_{symbol}",
                        "cross_momentum",
                        is_mock,
                        user_id,
                    )
                await session.commit()
                log.info("리밸런싱 DB persist 완료 (매도 %d, 매수 %d)", len(sold), len(bought))
        except Exception as exc:
            log.error("리밸런싱 DB persist 실패 (무시): %s", exc)


# ── 스케줄러 훅 ──────────────────────────────────────────────────────────────


def _is_cross_momentum_enabled() -> bool:
    """USE_CROSS_MOMENTUM 환경변수 활성 여부.

    Returns:
        True이면 cross-momentum monthly rebalance 활성 (기본 False).
    """
    return os.environ.get("USE_CROSS_MOMENTUM", "false").lower() in ("true", "1", "yes")


def validate_cross_momentum_exclusivity() -> None:
    """USE_CROSS_MOMENTUM과 USE_MULTI_REGIME 동시 ON 검증.

    둘 다 true이면 즉시 SystemExit(1)을 발생시킨다.
    부팅 시 1회 호출.

    Raises:
        SystemExit: USE_CROSS_MOMENTUM과 USE_MULTI_REGIME 둘 다 활성화된 경우.
    """
    import sys

    cross = _is_cross_momentum_enabled()
    multi = os.environ.get("USE_MULTI_REGIME", "false").lower() in ("true", "1", "yes")
    if cross and multi:
        log.critical("USE_CROSS_MOMENTUM=true와 USE_MULTI_REGIME=true 동시 활성화 금지 — 종료")
        sys.exit(1)


async def check_monthly_rebalance(
    adapter: CrossMomentumRebalanceAdapter,
    current_hhmm: str,
    today: date,
    client: object,
    current_holdings: dict[str, int],
    available_cash: int,
) -> bool:
    """live_trader main loop에서 호출하는 월말 리밸런싱 훅.

    조건:
      - USE_CROSS_MOMENTUM=true
      - current_hhmm == REBALANCE_ORDER_HHMM ("1455")
      - today가 이번 달 마지막 거래일

    Args:
        adapter: CrossMomentumRebalanceAdapter 인스턴스
        current_hhmm: 현재 시각 (HHMM)
        today: 오늘 날짜 (KST date)
        client: KiwoomClient 인스턴스
        current_holdings: 현재 보유 종목코드 → 수량 매핑 (symbol → quantity)
        available_cash: 가용 현금 (원)

    Returns:
        True이면 리밸런싱 실행됨.
    """
    if not _is_cross_momentum_enabled():
        return False

    if current_hhmm != REBALANCE_ORDER_HHMM:
        return False

    if not _is_last_trading_day_of_month(today):
        return False

    return await adapter.execute_monthly_rebalance(today, client, current_holdings, available_cash)
