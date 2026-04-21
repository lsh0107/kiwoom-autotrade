"""저장 유틸리티 단위 테스트."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    import pytest


class TestSaveJson:
    """save_json 테스트."""

    def test_save_json_creates_file(self, tmp_path: Path) -> None:
        """save_json 호출 시 파일이 생성되어야 한다."""
        import collectors.storage as storage_mod

        with patch.object(storage_mod, "DATA_DIR", tmp_path):
            result = storage_mod.save_json("premarket", "20250101", {"key": "value"})

        assert result == tmp_path / "premarket" / "20250101.json"
        assert result.exists()

    def test_save_json_content_is_correct(self, tmp_path: Path) -> None:
        """저장된 파일의 내용이 올바른 JSON이어야 한다."""
        import collectors.storage as storage_mod

        data = {"dart": [], "fred": {"vix": 18.5}, "overseas": {"SP500": {"close": 5000.0}}}

        with patch.object(storage_mod, "DATA_DIR", tmp_path):
            path = storage_mod.save_json("premarket", "20250101", data)

        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded == data

    def test_save_json_creates_parent_dirs(self, tmp_path: Path) -> None:
        """중간 디렉토리가 없어도 자동 생성되어야 한다."""
        import collectors.storage as storage_mod

        with patch.object(storage_mod, "DATA_DIR", tmp_path):
            storage_mod.save_json("nested/category", "20250101", {})

        assert (tmp_path / "nested" / "category").is_dir()

    def test_save_json_korean_characters(self, tmp_path: Path) -> None:
        """한글 문자가 포함된 데이터를 올바르게 저장해야 한다."""
        import collectors.storage as storage_mod

        data = {"종목": "삼성전자", "공시": "주요사항보고서"}

        with patch.object(storage_mod, "DATA_DIR", tmp_path):
            path = storage_mod.save_json("premarket", "20250101", data)

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # ensure_ascii=False 이므로 한글이 그대로 저장되어야 한다
        assert "삼성전자" in content


class TestLoadJson:
    """load_json 테스트."""

    def test_load_json_returns_data(self, tmp_path: Path) -> None:
        """저장된 파일을 올바르게 읽어야 한다."""
        import collectors.storage as storage_mod

        data = {"key": "value", "num": 42}
        path = tmp_path / "premarket" / "20250101.json"
        path.parent.mkdir(parents=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with patch.object(storage_mod, "DATA_DIR", tmp_path):
            result = storage_mod.load_json("premarket", "20250101")

        assert result == data

    def test_load_json_missing_file_returns_none(self, tmp_path: Path) -> None:
        """파일이 없을 때 None을 반환해야 한다."""
        import collectors.storage as storage_mod

        with patch.object(storage_mod, "DATA_DIR", tmp_path):
            result = storage_mod.load_json("premarket", "99991231")

        assert result is None

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """저장 후 로드 시 동일한 데이터를 반환해야 한다."""
        import collectors.storage as storage_mod

        original = {"dart": [{"corp": "삼성"}], "fred": {"vix": 20.0}}

        with patch.object(storage_mod, "DATA_DIR", tmp_path):
            storage_mod.save_json("premarket", "20250101", original)
            result = storage_mod.load_json("premarket", "20250101")

        assert result == original


class TestResolveDataDir:
    """_resolve_data_dir 테스트 (/opt/data 권한 에러 재발 방지)."""

    def test_env_var_takes_precedence(self, tmp_path: Path) -> None:
        """KIWOOM_DATA_DIR 환경변수가 설정되면 해당 경로를 사용해야 한다."""
        import collectors.storage as storage_mod

        with patch.dict("os.environ", {"KIWOOM_DATA_DIR": str(tmp_path)}):
            result = storage_mod._resolve_data_dir()

        assert result == tmp_path

    def test_airflow_home_fallback(self) -> None:
        """AIRFLOW_HOME 설정 시 env 미설정이어도 /opt/airflow/data 로 fallback."""
        import collectors.storage as storage_mod

        env = {"AIRFLOW_HOME": "/opt/airflow"}
        # KIWOOM_DATA_DIR 제거 후 AIRFLOW_HOME만 세팅
        with patch.dict("os.environ", env, clear=False):
            import os

            os.environ.pop("KIWOOM_DATA_DIR", None)
            result = storage_mod._resolve_data_dir()

        assert result == Path("/opt/airflow/data")

    def test_never_falls_back_to_opt_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """어떤 환경에서도 /opt/data 로 fallback 되지 않아야 한다 (권한 에러 재발 방지)."""
        import collectors.storage as storage_mod

        monkeypatch.delenv("KIWOOM_DATA_DIR", raising=False)
        monkeypatch.delenv("AIRFLOW_HOME", raising=False)

        result = storage_mod._resolve_data_dir()

        assert result != Path("/opt/data"), (
            f"fallback 경로가 /opt/data 가 되면 안 된다 (실제: {result})"
        )

    def test_host_dev_falls_back_to_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Airflow 환경이 아닐 때 프로젝트 루트 기반 data/ 를 사용해야 한다."""
        import collectors.storage as storage_mod

        monkeypatch.delenv("KIWOOM_DATA_DIR", raising=False)
        monkeypatch.delenv("AIRFLOW_HOME", raising=False)

        # 모듈 경로를 /opt/airflow 가 아닌 호스트 경로로 가장
        fake_module = tmp_path / "airflow" / "plugins" / "collectors" / "storage.py"
        fake_module.parent.mkdir(parents=True)
        fake_module.touch()
        monkeypatch.setattr(storage_mod, "__file__", str(fake_module))

        result = storage_mod._resolve_data_dir()

        assert result == tmp_path / "data"


class TestTodayStr:
    """today_str 테스트."""

    def test_today_str_format(self) -> None:
        """YYYYMMDD 형식의 8자리 문자열을 반환해야 한다."""
        from collectors.storage import today_str

        result = today_str()

        assert len(result) == 8
        assert result.isdigit()

    def test_today_str_is_kst(self) -> None:
        """KST 기준 날짜를 반환해야 한다 (UTC 15:00 = KST 00:00 다음날)."""
        import collectors.storage as storage_mod

        original_datetime = storage_mod.datetime

        class MockDatetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]  # noqa: ARG003
                return datetime.datetime(2025, 1, 1, 15, 0, 0, tzinfo=datetime.UTC)

        storage_mod.datetime = MockDatetime  # type: ignore[attr-defined]
        try:
            result = storage_mod.today_str()
        finally:
            storage_mod.datetime = original_datetime  # type: ignore[attr-defined]

        # UTC 15:00 + 9h = KST 00:00 다음날
        assert result == "20250102"
