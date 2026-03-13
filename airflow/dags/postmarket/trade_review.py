"""장후 매매 리뷰 DAG.

평일 15:30에 실행. pykrx 시장 데이터 + 당일 매매 기록 + 뉴스 감성을
LLM에 전달해 파라미터 조정 제안과 리뷰 리포트를 생성한다.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from include.callbacks.telegram import on_failure_telegram


@dag(
    dag_id="postmarket_trade_review",
    schedule="30 15 * * 1-5",
    start_date=days_ago(1),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["postmarket", "review"],
)
def postmarket_trade_review() -> None:
    """장후 매매 리뷰 파이프라인."""

    @task()
    def fetch_krx_data() -> dict:
        """당일 주가/투자자 매매 데이터 수집 (pykrx)."""
        import datetime

        from include.collectors.krx import collect_investor_trading, collect_ohlcv

        today = datetime.datetime.now(tz=datetime.UTC).date().strftime("%Y%m%d")
        ohlcv = collect_ohlcv(date=today)
        investor = collect_investor_trading(date=today)
        return {"ohlcv": ohlcv, "investor": investor}

    @task()
    def load_trade_history() -> list[dict]:
        """당일 매매 기록 로드."""
        # TODO: DB에서 당일 매매 기록 로드
        return []

    @task()
    def load_news_sentiment() -> list[dict]:
        """당일 뉴스 감성 분석 결과 로드."""
        # TODO: DB에서 당일 뉴스 감성 로드
        return []

    @task()
    def send_report(krx: dict, trades: list[dict], news: list[dict]) -> None:
        """LLM 리뷰 + 파라미터 제안 + 텔레그램 리포트 전송."""
        # TODO: LLM 리뷰 로직 + 텔레그램 전송 구현
        pass

    krx = fetch_krx_data()
    trades = load_trade_history()
    news = load_news_sentiment()
    send_report(krx, trades, news)


postmarket_trade_review()
