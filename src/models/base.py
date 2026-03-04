"""SQLAlchemy 베이스 + 공통 Mixin."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """DeclarativeBase."""


class UUIDMixin:
    """UUID 기본키 Mixin."""

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """생성/수정 시각 Mixin."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
