"""종목 유니버스 모델 — Pool A/B 분리."""

import uuid
from enum import StrEnum

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class StockPool(StrEnum):
    """종목 풀 구분."""

    POOL_A = "pool_a"  # 모멘텀 — KOSPI 시총 TOP 50
    POOL_B = "pool_b"  # 평균회귀 — 중형주 200~500위


class StockUniverse(UUIDMixin, TimestampMixin, Base):
    """종목 유니버스 테이블.

    pool_a: 모멘텀 전략 대상 (시총 상위 대형주)
    pool_b: 평균회귀 전략 대상 (중형주)
    (symbol, pool) unique 제약 — 같은 종목이 두 풀에 동시 존재 가능.
    """

    __tablename__ = "stock_universe"
    __table_args__ = (UniqueConstraint("symbol", "pool", name="uq_stock_universe_symbol_pool"),)

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    pool: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="pool_a (모멘텀) | pool_b (평균회귀)",
    )
    symbol: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="종목코드 6자리",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="종목명",
    )
    sector: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="기타",
        comment="섹터/테마 (반도체, 2차전지 등)",
    )
    market: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="KOSPI",
        comment="KOSPI | KOSDAQ",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="활성 여부 — False이면 매매 대상 제외",
    )
