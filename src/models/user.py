"""사용자 + 초대 모델."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(enum.StrEnum):
    """사용자 역할."""

    ADMIN = "admin"
    USER = "user"


class User(UUIDMixin, TimestampMixin, Base):
    """사용자 모델."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
        server_default="user",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # 관계
    broker_credentials: Mapped[list["BrokerCredential"]] = relationship(  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )
    strategies: Mapped[list["Strategy"]] = relationship(  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )


class Invite(UUIDMixin, TimestampMixin, Base):
    """초대 코드 모델."""

    __tablename__ = "invites"

    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
    )
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
