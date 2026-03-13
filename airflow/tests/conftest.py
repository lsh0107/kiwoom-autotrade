"""Airflow 테스트 공통 픽스처."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# plugins 디렉토리를 sys.path에 추가해 collectors, analysis 등을 직접 임포트 가능하게 한다
# Airflow는 plugins/를 자동으로 sys.path에 추가하므로 동일한 방식으로 테스트 환경도 설정한다
_AIRFLOW_DIR = str(Path(__file__).parent.parent)
_PLUGINS_DIR = str(Path(__file__).parent.parent / "plugins")
for _p in (_AIRFLOW_DIR, _PLUGINS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture(autouse=True)
def set_airflow_home(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트 시 AIRFLOW_HOME을 임시 디렉토리로 설정."""
    monkeypatch.setenv("AIRFLOW_HOME", str(tmp_path))
    monkeypatch.setenv("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
