"""야간 해외지수 수집 DAG.

미국장 시간대(KST 23:00, 03:00, 06:00)에 해외지수 + 선물 데이터를 수집한다.
수집 완료 후 Asset("overnight_data")을 발행해 overnight_analysis DAG를 트리거한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

overnight_dataset = Asset("overnight_data")


@dag(
    dag_id="overnight_index_collection",
    schedule="0 14,18,21 * * 0-4",  # KST 23:00, 03:00, 06:00 = UTC 14, 18, 21 (전날)
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=15),
    },
    tags=["overnight", "수집", "tier1"],
)
def overnight_index_collection() -> None:
    """야간 해외지수 + 선물 수집 파이프라인."""

    @task()
    def collect_overnight() -> dict:
        """해외지수 + 선물 데이터 수집 (yfinance)."""
        from collectors.overseas import collect_overnight_indices

        return collect_overnight_indices()

    @task(outlets=[overnight_dataset])
    def store(data: dict) -> None:
        """수집 결과 DB + JSON 저장 및 Asset 발행."""
        from collectors.storage import save_market_data, today_str

        save_market_data("overnight_index", today_str(), data)

    store(collect_overnight())


overnight_index_collection()
