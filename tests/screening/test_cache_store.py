"""DailyScreeningCacheStore 테스트 (SQLite in-memory).

비동기 engine에 직접 엔진을 주입해 sessionmaker 생성 → upsert/query 검증.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from src.models.base import Base
from src.screening.cache_store import DailyScreeningCacheStore, result_to_row


@pytest.fixture
async def async_engine():  # type: ignore[no-untyped-def]
    """테이블이 준비된 async engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def _params(threshold: float = 0.95, vr: float = 2.0, ms: int = 5) -> dict:
    return {
        "threshold": threshold,
        "volume_ratio_param": vr,
        "min_stocks_param": ms,
    }


class TestUpsertAndFetch:
    async def test_upsert_inserts_new_rows(self, async_engine) -> None:  # type: ignore[no-untyped-def]
        store = DailyScreeningCacheStore(async_engine=async_engine)
        rows = [
            result_to_row(
                {
                    "close": 70000,
                    "high_52w": 72000,
                    "price_ratio": 0.972,
                    "vol_ratio": 3.0,
                    "volume": 1_000_000,
                    "avg_volume": 330_000,
                    "bonus_score": 2,
                    "passed": True,
                    "rank": 1,
                },
                on_date=date(2026, 4, 21),
                profile="momentum_breakout",
                symbol="005930",
                name="삼성전자",
                sector="반도체",
                hint="BO",
                run_id="airflow_run_1",
                **_params(),
            ),
            result_to_row(
                {
                    "close": 130000,
                    "high_52w": 140000,
                    "price_ratio": 0.928,
                    "vol_ratio": 2.1,
                    "volume": 900_000,
                    "avg_volume": 430_000,
                    "bonus_score": 1,
                    "passed": True,
                    "rank": 2,
                },
                on_date=date(2026, 4, 21),
                profile="momentum_breakout",
                symbol="000660",
                name="SK하이닉스",
                sector="반도체",
                hint="BO",
                run_id="airflow_run_1",
                **_params(),
            ),
        ]
        n = await store.upsert_many(rows)
        assert n == 2

        passed = await store.fetch_passed(date(2026, 4, 21))
        assert [r.symbol for r in passed] == ["005930", "000660"]
        assert passed[0].rank == 1
        assert passed[0].run_id == "airflow_run_1"

    async def test_upsert_overwrites_existing(self, async_engine) -> None:  # type: ignore[no-untyped-def]
        store = DailyScreeningCacheStore(async_engine=async_engine)
        base_row = result_to_row(
            {
                "close": 70000,
                "high_52w": 72000,
                "price_ratio": 0.972,
                "vol_ratio": 3.0,
                "volume": 1_000_000,
                "avg_volume": 330_000,
                "bonus_score": 2,
                "passed": True,
                "rank": 5,
            },
            on_date=date(2026, 4, 21),
            profile="momentum_breakout",
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            hint="BO",
            run_id="run_A",
            **_params(),
        )
        await store.upsert_many([base_row])

        # 재실행 — rank/run_id 갱신
        updated = {**base_row, "rank": 1, "run_id": "run_B"}
        await store.upsert_many([updated])

        passed = await store.fetch_passed(date(2026, 4, 21))
        assert len(passed) == 1
        assert passed[0].rank == 1
        assert passed[0].run_id == "run_B"

    async def test_fetch_passed_filters_by_profile_and_passed(
        self,
        async_engine,  # type: ignore[no-untyped-def]
    ) -> None:
        store = DailyScreeningCacheStore(async_engine=async_engine)
        rows = [
            result_to_row(
                {
                    "close": 70000,
                    "high_52w": 72000,
                    "price_ratio": 0.97,
                    "vol_ratio": 3.0,
                    "bonus_score": 0,
                    "passed": True,
                    "rank": 1,
                },
                on_date=date(2026, 4, 21),
                profile="momentum_breakout",
                symbol="005930",
                name="삼성전자",
                sector="반도체",
                hint="BO",
                **_params(),
            ),
            # 미통과: 조회에서 제외
            result_to_row(
                {
                    "close": 50000,
                    "high_52w": 80000,
                    "price_ratio": 0.62,
                    "vol_ratio": 0.5,
                    "bonus_score": 0,
                    "passed": False,
                    "rank": 0,
                },
                on_date=date(2026, 4, 21),
                profile="momentum_breakout",
                symbol="035720",
                name="카카오",
                sector="IT",
                hint="BO",
                **_params(),
            ),
            # 다른 프로파일
            result_to_row(
                {
                    "close": 70000,
                    "high_52w": 72000,
                    "price_ratio": 0.97,
                    "vol_ratio": 3.0,
                    "bonus_score": 0,
                    "passed": True,
                    "rank": 1,
                },
                on_date=date(2026, 4, 21),
                profile="mean_reversion",
                symbol="005930",
                name="삼성전자",
                sector="반도체",
                hint="MR",
                **_params(),
            ),
        ]
        await store.upsert_many(rows)

        passed = await store.fetch_passed(date(2026, 4, 21), profile="momentum_breakout")
        assert [r.symbol for r in passed] == ["005930"]

        all_rows = await store.fetch_all_for_date(date(2026, 4, 21), profile="momentum_breakout")
        assert len(all_rows) == 2  # 005930(passed) + 035720(not passed)

    async def test_upsert_empty_returns_zero(self, async_engine) -> None:  # type: ignore[no-untyped-def]
        store = DailyScreeningCacheStore(async_engine=async_engine)
        assert await store.upsert_many([]) == 0


class TestResultToRow:
    """result_to_row 변환 — 파라미터 스냅샷 포함."""

    def test_result_dict_to_row_with_params(self) -> None:
        row = result_to_row(
            {
                "close": 70000,
                "high_52w": 72000,
                "price_ratio": 0.972,
                "vol_ratio": 3.1,
                "volume": 1_000_000,
                "avg_volume": 300_000,
                "bonus_score": 3,
                "passed": True,
                "rank": 1,
            },
            on_date=date(2026, 4, 21),
            profile="momentum_breakout",
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            hint="BO",
            threshold=0.95,
            volume_ratio_param=2.0,
            min_stocks_param=5,
            run_id="airflow_abc",
        )
        assert row["date"] == date(2026, 4, 21)
        assert row["symbol"] == "005930"
        assert row["threshold"] == 0.95
        assert row["volume_ratio_param"] == 2.0
        assert row["min_stocks_param"] == 5
        assert row["run_id"] == "airflow_abc"
        assert row["rank"] == 1
        assert row["passed"] is True
