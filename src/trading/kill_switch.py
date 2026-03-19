"""KillSwitch — 사용자 수준 수동 매매 중단/청산 컨트롤.

상태 전이:
  normal → soft_stopped → (resume) → normal
  normal → hard_stopped → (resume) → normal
  soft_stopped → hard_stopped → (resume) → normal

hard_stop은 confirm=True 플래그 필수.
파일 기반 영속화 — 서버 재시작 후에도 상태 유지.
"""

import json
import tempfile
import uuid
from enum import StrEnum
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# 영속화 파일 경로
_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / ".kill_switch_state.json"


class KillSwitchStatus(StrEnum):
    """KillSwitch 상태."""

    NORMAL = "normal"
    SOFT_STOPPED = "soft_stopped"
    HARD_STOPPED = "hard_stopped"


def _load_states() -> dict[uuid.UUID, KillSwitchStatus]:
    """파일에서 상태 로드."""
    if not _STATE_FILE.exists():
        return {}
    try:
        data = json.loads(_STATE_FILE.read_text())
        return {uuid.UUID(k): KillSwitchStatus(v) for k, v in data.items()}
    except Exception:
        logger.warning("KillSwitch 상태 파일 로드 실패, 초기화")
        return {}


def _save_states(states: dict[uuid.UUID, KillSwitchStatus]) -> None:
    """파일에 상태 저장 (atomic write: 임시 파일 → rename)."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps({str(k): v.value for k, v in states.items()})
        # 임시 파일에 쓰고 rename — 중간 크래시 시 파일 손상 방지
        fd, tmp_path = tempfile.mkstemp(dir=_STATE_FILE.parent, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                f.write(data)
            Path(tmp_path).replace(_STATE_FILE)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise
    except Exception:
        logger.warning("KillSwitch 상태 파일 저장 실패")


# 사용자별 상태 저장 (파일 기반 영속화)
_kill_switch_states: dict[uuid.UUID, KillSwitchStatus] = _load_states()


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
        _save_states(_kill_switch_states)
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
        _save_states(_kill_switch_states)
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
        _save_states(_kill_switch_states)
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
    """수동 킬스위치 활성화 — KillSwitch + DrawdownGuard 양쪽 동기화."""
    from src.trading.drawdown_guard import get_user_state

    kill_switch.soft_stop(user_id)
    state = get_user_state(user_id)
    state.manual_kill = True


def deactivate_manual_kill(user_id: uuid.UUID) -> None:
    """수동 킬스위치 해제 — KillSwitch + DrawdownGuard 양쪽 동기화."""
    from src.trading.drawdown_guard import get_user_state

    kill_switch.resume(user_id)
    state = get_user_state(user_id)
    state.manual_kill = False
