"""AI 시그널 + LLM 호출 로그 모델."""

import uuid

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class AISignal(UUIDMixin, TimestampMixin, Base):
    """AI 매매 시그널."""

    __tablename__ = "ai_signals"

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

    # 시그널
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[str] = mapped_column(String(10))  # BUY, SELL, HOLD
    confidence: Mapped[float] = mapped_column(Float)
    target_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_size_pct: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(10), default="MEDIUM")

    # 분석 결과
    reasoning: Mapped[str] = mapped_column(Text, default="")
    raw_analysis: Mapped[dict] = mapped_column(JSON, default=dict)

    # 실행 여부
    is_executed: Mapped[bool] = mapped_column(default=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class LLMCallLog(UUIDMixin, TimestampMixin, Base):
    """LLM API 호출 로그 (비용 추적)."""

    __tablename__ = "llm_call_logs"

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

    # LLM 정보
    provider: Mapped[str] = mapped_column(String(20))  # openai, anthropic
    model: Mapped[str] = mapped_column(String(50))
    prompt_type: Mapped[str] = mapped_column(String(50))  # market_analysis, disclosure 등

    # 토큰/비용
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # 결과
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
