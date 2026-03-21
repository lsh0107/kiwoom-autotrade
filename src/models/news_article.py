"""뉴스 기사 모델."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.stock import Stock


class NewsArticle(UUIDMixin, TimestampMixin, Base):
    """뉴스 기사 + 감성 분석 결과 모델.

    동일 URL은 1건만 저장 (unique constraint).
    sentiment_score: -1.0(부정) ~ 1.0(긍정).
    """

    __tablename__ = "news_articles"

    __table_args__ = (UniqueConstraint("url", name="uq_news_articles_url"),)

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    keyword: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="검색 키워드 (종목명 등)",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sentiment: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="neutral",
        comment="positive / negative / neutral",
    )
    sentiment_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="-1.0(부정) ~ 1.0(긍정)",
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="기사 발행 시각",
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="수집 시각",
    )
    stock_id: Mapped[uuid.UUID | None] = mapped_column(
        SA_Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="종목 FK — keyword로 매핑되면 채워짐",
    )
    stock: Mapped[Stock | None] = relationship("Stock", back_populates="news_articles")
