"""daily_screening DAG 무결성 테스트 (Design 012 PR 3)."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def dagbag():  # type: ignore[no-untyped-def]
    """daily_screening DAG 로드 전용 DagBag."""
    dags_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../dags"))
    from airflow.models import DagBag

    return DagBag(dag_folder=dags_folder, include_examples=False)


def test_dag_loaded(dagbag) -> None:  # type: ignore[no-untyped-def]
    """DAG가 import 에러 없이 로드된다."""
    assert dagbag.import_errors == {}, dagbag.import_errors
    assert "daily_screening" in dagbag.dags


def test_dag_tags(dagbag) -> None:  # type: ignore[no-untyped-def]
    """필수 태그 존재."""
    dag = dagbag.dags["daily_screening"]
    tags = set(dag.tags)
    assert "postmarket" in tags
    assert "screening" in tags


def test_dag_catchup_false(dagbag) -> None:  # type: ignore[no-untyped-def]
    """catchup 비활성."""
    dag = dagbag.dags["daily_screening"]
    assert dag.catchup is False


def test_dag_has_expected_tasks(dagbag) -> None:  # type: ignore[no-untyped-def]
    """load_params / compute_passed / upsert_cache 존재."""
    dag = dagbag.dags["daily_screening"]
    task_ids = {t.task_id for t in dag.tasks}
    assert {"load_params", "compute_passed", "upsert_cache"} <= task_ids


def test_dag_triggered_by_daily_candle_asset(dagbag) -> None:  # type: ignore[no-untyped-def]
    """schedule 에 daily_candle_collection Asset 포함."""
    dag = dagbag.dags["daily_screening"]
    schedule = dag.schedule
    schedule_str = str(schedule)
    assert "daily_candle_collection" in schedule_str


def test_dag_outlets_daily_screening_ready(dagbag) -> None:  # type: ignore[no-untyped-def]
    """upsert_cache task 가 daily_screening_ready Asset 생산."""
    dag = dagbag.dags["daily_screening"]
    upsert = next(t for t in dag.tasks if t.task_id == "upsert_cache")
    outlet_names = {getattr(a, "name", None) or getattr(a, "uri", "") for a in upsert.outlets}
    assert "daily_screening_ready" in outlet_names


def test_dag_not_paused_upon_creation(dagbag) -> None:  # type: ignore[no-untyped-def]
    """is_paused_upon_creation=False — dags_are_paused_at_creation=true 환경 대응."""
    dag = dagbag.dags["daily_screening"]
    # is_paused_upon_creation=False 이면 dag 속성이 False 또는 None이어야 한다
    assert dag.is_paused_upon_creation is False


def test_dag_start_date_allows_backfill(dagbag) -> None:  # type: ignore[no-untyped-def]
    """start_date가 2026-04-14 이전이어야 5영업일 백필 범위(2026-04-16~)를 포함한다."""
    from datetime import date

    dag = dagbag.dags["daily_screening"]
    assert dag.start_date is not None
    start = dag.start_date.date() if hasattr(dag.start_date, "date") else dag.start_date
    assert start <= date(2026, 4, 14), f"start_date={start} 가 백필 기준(2026-04-14)보다 늦습니다"
