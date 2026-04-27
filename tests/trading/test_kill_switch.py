"""KillSwitch 클래스 테스트 (soft_stop / hard_stop / resume / AutoKillSwitchMonitor)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.trading.kill_switch import (
    AutoKillSwitchMonitor,
    KillSwitch,
    KillSwitchStatus,
    _kill_switch_states,
    auto_kill_monitor,
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


# ── AutoKillSwitchMonitor 테스트 ─────────────────────────────────────


class TestAutoKillSwitchConsecutiveLoss:
    """트리거 1: 동일 종목 3회 연속 손절 → SOFT_STOP."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)
        self.monitor = AutoKillSwitchMonitor()

    def test_three_consecutive_losses_trigger_soft_stop(self) -> None:
        """동일 종목 3연속 손절 → SOFT_STOP 발동.

        per-loss = -0.003: 3회 합산 -0.009 < PnL 임계값 -0.015이므로
        슬라이딩 PnL 트리거 없이 연속 손절만 검증.
        """
        for _ in range(3):
            status = self.monitor.record_trade(self.user_id, "005930", -0.003)
        assert status == KillSwitchStatus.SOFT_STOPPED
        assert kill_switch.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED

    def test_two_consecutive_losses_no_trigger(self) -> None:
        """2연속 손절은 트리거 미발동 — NORMAL 유지."""
        for _ in range(2):
            status = self.monitor.record_trade(self.user_id, "005930", -0.003)
        assert status == KillSwitchStatus.NORMAL

    def test_profit_resets_consecutive_count(self) -> None:
        """수익 청산 시 연속 손절 카운트 초기화."""
        self.monitor.record_trade(self.user_id, "005930", -0.003)
        self.monitor.record_trade(self.user_id, "005930", -0.003)
        self.monitor.record_trade(self.user_id, "005930", 0.02)  # 수익 → 카운트 리셋
        status = self.monitor.record_trade(self.user_id, "005930", -0.003)
        # 리셋 후 1연속이므로 미발동 (PnL 합산 -0.006 + 0.02 - 0.003 = +0.011)
        assert status == KillSwitchStatus.NORMAL

    def test_different_symbols_counted_independently(self) -> None:
        """다른 종목의 손절은 각각 독립 카운트.

        per-loss = -0.002: 5회 합산 -0.010 < PnL 임계값 -0.015이므로
        슬라이딩 PnL 트리거 없이 연속 손절만 검증.
        """
        self.monitor.record_trade(self.user_id, "005930", -0.002)
        self.monitor.record_trade(self.user_id, "005930", -0.002)
        # 다른 종목 손절 3회 → 해당 종목만 트리거
        for _ in range(3):
            self.monitor.record_trade(self.user_id, "000660", -0.002)
        # kill_switch는 발동됨
        assert kill_switch.get_status(self.user_id) == KillSwitchStatus.SOFT_STOPPED


class TestAutoKillSwitchSlidingPnL:
    """트리거 2: 10분 슬라이딩 윈도우 누적 PnL -1.5% → SOFT_STOP."""

    def setup_method(self) -> None:
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)
        self.monitor = AutoKillSwitchMonitor()

    def test_sliding_pnl_triggers_soft_stop(self) -> None:
        """10분 내 누적 PnL -1.5% 도달 → SOFT_STOP."""
        # -0.5% x 3 = -1.5%
        self.monitor.record_trade(self.user_id, "005930", -0.005)
        self.monitor.record_trade(self.user_id, "000660", -0.005)
        status = self.monitor.record_trade(self.user_id, "035420", -0.005)
        assert status == KillSwitchStatus.SOFT_STOPPED

    def test_sliding_pnl_below_threshold_no_trigger(self) -> None:
        """누적 PnL -1.0% (임계값 미달) → NORMAL 유지."""
        self.monitor.record_trade(self.user_id, "005930", -0.005)
        status = self.monitor.record_trade(self.user_id, "000660", -0.005)
        assert status == KillSwitchStatus.NORMAL

    def test_expired_events_excluded_from_window(self) -> None:
        """10분 경과 이벤트는 슬라이딩 윈도우에서 제외."""
        monitor = AutoKillSwitchMonitor()
        # 11분 전 이벤트 수동 추가 (만료됨)
        old_time = datetime.now(tz=UTC) - timedelta(minutes=11)
        monitor._pnl_window.append((old_time, -0.01))
        monitor._pnl_window.append((old_time, -0.01))
        # 최신 이벤트는 -0.005만 추가 (합산 -0.005, 임계값 미달)
        status = monitor.record_trade(self.user_id, "005930", -0.005)
        assert status == KillSwitchStatus.NORMAL


class TestAutoKillSwitchOrderCount:
    """트리거 3: 일일 주문 건수 → SOFT_STOP(40) / HARD_STOP(60)."""

    def setup_method(self) -> None:
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)
        self.monitor = AutoKillSwitchMonitor()

    def test_orders_below_soft_limit_no_trigger(self) -> None:
        """40건 이하 주문 — NORMAL 유지."""
        for _ in range(40):
            status = self.monitor.record_order(self.user_id)
        assert status == KillSwitchStatus.NORMAL

    def test_orders_above_soft_limit_triggers_soft_stop(self) -> None:
        """41번째 주문 → SOFT_STOP."""
        for _ in range(41):
            status = self.monitor.record_order(self.user_id)
        assert status == KillSwitchStatus.SOFT_STOPPED

    def test_orders_above_hard_limit_triggers_hard_stop(self) -> None:
        """61번째 주문 → HARD_STOP."""
        for _ in range(61):
            status = self.monitor.record_order(self.user_id)
        assert status == KillSwitchStatus.HARD_STOPPED

    def test_get_daily_order_count(self) -> None:
        """일일 주문 건수 조회 정확성."""
        for _ in range(5):
            self.monitor.record_order(self.user_id)
        assert self.monitor.get_daily_order_count() == 5

    def test_hard_stop_persists_after_more_orders(self) -> None:
        """HARD_STOP 발동 후 추가 주문에도 HARD_STOPPED 유지."""
        for _ in range(61):
            self.monitor.record_order(self.user_id)
        status = self.monitor.record_order(self.user_id)
        assert status == KillSwitchStatus.HARD_STOPPED


class TestAutoKillSwitchSingleton:
    """auto_kill_monitor 싱글턴 및 리셋 테스트."""

    def setup_method(self) -> None:
        self.user_id = uuid.uuid4()
        _kill_switch_states.pop(self.user_id, None)
        auto_kill_monitor.reset_for_test()

    def test_singleton_instance(self) -> None:
        """auto_kill_monitor가 AutoKillSwitchMonitor 타입."""
        assert isinstance(auto_kill_monitor, AutoKillSwitchMonitor)

    def test_reset_for_test_clears_state(self) -> None:
        """reset_for_test 후 상태 초기화."""
        auto_kill_monitor.record_order(self.user_id)
        auto_kill_monitor.reset_for_test()
        assert auto_kill_monitor.get_daily_order_count() == 0
