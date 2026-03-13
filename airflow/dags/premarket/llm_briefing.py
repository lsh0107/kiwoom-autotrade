"""LLM 장전 브리핑 DAG.

premarket_data_collection 완료 시 Asset 트리거로 자동 실행.
DART 공시 + 해외지수 + VIX/금리를 LLM에 전달해 테마 스코어와 진입 가중치를 생성한다.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

premarket_dataset = Asset("premarket_data")


@dag(
    dag_id="llm_briefing",
    schedule=[premarket_dataset],
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=20),
    },
    tags=["premarket", "llm"],
)
def llm_briefing() -> None:
    """LLM 장전 브리핑 파이프라인."""

    @task()
    def load_premarket_data() -> dict:
        """당일 장전 수집 데이터 로드."""
        from collectors.storage import load_json, today_str

        date = today_str()
        data = load_json("premarket", date)
        if data is None:
            import logging

            logging.getLogger(__name__).warning("장전 데이터 없음: %s — 빈 딕셔너리 사용", date)
            return {}
        return data

    @task()
    def generate_briefing_task(data: dict) -> dict:
        """LLM으로 장전 브리핑 생성.

        산출물: 테마 스코어, 진입 가중치 ±20% 조정, 위험 종목 플래그.
        """
        import dataclasses

        from llm.briefing import generate_briefing

        result = generate_briefing(data)
        return dataclasses.asdict(result)

    @task()
    def store_briefing(briefing: dict) -> None:
        """브리핑 결과 저장 및 텔레그램 전송."""
        import logging

        from collectors.storage import save_json, today_str

        logger = logging.getLogger(__name__)
        date = today_str()
        save_json("briefing", date, briefing)
        logger.info("브리핑 저장 완료: %s", date)

        # 텔레그램 전송 (선택적)
        import os

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            try:
                import requests

                summary = briefing.get("summary", "")
                risk_flags = briefing.get("risk_flags", [])
                theme_scores = briefing.get("theme_scores", {})

                top_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)[:3]
                theme_text = ", ".join(f"{k}({v:.2f})" for k, v in top_themes)
                risk_text = "\n".join(f"⚠️ {r}" for r in risk_flags) if risk_flags else "없음"

                message = (
                    f"[장전 브리핑]\n{summary}\n\n주요 테마: {theme_text}\n리스크:\n{risk_text}"
                )
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": message},
                    timeout=10,
                )
                logger.info("텔레그램 브리핑 전송 완료")
            except Exception:
                logger.warning("텔레그램 전송 실패", exc_info=True)

    data = load_premarket_data()
    briefing = generate_briefing_task(data)
    store_briefing(briefing)


llm_briefing()
