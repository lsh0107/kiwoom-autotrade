"""리스크 관리 — HWM 드로우다운, 종목 쿨다운, 레짐별 포지션 한도.

drawdown_guard.py의 기존 3단계 주문 검증과 병행 동작:
- risk_manager: HWM 기반 드로우다운 (YELLOW/ORANGE/RED), 쿨다운, 레짐 가드
- drawdown_guard: Level 1/2/3 주문 검증 (기존 유지)

주요 변경사항 (drawdown_guard 대비):
- 드로우다운 기준: daily_start → HWM (장중 회복 후 재활성화 방지)
- 3단계 (기존 2단계): YELLOW(-2%) / ORANGE(-4%) / RED(-6%)
- RED 발동 시 hard_stopped_today=True — 당일 재개 불가
"""

from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

import structlog

from src.trading.market_regime import MarketRegime
from src.utils.time import now_kst, today_kst

logger = structlog.get_logger(__name__)


# ── 상수 ────────────────────────────────────────────────────────────

# HWM 기반 드로우다운 임계값 (HWM 대비 %)
HWM_YELLOW_PCT: float = -2.0  # Yellow: max_positions=1, 쿨다운 강제
HWM_ORANGE_PCT: float = -4.0  # Orange: 신규 매수 완전 중단
HWM_RED_PCT: float = -6.0  # Red: 전량 청산 + 당일 HARD_STOPPED

# 주간 scale_factor 축소 임계값 (-4% 도달 시 익주 0.5 적용)
WEEKLY_SCALE_THRESHOLD_PCT: float = -4.0
WEEKLY_SCALE_REDUCED: float = 0.5

# 종목 쿨다운
SYMBOL_COOLDOWN_MINUTES: int = 30  # 청산 후 재진입 금지 시간 (분)
SYMBOL_MAX_ENTRIES_PER_DAY: int = 3  # 당일 동일 심볼 최대 진입 횟수

# 레짐별 max_positions 하드 가드
REGIME_MAX_POSITIONS: dict[str, int] = {
    "aggressive": 5,
    "neutral": 3,
    "defensive": 1,
    "crisis": 0,
}

# 기본 리스크 파라미터 (position_sizer 기본값 하향)
DEFAULT_RISK_PCT: float = 0.01  # 종목당 리스크 비율 (0.03 → 0.01)
DEFAULT_MAX_POSITION_PCT: float = 0.05  # 종목당 최대 포지션 비율 (0.15 → 0.05)

# 영속화 파일
_RISK_STATE_FILE = (
    Path(__file__).resolve().parent.parent.parent / "data" / ".risk_manager_state.json"
)


# ── DrawdownLevel ────────────────────────────────────────────────────


class DrawdownLevel(StrEnum):
    """HWM 기반 드로우다운 레벨.

    장중 고점(HWM) 대비 하락률로 판정한다.
    기존 drawdown_guard는 당일 시작값 대비 — 장중 회복 후 임계값 재진입 시
    재활성화되는 문제가 있어 HWM 기준으로 교체.
    """

    NORMAL = "normal"
    YELLOW = "yellow"  # HWM -2%: max_positions=1, 쿨다운 30분
    ORANGE = "orange"  # HWM -4%: 신규 매수 완전 중단
    RED = "red"  # HWM -6%: 전량 청산 + 당일 재개 불가


# ── HWM 상태 ─────────────────────────────────────────────────────────


@dataclass
class _HWMState:
    """사용자별 HWM 드로우다운 내부 상태."""

    user_id: uuid.UUID
    hwm: int = 0  # 당일 최고 평가액 (High-Water Mark)
    daily_start_value: int = 0  # 당일 시작값 (초기화 판단용)
    current_drawdown_pct: float = 0.0  # HWM 대비 현재 드로우다운 (%)
    level: DrawdownLevel = DrawdownLevel.NORMAL
    hard_stopped_today: bool = False  # RED 발동 시 당일 재개 불가 플래그
    last_reset: datetime = field(default_factory=now_kst)

    # 주간 추적
    week_start_value: int = 0
    weekly_loss_pct: float = 0.0
    next_week_scale_factor: float = 1.0  # 익주 적용 scale_factor
    last_week_reset: datetime = field(default_factory=now_kst)


def _state_to_dict(s: _HWMState) -> dict:
    """_HWMState → JSON 직렬화 가능 dict."""
    return {
        "user_id": str(s.user_id),
        "hwm": s.hwm,
        "daily_start_value": s.daily_start_value,
        "current_drawdown_pct": s.current_drawdown_pct,
        "level": s.level,
        "hard_stopped_today": s.hard_stopped_today,
        "last_reset": s.last_reset.isoformat(),
        "week_start_value": s.week_start_value,
        "weekly_loss_pct": s.weekly_loss_pct,
        "next_week_scale_factor": s.next_week_scale_factor,
        "last_week_reset": s.last_week_reset.isoformat(),
    }


def _dict_to_state(d: dict) -> _HWMState:
    """dict → _HWMState 복원."""
    return _HWMState(
        user_id=uuid.UUID(d["user_id"]),
        hwm=d.get("hwm", 0),
        daily_start_value=d.get("daily_start_value", 0),
        current_drawdown_pct=d.get("current_drawdown_pct", 0.0),
        level=DrawdownLevel(d.get("level", "normal")),
        hard_stopped_today=d.get("hard_stopped_today", False),
        last_reset=datetime.fromisoformat(d["last_reset"]),
        week_start_value=d.get("week_start_value", 0),
        weekly_loss_pct=d.get("weekly_loss_pct", 0.0),
        next_week_scale_factor=d.get("next_week_scale_factor", 1.0),
        last_week_reset=datetime.fromisoformat(d["last_week_reset"]),
    )


# ── HWMDrawdownGuard ─────────────────────────────────────────────────


class HWMDrawdownGuard:
    """HWM(고점) 기반 3단계 드로우다운 가드.

    기존 drawdown_guard.py의 daily_start 대비 계산을 HWM 대비로 교체.
    파일 기반 영속화 — 서버 재시작 후에도 상태 유지.

    레벨별 조치:
        YELLOW (-2%): max_positions=1 강제, 쿨다운 30분
        ORANGE (-4%): STOP_BUY — 신규 매수 완전 중단
        RED    (-6%): 전량 청산 + hard_stopped_today=True (당일 재개 불가)
    """

    def __init__(self) -> None:
        self._states: dict[uuid.UUID, _HWMState] = self._load()

    def _load(self) -> dict[uuid.UUID, _HWMState]:
        if not _RISK_STATE_FILE.exists():
            return {}
        try:
            raw = json.loads(_RISK_STATE_FILE.read_text())
            return {uuid.UUID(k): _dict_to_state(v) for k, v in raw.items()}
        except Exception:
            logger.warning("HWMDrawdownGuard 상태 파일 로드 실패, 초기화")
            return {}

    def _save(self) -> None:
        try:
            _RISK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps({str(k): _state_to_dict(v) for k, v in self._states.items()})
            fd, tmp = tempfile.mkstemp(dir=_RISK_STATE_FILE.parent, suffix=".tmp")
            try:
                with open(fd, "w") as f:
                    f.write(data)
                Path(tmp).replace(_RISK_STATE_FILE)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        except Exception:
            logger.warning("HWMDrawdownGuard 상태 파일 저장 실패")

    def _get_state(self, user_id: uuid.UUID) -> _HWMState:
        if user_id not in self._states:
            self._states[user_id] = _HWMState(user_id=user_id)

        state = self._states[user_id]
        today = today_kst()

        # 날짜 변경 시 일간 데이터 리셋 (hard_stopped_today 포함)
        if state.last_reset.date() < today.date():
            state.hwm = 0
            state.daily_start_value = 0
            state.current_drawdown_pct = 0.0
            state.level = DrawdownLevel.NORMAL
            state.hard_stopped_today = False
            state.last_reset = today
            self._save()

        # 주 변경 시 주간 데이터 리셋
        current_week = today.date().isocalendar()[:2]
        last_week = state.last_week_reset.date().isocalendar()[:2]
        if current_week != last_week:
            state.week_start_value = 0
            state.weekly_loss_pct = 0.0
            state.last_week_reset = today
            self._save()

        return state

    def update(self, user_id: uuid.UUID, current_value: int) -> DrawdownLevel:
        """평가액 기반 HWM 드로우다운 레벨 갱신.

        Args:
            user_id: 사용자 ID
            current_value: 현재 총 평가액 (보유종목 평가 + 현금)

        Returns:
            DrawdownLevel: 현재 드로우다운 레벨
        """
        state = self._get_state(user_id)

        # 시작값 초기화 (당일 첫 호출)
        if state.daily_start_value == 0:
            state.daily_start_value = current_value
            state.hwm = current_value
            self._save()
            return DrawdownLevel.NORMAL

        # HWM 갱신 (평가액이 상승하면 고점 갱신)
        if current_value > state.hwm:
            state.hwm = current_value

        # HWM 대비 드로우다운 계산
        if state.hwm > 0:
            state.current_drawdown_pct = (current_value - state.hwm) / state.hwm * 100
        else:
            state.current_drawdown_pct = 0.0

        # 주간 손실률 추적
        if state.week_start_value == 0:
            state.week_start_value = current_value
        elif state.week_start_value > 0:
            state.weekly_loss_pct = (
                (current_value - state.week_start_value) / state.week_start_value * 100
            )
            if (
                state.weekly_loss_pct <= WEEKLY_SCALE_THRESHOLD_PCT
                and state.next_week_scale_factor > WEEKLY_SCALE_REDUCED
            ):
                state.next_week_scale_factor = WEEKLY_SCALE_REDUCED
                logger.warning(
                    "주간 손실 -4%% 도달 → 익주 scale_factor 0.5 예약",
                    user_id=str(user_id),
                    weekly_loss_pct=state.weekly_loss_pct,
                )

        # RED 발동 후 당일은 레벨 유지 (복구 불가)
        if state.hard_stopped_today:
            state.level = DrawdownLevel.RED
            self._save()
            return DrawdownLevel.RED

        # 3단계 레벨 판정
        if state.current_drawdown_pct <= HWM_RED_PCT:
            state.level = DrawdownLevel.RED
            state.hard_stopped_today = True
            logger.critical(
                "HWM 드로우다운 RED 발동 — 전량 청산 + 당일 재개 불가",
                user_id=str(user_id),
                drawdown_pct=round(state.current_drawdown_pct, 2),
                hwm=state.hwm,
                current_value=current_value,
            )
        elif state.current_drawdown_pct <= HWM_ORANGE_PCT:
            state.level = DrawdownLevel.ORANGE
            logger.warning(
                "HWM 드로우다운 ORANGE — 신규 매수 중단",
                user_id=str(user_id),
                drawdown_pct=round(state.current_drawdown_pct, 2),
            )
        elif state.current_drawdown_pct <= HWM_YELLOW_PCT:
            state.level = DrawdownLevel.YELLOW
            logger.warning(
                "HWM 드로우다운 YELLOW — max_positions=1, 쿨다운 30분",
                user_id=str(user_id),
                drawdown_pct=round(state.current_drawdown_pct, 2),
            )
        else:
            state.level = DrawdownLevel.NORMAL

        self._save()
        return state.level

    def get_level(self, user_id: uuid.UUID) -> DrawdownLevel:
        """현재 드로우다운 레벨 조회 (평가액 갱신 없음).

        Args:
            user_id: 사용자 ID

        Returns:
            DrawdownLevel: 현재 레벨
        """
        return self._get_state(user_id).level

    def is_hard_stopped(self, user_id: uuid.UUID) -> bool:
        """당일 RED 발동 여부 조회.

        Args:
            user_id: 사용자 ID

        Returns:
            True이면 당일 거래 재개 불가
        """
        return self._get_state(user_id).hard_stopped_today

    def get_next_week_scale_factor(self, user_id: uuid.UUID) -> float:
        """익주 scale_factor 조회.

        Returns:
            float: 1.0 (정상) 또는 0.5 (주간 -4% 이하 도달 시)
        """
        return self._get_state(user_id).next_week_scale_factor

    def get_max_positions_by_level(self, level: DrawdownLevel) -> int:
        """드로우다운 레벨별 max_positions 하드 가드.

        Args:
            level: 현재 드로우다운 레벨

        Returns:
            int: 허용 최대 포지션 수
        """
        mapping: dict[DrawdownLevel, int] = {
            DrawdownLevel.NORMAL: REGIME_MAX_POSITIONS.get("neutral", 3),
            DrawdownLevel.YELLOW: 1,
            DrawdownLevel.ORANGE: 0,
            DrawdownLevel.RED: 0,
        }
        return mapping[level]


# ── SymbolCooldownTracker ────────────────────────────────────────────


class SymbolCooldownTracker:
    """종목별 재진입 쿨다운 및 당일 진입 횟수 추적.

    - 청산 후 30분 이내 재진입 차단 (whipsaw 방지)
    - 당일 동일 심볼 최대 3회 진입 제한

    세션 내 메모리만 유지 (서버 재시작 시 리셋 — 쿨다운은 단기 보호).
    """

    def __init__(self) -> None:
        self._last_exit_times: dict[str, datetime] = {}
        self._daily_counts: dict[str, int] = {}
        self._last_reset_date = now_kst().date()

    def _reset_if_new_day(self) -> None:
        today = now_kst().date()
        if today != self._last_reset_date:
            self._last_exit_times.clear()
            self._daily_counts.clear()
            self._last_reset_date = today

    def record_exit(self, symbol: str) -> None:
        """청산 시각 기록 — 쿨다운 시작.

        Args:
            symbol: 종목코드
        """
        self._reset_if_new_day()
        self._last_exit_times[symbol] = now_kst()
        logger.info(
            "쿨다운 시작: %s (%d분 재진입 금지)",
            symbol,
            SYMBOL_COOLDOWN_MINUTES,
        )

    def record_entry(self, symbol: str) -> None:
        """진입 횟수 기록.

        Args:
            symbol: 종목코드
        """
        self._reset_if_new_day()
        self._daily_counts[symbol] = self._daily_counts.get(symbol, 0) + 1

    def can_enter(self, symbol: str) -> bool:
        """진입 가능 여부 확인.

        Args:
            symbol: 종목코드

        Returns:
            False: 쿨다운 중이거나 당일 진입 한도 초과
        """
        self._reset_if_new_day()

        # 당일 진입 횟수 체크
        if self._daily_counts.get(symbol, 0) >= SYMBOL_MAX_ENTRIES_PER_DAY:
            logger.info(
                "[%s] 당일 진입 한도 %d회 초과 → 스킵",
                symbol,
                SYMBOL_MAX_ENTRIES_PER_DAY,
            )
            return False

        # 쿨다운 체크
        last_exit = self._last_exit_times.get(symbol)
        if last_exit is not None:
            elapsed = now_kst() - last_exit
            if elapsed < timedelta(minutes=SYMBOL_COOLDOWN_MINUTES):
                remaining = SYMBOL_COOLDOWN_MINUTES - int(elapsed.total_seconds() / 60)
                logger.info(
                    "[%s] 쿨다운 중 (잔여 %d분) → 스킵",
                    symbol,
                    remaining,
                )
                return False

        return True

    def get_daily_count(self, symbol: str) -> int:
        """당일 진입 횟수 조회.

        Args:
            symbol: 종목코드

        Returns:
            int: 당일 진입 횟수
        """
        self._reset_if_new_day()
        return self._daily_counts.get(symbol, 0)


# ── 레짐별 max_positions ─────────────────────────────────────────────


def get_regime_max_positions(regime: MarketRegime) -> int:
    """레짐별 max_positions 하드 가드.

    CRISIS에서 max_positions=0 강제 — 진입 시도 자체를 차단.

    Args:
        regime: 현재 시장 레짐

    Returns:
        int: 허용 최대 포지션 수
    """
    return REGIME_MAX_POSITIONS.get(regime.value, 3)


# ── 싱글턴 ───────────────────────────────────────────────────────────

hwm_guard = HWMDrawdownGuard()
cooldown_tracker = SymbolCooldownTracker()
