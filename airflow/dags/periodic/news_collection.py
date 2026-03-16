"""뉴스 수집 DAG.

장중 2시간 간격 (09:00~15:00)으로 네이버 뉴스를 수집해 감성 분석 후 저장한다.
일 25,000건 한도 내 운영.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task

from callbacks.telegram import on_failure_telegram

# 대표 유니버스 키워드 (주요 종목 10개)
_UNIVERSE_KEYWORDS = [
    "삼성전자",
    "SK하이닉스",
    "LG에너지솔루션",
    "삼성바이오로직스",
    "현대차",
    "기아",
    "POSCO홀딩스",
    "KB금융",
    "신한지주",
    "카카오",
]


@dag(
    dag_id="news_collection",
    schedule="0 9,11,13,15 * * 1-5",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
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
        from collectors.news import collect_news

        return collect_news(_UNIVERSE_KEYWORDS, display=10)

    @task()
    def extract_sentiment(articles: list[dict]) -> list[dict]:
        """기사별 감성 분석 (긍정/부정/중립)."""
        from analysis.sentiment import analyze_news_sentiment

        return analyze_news_sentiment(articles)

    @task()
    def store_news_data(articles: list[dict]) -> None:
        """뉴스 및 감성 분석 결과 저장 (JSON + DB)."""
        from collectors.storage import save_json, save_news_articles, today_str

        save_json("news", today_str(), articles)
        save_news_articles(articles)

    articles = search_naver_news()
    analyzed = extract_sentiment(articles)
    store_news_data(analyzed)


news_collection()
