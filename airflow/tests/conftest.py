"""Airflow 테스트 공통 픽스처."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# airflow 디렉토리를 sys.path에 추가해 include 패키지를 임포트 가능하게 한다
_AIRFLOW_DIR = str(Path(__file__).parent.parent)
if _AIRFLOW_DIR not in sys.path:
    sys.path.insert(0, _AIRFLOW_DIR)


@pytest.fixture(autouse=True)
def set_airflow_home(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트 시 AIRFLOW_HOME을 임시 디렉토리로 설정."""
    monkeypatch.setenv("AIRFLOW_HOME", str(tmp_path))
    monkeypatch.setenv("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
