"""LLM 장전 브리핑 DAG.

premarket_data_collection 완료 시 Dataset 트리거로 자동 실행.
DART 공시 + 해외지수 + VIX/금리를 LLM에 전달해 테마 스코어와 진입 가중치를 생성한다.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.datasets import Dataset
from airflow.decorators import dag, task
from include.callbacks.telegram import on_failure_telegram

premarket_dataset = Dataset("premarket_data")


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
        """장전 수집 데이터 로드."""
        # TODO: DB에서 최신 premarket_data 로드
        return {}

    @task()
    def generate_briefing(data: dict) -> dict:  # noqa: ARG001
        """LLM으로 장전 브리핑 생성.

        산출물: 테마 스코어, 진입 가중치 ±20% 조정, 위험 종목 플래그.
        """
        # TODO: LLM 브리핑 로직 구현
        return {}

    @task()
    def send_telegram_briefing(briefing: dict) -> None:
        """텔레그램으로 브리핑 요약 전송."""
        # TODO: 텔레그램 전송 구현
        pass

    data = load_premarket_data()
    briefing = generate_briefing(data)
    send_telegram_briefing(briefing)


llm_briefing()
