"""거시경제 주간 수집 DAG.

매주 월요일 08:00에 ECOS 기준금리와 FRED 주간 지표를 수집해 저장한다.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from include.callbacks.telegram import on_failure_telegram


@dag(
    dag_id="macro_weekly",
    schedule="0 8 * * 1",
    start_date=days_ago(1),
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
        from include.collectors.ecos import collect_base_rate

        return collect_base_rate()

    @task()
    def store_macro_data(ecos: dict) -> None:
        """거시경제 데이터 저장."""
        # TODO: DB 저장 로직 구현
        pass

    ecos = fetch_ecos_rates()
    store_macro_data(ecos)


macro_weekly()
