"""장전 데이터 수집 DAG.

평일 08:00에 DART 공시, FRED 거시경제, 해외 지수를 병렬 수집한다.
수집 완료 후 Dataset("premarket_data")을 발행해 llm_briefing DAG를 트리거한다.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.datasets import Dataset
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from include.callbacks.telegram import on_failure_telegram

premarket_dataset = Dataset("premarket_data")


@dag(
    dag_id="premarket_data_collection",
    schedule="0 8 * * 1-5",
    start_date=days_ago(1),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["premarket", "data", "tier1"],
)
def premarket_data_collection() -> None:
    """장전 데이터 수집 파이프라인."""

    @task()
    def fetch_dart() -> list[dict]:
        """DART 전자공시 수집."""
        from include.collectors.dart import collect_disclosures

        return collect_disclosures(days=1)

    @task()
    def fetch_fred() -> dict:
        """FRED 거시경제 지표 수집 (VIX, 금리, 환율, WTI)."""
        from include.collectors.fred import collect_macro

        return collect_macro()

    @task()
    def fetch_overseas() -> dict:
        """해외 주요 지수 수집 (S&P500, 나스닥, 닛케이 등)."""
        from include.collectors.overseas import collect_indices

        return collect_indices()

    @task(outlets=[premarket_dataset])
    def store(dart: list[dict], fred: dict, overseas: dict) -> None:
        """수집 결과 통합 저장 및 Dataset 발행."""
        from include.collectors.storage import save_json, today_str

        data = {
            "dart": dart,
            "fred": fred,
            "overseas": overseas,
        }
        save_json("premarket", today_str(), data)

    store(fetch_dart(), fetch_fred(), fetch_overseas())


premarket_data_collection()
