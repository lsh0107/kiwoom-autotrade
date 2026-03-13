"""Airflow 테스트 공통 픽스처."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def set_airflow_home(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트 시 AIRFLOW_HOME을 임시 디렉토리로 설정."""
    monkeypatch.setenv("AIRFLOW_HOME", str(tmp_path))
    monkeypatch.setenv("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
