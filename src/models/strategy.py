"""전략 모델."""

import enum
import uuid

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class StrategyStatus(enum.StrEnum):
    """전략 상태."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class Strategy(UUIDMixin, TimestampMixin, Base):
    """투자 전략 모델."""

    __tablename__ = "strategies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")

    # 전략 설정
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    symbols: Mapped[list] = mapped_column(JSON, default=list)

    # 상태
    status: Mapped[StrategyStatus] = mapped_column(
        Enum(StrategyStatus),
        default=StrategyStatus.STOPPED,
    )
    is_auto_trading: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # 리스크 설정
    max_investment: Mapped[int] = mapped_column(Integer, default=1_000_000)
    max_loss_pct: Mapped[float] = mapped_column(Float, default=-3.0)
    max_position_pct: Mapped[float] = mapped_column(Float, default=30.0)

    # Kill Switch
    kill_switch_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # 관계
    user: Mapped["User"] = relationship(back_populates="strategies")  # noqa: F821
