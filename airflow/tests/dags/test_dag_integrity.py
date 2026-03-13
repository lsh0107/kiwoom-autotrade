"""DAG 무결성 검증 테스트.

import 에러, 순환 의존성, 태그 누락을 자동 검증한다.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def dagbag():
    """DagBag 픽스처 — 세션 범위로 한 번만 로드."""
    # airflow 디렉토리 기준으로 dags 폴더 지정
    dags_folder = os.path.join(os.path.dirname(__file__), "../../dags")
    dags_folder = os.path.abspath(dags_folder)

    from airflow.models import DagBag

    return DagBag(dag_folder=dags_folder, include_examples=False)


def test_no_import_errors(dagbag) -> None:
    """모든 DAG가 import 에러 없이 로드되어야 한다."""
    assert dagbag.import_errors == {}, "DAG import 에러 발생:\n" + "\n".join(
        f"{path}: {err}" for path, err in dagbag.import_errors.items()
    )


def test_all_dags_have_tags(dagbag) -> None:
    """모든 DAG에 태그가 설정되어야 한다."""
    for dag_id, dag in dagbag.dags.items():
        assert dag.tags, f"{dag_id}에 태그가 없습니다. tags 파라미터를 추가하세요."


def test_expected_dag_ids_exist(dagbag) -> None:
    """기대하는 DAG ID가 모두 존재해야 한다."""
    expected_dag_ids = {
        "premarket_data_collection",
        "llm_briefing",
        "postmarket_trade_review",
        "news_collection",
        "macro_weekly",
    }
    actual_dag_ids = set(dagbag.dags.keys())
    missing = expected_dag_ids - actual_dag_ids
    assert not missing, f"누락된 DAG: {missing}"
