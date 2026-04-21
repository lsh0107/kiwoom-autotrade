"""DailyCandle 모델 테스트.

SQLite(인메모리) 기반. upsert는 SQLAlchemy Core의 DB 방언별 insert() 사용.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_candle import DailyCandle


class TestDailyCandleCreate:
    """DailyCandle 생성 테스트."""

    async def test_create_single(self, db: AsyncSession) -> None:
        """단일 row 생성."""
        candle = DailyCandle(
            symbol="005930",
            date=date(2026, 4, 21),
            open=70000,
            high=71500,
            low=69800,
            close=71000,
            volume=12_345_678,
            source="pykrx",
        )
        db.add(candle)
        await db.flush()

        fetched = (
            await db.execute(
                select(DailyCandle).where(
                    DailyCandle.symbol == "005930",
                    DailyCandle.date == date(2026, 4, 21),
                )
            )
        ).scalar_one()
        assert fetched.open == 70000
        assert fetched.close == 71000
        assert fetched.volume == 12_345_678
        assert fetched.source == "pykrx"
        assert fetched.created_at is not None

    async def test_create_multiple_symbols_same_date(self, db: AsyncSession) -> None:
        """같은 날짜, 다른 종목은 공존 가능."""
        for sym, close in [("005930", 71000), ("000660", 135000), ("035720", 48000)]:
            db.add(
                DailyCandle(
                    symbol=sym,
                    date=date(2026, 4, 21),
                    open=close - 500,
                    high=close + 500,
                    low=close - 1000,
                    close=close,
                    volume=1_000_000,
                )
            )
        await db.flush()

        rows = (
            (await db.execute(select(DailyCandle).where(DailyCandle.date == date(2026, 4, 21))))
            .scalars()
            .all()
        )
        assert len(rows) == 3


class TestDailyCandlePrimaryKey:
    """복합 PK (symbol, date) 제약 테스트."""

    async def test_duplicate_raises(self, db: AsyncSession) -> None:
        """같은 (symbol, date) 중복 insert 시 IntegrityError."""
        c1 = DailyCandle(
            symbol="005930",
            date=date(2026, 4, 21),
            open=70000,
            high=71000,
            low=69500,
            close=70500,
            volume=1_000_000,
        )
        db.add(c1)
        await db.flush()

        c2 = DailyCandle(
            symbol="005930",
            date=date(2026, 4, 21),
            open=70000,
            high=71000,
            low=69500,
            close=70500,
            volume=2_000_000,
        )
        db.add(c2)
        with pytest.raises(IntegrityError):
            await db.flush()


class TestDailyCandleUpsert:
    """Upsert 동작 — SQLite 방언의 INSERT ON CONFLICT DO UPDATE."""

    async def test_upsert_updates_existing(self, db: AsyncSession) -> None:
        """동일 PK 존재 시 source/close 값이 갱신된다."""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        payload = {
            "symbol": "005930",
            "date": date(2026, 4, 21),
            "open": 70000,
            "high": 71000,
            "low": 69500,
            "close": 70500,
            "volume": 1_000_000,
            "source": "pykrx",
        }
        stmt = sqlite_insert(DailyCandle).values(**payload)
        await db.execute(stmt)
        await db.flush()

        # 동일 PK로 덮어쓰기 (source/close 변경)
        payload_updated = {**payload, "close": 71200, "volume": 2_500_000, "source": "kiwoom"}
        stmt2 = sqlite_insert(DailyCandle).values(**payload_updated)
        stmt2 = stmt2.on_conflict_do_update(
            index_elements=["symbol", "date"],
            set_={
                "open": stmt2.excluded.open,
                "high": stmt2.excluded.high,
                "low": stmt2.excluded.low,
                "close": stmt2.excluded.close,
                "volume": stmt2.excluded.volume,
                "source": stmt2.excluded.source,
            },
        )
        await db.execute(stmt2)
        await db.flush()

        row = (
            await db.execute(
                select(DailyCandle).where(
                    DailyCandle.symbol == "005930",
                    DailyCandle.date == date(2026, 4, 21),
                )
            )
        ).scalar_one()
        assert row.close == 71200
        assert row.volume == 2_500_000
        assert row.source == "kiwoom"

    async def test_upsert_inserts_when_missing(self, db: AsyncSession) -> None:
        """존재하지 않는 PK는 일반 INSERT로 처리된다."""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(DailyCandle).values(
            symbol="000660",
            date=date(2026, 4, 21),
            open=135000,
            high=136500,
            low=134200,
            close=136000,
            volume=3_000_000,
            source="pykrx",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date"],
            set_={"close": stmt.excluded.close},
        )
        await db.execute(stmt)
        await db.flush()

        row = (
            await db.execute(select(DailyCandle).where(DailyCandle.symbol == "000660"))
        ).scalar_one()
        assert row.close == 136000


class TestDailyCandleQuery:
    """조회 패턴 테스트."""

    async def test_range_query_by_symbol(self, db: AsyncSession) -> None:
        """특정 종목의 날짜 범위 조회."""
        for day, close in [(15, 70000), (16, 70500), (17, 71000), (20, 71200), (21, 71500)]:
            db.add(
                DailyCandle(
                    symbol="005930",
                    date=date(2026, 4, day),
                    open=close - 500,
                    high=close + 300,
                    low=close - 800,
                    close=close,
                    volume=1_000_000,
                )
            )
        await db.flush()

        rows = (
            (
                await db.execute(
                    select(DailyCandle)
                    .where(
                        DailyCandle.symbol == "005930",
                        DailyCandle.date >= date(2026, 4, 16),
                        DailyCandle.date <= date(2026, 4, 20),
                    )
                    .order_by(DailyCandle.date.asc())
                )
            )
            .scalars()
            .all()
        )
        assert [r.date.day for r in rows] == [16, 17, 20]
        assert [r.close for r in rows] == [70500, 71000, 71200]
