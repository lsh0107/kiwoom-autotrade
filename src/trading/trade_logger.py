"""거래 감사 추적 로깅."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.trade_log import TradeLog

logger = structlog.get_logger(__name__)


async def log_trade_event(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    event_type: str,
    symbol: str = "",
    side: str = "",
    price: int = 0,
    quantity: int = 0,
    message: str = "",
    details: dict | None = None,
    order_id: uuid.UUID | None = None,
    strategy_id: uuid.UUID | None = None,
    is_mock: bool = True,
) -> TradeLog:
    """거래 이벤트를 DB에 기록."""
    trade_log = TradeLog(
        user_id=user_id,
        order_id=order_id,
        strategy_id=strategy_id,
        event_type=event_type,
        symbol=symbol,
        side=side,
        price=price,
        quantity=quantity,
        message=message,
        details=details or {},
        is_mock=is_mock,
    )
    db.add(trade_log)

    await logger.ainfo(
        "거래 이벤트",
        event_type=event_type,
        symbol=symbol,
        side=side,
        price=price,
        quantity=quantity,
        is_mock=is_mock,
        message=message,
    )

    return trade_log
