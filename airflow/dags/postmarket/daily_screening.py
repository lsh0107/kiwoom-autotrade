"""사전 스크리닝 DAG (Design 012 PR 3).

daily_candle_collection 완료 직후(Asset trigger) 스크리닝을 수행하고
daily_screening_cache 에 결과를 저장한다.

Asset 토폴로지:
    Asset("daily_candle_collection")  ──▶  daily_screening  ──▶  Asset("daily_screening_ready")
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

daily_candle_asset = Asset("daily_candle_collection")
daily_screening_asset = Asset("daily_screening_ready")


@dag(
    dag_id="daily_screening",
    schedule=[daily_candle_asset],  # 일봉 수집 완료 직후 실행
    start_date=datetime(2026, 4, 22, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["postmarket", "screening", "tier1"],
)
def daily_screening() -> None:
    """장 마감 후 사전 스크리닝 파이프라인."""

    @task()
    def load_params() -> dict:
        """스크리닝 파라미터 로드 (환경변수 기반 기본값)."""
        from collectors.screening import load_screening_params

        return load_screening_params()

    @task()
    def compute_passed(params: dict, **context) -> list[dict]:  # type: ignore[no-untyped-def]
        """DB 일봉을 읽어 스크리닝을 수행하고 upsert 대상 dict 리스트 반환."""
        import datetime as dt

        from collectors.screening import compute_screening
        from scripts.screen_symbols import UNIVERSE, get_sector, get_strategy_hint

        on_date = dt.datetime.now(tz=dt.UTC).date()
        run_id = str(context.get("run_id") or "")
        return compute_screening(
            params,
            on_date=on_date,
            universe=UNIVERSE.items(),
            get_sector=get_sector,
            get_hint=get_strategy_hint,
            run_id=run_id,
        )

    @task(outlets=[daily_screening_asset])
    def upsert_cache(rows: list[dict]) -> int:
        """daily_screening_cache에 ON CONFLICT upsert."""
        import logging

        from collectors.screening import upsert_screening_rows

        logger = logging.getLogger(__name__)
        if not rows:
            logger.warning("스크리닝 결과 없음 — 휴장 또는 일봉 부재 가능")
            return 0
        count = upsert_screening_rows(rows)
        passed_count = sum(1 for r in rows if r.get("passed"))
        logger.info(
            "daily_screening_cache 업서트: 전체 %d / 통과 %d",
            count,
            passed_count,
        )
        return count

    params = load_params()
    rows = compute_passed(params)
    upsert_cache(rows)


daily_screening()
