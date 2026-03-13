"""뉴스 수집 DAG.

장중 2시간 간격 (09:00~15:00)으로 네이버 뉴스를 수집해 감성 분석 후 저장한다.
일 25,000건 한도 내 운영.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from include.callbacks.telegram import on_failure_telegram


@dag(
    dag_id="news_collection",
    schedule="0 */2 9-15 * * 1-5",
    start_date=days_ago(1),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=3),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=15),
    },
    tags=["periodic", "news"],
)
def news_collection() -> None:
    """뉴스 수집 파이프라인."""

    @task()
    def search_naver_news() -> list[dict]:
        """유니버스 종목명으로 네이버 뉴스 검색."""
        # TODO: news 수집기 구현 후 활성화
        return []

    @task()
    def extract_sentiment(articles: list[dict]) -> list[dict]:  # noqa: ARG001
        """기사별 감성 분석 (긍정/부정/중립)."""
        # TODO: 감성 분석 로직 구현
        return []

    @task()
    def store_news_data(articles: list[dict]) -> None:
        """뉴스 및 감성 분석 결과 저장."""
        # TODO: DB 저장 로직 구현
        pass

    articles = search_naver_news()
    analyzed = extract_sentiment(articles)
    store_news_data(analyzed)


news_collection()
