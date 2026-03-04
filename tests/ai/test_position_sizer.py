"""주문 수량 계산 테스트."""

from src.ai.analysis.models import TradingSignal
from src.ai.signal.position_sizer import calculate_order_quantity
from src.trading.kill_switch import MAX_ORDER_AMOUNT


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
