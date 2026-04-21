"""일봉 캐시 수집 DAG.

Design 011 PR 2. 평일 KST 18:00(UTC 09:00)에 pykrx로
KOSPI/KOSDAQ 전 종목 일봉을 수집하여 daily_candles에 upsert한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

daily_candle_asset = Asset("daily_candle_collection")


@dag(
    dag_id="daily_candle_collection",
    schedule="0 9 * * 1-5",  # UTC 월~금 09:00 = KST 월~금 18:00 장 마감 후
    start_date=datetime(2026, 4, 22, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=10),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=60),
    },
    tags=["postmarket", "daily_candle", "tier1"],
)
def daily_candle_collection() -> None:
    """장 마감 후 일봉 캐시 수집 파이프라인."""

    @task()
    def fetch_kospi_ohlcv() -> list[dict]:
        """KOSPI 전 종목 당일 일봉 수집."""
        import datetime as dt

        from collectors.candles import collect_daily_ohlcv

        today = dt.datetime.now(tz=dt.UTC).date().strftime("%Y%m%d")
        return collect_daily_ohlcv(today, market="KOSPI")

    @task()
    def fetch_kosdaq_ohlcv() -> list[dict]:
        """KOSDAQ 전 종목 당일 일봉 수집."""
        import datetime as dt

        from collectors.candles import collect_daily_ohlcv

        today = dt.datetime.now(tz=dt.UTC).date().strftime("%Y%m%d")
        return collect_daily_ohlcv(today, market="KOSDAQ")

    @task(outlets=[daily_candle_asset])
    def upsert_candles(kospi: list[dict], kosdaq: list[dict]) -> int:
        """KOSPI+KOSDAQ 합쳐 daily_candles에 upsert."""
        import logging

        from collectors.candles import upsert_daily_candles

        logger = logging.getLogger(__name__)
        combined = list(kospi) + list(kosdaq)
        if not combined:
            logger.warning("수집된 일봉 데이터 없음 — 휴장 또는 pykrx 미제공 가능")
            return 0
        count = upsert_daily_candles(combined, source="pykrx")
        logger.info(
            "daily_candles 업서트: KOSPI %d + KOSDAQ %d = %d", len(kospi), len(kosdaq), count
        )
        return count

    kospi = fetch_kospi_ohlcv()
    kosdaq = fetch_kosdaq_ohlcv()
    upsert_candles(kospi, kosdaq)


daily_candle_collection()
