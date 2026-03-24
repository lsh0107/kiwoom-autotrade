"""야간 해외 변동 분석 DAG.

미국장 마감(06:00 KST) 후 해외지수 변동을 분석하여
익일 투자 전략에 활용할 야간 브리핑과 투자 결정을 생성한다.
"""

from __future__ import annotations

from datetime import timedelta

from airflow.sdk import Asset, dag, task

from callbacks.telegram import on_failure_telegram

overnight_dataset = Asset("overnight_data")
overnight_briefing_dataset = Asset("overnight_briefing")


@dag(
    dag_id="overnight_analysis",
    schedule=[overnight_dataset],
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=20),
    },
    tags=["overnight", "LLM", "tier1"],
)
def overnight_analysis() -> None:
    """야간 해외 변동 분석 → LLM 브리핑 + 투자 결정."""

    @task()
    def build_context() -> dict:
        """야간 분석용 DB 컨텍스트 구축."""
        from context.builder import build_overnight_context

        return build_overnight_context()

    @task()
    def analyze(ctx: dict) -> dict:
        """LLM으로 야간 분석 수행."""
        from llm.overnight import generate_overnight_analysis

        return generate_overnight_analysis(ctx)

    @task(outlets=[overnight_briefing_dataset])
    def store(result: dict) -> None:
        """분석 결과 저장 (브리핑 + 결정)."""
        from collectors.storage import save_briefing, save_decision, today_str

        date = today_str()

        # 브리핑 저장
        save_briefing(
            date,
            {
                "summary": result.get("summary", ""),
                "theme_scores": result.get("theme_scores", {}),
                "risk_flags": result.get("risk_flags", []),
                "weight_adjustments": result.get("weight_adjustments", {}),
                "raw_response": result.get("raw_response", ""),
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
            },
        )

        # 투자 결정 저장 (있으면)
        for decision in result.get("decisions", []):
            save_decision(
                date,
                {
                    **decision,
                    "context_source": "overnight",
                    "raw_response": result.get("raw_response", ""),
                },
            )

    ctx = build_context()
    result = analyze(ctx)
    store(result)


overnight_analysis()
