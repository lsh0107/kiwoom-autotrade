"""거시경제 주간 수집 DAG.

매주 월요일 08:00에 ECOS 기준금리와 FRED 주간 지표를 수집해 저장한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task

from callbacks.telegram import on_failure_telegram


@dag(
    dag_id="macro_weekly",
    schedule="0 23 * * 0",  # KST 월요일 08:00 = UTC 일요일 23:00
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=20),
    },
    tags=["periodic", "macro"],
)
def macro_weekly() -> None:
    """거시경제 주간 수집 파이프라인."""

    @task()
    def fetch_ecos_rates() -> dict:
        """한국은행 ECOS 기준금리 및 거시경제 지표 수집."""
        from collectors.ecos import collect_base_rate

        return collect_base_rate()

    @task()
    def store_macro_data(ecos: dict) -> None:
        """거시경제 데이터 저장 (JSON + DB)."""
        from collectors.storage import save_json, save_market_data, today_str

        date_str = today_str()
        save_json("macro_weekly", date_str, ecos)
        save_market_data("ecos_rate", date_str, ecos)

    ecos = fetch_ecos_rates()
    store_macro_data(ecos)


macro_weekly()
