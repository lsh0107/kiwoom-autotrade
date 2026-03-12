"""TradingSignal → OrderRequest 변환."""

import structlog

from src.ai.analysis.models import TradingSignal
from src.ai.signal.position_sizer import calculate_order_quantity
from src.broker.schemas import OrderRequest

logger = structlog.get_logger(__name__)


def build_buy_order(
    *,
    signal: TradingSignal,
    available_cash: int,
    current_price: int,
    max_position_pct: float = 30.0,
    total_portfolio_value: int = 0,
) -> OrderRequest | None:
    """매수 시그널 → 주문 요청."""
    quantity = calculate_order_quantity(
        signal=signal,
        available_cash=available_cash,
        current_price=current_price,
        max_position_pct=max_position_pct,
        total_portfolio_value=total_portfolio_value,
    )

    if quantity <= 0:
        return None

    # 지정가: 시그널 target_price 또는 현재가
    price = signal.target_price or current_price

    return OrderRequest(
        symbol=signal.symbol,
        side="buy",
        price=price,
        quantity=quantity,
        order_type="limit",
    )


def build_sell_order(
    *,
    signal: TradingSignal,
    holding_quantity: int,
    current_price: int,
) -> OrderRequest | None:
    """매도 시그널 → 주문 요청."""
    if holding_quantity <= 0:
        return None

    # 전량 매도
    price = signal.target_price or current_price

    return OrderRequest(
        symbol=signal.symbol,
        side="sell",
        price=price,
        quantity=holding_quantity,
        order_type="limit",
    )
