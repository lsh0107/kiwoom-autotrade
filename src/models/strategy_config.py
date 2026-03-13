"""전략 파라미터 설정 모델."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class StrategyConfig(UUIDMixin, TimestampMixin, Base):
    """전략 파라미터 key-value 테이블.

    key는 유니크 — 파라미터 1개 = 1행.
    value는 JSONB — 숫자/문자열/리스트 모두 저장 가능.
    updated_by: "system" | "user" | "llm"
    """

    __tablename__ = "strategy_config"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="파라미터 키 (예: atr_stop_mult)",
    )
    value: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="파라미터 값 (JSONB — 숫자/문자열/리스트 가능)",
    )
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
        comment="파라미터 설명",
    )
    updated_by: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="system",
        comment="최종 수정 주체: system | user | llm",
    )


class StrategyConfigSuggestion(UUIDMixin, TimestampMixin, Base):
    """LLM이 제안한 전략 파라미터 변경 제안 테이블.

    status: "pending" → "approved" | "rejected"
    승인 시 StrategyConfig.value 업데이트 필요.
    """

    __tablename__ = "strategy_config_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    config_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="strategy_config.key 참조 (FK 없이 soft reference)",
    )
    current_value: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="제안 당시 현재 값",
    )
    suggested_value: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="제안된 새 값",
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="LLM 제안 근거",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="제안 출처: postmarket_review | param_tuner",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | approved | rejected",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="검토 시각",
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="검토자 (user_id 또는 시스템 식별자)",
    )
