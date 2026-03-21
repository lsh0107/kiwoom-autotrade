"""종목 연관관계 모델."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.stock import Stock


class RelationType(StrEnum):
    """종목 연관관계 유형."""

    SECTOR_PEER = "sector_peer"  # 같은 섹터
    THEME_PEER = "theme_peer"  # 같은 테마
    PRICE_CORRELATION = "price_correlation"  # 가격 상관관계
    SUPPLY_CHAIN = "supply_chain"  # 공급망 관계


class StockRelation(UUIDMixin, Base):
    """종목 간 연관관계 테이블.

    (from_stock_id, to_stock_id, relation_type) UNIQUE 제약.
    방향성 있음 — A→B와 B→A 별도 저장.
    """

    __tablename__ = "stock_relations"
    __table_args__ = (
        UniqueConstraint(
            "from_stock_id",
            "to_stock_id",
            "relation_type",
            name="uq_stock_relation",
        ),
    )

    from_stock_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="출발 종목",
    )
    to_stock_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="도착 종목",
    )
    relation_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="sector_peer | theme_peer | price_correlation | supply_chain",
    )
    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="관계 강도 (상관계수 등)",
    )
    period_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="상관관계 계산 기간(일)",
    )
    source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="pykrx_correlation | manual | dart | seed",
    )
    valid_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="유효 시작일",
    )
    valid_until: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="유효 종료일 (NULL = 현재 유효)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    from_stock: Mapped[Stock] = relationship(
        "Stock",
        foreign_keys=[from_stock_id],
        back_populates="relations_from",
    )
    to_stock: Mapped[Stock] = relationship(
        "Stock",
        foreign_keys=[to_stock_id],
        back_populates="relations_to",
    )
