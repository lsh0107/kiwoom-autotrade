"""주문 빌더 테스트."""

from src.ai.analysis.models import TradingSignal
from src.ai.signal.order_builder import build_buy_order, build_sell_order
from src.broker.schemas import OrderRequest


class TestBuildBuyOrder:
    """build_buy_order 함수 테스트."""

    def test_normal_buy_order(self) -> None:
        """정상 매수 주문 생성."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.8,
            target_price=70000,
            position_size_pct=0.1,
        )
        order = build_buy_order(
            signal=signal,
            available_cash=10_000_000,
            current_price=70000,
        )

        assert order is not None
        assert isinstance(order, OrderRequest)
        assert order.symbol == "005930"
        assert order.side == "buy"
        assert order.price == 70000  # target_price 사용
        assert order.quantity > 0
        assert order.order_type == "limit"

    def test_buy_order_uses_current_price_when_no_target(self) -> None:
        """target_price 없으면 현재가 사용."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.8,
            target_price=None,
            position_size_pct=0.1,
        )
        order = build_buy_order(
            signal=signal,
            available_cash=10_000_000,
            current_price=65000,
        )

        assert order is not None
        assert order.price == 65000

    def test_buy_order_zero_quantity_returns_none(self) -> None:
        """수량이 0이면 None 반환."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.8,
            position_size_pct=0.01,  # 매우 작은 비중
        )
        order = build_buy_order(
            signal=signal,
            available_cash=100_000,
            current_price=500_000,  # 가용현금보다 비쌈
        )

        assert order is None

    def test_buy_order_with_portfolio_value(self) -> None:
        """포트폴리오 가치 기반 매수 주문."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.85,
            position_size_pct=0.1,
        )
        order = build_buy_order(
            signal=signal,
            available_cash=5_000_000,
            current_price=50000,
            total_portfolio_value=10_000_000,
        )

        assert order is not None
        assert order.quantity > 0


class TestBuildSellOrder:
    """build_sell_order 함수 테스트."""

    def test_normal_sell_order(self) -> None:
        """정상 매도 주문 생성."""
        signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.75,
            target_price=72000,
        )
        order = build_sell_order(
            signal=signal,
            holding_quantity=10,
            current_price=70000,
        )

        assert order is not None
        assert isinstance(order, OrderRequest)
        assert order.symbol == "005930"
        assert order.side == "sell"
        assert order.price == 72000  # target_price 사용
        assert order.quantity == 10  # 전량 매도
        assert order.order_type == "limit"

    def test_sell_order_uses_current_price_when_no_target(self) -> None:
        """target_price 없으면 현재가 사용."""
        signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.7,
            target_price=None,
        )
        order = build_sell_order(
            signal=signal,
            holding_quantity=5,
            current_price=68000,
        )

        assert order is not None
        assert order.price == 68000

    def test_sell_order_zero_holding_returns_none(self) -> None:
        """보유수량이 0이면 None 반환."""
        signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.8,
        )
        order = build_sell_order(
            signal=signal,
            holding_quantity=0,
            current_price=70000,
        )

        assert order is None

    def test_sell_order_negative_holding_returns_none(self) -> None:
        """보유수량이 음수이면 None 반환."""
        signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.8,
        )
        order = build_sell_order(
            signal=signal,
            holding_quantity=-5,
            current_price=70000,
        )

        assert order is None
