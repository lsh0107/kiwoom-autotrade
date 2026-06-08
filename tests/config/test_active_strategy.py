"""ADR-024: ACTIVE_STRATEGY enum 단위 테스트.

PR 1 (multi-strategy controller): legacy ACTIVE_STRATEGY compatibility guard 의
현재 동작을 고정하는 회귀 테스트. 실제 제거/대체 전(PR 5+)까지 이 동작은 보존돼야
한다 (6/15 본 관찰 guard). 인벤토리/제거 계획은
``docs/design/active-strategy-legacy-audit.md`` 참조.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config.active_strategy import (
    ActiveStrategy,
    get_active_strategy,
    is_strategy_enabled_db,
)


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


def _db_returning(row: object | None) -> AsyncMock:
    """scalar_one_or_none() == row 인 AsyncSession mock."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _db_raising() -> AsyncMock:
    """db.execute 가 예외를 던지는 AsyncSession mock."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))
    return db


class TestIsStrategyEnabledDb:
    """is_strategy_enabled_db: DB 우선 + env fallback (design-025 guard).

    PR 1 회귀 — short_swing / short_swing_exit / cross_momentum 핸들러가 의존하는
    가드. DB row 가 있으면 그 값을, 없거나 조회 실패 시 env ACTIVE_STRATEGY 로 fallback.
    """

    @pytest.mark.asyncio
    async def test_db_row_enabled_true_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # env 와 무관하게 DB 우선
        monkeypatch.delenv("ACTIVE_STRATEGY", raising=False)
        row = MagicMock()
        row.enabled = True
        db = _db_returning(row)
        assert await is_strategy_enabled_db(db, "cross_momentum") is True

    @pytest.mark.asyncio
    async def test_db_row_enabled_false_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # DB 가 disabled 면 env 가 켜져 있어도 False (DB 우선)
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        row = MagicMock()
        row.enabled = False
        db = _db_returning(row)
        assert await is_strategy_enabled_db(db, "cross_momentum") is False

    @pytest.mark.asyncio
    async def test_no_db_row_falls_back_to_env_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        db = _db_returning(None)
        assert await is_strategy_enabled_db(db, "cross_momentum") is True

    @pytest.mark.asyncio
    async def test_no_db_row_env_mismatch_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        db = _db_returning(None)
        assert await is_strategy_enabled_db(db, "short_swing") is False

    @pytest.mark.asyncio
    async def test_db_error_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # DB 조회 실패 → env fallback (예외를 삼키고 idle-safe 동작)
        monkeypatch.setenv("ACTIVE_STRATEGY", "short_swing")
        db = _db_raising()
        assert await is_strategy_enabled_db(db, "short_swing") is True
        assert await is_strategy_enabled_db(db, "cross_momentum") is False

    @pytest.mark.asyncio
    async def test_db_error_env_unset_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ACTIVE_STRATEGY", raising=False)
        db = _db_raising()
        assert await is_strategy_enabled_db(db, "cross_momentum") is False
