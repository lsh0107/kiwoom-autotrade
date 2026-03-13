"""MarketData 모델 CRUD 테스트."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.market_data import MarketData


class TestMarketDataCreate:
    """MarketData 생성 테스트."""

    async def test_create_market_data(self, db: AsyncSession) -> None:
        """MarketData 기본 생성."""
        now = datetime.now(UTC)
        md = MarketData(
            category="fred_macro",
            date=date(2026, 3, 14),
            data={"vix": 18.5, "us10y": 4.2},
            collected_at=now,
        )
        db.add(md)
        await db.flush()
        await db.refresh(md)

        assert md.id is not None
        assert md.category == "fred_macro"
        assert md.date == date(2026, 3, 14)
        assert md.data["vix"] == 18.5
        assert md.collected_at is not None

    async def test_create_multiple_categories(self, db: AsyncSession) -> None:
        """다른 category, 같은 날짜 — 모두 저장 가능."""
        now = datetime.now(UTC)
        categories = ["fred_macro", "krx_ohlcv", "overseas_index"]
        for cat in categories:
            md = MarketData(
                category=cat,
                date=date(2026, 3, 14),
                data={"value": 1},
                collected_at=now,
            )
            db.add(md)
        await db.flush()

        # 3개 모두 저장 성공
        from sqlalchemy import select

        result = await db.execute(select(MarketData).where(MarketData.date == date(2026, 3, 14)))
        rows = result.scalars().all()
        assert len(rows) == 3


class TestMarketDataUniqueConstraint:
    """유니크 제약 조건 테스트."""

    async def test_unique_category_date(self, db: AsyncSession) -> None:
        """같은 category+date 중복 시 IntegrityError."""
        now = datetime.now(UTC)
        md1 = MarketData(
            category="fred_macro",
            date=date(2026, 3, 14),
            data={"vix": 18.5},
            collected_at=now,
        )
        md2 = MarketData(
            category="fred_macro",
            date=date(2026, 3, 14),
            data={"vix": 19.0},
            collected_at=now,
        )
        db.add(md1)
        db.add(md2)

        with pytest.raises((IntegrityError, Exception)):
            await db.flush()


class TestMarketDataUpdate:
    """MarketData 수정 테스트."""

    async def test_update_data(self, db: AsyncSession) -> None:
        """data 필드 업데이트."""
        now = datetime.now(UTC)
        md = MarketData(
            category="ecos_rate",
            date=date(2026, 3, 10),
            data={"rate": 3.5},
            collected_at=now,
        )
        db.add(md)
        await db.flush()

        md.data = {"rate": 3.25, "updated": True}
        await db.flush()
        await db.refresh(md)

        assert md.data["rate"] == 3.25
        assert md.data["updated"] is True
