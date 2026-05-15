"""Short Swing 후보 생성 DAG.

설계 문서 8절 — 장마감 후 daily_candle 수집 완료 직후
short_swing 전략 후보를 생성하여 short_swing_candidates 테이블에 저장한다.

Asset 토폴로지:
    Asset("daily_candle_collection")  ──▶  short_swing_screening
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

daily_candle_asset = Asset("daily_candle_collection")


@dag(
    dag_id="short_swing_screening",
    schedule=[daily_candle_asset],  # 일봉 수집 완료 직후 트리거
    start_date=datetime(2026, 5, 14, tzinfo=UTC),
    catchup=False,
    is_paused_upon_creation=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["short_swing", "screening", "postmarket"],
)
def short_swing_screening() -> None:
    """장마감 후 short_swing 후보 생성 파이프라인."""

    @task()
    def run_screening(**context) -> dict:  # type: ignore[no-untyped-def]
        """short_swing 후보 생성 — DB 일봉 기반 스크리닝."""
        import asyncio
        import datetime as dt
        import logging
        from zoneinfo import ZoneInfo

        from sqlalchemy import func as sa_func
        from sqlalchemy import select as sa_select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        logger = logging.getLogger(__name__)
        run_id = str(context.get("run_id") or "")

        from src.config.settings import get_settings
        from src.models.daily_candle import DailyCandle
        from src.screening.short_swing_screener import run_short_swing_screening

        settings = get_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def _run() -> tuple[int, str]:
            async with factory() as db:
                # 기준일: DailyCandle 최신 날짜 (수집 완료 데이터 기준)
                latest = (await db.execute(sa_select(sa_func.max(DailyCandle.date)))).scalar()
                # 폴백: KST 오늘 날짜 (장마감 후이므로 당일)
                trade_date = latest or dt.datetime.now(tz=ZoneInfo("Asia/Seoul")).date()

                logger.info(
                    "short_swing_screening 시작: trade_date=%s (source=%s), run_id=%s",
                    trade_date,
                    "daily_candle" if latest else "kst_fallback",
                    run_id,
                )

                candidates = await run_short_swing_screening(db, trade_date)
                await db.commit()
                return len(candidates), str(trade_date)

        count, trade_date_str = asyncio.run(_run())
        logger.info("short_swing_screening 완료: %d 후보 저장", count)
        return {"trade_date": trade_date_str, "candidates": count}

    run_screening()


short_swing_screening()
