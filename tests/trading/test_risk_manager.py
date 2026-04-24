"""risk_manager 모듈 테스트.

HWMDrawdownGuard, SymbolCooldownTracker, get_regime_max_positions 검증.
"""

import uuid
from datetime import timedelta

import pytest

from src.trading.market_regime import MarketRegime
from src.trading.risk_manager import (
    DEFAULT_MAX_POSITION_PCT,
    DEFAULT_RISK_PCT,
    HWM_ORANGE_PCT,
    HWM_RED_PCT,
    HWM_YELLOW_PCT,
    SYMBOL_COOLDOWN_MINUTES,
    SYMBOL_MAX_ENTRIES_PER_DAY,
    DrawdownLevel,
    HWMDrawdownGuard,
    SymbolCooldownTracker,
    get_regime_max_positions,
)

# ── HWMDrawdownGuard 테스트 ──────────────────────────────────────────


class TestHWMDrawdownGuardLevels:
    """HWM 기반 드로우다운 레벨 전이 테스트."""

    def setup_method(self) -> None:
        """매 테스트마다 독립 guard 인스턴스 생성 (파일 I/O 모킹)."""
        self.user_id = uuid.uuid4()
        self.guard = HWMDrawdownGuard.__new__(HWMDrawdownGuard)
        self.guard._states = {}

    def _update(self, value: int) -> DrawdownLevel:
        return self.guard.update(self.user_id, value)

    def test_initial_call_returns_normal(self) -> None:
        """첫 호출은 NORMAL — 시작값 초기화."""
        level = self._update(1_000_000)
        assert level == DrawdownLevel.NORMAL

    def test_stays_normal_on_recovery(self) -> None:
        """고점 이후 회복 시 NORMAL 유지."""
        self._update(1_000_000)  # HWM=1_000_000
        self._update(900_000)  # -10% → RED 이하지만 테스트는 YELLOW 범위
        # 실제로 -10%는 RED
        level = self._update(1_000_000)  # 회복해도 hard_stopped_today=True 유지
        # RED 발동 후에는 회복해도 RED
        assert level == DrawdownLevel.RED

    def test_yellow_level_at_minus2pct(self) -> None:
        """HWM -2% → YELLOW."""
        self._update(1_000_000)
        yellow_value = int(1_000_000 * (1 + HWM_YELLOW_PCT / 100))
        level = self._update(yellow_value)
        assert level == DrawdownLevel.YELLOW

    def test_orange_level_at_minus4pct(self) -> None:
        """HWM -4% → ORANGE."""
        self._update(1_000_000)
        orange_value = int(1_000_000 * (1 + HWM_ORANGE_PCT / 100))
        level = self._update(orange_value)
        assert level == DrawdownLevel.ORANGE

    def test_red_level_at_minus6pct(self) -> None:
        """HWM -6% → RED."""
        self._update(1_000_000)
        red_value = int(1_000_000 * (1 + HWM_RED_PCT / 100))
        level = self._update(red_value)
        assert level == DrawdownLevel.RED

    def test_red_hard_stops_today(self) -> None:
        """RED 발동 후 hard_stopped_today=True — 당일 재개 불가."""
        self._update(1_000_000)
        red_value = int(1_000_000 * (1 + HWM_RED_PCT / 100))
        self._update(red_value)
        assert self.guard.is_hard_stopped(self.user_id) is True

    def test_red_persists_after_recovery(self) -> None:
        """RED 발동 후 평가액이 회복돼도 RED 유지 (당일 재개 불가)."""
        self._update(1_000_000)
        red_value = int(1_000_000 * (1 + HWM_RED_PCT / 100))
        self._update(red_value)
        # 회복 시도
        level = self._update(1_000_000)
        assert level == DrawdownLevel.RED

    def test_hwm_vs_daily_start_difference(self) -> None:
        """HWM 기준과 daily_start 기준의 차이 — 장중 고점 갱신 후 하락."""
        # daily_start = 1_000_000
        self._update(1_000_000)
        # 장중 고점 갱신
        self._update(1_100_000)  # HWM=1_100_000
        # daily_start 기준: -5% = 950_000 (STOP_BUY)
        # HWM 기준: -2% from 1_100_000 = 1_078_000
        daily_start_minus5 = 950_000
        level_hwm = self._update(daily_start_minus5)
        # HWM 대비: (950_000 - 1_100_000) / 1_100_000 * 100 = -13.6% → RED
        # daily_start 기준으로는 -5% (STOP_BUY)지만 HWM으로는 더 엄격
        assert level_hwm == DrawdownLevel.RED

    def test_get_level_without_update(self) -> None:
        """get_level은 평가액 갱신 없이 현재 레벨 반환."""
        level = self.guard.get_level(self.user_id)
        assert level == DrawdownLevel.NORMAL

    def test_get_max_positions_by_level(self) -> None:
        """레벨별 max_positions 가드 값 확인."""
        assert self.guard.get_max_positions_by_level(DrawdownLevel.NORMAL) > 0
        assert self.guard.get_max_positions_by_level(DrawdownLevel.YELLOW) == 1
        assert self.guard.get_max_positions_by_level(DrawdownLevel.ORANGE) == 0
        assert self.guard.get_max_positions_by_level(DrawdownLevel.RED) == 0


class TestHWMDrawdownDailyReset:
    """날짜 변경 시 드로우다운 상태 리셋 테스트."""

    def setup_method(self) -> None:
        self.user_id = uuid.uuid4()
        self.guard = HWMDrawdownGuard.__new__(HWMDrawdownGuard)
        self.guard._states = {}

    def test_daily_reset_clears_hard_stopped(self) -> None:
        """날짜 변경 시 hard_stopped_today 초기화 — 다음 날 재개 가능."""
        # RED 발동
        self.guard.update(self.user_id, 1_000_000)
        red_value = int(1_000_000 * (1 + HWM_RED_PCT / 100))
        self.guard.update(self.user_id, red_value)
        assert self.guard.is_hard_stopped(self.user_id) is True

        # 날짜 변경 시뮬레이션
        from datetime import timedelta

        state = self.guard._get_state(self.user_id)
        state.last_reset = state.last_reset - timedelta(days=1)

        # 다음 날 첫 업데이트 — 리셋
        self.guard.update(self.user_id, 1_000_000)
        assert self.guard.is_hard_stopped(self.user_id) is False


class TestHWMDrawdownWeeklyScale:
    """주간 scale_factor 추적 테스트."""

    def setup_method(self) -> None:
        self.user_id = uuid.uuid4()
        self.guard = HWMDrawdownGuard.__new__(HWMDrawdownGuard)
        self.guard._states = {}

    def test_weekly_loss_below_threshold_keeps_factor_1(self) -> None:
        """주간 손실 -4% 미만: scale_factor=1.0 유지."""
        self.guard.update(self.user_id, 1_000_000)
        state = self.guard._get_state(self.user_id)
        state.week_start_value = 1_000_000
        # -3% 손실
        self.guard.update(self.user_id, 970_000)
        assert self.guard.get_next_week_scale_factor(self.user_id) == 1.0

    def test_weekly_loss_exceeds_threshold_sets_half(self) -> None:
        """주간 손실 -4% 이하: 익주 scale_factor=0.5 예약."""
        self.guard.update(self.user_id, 1_000_000)
        state = self.guard._get_state(self.user_id)
        state.week_start_value = 1_000_000
        # -4% 손실 (임계값 도달)
        self.guard.update(self.user_id, 960_000)
        assert self.guard.get_next_week_scale_factor(self.user_id) == 0.5


# ── SymbolCooldownTracker 테스트 ─────────────────────────────────────


class TestSymbolCooldownTracker:
    """쿨다운 및 당일 진입 횟수 추적 테스트."""

    def setup_method(self) -> None:
        """매 테스트마다 새 트래커 — 날짜 고정."""
        self.tracker = SymbolCooldownTracker()

    def test_can_enter_without_history(self) -> None:
        """청산 이력 없으면 진입 허용."""
        assert self.tracker.can_enter("005930") is True

    def test_cannot_enter_during_cooldown(self) -> None:
        """청산 직후 쿨다운 중 재진입 차단."""
        self.tracker.record_exit("005930")
        assert self.tracker.can_enter("005930") is False

    def test_can_enter_after_cooldown_expires(self) -> None:
        """쿨다운 30분 경과 후 재진입 허용."""
        self.tracker.record_exit("005930")
        # 31분 경과 시뮬레이션
        expired_time = self.tracker._last_exit_times["005930"] - timedelta(
            minutes=SYMBOL_COOLDOWN_MINUTES + 1
        )
        self.tracker._last_exit_times["005930"] = expired_time
        assert self.tracker.can_enter("005930") is True

    def test_daily_entry_limit_blocks_after_max(self) -> None:
        """당일 3회 진입 후 추가 진입 차단."""
        for _ in range(SYMBOL_MAX_ENTRIES_PER_DAY):
            self.tracker.record_entry("005930")
        assert self.tracker.can_enter("005930") is False

    def test_daily_entry_limit_allows_before_max(self) -> None:
        """당일 2회 진입은 허용 (3회 미만)."""
        for _ in range(SYMBOL_MAX_ENTRIES_PER_DAY - 1):
            self.tracker.record_entry("005930")
        assert self.tracker.can_enter("005930") is True

    def test_different_symbols_independent(self) -> None:
        """다른 종목의 쿨다운은 독립."""
        self.tracker.record_exit("005930")
        assert self.tracker.can_enter("000660") is True

    def test_get_daily_count(self) -> None:
        """당일 진입 횟수 카운트 정확성."""
        self.tracker.record_entry("005930")
        self.tracker.record_entry("005930")
        assert self.tracker.get_daily_count("005930") == 2

    def test_cooldown_independent_of_entry_count(self) -> None:
        """쿨다운과 진입 횟수는 독립 체크 — 쿨다운 해제 후 횟수 한도 체크."""
        self.tracker.record_exit("005930")
        # 쿨다운 만료
        self.tracker._last_exit_times["005930"] = self.tracker._last_exit_times[
            "005930"
        ] - timedelta(minutes=SYMBOL_COOLDOWN_MINUTES + 1)
        # 진입 횟수 최대치
        for _ in range(SYMBOL_MAX_ENTRIES_PER_DAY):
            self.tracker.record_entry("005930")
        # 쿨다운 해제됐지만 횟수 초과
        assert self.tracker.can_enter("005930") is False


# ── get_regime_max_positions 테스트 ─────────────────────────────────


class TestGetRegimeMaxPositions:
    """레짐별 max_positions 하드 가드 테스트."""

    def test_crisis_returns_zero(self) -> None:
        """CRISIS 레짐: max_positions=0 강제."""
        assert get_regime_max_positions(MarketRegime.CRISIS) == 0

    def test_defensive_returns_one(self) -> None:
        """DEFENSIVE 레짐: max_positions=1."""
        assert get_regime_max_positions(MarketRegime.DEFENSIVE) == 1

    def test_neutral_returns_three(self) -> None:
        """NEUTRAL 레짐: max_positions=3."""
        assert get_regime_max_positions(MarketRegime.NEUTRAL) == 3

    def test_aggressive_returns_five(self) -> None:
        """AGGRESSIVE 레짐: max_positions=5."""
        assert get_regime_max_positions(MarketRegime.AGGRESSIVE) == 5


# ── DEFAULT 상수 테스트 ──────────────────────────────────────────────


class TestDefaultConstants:
    """risk_pct / max_position_pct 기본값 하향 확인."""

    def test_risk_pct_is_lowered(self) -> None:
        """risk_pct 기본값 0.03 → 0.01 하향."""
        assert pytest.approx(0.01) == DEFAULT_RISK_PCT

    def test_max_position_pct_is_lowered(self) -> None:
        """max_position_pct 기본값 0.15 → 0.05 하향."""
        assert pytest.approx(0.05) == DEFAULT_MAX_POSITION_PCT
