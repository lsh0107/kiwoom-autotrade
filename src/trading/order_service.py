"""주문 생성/제출/취소 서비스."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import OrderResponse
from src.models.order import Order, OrderSide, OrderStatus
from src.models.strategy import Strategy
from src.trading.kill_switch import run_all_checks
from src.trading.order_state import validate_transition
from src.trading.trade_logger import log_trade_event
from src.utils.exceptions import NotFoundError
from src.utils.time import now_kst

logger = structlog.get_logger(__name__)


async def create_order(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
    symbol_name: str,
    side: OrderSide,
    price: int,
    quantity: int,
    strategy_id: uuid.UUID | None = None,
    reason: str | None = None,
    is_mock: bool = True,
    prev_close: int | None = None,
    check_market_hours: bool = True,
) -> Order:
    """주문 생성 (Kill Switch 검증 포함)."""
    # 전략별 설정 로드
    max_investment = 1_000_000
    current_invested = 0
    strategy_pnl_pct = 0.0
    max_loss_pct = -3.0

    if strategy_id:
        strategy = await db.get(Strategy, strategy_id)
        if strategy:
            max_investment = strategy.max_investment
            max_loss_pct = strategy.max_loss_pct

    # Kill Switch 3단계 검증
    await run_all_checks(
        user_id=user_id,
        symbol=symbol,
        side=side.value,
        price=price,
        quantity=quantity,
        db=db,
        prev_close=prev_close,
        max_investment=max_investment,
        current_invested=current_invested,
        strategy_pnl_pct=strategy_pnl_pct,
        max_loss_pct=max_loss_pct,
        check_market_hours=check_market_hours,
    )

    # 주문 생성
    order = Order(
        user_id=user_id,
        strategy_id=strategy_id,
        symbol=symbol,
        symbol_name=symbol_name,
        side=side,
        price=price,
        quantity=quantity,
        is_mock=is_mock,
        reason=reason,
    )
    db.add(order)
    await db.flush()

    # 감사 로그
    await log_trade_event(
        db=db,
        user_id=user_id,
        event_type="order_created",
        symbol=symbol,
        side=side.value,
        price=price,
        quantity=quantity,
        message=f"주문 생성: {symbol} {side.value} {quantity}주 @ {price:,}원",
        order_id=order.id,
        strategy_id=strategy_id,
        is_mock=is_mock,
    )

    await logger.ainfo(
        "주문 생성",
        order_id=str(order.id),
        symbol=symbol,
        side=side.value,
        price=price,
        quantity=quantity,
    )

    return order


async def submit_order(
    *,
    db: AsyncSession,
    order: Order,
    broker_response: OrderResponse,
) -> Order:
    """주문 제출 결과 반영."""
    if broker_response.status == "submitted":
        validate_transition(order.status, OrderStatus.SUBMITTED)
        order.status = OrderStatus.SUBMITTED
        order.broker_order_no = broker_response.order_no
        order.submitted_at = now_kst()
    else:
        validate_transition(order.status, OrderStatus.FAILED)
        order.status = OrderStatus.FAILED
        order.error_message = broker_response.message

    await log_trade_event(
        db=db,
        user_id=order.user_id,
        event_type="order_submitted" if order.status == OrderStatus.SUBMITTED else "order_failed",
        symbol=order.symbol,
        side=order.side.value,
        price=order.price,
        quantity=order.quantity,
        message=(
            f"주문 {'제출' if order.status == OrderStatus.SUBMITTED else '실패'}"
            f": {broker_response.message}"
        ),
        order_id=order.id,
        is_mock=order.is_mock,
        details={"broker_order_no": broker_response.order_no},
    )

    return order


async def cancel_order(
    *,
    db: AsyncSession,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Order:
    """주문 취소."""
    order = await db.get(Order, order_id)
    if not order or order.user_id != user_id:
        raise NotFoundError("주문")

    validate_transition(order.status, OrderStatus.CANCELLED)
    order.status = OrderStatus.CANCELLED

    await log_trade_event(
        db=db,
        user_id=user_id,
        event_type="order_cancelled",
        symbol=order.symbol,
        side=order.side.value,
        price=order.price,
        quantity=order.quantity,
        message=f"주문 취소: {order.symbol}",
        order_id=order.id,
        is_mock=order.is_mock,
    )

    return order


async def get_user_orders(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    status: OrderStatus | None = None,
    limit: int = 50,
) -> list[Order]:
    """사용자 주문 목록 조회."""
    query = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    if status:
        query = query.where(Order.status == status)
    query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())
