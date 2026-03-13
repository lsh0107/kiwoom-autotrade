"""시장 데이터 모델."""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, String, UniqueConstraint
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class MarketData(UUIDMixin, TimestampMixin, Base):
    """수집된 시장 데이터 통합 모델.

    category별로 다른 형태의 데이터를 JSONB로 저장한다.
    (category, date) 조합은 유니크 — 같은 날 같은 종류 데이터는 1건.
    """

    __tablename__ = "market_data"

    __table_args__ = (UniqueConstraint("category", "date", name="uq_market_data_category_date"),)

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="dart_disclosure / fred_macro / overseas_index / ecos_rate / krx_ohlcv 등",
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="수집 대상 날짜",
    )
    data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="수집된 데이터 (구조는 category마다 상이)",
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="실제 수집 시각",
    )
