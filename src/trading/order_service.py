"""주문 생성/제출/취소 서비스."""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import BrokerOrderResponse
from src.models.order import Order, OrderSide, OrderStatus
from src.models.strategy import Strategy
from src.trading.drawdown_guard import run_all_checks
from src.trading.order_state import validate_transition
from src.trading.trade_logger import log_trade_event
from src.utils.exceptions import NotFoundError
from src.utils.time import now_kst

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CreateOrderParams:
    """주문 생성 비즈니스 매개변수."""

    user_id: uuid.UUID
    symbol: str
    symbol_name: str
    side: OrderSide
    price: int
    quantity: int
    strategy_id: uuid.UUID | None = None
    reason: str | None = None
    is_mock: bool = True
    prev_close: int | None = None
    check_market_hours: bool = True


async def create_order(
    *,
    db: AsyncSession,
    params: CreateOrderParams,
) -> Order:
    """주문 생성 (Kill Switch 검증 포함)."""
    # 전략별 설정 로드
    max_investment = 1_000_000
    strategy_pnl_pct = 0.0
    max_loss_pct = -3.0

    if params.strategy_id:
        strategy = await db.get(Strategy, params.strategy_id)
        if strategy:
            max_investment = strategy.max_investment
            max_loss_pct = strategy.max_loss_pct

    # 현재 투자금 계산 — 미체결/체결 주문 총액 합산
    from sqlalchemy import func as sa_func

    invested_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Order.price * Order.quantity), 0)).where(
            Order.user_id == params.user_id,
            Order.status.in_(["submitted", "accepted", "partial_fill", "filled"]),
            *([Order.strategy_id == params.strategy_id] if params.strategy_id else []),
        )
    )
    current_invested = int(invested_result.scalar() or 0)

    # Kill Switch 3단계 검증
    await run_all_checks(
        user_id=params.user_id,
        symbol=params.symbol,
        side=params.side.value,
        price=params.price,
        quantity=params.quantity,
        db=db,
        prev_close=params.prev_close,
        max_investment=max_investment,
        current_invested=current_invested,
        strategy_pnl_pct=strategy_pnl_pct,
        max_loss_pct=max_loss_pct,
        check_market_hours=params.check_market_hours,
    )

    # 주문 생성
    order = Order(
        user_id=params.user_id,
        strategy_id=params.strategy_id,
        symbol=params.symbol,
        symbol_name=params.symbol_name,
        side=params.side,
        price=params.price,
        quantity=params.quantity,
        is_mock=params.is_mock,
        reason=params.reason,
    )
    db.add(order)
    await db.flush()

    # 감사 로그
    await log_trade_event(
        db=db,
        user_id=params.user_id,
        event_type="order_created",
        symbol=params.symbol,
        side=params.side.value,
        price=params.price,
        quantity=params.quantity,
        message=(
            f"주문 생성: {params.symbol} {params.side.value}"
            f" {params.quantity}주 @ {params.price:,}원"
        ),
        order_id=order.id,
        strategy_id=params.strategy_id,
        is_mock=params.is_mock,
    )

    await logger.ainfo(
        "주문 생성",
        order_id=str(order.id),
        symbol=params.symbol,
        side=params.side.value,
        price=params.price,
        quantity=params.quantity,
    )

    return order


async def submit_order(
    *,
    db: AsyncSession,
    order: Order,
    broker_response: BrokerOrderResponse,
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
