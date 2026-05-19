"""전략 런타임 토글 + budget 분리 모델 (design-025)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class StrategyRuntime(Base):
    """전략별 런타임 토글 + 자산 한도.

    cross_momentum / short_swing / multi_regime 등 각 전략을 DB 기반으로
    enabled on/off + budget_pct + max_order_amount 제어한다.

    env ACTIVE_STRATEGY 단일 토글 (ADR-024) 의 후속 — 다중 전략 동시 운영
    + 즉시 스위칭 지원.
    """

    __tablename__ = "strategy_runtime"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    strategy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="전략 식별자 (cross_momentum / short_swing / multi_regime)",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="활성 여부. orchestrator 가 매 tick 마다 조회",
    )

    budget_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("0"),
        comment="전략별 자산 비율 (0.0~1.0). 합이 1.0 초과 불가",
    )

    max_order_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1_000_000,
        comment="1회 주문 최대 금액 (원). risk gate 에 주입",
    )

    max_daily_orders: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="일일 주문 최대 횟수. risk gate 에 주입",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    updated_by: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="변경 주체 (user_id / 'migration_021' / 'api' 등)",
    )
