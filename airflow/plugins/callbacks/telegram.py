"""Airflow 태스크 실패 시 텔레그램 알림 콜백."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def on_failure_telegram(context: dict[str, Any]) -> None:
    """태스크 실패 시 텔레그램으로 알림 전송.

    Airflow default_args의 on_failure_callback으로 등록해 사용한다.

    Args:
        context: Airflow 태스크 실행 컨텍스트.
            dag_id, task_id, execution_date, exception 등을 포함.
    """
    # TODO: 텔레그램 봇 전송 구현
    # 현재는 로그만 출력
    dag_id = context.get("dag").dag_id if context.get("dag") else "unknown"
    task_id = context.get("task_instance").task_id if context.get("task_instance") else "unknown"
    execution_date = context.get("execution_date", "unknown")
    exception = context.get("exception", "unknown")

    message = (
        f"[Airflow 실패 알림]\n"
        f"DAG: {dag_id}\n"
        f"Task: {task_id}\n"
        f"실행 시각: {execution_date}\n"
        f"에러: {exception}"
    )

    logger.error(message)

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정 — 텔레그램 전송 스킵")
        return

    # TODO: requests.post로 텔레그램 Bot API 호출 구현
