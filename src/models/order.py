"""주문 모델 + 상태 enum."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    """주문 상태."""

    CREATED = "created"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class OrderSide(str, enum.Enum):
    """매수/매도."""

    BUY = "buy"
    SELL = "sell"


class Order(UUIDMixin, TimestampMixin, Base):
    """주문 모델."""

    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 종목 정보
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    symbol_name: Mapped[str] = mapped_column(String(100), default="")

    # 주문 정보
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide))
    order_type: Mapped[str] = mapped_column(String(20), default="limit")
    price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    filled_price: Mapped[int] = mapped_column(Integer, default=0)

    # 상태
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.CREATED,
        index=True,
    )

    # 브로커 정보
    broker_order_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_mock: Mapped[bool] = mapped_column(default=True)

    # 메타
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
