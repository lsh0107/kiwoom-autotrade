"""KillSwitch — 사용자 수준 수동/자동 매매 중단/청산 컨트롤.

상태 전이:
  normal → soft_stopped → (resume) → normal
  normal → hard_stopped → (resume) → normal
  soft_stopped → hard_stopped → (resume) → normal

hard_stop은 confirm=True 플래그 필수.
파일 기반 영속화 — 서버 재시작 후에도 상태 유지.

AutoKillSwitchMonitor — 3종 자동 트리거:
  1. 동일 종목 3회 연속 손절 → SOFT_STOP
  2. 10분 슬라이딩 윈도우 내 누적 실현 PnL -1.5% → SOFT_STOP
  3. 일일 주문 건수 40건 초과 → SOFT_STOP, 60건 → HARD_STOP
"""

import json
import tempfile
import uuid
from datetime import UTC, date, datetime, timedelta
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


# ── AutoKillSwitchMonitor ────────────────────────────────────────────


class AutoKillSwitchMonitor:
    """자동 kill_switch 발동 모니터 — 3종 트리거.

    1. 동일 종목 3회 연속 손절 → SOFT_STOP 자동 발동
    2. 10분 슬라이딩 윈도우 내 누적 실현 PnL -1.5% → SOFT_STOP
    3. 일일 주문 건수 40건 초과 → SOFT_STOP, 60건 → HARD_STOP

    세션 내 메모리 유지 (영속화 없음 — 일중 보호 목적).
    """

    # 트리거 임계값
    CONSECUTIVE_LOSS_LIMIT: int = 3  # 동일 종목 연속 손절 허용 횟수
    SLIDING_PNL_THRESHOLD: float = -0.015  # 슬라이딩 윈도우 PnL 임계값 (-1.5%)
    SLIDING_WINDOW_MINUTES: int = 10  # 슬라이딩 윈도우 크기 (분)
    SOFT_STOP_ORDER_LIMIT: int = 40  # SOFT_STOP 주문 한도 (건)
    HARD_STOP_ORDER_LIMIT: int = 60  # HARD_STOP 주문 한도 (건)

    def __init__(self) -> None:
        self._consecutive_losses: dict[str, int] = {}  # symbol → 연속 손절 횟수
        self._pnl_window: list[tuple[datetime, float]] = []  # (UTC시각, 손익률)
        self._daily_order_count: int = 0
        self._last_order_reset_date: date | None = None

    def _reset_if_new_day(self) -> None:
        today = datetime.now(tz=UTC).date()
        if self._last_order_reset_date != today:
            self._daily_order_count = 0
            self._consecutive_losses.clear()
            self._pnl_window.clear()
            self._last_order_reset_date = today

    def _prune_window(self) -> None:
        """10분 경과 PnL 이벤트 제거."""
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=self.SLIDING_WINDOW_MINUTES)
        self._pnl_window = [(t, p) for t, p in self._pnl_window if t > cutoff]

    def record_trade(
        self,
        user_id: uuid.UUID,
        symbol: str,
        pnl_pct: float,
    ) -> KillSwitchStatus:
        """청산 후 손익 기록 및 자동 kill_switch 판정.

        Args:
            user_id: 사용자 ID
            symbol: 종목코드
            pnl_pct: 청산 순손익률 (음수=손실)

        Returns:
            현재 KillSwitch 상태
        """
        self._reset_if_new_day()

        current_status = kill_switch.get_status(user_id)
        if current_status != KillSwitchStatus.NORMAL:
            return current_status

        # 트리거 1: 동일 종목 연속 손절 체크
        if pnl_pct < 0:
            self._consecutive_losses[symbol] = self._consecutive_losses.get(symbol, 0) + 1
            count = self._consecutive_losses[symbol]
            if count >= self.CONSECUTIVE_LOSS_LIMIT:
                logger.warning(
                    "AutoKillSwitch: 동일 종목 %d연속 손절 → SOFT_STOP",
                    count,
                    symbol=symbol,
                    user_id=str(user_id),
                )
                return kill_switch.soft_stop(user_id)
        else:
            self._consecutive_losses[symbol] = 0

        # 트리거 2: 10분 슬라이딩 윈도우 PnL 체크
        now_utc = datetime.now(tz=UTC)
        self._pnl_window.append((now_utc, pnl_pct))
        self._prune_window()
        sliding_pnl = sum(p for _, p in self._pnl_window)
        if sliding_pnl <= self.SLIDING_PNL_THRESHOLD:
            logger.warning(
                "AutoKillSwitch: 10분 슬라이딩 PnL %.2f%% → SOFT_STOP",
                sliding_pnl * 100,
                window_trades=len(self._pnl_window),
                user_id=str(user_id),
            )
            return kill_switch.soft_stop(user_id)

        return current_status

    def record_order(self, user_id: uuid.UUID) -> KillSwitchStatus:
        """주문 발생 시 일일 주문 건수 체크 및 자동 kill_switch 판정.

        Args:
            user_id: 사용자 ID

        Returns:
            현재 KillSwitch 상태
        """
        self._reset_if_new_day()
        self._daily_order_count += 1
        count = self._daily_order_count

        current_status = kill_switch.get_status(user_id)
        if current_status == KillSwitchStatus.HARD_STOPPED:
            return current_status

        # 트리거 3-b: HARD_STOP (60건 초과)
        if count > self.HARD_STOP_ORDER_LIMIT:
            logger.critical(
                "AutoKillSwitch: 일일 주문 %d건 초과 → HARD_STOP",
                count,
                user_id=str(user_id),
            )
            return kill_switch.hard_stop(user_id, confirm=True)

        # 트리거 3-a: SOFT_STOP (40건 초과)
        if count > self.SOFT_STOP_ORDER_LIMIT and current_status == KillSwitchStatus.NORMAL:
            logger.warning(
                "AutoKillSwitch: 일일 주문 %d건 초과 → SOFT_STOP",
                count,
                user_id=str(user_id),
            )
            return kill_switch.soft_stop(user_id)

        return current_status

    def get_daily_order_count(self) -> int:
        """당일 주문 건수 조회.

        Returns:
            int: 당일 누적 주문 건수
        """
        self._reset_if_new_day()
        return self._daily_order_count

    def reset_for_test(self) -> None:
        """테스트 전용 상태 초기화."""
        self._consecutive_losses.clear()
        self._pnl_window.clear()
        self._daily_order_count = 0
        self._last_order_reset_date = None


# 싱글턴 (앱 전역 사용)
auto_kill_monitor = AutoKillSwitchMonitor()
