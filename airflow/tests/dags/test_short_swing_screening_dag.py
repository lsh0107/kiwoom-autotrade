"""short_swing_screening DAG 무결성 테스트."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def dagbag():  # type: ignore[no-untyped-def]
    """short_swing_screening DAG 로드 전용 DagBag."""
    dags_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../dags"))
    from airflow.models import DagBag

    return DagBag(dag_folder=dags_folder, include_examples=False)


def test_dag_loaded(dagbag) -> None:  # type: ignore[no-untyped-def]
    """DAG가 import 에러 없이 로드된다."""
    assert dagbag.import_errors == {}, dagbag.import_errors
    assert "short_swing_screening" in dagbag.dags


def test_dag_tags(dagbag) -> None:  # type: ignore[no-untyped-def]
    """필수 태그 존재."""
    dag = dagbag.dags["short_swing_screening"]
    tags = set(dag.tags)
    assert "short_swing" in tags
    assert "screening" in tags


def test_dag_catchup_false(dagbag) -> None:  # type: ignore[no-untyped-def]
    """catchup 비활성."""
    dag = dagbag.dags["short_swing_screening"]
    assert dag.catchup is False


def test_dag_has_run_screening_task(dagbag) -> None:  # type: ignore[no-untyped-def]
    """run_screening 태스크 존재."""
    dag = dagbag.dags["short_swing_screening"]
    task_ids = {t.task_id for t in dag.tasks}
    assert "run_screening" in task_ids


def test_dag_triggered_by_daily_candle_asset(dagbag) -> None:  # type: ignore[no-untyped-def]
    """schedule에 daily_candle_collection Asset 포함."""
    dag = dagbag.dags["short_swing_screening"]
    schedule = dag.schedule
    schedule_str = str(schedule)
    assert "daily_candle_collection" in schedule_str


def test_dag_not_paused_upon_creation(dagbag) -> None:  # type: ignore[no-untyped-def]
    """is_paused_upon_creation=False."""
    dag = dagbag.dags["short_swing_screening"]
    assert dag.is_paused_upon_creation is False


def test_dag_default_args_retries(dagbag) -> None:  # type: ignore[no-untyped-def]
    """retries >= 2."""
    dag = dagbag.dags["short_swing_screening"]
    retries = dag.default_args.get("retries", 0)
    assert retries >= 2


def test_dag_default_args_execution_timeout(dagbag) -> None:  # type: ignore[no-untyped-def]
    """execution_timeout이 설정되어 있다."""
    from datetime import timedelta

    dag = dagbag.dags["short_swing_screening"]
    timeout = dag.default_args.get("execution_timeout")
    assert timeout is not None
    assert isinstance(timeout, timedelta)
    assert timeout <= timedelta(minutes=60)


def test_screening_date_uses_kst_or_daily_candle() -> None:
    """trade_date가 UTC 직접 사용이 아닌 DailyCandle.date 또는 KST 기준 (테스트 #10)."""
    dag_path = os.path.join(
        os.path.dirname(__file__), "../../dags/postmarket/short_swing_screening.py"
    )
    with open(dag_path) as f:
        source = f.read()

    # UTC 기반 date 계산이 없어야 함
    assert "now(tz=dt.UTC).date()" not in source, "UTC 기반 date 사용 금지"
    assert "now(tz=UTC).date()" not in source, "UTC 기반 date 사용 금지"

    # DailyCandle.date 또는 KST 기반이어야 함
    assert "DailyCandle" in source or "Asia/Seoul" in source, (
        "DailyCandle.date max 또는 KST 기반 date 사용 필수"
    )
