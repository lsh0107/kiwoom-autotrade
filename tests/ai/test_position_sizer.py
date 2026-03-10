"""주문 수량 계산 테스트."""

from src.ai.analysis.models import TradingSignal
from src.ai.signal.position_sizer import (
    calc_atr,
    calc_dynamic_position_size,
    calculate_order_quantity,
)
from src.broker.schemas import DailyPrice
from src.trading.kill_switch import MAX_ORDER_AMOUNT


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
