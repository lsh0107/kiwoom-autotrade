"""주문 수량 계산 테스트."""

from src.ai.analysis.models import TradingSignal
from src.ai.signal.position_sizer import (
    StrategyBudget,
    calc_atr,
    calc_dynamic_position_size,
    calculate_order_quantity,
)
from src.broker.schemas import DailyPrice
from src.trading.drawdown_guard import MAX_ORDER_AMOUNT


def _make_daily(prices: list[tuple[int, int, int, int]]) -> list[DailyPrice]:
    """(open, high, low, close) 리스트로 DailyPrice 생성 헬퍼."""
    return [
        DailyPrice(
            date=f"20260{i + 1:02d}01",
            open=o,
            high=h,
            low=lo,
            close=c,
            volume=100_000,
        )
        for i, (o, h, lo, c) in enumerate(prices)
    ]


class TestCalculateOrderQuantity:
    """calculate_order_quantity 함수 테스트."""

    def _make_buy_signal(
        self,
        confidence: float = 0.8,
        position_size_pct: float = 0.1,
    ) -> TradingSignal:
        """매수 시그널 생성 헬퍼."""
        return TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=confidence,
            position_size_pct=position_size_pct,
        )

    def test_basic_calculation(self) -> None:
        """기본 수량 계산 (가용현금 기반)."""
        signal = self._make_buy_signal(position_size_pct=0.1)
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=10_000_000,
            current_price=50_000,
        )
        # target_amount = 10_000_000 * 0.1 = 1_000_000
        # 1_000_000 // 50_000 = 20
        assert qty == 20

    def test_portfolio_based_calculation(self) -> None:
        """포트폴리오 가치 기반 수량 계산."""
        signal = self._make_buy_signal(position_size_pct=0.05)
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=5_000_000,
            current_price=50_000,
            total_portfolio_value=20_000_000,
        )
        # target_amount = 20_000_000 * 0.05 = 1_000_000
        # 1_000_000 // 50_000 = 20
        assert qty == 20

    def test_max_order_amount_limit(self) -> None:
        """MAX_ORDER_AMOUNT 제한 적용."""
        signal = self._make_buy_signal(position_size_pct=0.5)
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=50_000_000,  # 매우 큰 가용현금
            current_price=10_000,
        )
        # target_amount = 50_000_000 * 0.5 = 25_000_000 → MAX_ORDER_AMOUNT(1_000_000)로 제한
        # 1_000_000 // 10_000 = 100
        assert qty == MAX_ORDER_AMOUNT // 10_000

    def test_available_cash_limit(self) -> None:
        """가용 현금 제한 적용."""
        signal = self._make_buy_signal(position_size_pct=0.5)
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=500_000,  # 적은 가용현금
            current_price=10_000,
        )
        # target_amount = 500_000 * 0.5 = 250_000 → available_cash(500_000)보다 적으므로 OK
        # 250_000 // 10_000 = 25
        assert qty == 25

    def test_portfolio_position_pct_limit(self) -> None:
        """포트폴리오 비중 제한 적용."""
        signal = self._make_buy_signal(position_size_pct=0.5)
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=5_000_000,
            current_price=10_000,
            total_portfolio_value=1_000_000,
            max_position_pct=10.0,  # 10%
        )
        # target_amount = 1_000_000 * 0.5 = 500_000
        # max_amount(비중 제한) = 1_000_000 * 10 / 100 = 100_000
        # 최종 target_amount = min(500_000, MAX_ORDER_AMOUNT, 5_000_000, 100_000) = 100_000
        # 100_000 // 10_000 = 10
        assert qty == 10

    def test_zero_quantity_when_price_too_high(self) -> None:
        """가격이 가용현금보다 높으면 수량 0."""
        signal = self._make_buy_signal(position_size_pct=0.1)
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=100_000,
            current_price=500_000,
        )
        # target_amount = 100_000 * 0.1 = 10_000
        # 10_000 // 500_000 = 0
        assert qty == 0

    def test_sell_signal_returns_zero(self) -> None:
        """매도 시그널은 수량 0 반환."""
        signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.8,
            position_size_pct=0.1,
        )
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=10_000_000,
            current_price=50_000,
        )
        assert qty == 0

    def test_hold_signal_returns_zero(self) -> None:
        """HOLD 시그널은 수량 0 반환."""
        signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=0.5,
        )
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=10_000_000,
            current_price=50_000,
        )
        assert qty == 0

    def test_zero_price_returns_zero(self) -> None:
        """현재가가 0이면 수량 0 반환."""
        signal = self._make_buy_signal()
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=10_000_000,
            current_price=0,
        )
        assert qty == 0

    def test_position_size_pct_zero(self) -> None:
        """position_size_pct가 0이면 수량 0."""
        signal = self._make_buy_signal(position_size_pct=0.0)
        qty = calculate_order_quantity(
            signal=signal,
            available_cash=10_000_000,
            current_price=50_000,
        )
        assert qty == 0


class TestCalcAtr:
    """ATR 계산 테스트."""

    def test_empty_data_returns_zero(self) -> None:
        """데이터 없으면 0."""
        assert calc_atr([]) == 0.0

    def test_single_candle_returns_zero(self) -> None:
        """캔들 1개면 0."""
        daily = _make_daily([(10000, 11000, 9000, 10500)])
        assert calc_atr(daily) == 0.0

    def test_basic_atr_calculation(self) -> None:
        """기본 ATR 계산."""
        # 5일치: tr = high-low = 1000 (전일종가 차이 무시하는 단순 케이스)
        daily = _make_daily(
            [
                (10000, 11000, 10000, 10500),  # 1일
                (10500, 11500, 10500, 11000),  # 2일: tr=max(1000, 500, 500)=1000
                (11000, 12000, 11000, 11500),  # 3일
                (11500, 12500, 11500, 12000),  # 4일
                (12000, 13000, 12000, 12500),  # 5일
            ]
        )
        atr = calc_atr(daily, period=4)
        assert atr == 1000.0

    def test_atr_uses_true_range(self) -> None:
        """TR = max(H-L, |H-prev_C|, |L-prev_C|) 정확히 계산."""
        # 갭 있는 케이스: prev_close=10000, curr high=9500, low=8500
        daily = _make_daily(
            [
                (10000, 10000, 10000, 10000),
                (8500, 9500, 8500, 9000),  # TR = max(1000, |9500-10000|, |8500-10000|) = 1500
            ]
        )
        atr = calc_atr(daily, period=1)
        assert atr == 1500.0

    def test_period_clips_to_available_data(self) -> None:
        """데이터가 period보다 적으면 전체 사용."""
        daily = _make_daily(
            [
                (10000, 11000, 9000, 10000),
                (10000, 11000, 9000, 10000),  # TR=2000
            ]
        )
        # period=20 지정해도 데이터 1개로 계산
        atr = calc_atr(daily, period=20)
        assert atr == 2000.0


class TestCalcDynamicPositionSize:
    """동적 포지션 사이징 테스트."""

    def _daily_with_atr(self, atr_value: int, n: int = 21) -> list[DailyPrice]:
        """ATR이 atr_value인 일봉 데이터 생성."""
        # 매 캔들: high-low = atr_value, 갭 없음
        base = 50000
        return _make_daily([(base, base + atr_value, base, base)] * n)

    def test_zero_price_returns_zero(self) -> None:
        """가격 0이면 0."""
        assert calc_dynamic_position_size(price=0, daily=[], account_balance=10_000_000) == 0

    def test_zero_balance_returns_zero(self) -> None:
        """잔고 0이면 0."""
        assert calc_dynamic_position_size(price=50000, daily=[], account_balance=0) == 0

    def test_no_atr_data_fallback(self) -> None:
        """ATR 데이터 없으면 고정 사이징 폴백 (최소 1주)."""
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=[],
            account_balance=10_000_000,
        )
        assert qty >= 1

    def test_atr_based_quantity(self) -> None:
        """ATR 기반 수량 계산 확인 (ATR이 최대 한도보다 구속적인 경우)."""
        # ATR=5000, price=50_000, account=10_000_000
        # risk_amount = 10_000_000 * 0.02 = 200_000
        # quantity = 200_000 / (5000 * 2) = 20
        # max_qty = 10_000_000 * 0.15 / 50_000 = 30
        # Result: min(20, 30) = 20  ← ATR 제약이 binding
        daily = self._daily_with_atr(5000)
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
        )
        assert qty == 20

    def test_max_position_pct_caps_quantity(self) -> None:
        """최대 포지션 비율로 수량 제한."""
        # ATR=100 → 큰 수량 계산 → 15% 상한으로 제한
        # max_qty = 10_000_000 * 0.15 / 50_000 = 30
        daily = self._daily_with_atr(100)
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
            max_position_pct=0.15,
        )
        assert qty == 30

    def test_scale_factor_reduces_quantity(self) -> None:
        """scale_factor=0.5 적용 시 수량 50% 감소."""
        daily = self._daily_with_atr(1000)
        qty_normal = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
            scale_factor=1.0,
        )
        qty_scaled = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
            scale_factor=0.5,
        )
        assert qty_scaled == qty_normal // 2

    def test_minimum_quantity_is_1(self) -> None:
        """최소 수량은 1주."""
        # ATR이 매우 크면 계산 수량이 0 → 최소 1로 보정
        daily = self._daily_with_atr(100_000_000)
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
        )
        assert qty >= 1


class TestStrategyBudget:
    """전략별 자금 버킷 테스트."""

    def test_strategy_budget_reset(self) -> None:
        """reset 후 상태 확인."""

        budget = StrategyBudget()
        budget.reset(10_000_000)
        assert budget.total_balance == 10_000_000
        assert budget.used("momentum") == 0
        assert budget.used("mean_reversion") == 0

    def test_strategy_budget_allocate_release(self) -> None:
        """할당/해제 정상 동작."""

        budget = StrategyBudget()
        budget.reset(10_000_000)

        # momentum 예산: 10_000_000 * 0.4 = 4_000_000
        assert budget.allocate("momentum", 1_000_000) is True
        assert budget.used("momentum") == 1_000_000
        assert budget.available("momentum") == 3_000_000

        budget.release("momentum", 500_000)
        assert budget.used("momentum") == 500_000
        assert budget.available("momentum") == 3_500_000

    def test_strategy_budget_allocate_exceed(self) -> None:
        """가용액 초과 할당 시 False 반환."""

        budget = StrategyBudget()
        budget.reset(10_000_000)

        # momentum 예산: 4_000_000 → 초과 할당 시도
        assert budget.allocate("momentum", 5_000_000) is False
        assert budget.used("momentum") == 0  # 변경 없음

    def test_strategy_budget_available(self) -> None:
        """가용 금액 계산 정확성."""

        budget = StrategyBudget()
        budget.reset(10_000_000)

        # momentum: 40% = 4_000_000
        assert budget.budget_for("momentum") == 4_000_000
        assert budget.available("momentum") == 4_000_000

        # mean_reversion: 60% = 6_000_000
        assert budget.budget_for("mean_reversion") == 6_000_000
        assert budget.available("mean_reversion") == 6_000_000

        # 할당 후 가용액 감소
        budget.allocate("momentum", 2_000_000)
        assert budget.available("momentum") == 2_000_000

    def test_strategy_budget_unknown_strategy(self) -> None:
        """알려지지 않은 전략은 예산 0."""

        budget = StrategyBudget()
        budget.reset(10_000_000)

        assert budget.budget_for("unknown") == 0
        assert budget.available("unknown") == 0
        assert budget.allocate("unknown", 100) is False

    def test_strategy_budget_summary(self) -> None:
        """summary 메서드 확인."""

        budget = StrategyBudget()
        budget.reset(10_000_000)
        budget.allocate("momentum", 1_000_000)

        s = budget.summary()
        assert s["momentum"]["budget"] == 4_000_000
        assert s["momentum"]["used"] == 1_000_000
        assert s["momentum"]["available"] == 3_000_000
        assert s["mean_reversion"]["budget"] == 6_000_000
        assert s["mean_reversion"]["used"] == 0


class TestCalcDynamicPositionSizeWithBudget:
    """버킷 적용 동적 포지션 사이징 테스트."""

    def _daily_with_atr(self, atr_value: int, n: int = 21) -> list[DailyPrice]:
        """ATR이 atr_value인 일봉 데이터 생성."""
        base = 50000
        return _make_daily([(base, base + atr_value, base, base)] * n)

    def test_calc_position_size_with_budget(self) -> None:
        """버킷 적용 시 전략 가용 예산 기준으로 계산."""

        budget = StrategyBudget()
        budget.reset(10_000_000)
        # momentum 가용: 4_000_000

        # ATR=5000, price=50_000, effective_balance=4_000_000
        # risk_amount=80_000, qty=80_000/(5000*2)=8, max_qty=8 → 8
        daily = self._daily_with_atr(5000)
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
            strategy="momentum",
            budget=budget,
        )
        assert qty == 8

    def test_calc_position_size_without_budget(self) -> None:
        """budget=None이면 기존 로직 (하위호환)."""
        daily = self._daily_with_atr(5000)
        # budget 없이 호출 — 기존 동작과 동일해야 함
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
        )
        # risk_amount = 10_000_000 * 0.02 = 200_000
        # quantity = 200_000 / (5000 * 2) = 20
        assert qty == 20

    def test_budget_exhausted_returns_zero(self) -> None:
        """전략 예산 소진 시 0 반환."""

        budget = StrategyBudget()
        budget.reset(10_000_000)
        budget.allocate("momentum", 4_000_000)  # 전액 사용

        daily = self._daily_with_atr(5000)
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
            strategy="momentum",
            budget=budget,
        )
        assert qty == 0

    def test_budget_caps_order_amount(self) -> None:
        """계산된 주문 금액이 가용액 초과 시 축소."""

        budget = StrategyBudget()
        budget.reset(10_000_000)
        budget.allocate("momentum", 3_500_000)  # 가용: 500_000

        # ATR=100 → 큰 수량 → 가용액 범위로 제한
        daily = self._daily_with_atr(100)
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
            strategy="momentum",
            budget=budget,
        )
        # 가용 500_000 / 50_000 = 10주가 한도
        assert qty <= 500_000 // 50_000

    def test_mean_reversion_uses_own_budget(self) -> None:
        """mean_reversion 전략은 자체 예산 사용."""

        budget = StrategyBudget()
        budget.reset(10_000_000)
        # mean_reversion 가용: 6_000_000

        daily = self._daily_with_atr(5000)
        qty = calc_dynamic_position_size(
            price=50_000,
            daily=daily,
            account_balance=10_000_000,
            strategy="mean_reversion",
            budget=budget,
        )
        # effective_balance=6_000_000, risk_amount=120_000
        # qty=120_000/(5000*2)=12, max_qty=12 → 12
        assert qty == 12
