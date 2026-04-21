"""DailyScreeningCache upsert/query 저장소.

Airflow DAG가 대량 upsert, live_trader가 단건 조회에 사용한다.
SQLite/PostgreSQL 양쪽 방언 지원 (ON CONFLICT DO UPDATE).
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from src.models.daily_screening_cache import DailyScreeningCache

log = logging.getLogger(__name__)

# upsert 시 PK(`date`, `profile`, `symbol`) 제외한 업데이트 대상 컬럼
_UPDATE_COLUMNS: tuple[str, ...] = (
    "name",
    "sector",
    "hint",
    "rank",
    "passed",
    "price_ratio",
    "vol_ratio",
    "bonus_score",
    "close",
    "high_52w",
    "volume",
    "avg_volume",
    "threshold",
    "volume_ratio_param",
    "min_stocks_param",
    "run_id",
)


class DailyScreeningCacheStore:
    """DailyScreeningCache 접근 래퍼.

    비동기/동기 세션 양쪽 지원. Airflow operator(동기)와
    process_manager(비동기) 양쪽에서 쓰기 위함.
    """

    def __init__(
        self,
        async_engine: AsyncEngine | None = None,
        sync_engine: Engine | None = None,
    ) -> None:
        self._async_session_factory: async_sessionmaker[AsyncSession] | None = None
        self._sync_session_factory: sessionmaker[Session] | None = None
        if async_engine is not None:
            self._async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
        if sync_engine is not None:
            self._sync_session_factory = sessionmaker(sync_engine, expire_on_commit=False)

    # ── 내부 유틸 ───────────────────────────────────

    @staticmethod
    def _build_upsert_stmt(rows: list[dict[str, Any]], dialect_name: str) -> Any:
        """방언에 따라 ON CONFLICT DO UPDATE 문 구성.

        PostgreSQL / SQLite(테스트) 모두 `on_conflict_do_update` API를 제공한다.
        """
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            pg_stmt = pg_insert(DailyScreeningCache).values(rows)
            return pg_stmt.on_conflict_do_update(
                index_elements=["date", "profile", "symbol"],
                set_={c: getattr(pg_stmt.excluded, c) for c in _UPDATE_COLUMNS},
            )

        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        sqlite_stmt = sqlite_insert(DailyScreeningCache).values(rows)
        return sqlite_stmt.on_conflict_do_update(
            index_elements=["date", "profile", "symbol"],
            set_={c: getattr(sqlite_stmt.excluded, c) for c in _UPDATE_COLUMNS},
        )

    # ── 동기 API (Airflow 오퍼레이터용) ──────────────

    def upsert_many_sync(self, rows: list[dict[str, Any]]) -> int:
        """동기 세션으로 upsert. insert 시도 건수 반환."""
        if not rows:
            return 0
        if self._sync_session_factory is None:
            raise RuntimeError("sync_engine이 주입되지 않았습니다.")
        with self._sync_session_factory() as session:
            dialect_name = session.get_bind().dialect.name
            stmt = self._build_upsert_stmt(rows, dialect_name)
            session.execute(stmt)
            session.commit()
            return len(rows)

    def fetch_passed_sync(
        self,
        on_date: date_type,
        profile: str = "momentum_breakout",
    ) -> list[DailyScreeningCache]:
        """동기 세션으로 통과 종목을 rank 오름차순 조회."""
        if self._sync_session_factory is None:
            raise RuntimeError("sync_engine이 주입되지 않았습니다.")
        with self._sync_session_factory() as session:
            return list(
                session.execute(
                    select(DailyScreeningCache)
                    .where(
                        DailyScreeningCache.date == on_date,
                        DailyScreeningCache.profile == profile,
                        DailyScreeningCache.passed.is_(True),
                    )
                    .order_by(DailyScreeningCache.rank.asc())
                )
                .scalars()
                .all()
            )

    # ── 비동기 API (FastAPI / process_manager) ────────

    async def upsert_many(self, rows: list[dict[str, Any]]) -> int:
        """비동기 세션으로 upsert."""
        if not rows:
            return 0
        if self._async_session_factory is None:
            raise RuntimeError("async_engine이 주입되지 않았습니다.")
        async with self._async_session_factory() as session:
            dialect_name = session.get_bind().dialect.name
            stmt = self._build_upsert_stmt(rows, dialect_name)
            await session.execute(stmt)
            await session.commit()
            return len(rows)

    async def fetch_passed(
        self,
        on_date: date_type,
        profile: str = "momentum_breakout",
    ) -> list[DailyScreeningCache]:
        """비동기 세션으로 통과 종목을 rank 오름차순 조회."""
        if self._async_session_factory is None:
            raise RuntimeError("async_engine이 주입되지 않았습니다.")
        async with self._async_session_factory() as session:
            result = await session.execute(
                select(DailyScreeningCache)
                .where(
                    DailyScreeningCache.date == on_date,
                    DailyScreeningCache.profile == profile,
                    DailyScreeningCache.passed.is_(True),
                )
                .order_by(DailyScreeningCache.rank.asc())
            )
            return list(result.scalars().all())

    async def fetch_all_for_date(
        self,
        on_date: date_type,
        profile: str = "momentum_breakout",
    ) -> list[DailyScreeningCache]:
        """당일 모든 엔트리(통과/미통과) 조회 — 디버깅/분석용."""
        if self._async_session_factory is None:
            raise RuntimeError("async_engine이 주입되지 않았습니다.")
        async with self._async_session_factory() as session:
            result = await session.execute(
                select(DailyScreeningCache)
                .where(
                    DailyScreeningCache.date == on_date,
                    DailyScreeningCache.profile == profile,
                )
                .order_by(DailyScreeningCache.rank.asc())
            )
            return list(result.scalars().all())


def result_to_row(
    result: dict[str, Any],
    *,
    on_date: date_type,
    profile: str,
    symbol: str,
    name: str,
    sector: str,
    hint: str,
    threshold: float,
    volume_ratio_param: float,
    min_stocks_param: int,
    run_id: str | None = None,
) -> dict[str, Any]:
    """engine.check_screen_condition() 결과 dict → upsert 행 변환.

    엔진 dict에 symbol/name/sector/hint 및 파라미터 스냅샷을 합쳐 반환한다.
    rank는 `rank_and_fill()` 이후 호출자가 주입한다.
    """
    return {
        "date": on_date,
        "profile": profile,
        "symbol": symbol,
        "name": name,
        "sector": sector,
        "hint": hint,
        "rank": int(result.get("rank", 0)),
        "passed": bool(result.get("passed", False)),
        "price_ratio": float(result.get("price_ratio", 0.0)),
        "vol_ratio": float(result.get("vol_ratio", 0.0)),
        "bonus_score": int(result.get("bonus_score", 0)),
        "close": int(result.get("close", 0)),
        "high_52w": int(result.get("high_52w", 0)),
        "volume": int(result.get("volume", 0)),
        "avg_volume": int(result.get("avg_volume", 0)),
        "threshold": float(threshold),
        "volume_ratio_param": float(volume_ratio_param),
        "min_stocks_param": int(min_stocks_param),
        "run_id": run_id,
    }
