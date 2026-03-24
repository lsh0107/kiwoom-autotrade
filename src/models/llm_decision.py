"""LLM 투자 결정 모델 — 결정 추적 + 피드백 루프."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class LLMDecision(UUIDMixin, TimestampMixin, Base):
    """LLM 투자 결정 추적 테이블.

    status 플로우: pending → approved → applied → evaluated
    """

    __tablename__ = "llm_decisions"

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    decision_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="weight_adjust, risk_mode, param_tune, stock_swap",
    )
    context_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="overnight, premarket, postmarket",
    )
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        Index("ix_llm_decisions_date_type", "date", "decision_type"),
        Index("ix_llm_decisions_status", "status"),
    )
