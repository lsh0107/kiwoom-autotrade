"""파라미터 자동 조정 DAG.

postmarket_trade_review 완료 후 15:45에 실행.
LLM 리뷰 결과를 분석해 파라미터 조정 제안을 DB에 저장한다.

주의: 제안은 status='pending'으로만 저장. 자동 적용 절대 금지.
사용자가 /settings/strategy/suggestions/{id}/approve 엔드포인트로 승인해야 적용.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task

from callbacks.telegram import on_failure_telegram


@dag(
    dag_id="postmarket_param_adjustment",
    schedule="45 6 * * 1-5",  # KST 15:45 = UTC 06:45
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=15),
    },
    tags=["postmarket", "param", "llm"],
)
def postmarket_param_adjustment() -> None:
    """파라미터 자동 조정 제안 파이프라인.

    ⚠️  제안만 생성. 자동 적용 금지. 사용자 승인 필수.
    """

    @task()
    def load_review() -> dict:
        """당일 LLM 리뷰 결과 로드."""
        import logging

        from collectors.storage import load_json, today_str

        logger = logging.getLogger(__name__)
        date = today_str()
        data = load_json("review", date)
        if data is None:
            logger.warning("당일 리뷰 없음: %s — 빈 딕셔너리 사용", date)
            return {}
        return data

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
    def analyze_params(review: dict, trades: list[dict]) -> list[dict]:
        """LLM 리뷰 + 매매 기록 → 파라미터 조정 제안 분석.

        ⚠️ 분석 결과는 pending 제안으로만 저장. 자동 적용 금지.
        """
        import dataclasses
        import logging

        from analysis.param_tuner import analyze_and_suggest

        logger = logging.getLogger(__name__)

        if not review:
            logger.info("리뷰 데이터 없음 — 파라미터 분석 스킵")
            return []

        suggestions = analyze_and_suggest(
            review_result=review,
            trade_history=trades,
        )
        logger.info("파라미터 제안 %d개 생성", len(suggestions))
        return [dataclasses.asdict(s) for s in suggestions]

    @task()
    def save_suggestions_task(suggestions: list[dict]) -> int:
        """파라미터 제안을 DB에 status='pending'으로 저장.

        자동 적용하지 않음. 사용자 승인 후에만 적용됨.
        """
        import logging

        from analysis.param_tuner import ParamSuggestion, save_suggestions

        logger = logging.getLogger(__name__)

        if not suggestions:
            logger.info("저장할 제안 없음")
            return 0

        param_suggestions = [
            ParamSuggestion(
                key=s["key"],
                current_value=s["current_value"],
                suggested_value=s["suggested_value"],
                reason=s["reason"],
                confidence=s["confidence"],
                source=s.get("source", "param_tuner"),
            )
            for s in suggestions
        ]
        count = save_suggestions(param_suggestions)
        logger.info("제안 %d개 저장 완료 (status=pending, 자동 적용 없음)", count)
        return count

    @task()
    def notify_telegram(suggestions: list[dict], saved_count: int) -> None:
        """텔레그램으로 파라미터 제안 알림 전송."""
        import logging
        import os

        logger = logging.getLogger(__name__)

        if not suggestions:
            logger.info("제안 없음 — 텔레그램 전송 스킵")
            return

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        # 제안 요약 텍스트 생성
        lines = [f"[파라미터 조정 제안] {saved_count}개 대기 중 (승인 필요)\n"]
        for s in suggestions[:5]:
            key = s.get("key", "")
            cur = s.get("current_value", "")
            sug = s.get("suggested_value", "")
            conf = s.get("confidence", 0.0)
            reason = s.get("reason", "")[:50]
            lines.append(f"• {key}: {cur} → {sug} (신뢰도 {conf:.0%})")
            lines.append(f"  근거: {reason}")

        lines.append("\n승인: /settings/strategy/suggestions 에서 확인")
        message = "\n".join(lines)

        logger.info("파라미터 제안 알림:\n%s", message)

        if bot_token and chat_id:
            try:
                import requests

                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": message},
                    timeout=10,
                )
                logger.info("텔레그램 파라미터 제안 전송 완료")
            except Exception:
                logger.warning("텔레그램 전송 실패", exc_info=True)

    review = load_review()
    trades = load_trade_history()
    suggestions = analyze_params(review, trades)
    saved_count = save_suggestions_task(suggestions)
    notify_telegram(suggestions, saved_count)


postmarket_param_adjustment()
