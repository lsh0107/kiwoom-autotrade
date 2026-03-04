"""주문 API 라우터."""

import uuid

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.order import Order, OrderSide, OrderStatus
from src.models.user import User
from src.trading.order_service import cancel_order, create_order, get_user_orders
from src.utils.exceptions import NotFoundError

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/orders", tags=["주문"])


# ── 스키마 ────────────────────────────────────────────


class CreateOrderRequest(BaseModel):
    """주문 생성 요청."""

    symbol: str = Field(min_length=1, max_length=20)
    symbol_name: str = Field(default="", max_length=100)
    side: OrderSide
    price: int = Field(gt=0)
    quantity: int = Field(gt=0)
    strategy_id: uuid.UUID | None = None
    reason: str | None = None


class OrderResponse(BaseModel):
    """주문 응답."""

    id: uuid.UUID
    symbol: str
    symbol_name: str
    side: OrderSide
    price: int
    quantity: int
    filled_quantity: int
    filled_price: int
    status: OrderStatus
    broker_order_no: str | None
    is_mock: bool
    reason: str | None
    error_message: str | None
    created_at: str
    submitted_at: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_order(cls, order: Order) -> "OrderResponse":
        """Order 모델 → 응답."""
        return cls(
            id=order.id,
            symbol=order.symbol,
            symbol_name=order.symbol_name,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            filled_price=order.filled_price,
            status=order.status,
            broker_order_no=order.broker_order_no,
            is_mock=order.is_mock,
            reason=order.reason,
            error_message=order.error_message,
            created_at=order.created_at.isoformat() if order.created_at else "",
            submitted_at=order.submitted_at.isoformat() if order.submitted_at else None,
        )


# ── 엔드포인트 ────────────────────────────────────────


@router.post("", response_model=OrderResponse)
async def create_order_endpoint(
    req: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderResponse:
    """주문 생성 (Kill Switch 검증 포함)."""
    from src.config.settings import get_settings

    settings = get_settings()

    order = await create_order(
        db=db,
        user_id=user.id,
        symbol=req.symbol,
        symbol_name=req.symbol_name,
        side=req.side,
        price=req.price,
        quantity=req.quantity,
        strategy_id=req.strategy_id,
        reason=req.reason,
        is_mock=settings.is_mock_trading,
        check_market_hours=False,  # MVP에서는 시간 제한 완화
    )

    return OrderResponse.from_order(order)


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: OrderStatus | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OrderResponse]:
    """주문 목록 조회."""
    orders = await get_user_orders(db=db, user_id=user.id, status=status, limit=limit)
    return [OrderResponse.from_order(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderResponse:
    """주문 상세 조회."""
    order = await db.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise NotFoundError("주문")
    return OrderResponse.from_order(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order_endpoint(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderResponse:
    """주문 취소."""
    order = await cancel_order(db=db, order_id=order_id, user_id=user.id)
    return OrderResponse.from_order(order)
