"""daily_candle_collection DAG 무결성 테스트."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def dagbag():
    """daily_candle_collection DAG 로드 전용 DagBag."""
    dags_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../dags"))
    from airflow.models import DagBag

    return DagBag(dag_folder=dags_folder, include_examples=False)


def test_dag_loaded(dagbag) -> None:
    """DAG가 import 에러 없이 로드된다."""
    assert dagbag.import_errors == {}, dagbag.import_errors
    assert "daily_candle_collection" in dagbag.dags


def test_dag_schedule_kst_1800(dagbag) -> None:
    """스케줄은 UTC 09:00 평일 (KST 18:00 월~금)이어야 한다."""
    dag = dagbag.dags["daily_candle_collection"]
    assert str(dag.schedule) == "0 9 * * 1-5"


def test_dag_tags(dagbag) -> None:
    """필수 태그 존재."""
    dag = dagbag.dags["daily_candle_collection"]
    tags = set(dag.tags)
    assert "postmarket" in tags
    assert "daily_candle" in tags


def test_dag_catchup_false(dagbag) -> None:
    """catchup 비활성."""
    dag = dagbag.dags["daily_candle_collection"]
    assert dag.catchup is False


def test_dag_has_expected_tasks(dagbag) -> None:
    """fetch_kospi_ohlcv / fetch_kosdaq_ohlcv / upsert_candles 존재."""
    dag = dagbag.dags["daily_candle_collection"]
    task_ids = {t.task_id for t in dag.tasks}
    assert {"fetch_kospi_ohlcv", "fetch_kosdaq_ohlcv", "upsert_candles"} <= task_ids


def test_dag_not_paused_upon_creation(dagbag) -> None:
    """is_paused_upon_creation=False — dags_are_paused_at_creation=true 환경 대응."""
    dag = dagbag.dags["daily_candle_collection"]
    assert dag.is_paused_upon_creation is False


def test_dag_start_date_allows_backfill(dagbag) -> None:
    """start_date가 2026-04-14 이전이어야 5영업일 백필 범위(2026-04-16~)를 포함한다."""
    from datetime import date

    dag = dagbag.dags["daily_candle_collection"]
    assert dag.start_date is not None
    start = dag.start_date.date() if hasattr(dag.start_date, "date") else dag.start_date
    assert start <= date(2026, 4, 14), f"start_date={start} 가 백필 기준(2026-04-14)보다 늦습니다"
