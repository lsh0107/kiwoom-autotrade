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
        "postmarket_param_adjustment",
        "news_collection",
        "macro_weekly",
        "monthly_rebalance",
        "stock_master_sync",
        "daily_candle_collection",
    }
    actual_dag_ids = set(dagbag.dags.keys())
    missing = expected_dag_ids - actual_dag_ids
    assert not missing, f"누락된 DAG: {missing}"


def test_cron_schedules_use_utc_for_kst_intent(dagbag) -> None:
    """cron 스케줄이 UTC 기준으로 정확히 설정되어야 한다.

    Airflow `@dag` 기본 timezone이 UTC이므로, KST 의도 시각은 UTC로 변환해야 한다.
    (UTC = KST - 9시간)

    이 테스트는 cron schedule 문자열이 KST 의도를 UTC로 올바르게 변환했는지 검증한다.
    Asset 트리거(비-cron)는 검증 대상에서 제외된다.
    """
    expected_schedules = {
        # KST 23/03/06시 (UTC 14/18/21시, 같은 날 UTC로 간주)
        "overnight_index_collection": "0 14,18,21 * * 0-5",
        # KST 월~금 08:00 (UTC 일~목 23:00)
        "premarket_data_collection": "0 23 * * 0-4",
        # KST 월 08:00 (UTC 일 23:00)
        "macro_weekly": "0 23 * * 0",
        # KST 매월 1일 10:00 (UTC 1일 01:00)
        "stock_master_sync": "0 1 1 * *",
        # KST 월~금 09/11/13/15시 (UTC 월~금 00/02/04/06시)
        "news_collection": "0 0,2,4,6 * * 1-5",
        # KST 월~금 15:30 (UTC 월~금 06:30)
        "postmarket_trade_review": "30 6 * * 1-5",
        # KST 28-31일 15:00 (UTC 28-31일 06:00)
        "monthly_rebalance": "0 6 28-31 * *",
        # KST 월~금 18:00 (UTC 월~금 09:00) 장 마감 후 일봉 수집
        "daily_candle_collection": "0 9 * * 1-5",
    }

    for dag_id, expected in expected_schedules.items():
        dag = dagbag.dags.get(dag_id)
        assert dag is not None, f"{dag_id} DAG 로드 실패"
        actual = str(dag.schedule) if dag.schedule else None
        assert actual == expected, (
            f"{dag_id} schedule 불일치 — "
            f"expected={expected!r}, actual={actual!r}. "
            "KST 의도 시각은 UTC로 변환 필요 (UTC = KST - 9h)."
        )
