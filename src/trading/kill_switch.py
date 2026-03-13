"""KillSwitch — 사용자 수준 수동 매매 중단/청산 컨트롤.

상태 전이:
  normal → soft_stopped → (resume) → normal
  normal → hard_stopped → (resume) → normal
  soft_stopped → hard_stopped → (resume) → normal

hard_stop은 confirm=True 플래그 필수.
인메모리 상태 — 서버 재시작 시 초기화됨 (단기 보호 목적).
"""

import uuid
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)


class KillSwitchStatus(StrEnum):
    """KillSwitch 상태."""

    NORMAL = "normal"
    SOFT_STOPPED = "soft_stopped"
    HARD_STOPPED = "hard_stopped"


# 사용자별 상태 저장 (인메모리)
_kill_switch_states: dict[uuid.UUID, KillSwitchStatus] = {}


class KillSwitch:
    """사용자 수준 수동 매매 중단/긴급 청산 컨트롤.

    soft_stop: 신규 매수 중단, 보유분은 전략대로 청산.
    hard_stop: 즉시 전량 시장가 청산 + 매매 완전 중단.
    resume: 정상 상태로 복귀.
    get_status: 현재 상태 조회.
    """

    def soft_stop(self, user_id: uuid.UUID) -> KillSwitchStatus:
        """신규 매수를 중단한다. 보유분은 전략대로 청산 가능.

        Args:
            user_id: 대상 사용자 ID

        Returns:
            갱신된 상태 (SOFT_STOPPED)
        """
        current = _kill_switch_states.get(user_id, KillSwitchStatus.NORMAL)
        if current == KillSwitchStatus.HARD_STOPPED:
            logger.warning(
                "KillSwitch: HARD_STOPPED 상태에서 soft_stop 무시",
                user_id=str(user_id),
            )
            return current

        _kill_switch_states[user_id] = KillSwitchStatus.SOFT_STOPPED
        logger.warning(
            "KillSwitch: soft_stop 활성화 — 신규 매수 중단",
            user_id=str(user_id),
        )
        return KillSwitchStatus.SOFT_STOPPED

    def hard_stop(self, user_id: uuid.UUID, *, confirm: bool = False) -> KillSwitchStatus:
        """전량 시장가 청산 + 매매 완전 중단.

        Args:
            user_id: 대상 사용자 ID
            confirm: 확인 플래그 (True 필수 — 실수 방지)

        Returns:
            갱신된 상태 (HARD_STOPPED)

        Raises:
            ValueError: confirm=False 시 실행 거부
        """
        if not confirm:
            raise ValueError("hard_stop은 confirm=True 필수 (긴급 청산은 되돌릴 수 없습니다)")

        _kill_switch_states[user_id] = KillSwitchStatus.HARD_STOPPED
        logger.critical(
            "KillSwitch: hard_stop 활성화 — 전량 청산 + 매매 중단",
            user_id=str(user_id),
        )
        return KillSwitchStatus.HARD_STOPPED

    def resume(self, user_id: uuid.UUID) -> KillSwitchStatus:
        """KillSwitch를 해제하고 정상 상태로 복귀한다.

        Args:
            user_id: 대상 사용자 ID

        Returns:
            갱신된 상태 (NORMAL)
        """
        _kill_switch_states[user_id] = KillSwitchStatus.NORMAL
        logger.info(
            "KillSwitch: resume — 정상 매매 복귀",
            user_id=str(user_id),
        )
        return KillSwitchStatus.NORMAL

    def get_status(self, user_id: uuid.UUID) -> KillSwitchStatus:
        """현재 KillSwitch 상태를 반환한다.

        Args:
            user_id: 대상 사용자 ID

        Returns:
            현재 상태 (기본값: NORMAL)
        """
        return _kill_switch_states.get(user_id, KillSwitchStatus.NORMAL)


# 싱글턴 인스턴스 (앱 전역 사용)
kill_switch = KillSwitch()


# ── 하위 호환 헬퍼 (bot.py에서 사용 중) ──────────────────


def activate_manual_kill(user_id: uuid.UUID) -> None:
    """수동 킬스위치 활성화 (하위 호환 — soft_stop과 동일)."""
    kill_switch.soft_stop(user_id)


def deactivate_manual_kill(user_id: uuid.UUID) -> None:
    """수동 킬스위치 해제 (하위 호환 — resume과 동일)."""
    kill_switch.resume(user_id)
