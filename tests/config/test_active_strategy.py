"""ADR-024: ACTIVE_STRATEGY enum 단위 테스트."""

from __future__ import annotations

import pytest

from src.config.active_strategy import ActiveStrategy, get_active_strategy


class TestGetActiveStrategy:
    def test_default_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """환경변수 미설정 시 NONE."""
        monkeypatch.delenv("ACTIVE_STRATEGY", raising=False)
        assert get_active_strategy() == ActiveStrategy.NONE

    def test_cross_momentum_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        assert get_active_strategy() == ActiveStrategy.CROSS_MOMENTUM

    def test_multi_regime_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        assert get_active_strategy() == ActiveStrategy.MULTI_REGIME

    def test_none_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "none")
        assert get_active_strategy() == ActiveStrategy.NONE

    def test_uppercase_normalised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """대소문자 무관 (lower 변환)."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "CROSS_MOMENTUM")
        assert get_active_strategy() == ActiveStrategy.CROSS_MOMENTUM

    def test_whitespace_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "  cross_momentum  ")
        assert get_active_strategy() == ActiveStrategy.CROSS_MOMENTUM

    def test_invalid_value_falls_back_to_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """잘못된 값은 NONE 폴백 (시스템 idle 안전 default)."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "garbage")
        assert get_active_strategy() == ActiveStrategy.NONE

    def test_empty_value_falls_back_to_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "")
        assert get_active_strategy() == ActiveStrategy.NONE
