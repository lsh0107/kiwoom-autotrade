"""주문 수량 계산."""

import structlog

from src.ai.analysis.models import TradingSignal
from src.trading.kill_switch import MAX_ORDER_AMOUNT

logger = structlog.get_logger(__name__)


def calculate_order_quantity(
    *,
    signal: TradingSignal,
    available_cash: int,
    current_price: int,
    max_position_pct: float = 30.0,
    total_portfolio_value: int = 0,
) -> int:
    """매수 수량 계산."""
    if signal.action != "BUY" or current_price <= 0:
        return 0

    # 1. 시그널의 포지션 비중 기반 금액
    if total_portfolio_value > 0:
        target_amount = int(total_portfolio_value * signal.position_size_pct)
    else:
        target_amount = int(available_cash * signal.position_size_pct)

    # 2. 최대 주문 금액 제한
    target_amount = min(target_amount, MAX_ORDER_AMOUNT)

    # 3. 가용 현금 제한
    target_amount = min(target_amount, available_cash)

    # 4. 포트폴리오 비중 제한
    if total_portfolio_value > 0:
        max_amount = int(total_portfolio_value * max_position_pct / 100)
        target_amount = min(target_amount, max_amount)

    # 5. 수량 계산 (내림)
    quantity = target_amount // current_price

    if quantity <= 0:
        logger.warning(
            "계산된 수량이 0",
            symbol=signal.symbol,
            target_amount=target_amount,
            current_price=current_price,
        )

    return quantity
