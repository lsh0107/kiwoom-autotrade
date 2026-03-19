"""장후 매매 리뷰 DAG.

평일 15:30에 실행. pykrx 시장 데이터 + 당일 매매 기록 + 뉴스 감성을
LLM에 전달해 파라미터 조정 제안과 리뷰 리포트를 생성한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

trade_review_dataset = Asset("postmarket_trade_review")


@dag(
    dag_id="postmarket_trade_review",
    schedule="30 6 * * 1-5",  # KST 15:30 = UTC 06:30
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
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

        from collectors.krx import collect_investor_trading, collect_ohlcv

        today = datetime.datetime.now(tz=datetime.UTC).date().strftime("%Y%m%d")
        ohlcv = collect_ohlcv(date=today)
        investor = collect_investor_trading(date=today)
        return {"ohlcv": ohlcv, "investor": investor}

    @task()
    def load_trade_history() -> list[dict]:
        """당일 매매 기록 로드."""
        import logging

        from collectors.storage import load_json, today_str

        logger = logging.getLogger(__name__)
        date = today_str()
        data = load_json("trades", date)
        if data is None:
            logger.warning("당일 매매 기록 없음: %s", date)
            return []
        if isinstance(data, list):
            return data
        return data.get("trades", [])

    @task()
    def load_news_sentiment() -> list[dict]:
        """당일 뉴스 감성 분석 결과 로드."""
        import logging

        from collectors.storage import load_json, today_str

        logger = logging.getLogger(__name__)
        date = today_str()
        data = load_json("news", date)
        if data is None:
            logger.warning("당일 뉴스 데이터 없음: %s", date)
            return []
        if isinstance(data, list):
            return data
        return data.get("articles", [])

    @task()
    def llm_review_task(krx: dict, trades: list[dict], news: list[dict]) -> dict:
        """LLM으로 장후 리뷰 생성."""
        import dataclasses

        from llm.review import generate_review

        result = generate_review(
            trade_data=trades,
            market_data=krx,
            news_data=news,
        )
        return dataclasses.asdict(result)

    @task(outlets=[trade_review_dataset])
    def store_review(review: dict) -> None:
        """리뷰 결과 저장 및 텔레그램 리포트 전송."""
        import logging
        import os

        from collectors.storage import save_json, today_str

        logger = logging.getLogger(__name__)
        date = today_str()
        save_json("review", date, review)
        logger.info("리뷰 저장 완료: %s", date)

        # 텔레그램 전송 (선택적)
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            try:
                import requests

                summary = review.get("summary", "")
                performance = review.get("performance_analysis", "")
                risk = review.get("risk_assessment", "")
                suggestions = review.get("suggestions", [])
                sug_text = ""
                if suggestions:
                    lines = [
                        f"• {s['key']}: {s['current_value']} → {s['suggested_value']} "
                        f"({s['reason']})"
                        for s in suggestions[:3]
                    ]
                    sug_text = "\n파라미터 제안:\n" + "\n".join(lines)

                message = (
                    f"[장후 리뷰]\n{summary}\n\n성과: {performance}\n\n리스크: {risk}{sug_text}"
                )
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": message},
                    timeout=10,
                )
                logger.info("텔레그램 리뷰 전송 완료")
            except Exception:
                logger.warning("텔레그램 전송 실패", exc_info=True)

    krx = fetch_krx_data()
    trades = load_trade_history()
    news = load_news_sentiment()
    review = llm_review_task(krx, trades, news)
    store_review(review)


postmarket_trade_review()
