"""DailyScreeningCache 모델 테스트.

SQLite(인메모리) 기반. upsert는 SQLAlchemy Core의 DB 방언별 insert() 사용.
(date, profile, symbol) 복합 PK 동작 검증.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_screening_cache import DailyScreeningCache


def _make_row(
    symbol: str = "005930",
    on_date: date = date(2026, 4, 21),
    profile: str = "momentum_breakout",
    *,
    passed: bool = True,
    rank: int = 1,
    close: int = 70000,
    high_52w: int = 72000,
    volume: int = 1_000_000,
    avg_volume: int = 500_000,
) -> DailyScreeningCache:
    return DailyScreeningCache(
        date=on_date,
        profile=profile,
        symbol=symbol,
        name=f"NAME_{symbol}",
        sector="반도체",
        hint="BO",
        rank=rank,
        passed=passed,
        price_ratio=close / high_52w,
        vol_ratio=volume / max(avg_volume, 1),
        bonus_score=0,
        close=close,
        high_52w=high_52w,
        volume=volume,
        avg_volume=avg_volume,
        threshold=0.95,
        volume_ratio_param=2.0,
        min_stocks_param=5,
        run_id="airflow_run_001",
    )


class TestDailyScreeningCacheCreate:
    """생성 동작."""

    async def test_create_single_passed(self, db: AsyncSession) -> None:
        db.add(_make_row())
        await db.flush()

        fetched = (
            await db.execute(
                select(DailyScreeningCache).where(
                    DailyScreeningCache.date == date(2026, 4, 21),
                    DailyScreeningCache.profile == "momentum_breakout",
                    DailyScreeningCache.symbol == "005930",
                )
            )
        ).scalar_one()
        assert fetched.passed is True
        assert fetched.rank == 1
        assert fetched.close == 70000
        assert fetched.high_52w == 72000
        assert fetched.run_id == "airflow_run_001"
        assert fetched.created_at is not None

    async def test_create_passed_and_failed_mix(self, db: AsyncSession) -> None:
        """통과/미통과 여러 종목 동시 저장."""
        db.add(_make_row(symbol="005930", passed=True, rank=1))
        db.add(_make_row(symbol="000660", passed=True, rank=2))
        db.add(_make_row(symbol="035720", passed=False, rank=0))
        await db.flush()

        rows = (
            (
                await db.execute(
                    select(DailyScreeningCache).where(DailyScreeningCache.date == date(2026, 4, 21))
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 3
        passed_rows = [r for r in rows if r.passed]
        assert len(passed_rows) == 2

    async def test_same_symbol_different_profile_coexists(self, db: AsyncSession) -> None:
        """같은 (date, symbol)이라도 profile이 다르면 별개 row."""
        db.add(_make_row(profile="momentum_breakout"))
        db.add(_make_row(profile="mean_reversion", rank=5))
        await db.flush()

        rows = (
            (
                await db.execute(
                    select(DailyScreeningCache).where(
                        DailyScreeningCache.date == date(2026, 4, 21),
                        DailyScreeningCache.symbol == "005930",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert {r.profile for r in rows} == {"momentum_breakout", "mean_reversion"}


class TestDailyScreeningCachePrimaryKey:
    """복합 PK (date, profile, symbol) 제약."""

    async def test_duplicate_raises(self, db: AsyncSession) -> None:
        db.add(_make_row())
        await db.flush()

        db.add(_make_row())
        with pytest.raises(IntegrityError):
            await db.flush()


class TestDailyScreeningCacheUpsert:
    """Upsert — SQLite 방언의 INSERT ON CONFLICT DO UPDATE."""

    async def test_upsert_updates_existing(self, db: AsyncSession) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        payload = {
            "date": date(2026, 4, 21),
            "profile": "momentum_breakout",
            "symbol": "005930",
            "name": "삼성전자",
            "sector": "반도체",
            "hint": "BO",
            "rank": 3,
            "passed": True,
            "price_ratio": 0.97,
            "vol_ratio": 2.5,
            "bonus_score": 1,
            "close": 70000,
            "high_52w": 72000,
            "volume": 1_000_000,
            "avg_volume": 500_000,
            "threshold": 0.95,
            "volume_ratio_param": 2.0,
            "min_stocks_param": 5,
            "run_id": "run_A",
        }
        await db.execute(sqlite_insert(DailyScreeningCache).values(**payload))
        await db.flush()

        payload_updated = {**payload, "rank": 1, "close": 71500, "run_id": "run_B"}
        stmt = sqlite_insert(DailyScreeningCache).values(**payload_updated)
        stmt = stmt.on_conflict_do_update(
            index_elements=["date", "profile", "symbol"],
            set_={
                "rank": stmt.excluded.rank,
                "close": stmt.excluded.close,
                "run_id": stmt.excluded.run_id,
            },
        )
        await db.execute(stmt)
        await db.flush()

        row = (
            await db.execute(
                select(DailyScreeningCache).where(
                    DailyScreeningCache.date == date(2026, 4, 21),
                    DailyScreeningCache.profile == "momentum_breakout",
                    DailyScreeningCache.symbol == "005930",
                )
            )
        ).scalar_one()
        assert row.rank == 1
        assert row.close == 71500
        assert row.run_id == "run_B"

    async def test_upsert_inserts_when_missing(self, db: AsyncSession) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(DailyScreeningCache).values(
            date=date(2026, 4, 21),
            profile="momentum_breakout",
            symbol="000660",
            name="SK하이닉스",
            sector="반도체",
            hint="MB",
            rank=2,
            passed=True,
            price_ratio=0.96,
            vol_ratio=1.8,
            bonus_score=0,
            close=135000,
            high_52w=140000,
            volume=3_000_000,
            avg_volume=1_500_000,
            threshold=0.95,
            volume_ratio_param=2.0,
            min_stocks_param=5,
            run_id="run_C",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date", "profile", "symbol"],
            set_={"close": stmt.excluded.close},
        )
        await db.execute(stmt)
        await db.flush()

        row = (
            await db.execute(
                select(DailyScreeningCache).where(DailyScreeningCache.symbol == "000660")
            )
        ).scalar_one()
        assert row.close == 135000


class TestDailyScreeningCacheQuery:
    """조회 패턴."""

    async def test_query_by_date_profile_passed(self, db: AsyncSession) -> None:
        """당일, 특정 프로파일, passed=True 를 rank 순으로."""
        db.add(_make_row(symbol="005930", passed=True, rank=1))
        db.add(_make_row(symbol="000660", passed=True, rank=2))
        db.add(_make_row(symbol="035720", passed=True, rank=3))
        db.add(_make_row(symbol="066570", passed=False, rank=0))
        await db.flush()

        rows = (
            (
                await db.execute(
                    select(DailyScreeningCache)
                    .where(
                        DailyScreeningCache.date == date(2026, 4, 21),
                        DailyScreeningCache.profile == "momentum_breakout",
                        DailyScreeningCache.passed.is_(True),
                    )
                    .order_by(DailyScreeningCache.rank.asc())
                )
            )
            .scalars()
            .all()
        )
        assert [r.symbol for r in rows] == ["005930", "000660", "035720"]

    async def test_query_different_dates_isolated(self, db: AsyncSession) -> None:
        """날짜별 분리."""
        db.add(_make_row(on_date=date(2026, 4, 20), symbol="005930"))
        db.add(_make_row(on_date=date(2026, 4, 21), symbol="005930"))
        await db.flush()

        rows_today = (
            (
                await db.execute(
                    select(DailyScreeningCache).where(DailyScreeningCache.date == date(2026, 4, 21))
                )
            )
            .scalars()
            .all()
        )
        assert len(rows_today) == 1
        assert rows_today[0].date == date(2026, 4, 21)
