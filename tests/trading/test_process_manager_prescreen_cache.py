"""process_manager의 USE_PRESCREEN_CACHE 분기 테스트 (Design 012 PR 4).

subprocess/_run_screening 전체를 돌리지 않고 `_try_prescreen_cache_bridge` 경로만
격리 검증한다.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.trading.process_manager import TradingProcessManager


class TestTryPrescreenCacheBridge:
    """_try_prescreen_cache_bridge 흐름."""

    async def test_flag_off_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USE_PRESCREEN_CACHE", raising=False)
        pm = TradingProcessManager()
        result = await pm._try_prescreen_cache_bridge()
        assert result is False

    async def test_cache_hit_returns_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """flag on + write_screened_json_from_db 성공 경로."""
        monkeypatch.setenv("USE_PRESCREEN_CACHE", "true")
        pm = TradingProcessManager()

        fake_file = tmp_path / "screened_20260421_120000.json"
        fake_file.write_text("{}", encoding="utf-8")

        with patch(
            "src.trading.prescreen_cache.write_screened_json_from_db",
            return_value=fake_file,
        ):
            result = await pm._try_prescreen_cache_bridge()
        assert result is True
        # stdout 버퍼에 적중 메시지 기록
        assert any("prescreen_cache 적중" in line for line in pm._stdout_buffer)

    async def test_cache_miss_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag on + 캐시 비어 있음 (write_screened_json_from_db → None)."""
        monkeypatch.setenv("USE_PRESCREEN_CACHE", "true")
        pm = TradingProcessManager()

        with patch(
            "src.trading.prescreen_cache.write_screened_json_from_db",
            return_value=None,
        ):
            result = await pm._try_prescreen_cache_bridge()
        assert result is False
        assert any("미스" in line for line in pm._stdout_buffer)

    async def test_bridge_exception_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """brokerage 브리지 예외 발생 시 False + 폴백 메시지."""
        monkeypatch.setenv("USE_PRESCREEN_CACHE", "true")
        pm = TradingProcessManager()

        def _raise(*_a: object, **_kw: object) -> None:
            raise RuntimeError("db offline")

        with patch(
            "src.trading.prescreen_cache.write_screened_json_from_db",
            side_effect=_raise,
        ):
            result = await pm._try_prescreen_cache_bridge()
        assert result is False
        assert any("브리지 실패" in line for line in pm._stdout_buffer)
