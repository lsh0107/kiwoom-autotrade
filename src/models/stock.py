"""종목 마스터 모델."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.news_article import NewsArticle
    from src.models.stock_relation import StockRelation
    from src.models.stock_universe import StockUniverse


class MarketCapTier(StrEnum):
    """시가총액 등급."""

    LARGE = "large"  # 1조+
    MID = "mid"  # 300억~1조
    SMALL = "small"  # 300억 미만


class Stock(UUIDMixin, TimestampMixin, Base):
    """종목 마스터 테이블.

    KRX 전체 종목 정보를 저장한다. symbol UNIQUE 제약.
    stock_universe, news_articles가 FK로 참조한다.
    """

    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        unique=True,
        index=True,
        comment="종목코드 6자리",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="종목명",
    )
    market: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="KOSPI",
        comment="KOSPI | KOSDAQ",
    )
    sector: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="기타",
        comment="섹터/테마",
    )
    theme: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="테마 (없으면 NULL)",
    )
    strategy_hint: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="momentum | mean_reversion",
    )
    market_cap_tier: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="large | mid | small",
    )
    dart_corp_code: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment="DART 고유번호 8자리",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="활성 여부",
    )

    # relationships
    universe_entries: Mapped[list[StockUniverse]] = relationship(
        "StockUniverse",
        back_populates="stock",
    )
    news_articles: Mapped[list[NewsArticle]] = relationship(
        "NewsArticle",
        back_populates="stock",
    )
    relations_from: Mapped[list[StockRelation]] = relationship(
        "StockRelation",
        foreign_keys="StockRelation.from_stock_id",
        back_populates="from_stock",
    )
    relations_to: Mapped[list[StockRelation]] = relationship(
        "StockRelation",
        foreign_keys="StockRelation.to_stock_id",
        back_populates="to_stock",
    )
