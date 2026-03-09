"""브로커 자격증명 모델 (AES-256 암호화)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class BrokerCredential(UUIDMixin, TimestampMixin, Base):
    """키움증권 API 자격증명 (암호화 저장)."""

    __tablename__ = "broker_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    broker_name: Mapped[str] = mapped_column(String(50), default="kiwoom")

    # AES-256 암호화된 값
    encrypted_app_key: Mapped[str] = mapped_column(Text)
    encrypted_app_secret: Mapped[str] = mapped_column(Text)
    account_no: Mapped[str] = mapped_column(String(20))

    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # 토큰 캐시 (암호화된 access_token + 메타데이터)
    cached_token: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    token_type: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    token_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # 관계
    user: Mapped["User"] = relationship(back_populates="broker_credentials")  # noqa: F821
