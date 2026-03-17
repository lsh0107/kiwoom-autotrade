"""KillSwitch 클래스 테스트 (soft_stop / hard_stop / resume / get_status)."""

import uuid

import pytest

from src.trading.kill_switch import (
    KillSwitch,
    KillSwitchStatus,
    _kill_switch_states,
    kill_switch,
)


class TestKillSwitchGetStatus:
    """get_status 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)

    def test_initial_status_is_normal(self) -> None:
        """초기 상태는 NORMAL."""
        ks = KillSwitch()
        assert ks.get_status(self.user_id) == KillSwitchStatus.NORMAL

    def test_returns_existing_status(self) -> None:
        """저장된 상태 반환."""
        _kill_switch_states[self.user_id] = KillSwitchStatus.SOFT_STOPPED
        ks = KillSwitch()
        assert ks.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED


class TestKillSwitchSoftStop:
    """soft_stop 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)

    def test_soft_stop_from_normal(self) -> None:
        """NORMAL → SOFT_STOPPED 전이."""
        ks = KillSwitch()
        result = ks.soft_stop(self.user_id)
        assert result == KillSwitchStatus.SOFT_STOPPED
        assert ks.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED

    def test_soft_stop_idempotent(self) -> None:
        """SOFT_STOPPED 상태에서 재호출 — 상태 유지."""
        ks = KillSwitch()
        ks.soft_stop(self.user_id)
        result = ks.soft_stop(self.user_id)
        assert result == KillSwitchStatus.SOFT_STOPPED

    def test_soft_stop_ignored_when_hard_stopped(self) -> None:
        """HARD_STOPPED 상태에서 soft_stop 무시 — HARD_STOPPED 유지."""
        ks = KillSwitch()
        ks.hard_stop(self.user_id, confirm=True)
        result = ks.soft_stop(self.user_id)
        assert result == KillSwitchStatus.HARD_STOPPED
        assert ks.get_status(self.user_id) == KillSwitchStatus.HARD_STOPPED


class TestKillSwitchHardStop:
    """hard_stop 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)

    def test_hard_stop_requires_confirm(self) -> None:
        """confirm=False 시 ValueError 발생."""
        ks = KillSwitch()
        with pytest.raises(ValueError, match="confirm=True 필수"):
            ks.hard_stop(self.user_id)

    def test_hard_stop_with_confirm(self) -> None:
        """confirm=True — HARD_STOPPED 전이."""
        ks = KillSwitch()
        result = ks.hard_stop(self.user_id, confirm=True)
        assert result == KillSwitchStatus.HARD_STOPPED
        assert ks.get_status(self.user_id) == KillSwitchStatus.HARD_STOPPED

    def test_hard_stop_from_soft_stopped(self) -> None:
        """SOFT_STOPPED → HARD_STOPPED 전이."""
        ks = KillSwitch()
        ks.soft_stop(self.user_id)
        result = ks.hard_stop(self.user_id, confirm=True)
        assert result == KillSwitchStatus.HARD_STOPPED

    def test_hard_stop_idempotent(self) -> None:
        """HARD_STOPPED 상태에서 재호출 — 상태 유지."""
        ks = KillSwitch()
        ks.hard_stop(self.user_id, confirm=True)
        result = ks.hard_stop(self.user_id, confirm=True)
        assert result == KillSwitchStatus.HARD_STOPPED


class TestKillSwitchResume:
    """resume 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)

    def test_resume_from_soft_stopped(self) -> None:
        """SOFT_STOPPED → resume → NORMAL."""
        ks = KillSwitch()
        ks.soft_stop(self.user_id)
        result = ks.resume(self.user_id)
        assert result == KillSwitchStatus.NORMAL
        assert ks.get_status(self.user_id) == KillSwitchStatus.NORMAL

    def test_resume_from_hard_stopped(self) -> None:
        """HARD_STOPPED → resume → NORMAL."""
        ks = KillSwitch()
        ks.hard_stop(self.user_id, confirm=True)
        result = ks.resume(self.user_id)
        assert result == KillSwitchStatus.NORMAL
        assert ks.get_status(self.user_id) == KillSwitchStatus.NORMAL

    def test_resume_from_normal(self) -> None:
        """NORMAL → resume → NORMAL (멱등)."""
        ks = KillSwitch()
        result = ks.resume(self.user_id)
        assert result == KillSwitchStatus.NORMAL

    def test_full_cycle_soft_stop_resume(self) -> None:
        """전체 순환: NORMAL → SOFT → HARD → NORMAL."""
        ks = KillSwitch()
        ks.soft_stop(self.user_id)
        assert ks.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED
        ks.hard_stop(self.user_id, confirm=True)
        assert ks.get_status(self.user_id) == KillSwitchStatus.HARD_STOPPED
        ks.resume(self.user_id)
        assert ks.get_status(self.user_id) == KillSwitchStatus.NORMAL


class TestKillSwitchSingleton:
    """kill_switch 싱글턴 인스턴스 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)

    def test_singleton_instance(self) -> None:
        """kill_switch 인스턴스가 KillSwitch 타입."""
        assert isinstance(kill_switch, KillSwitch)

    def test_singleton_state_shared(self) -> None:
        """싱글턴으로 상태 공유."""
        kill_switch.soft_stop(self.user_id)
        assert kill_switch.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED
        kill_switch.resume(self.user_id)


class TestKillSwitchCompatHelpers:
    """하위 호환 헬퍼(activate_manual_kill, deactivate_manual_kill) 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)

    def test_activate_manual_kill_equals_soft_stop(self) -> None:
        """activate_manual_kill → SOFT_STOPPED."""
        from src.trading.kill_switch import activate_manual_kill

        activate_manual_kill(self.user_id)
        assert kill_switch.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED

    def test_deactivate_manual_kill_equals_resume(self) -> None:
        """deactivate_manual_kill → NORMAL."""
        from src.trading.kill_switch import deactivate_manual_kill

        kill_switch.soft_stop(self.user_id)
        deactivate_manual_kill(self.user_id)
        assert kill_switch.get_status(self.user_id) == KillSwitchStatus.NORMAL


class TestKillSwitchStateSync:
    """[P1] KillSwitch ↔ DrawdownGuard 상태 동기화 검증."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)

    def test_activate_syncs_both_states(self) -> None:
        """activate_manual_kill → drawdown_guard + kill_switch 양쪽 반영."""
        from src.trading.drawdown_guard import get_user_state
        from src.trading.kill_switch import activate_manual_kill

        activate_manual_kill(self.user_id)

        # KillSwitch 상태
        assert kill_switch.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED

        # DrawdownGuard 상태
        dg_state = get_user_state(self.user_id)
        assert dg_state.manual_kill is True

    def test_deactivate_syncs_both_states(self) -> None:
        """deactivate_manual_kill → 양쪽 해제."""
        from src.trading.drawdown_guard import get_user_state
        from src.trading.kill_switch import activate_manual_kill, deactivate_manual_kill

        activate_manual_kill(self.user_id)
        deactivate_manual_kill(self.user_id)

        assert kill_switch.get_status(self.user_id) == KillSwitchStatus.NORMAL
        dg_state = get_user_state(self.user_id)
        assert dg_state.manual_kill is False

    def test_soft_stop_blocks_check_level3(self) -> None:
        """soft_stop 후 check_level3에서 KillSwitchError 발생."""
        from unittest.mock import AsyncMock

        from src.trading.drawdown_guard import check_level3
        from src.utils.exceptions import KillSwitchError

        kill_switch.soft_stop(self.user_id)

        mock_db = AsyncMock()
        with pytest.raises(KillSwitchError, match="KillSwitch"):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                check_level3(user_id=self.user_id, db=mock_db)
            )
