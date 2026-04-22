"""MomentumStrategy 거래량 기반 진입 로직 테스트."""

import pytest

from src.backtest.strategy import MomentumParams
from src.broker.schemas import DailyPrice
from src.strategy.momentum import MomentumStrategy


class TestMomentumStrategy20DayAvg:
    """MomentumStrategy 20일 평균 거래량 테스트."""

    def _make_daily_with_volume(self, volume: int, high: int = 10000) -> DailyPrice:
        return DailyPrice(
            date="20250101", open=9000, high=high, low=8900, close=9500, volume=volume
        )

    def test_uses_recent_20_days_not_full_history(self) -> None:
        """전체 일봉이 아닌 최근 20일 평균 거래량을 사용한다.

        오래된 250일: 거래량 10000 (평균 높음)
        최근 20일: 거래량 1000 (평균 낮음)
        → 최근 20일 기준으로 current_volume=1500 > avg*1.5=1500 → 진입 가능
        → 전체 기준으로는 avg=9267 → 1500 < 9267*1.5 → 진입 불가
        """
        strategy = MomentumStrategy()

        # 오래된 250일: volume=10000 (높음)
        old_days = [self._make_daily_with_volume(10000, high=10000) for _ in range(250)]
        # 최근 20일: volume=1000 (낮음)
        recent_days = [self._make_daily_with_volume(1000, high=10000) for _ in range(20)]
        daily = old_days + recent_days

        # avg_volume (최근 20일) = 1000 → threshold = 1000 * 1.5 = 1500
        # current_volume=1500 → 1500 >= 1500 → True (최근 20일 기준)
        result = strategy.check_entry_signal(daily, current_price=10000, current_volume=1500)
        assert result is True

    def test_fewer_than_20_days_uses_all(self) -> None:
        """일봉이 20개 미만이면 전체 평균을 사용한다."""
        strategy = MomentumStrategy()

        # 5일치, volume=1000
        daily = [self._make_daily_with_volume(1000, high=10000) for _ in range(5)]
        # avg=1000 → threshold=1500
        result = strategy.check_entry_signal(daily, current_price=10000, current_volume=1500)
        assert result is True

    def test_time_ratio_scales_volume_threshold(self) -> None:
        """time_ratio=0.5이면 평균 거래량의 절반이 기준이 된다."""
        strategy = MomentumStrategy()
        daily = [self._make_daily_with_volume(1000, high=10000) for _ in range(20)]

        # time_ratio=0.5: avg_volume*0.5=500 → threshold=500*1.5=750
        # current_volume=800 >= 750 → True
        result = strategy.check_entry_signal(
            daily, current_price=10000, current_volume=800, time_ratio=0.5
        )
        assert result is True

    def test_time_ratio_default_no_entry_without_sufficient_volume(self) -> None:
        """time_ratio=1.0 (기본)에서 거래량 미달 시 False."""
        strategy = MomentumStrategy(params=MomentumParams(volume_ratio=1.5))
        daily = [self._make_daily_with_volume(1000, high=10000) for _ in range(20)]

        # avg=1000, volume_ratio=1.5 → threshold=1500, current=1400 → False
        result = strategy.check_entry_signal(daily, current_price=10000, current_volume=1400)
        assert result is False


class TestMomentumStrategyCheckExitSignal:
    """MomentumStrategy.check_exit_signal 래퍼 동작 테스트.

    live_trader는 force_close 시각 판단을 직접 수행하므로, 래퍼는
    내부 check_exit_signal 호출 시 force_close 결과를 None으로 변환해야 한다.
    """

    def test_stop_loss_triggers_sell_signal(self) -> None:
        """손절선 이하 하락 → 'stop_loss' 사유 반환 (래퍼는 내부 함수 결과를 그대로 전달)."""
        strategy = MomentumStrategy(params=MomentumParams(stop_loss=-0.03, take_profit=0.10))
        # entry=10000, current=9690 (-3.1%) → 손절선(-3%) 이하 → stop_loss
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=9690, high_since_entry=10000
        )
        assert result == "stop_loss"

    def test_take_profit_triggers_sell_signal(self) -> None:
        """익절선 이상 상승 → 'take_profit' 사유 반환 (트레일링 비활성 시)."""
        # 트레일링 스탑 활성 시 take_profit 대신 트레일링이 수익 관리를 담당하므로,
        # 순수 take_profit 동작만 검증하려면 trailing_stop_pct=None으로 설정.
        strategy = MomentumStrategy(
            params=MomentumParams(stop_loss=-0.03, take_profit=0.10, trailing_stop_pct=None)
        )
        # entry=10000, current=11100 (+11%) → 익절선(+10%) 이상 → take_profit
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=11100, high_since_entry=11100
        )
        assert result == "take_profit"

    def test_no_exit_when_price_within_bounds(self) -> None:
        """손절/익절 범위 내 → None 반환."""
        strategy = MomentumStrategy(params=MomentumParams(stop_loss=-0.03, take_profit=0.10))
        # entry=10000, current=10050 (+0.5%) → 손절/익절 모두 미달 → None
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=10050, high_since_entry=10050
        )
        assert result is None


class TestMomentumStrategyTrailingArmed:
    """Trailing armed threshold feature flag 동작 테스트.

    `USE_TRAILING_ARMED=true` 설정 시, 진입 후 최고가가 진입가 대비
    `TRAILING_ARMED_PCT`(기본 0.5%) 이상 상승한 경우에만 trailing_stop을
    평가한다. armed 전에는 stop_loss만 작동해야 한다.

    2026-04-20 실거래 사례(299660 현대로템): 진입가 4,440 → peak 4,440
    → 현재가 4,435(-0.11%)에서 trailing_stop 발동됨. armed 개념으로 방지.
    """

    def test_flag_off_preserves_legacy_trailing_behavior(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """flag off(기본값) 시 기존 trailing_stop 동작 100% 보존.

        299660 재현: entry=4440, peak=4480(+0.9%), current=4435(-1.00%
        from peak) → 기존 동작대로 trailing_stop 발동.
        """
        monkeypatch.delenv("USE_TRAILING_ARMED", raising=False)
        strategy = MomentumStrategy(params=MomentumParams(stop_loss=-0.03, trailing_stop_pct=-0.01))
        result = strategy.check_exit_signal(
            entry_price=4440, current_price=4435, high_since_entry=4480
        )
        assert result == "trailing_stop"

    def test_flag_on_blocks_trailing_before_armed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag on + armed 미달 시 진입가 근처 소폭 하락은 trailing 발동 안 함.

        entry=4440, peak=4445(+0.11%, armed 0.5% 미달), current=4435
        → armed 전이므로 trailing 스킵, stop_loss도 미달 → None.
        """
        monkeypatch.setenv("USE_TRAILING_ARMED", "true")
        strategy = MomentumStrategy(params=MomentumParams(stop_loss=-0.03, trailing_stop_pct=-0.01))
        result = strategy.check_exit_signal(
            entry_price=4440, current_price=4435, high_since_entry=4445
        )
        assert result is None

    def test_flag_on_triggers_trailing_after_armed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag on + armed 달성 후 고점 대비 하락 시 정상 trailing.

        entry=10000, peak=10100(+1.0%, armed 초과), current=10000
        (peak 대비 -0.99% ≈ 트레일링 기준 -1.0% 부근) → trailing_stop.
        """
        monkeypatch.setenv("USE_TRAILING_ARMED", "true")
        strategy = MomentumStrategy(params=MomentumParams(stop_loss=-0.03, trailing_stop_pct=-0.01))
        # peak=10100, current=9999 → drop = -1.0% exactly → trailing 발동
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=9999, high_since_entry=10100
        )
        assert result == "trailing_stop"

    def test_flag_on_stop_loss_still_works_before_armed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """flag on + armed 미달이라도 stop_loss는 정상 작동 (손실 컷 보장)."""
        monkeypatch.setenv("USE_TRAILING_ARMED", "true")
        strategy = MomentumStrategy(params=MomentumParams(stop_loss=-0.03, trailing_stop_pct=-0.01))
        # entry=10000, peak=10020(armed 미달), current=9700(-3.0%) → stop_loss
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=9700, high_since_entry=10020
        )
        assert result == "stop_loss"

    def test_custom_armed_pct_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TRAILING_ARMED_PCT 환경변수로 armed 기준 커스터마이즈 가능.

        armed=1.0%로 설정 → peak=+0.8%는 여전히 armed 미달이라
        trailing 미발동.
        """
        monkeypatch.setenv("USE_TRAILING_ARMED", "true")
        monkeypatch.setenv("TRAILING_ARMED_PCT", "0.01")
        strategy = MomentumStrategy(
            params=MomentumParams(stop_loss=-0.03, trailing_stop_pct=-0.005)
        )
        # entry=10000, peak=10080(+0.8%, armed 1.0% 미달),
        # current=10020 → armed 전이므로 trailing 스킵
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=10020, high_since_entry=10080
        )
        assert result is None


class TestMomentumVolumeRatioOverride:
    """Design 013 — volume_ratio_override keyword 테스트."""

    def _make_daily_with_volume(self, volume: int, high: int = 10000) -> DailyPrice:
        return DailyPrice(
            date="20250101", open=9000, high=high, low=8900, close=9500, volume=volume
        )

    def test_override_none_uses_params_default(self) -> None:
        """override=None이면 기존 params.volume_ratio 사용 (기본 동작 유지)."""
        strategy = MomentumStrategy(
            params=MomentumParams(volume_ratio=1.0, price_change_min=0.0, require_bullish_bar=False)
        )
        daily = [self._make_daily_with_volume(1000) for _ in range(20)]
        # avg=1000, threshold=1000*1.0=1000, current=999 → 진입 불가
        assert strategy.check_entry_signal(daily, current_price=10000, current_volume=999) is False
        # current=1000 → 진입 가능
        assert strategy.check_entry_signal(daily, current_price=10000, current_volume=1000) is True

    def test_override_relaxes_threshold(self) -> None:
        """override=0.5이면 params.volume_ratio 무시하고 0.5로 평가."""
        strategy = MomentumStrategy(
            params=MomentumParams(volume_ratio=1.0, price_change_min=0.0, require_bullish_bar=False)
        )
        daily = [self._make_daily_with_volume(1000) for _ in range(20)]
        # override=0.5: threshold = 1000*0.5 = 500, current=600 → 진입 가능
        assert (
            strategy.check_entry_signal(
                daily, current_price=10000, current_volume=600, volume_ratio_override=0.5
            )
            is True
        )

    def test_override_tightens_threshold(self) -> None:
        """override=2.0이면 더 엄격: 기본 0.5 통과도 불가."""
        strategy = MomentumStrategy(
            params=MomentumParams(volume_ratio=0.5, price_change_min=0.0, require_bullish_bar=False)
        )
        daily = [self._make_daily_with_volume(1000) for _ in range(20)]
        # 기본(0.5): threshold=500, current=600 → 통과
        assert strategy.check_entry_signal(daily, current_price=10000, current_volume=600) is True
        # override=2.0: threshold=2000, current=600 → 불통
        assert (
            strategy.check_entry_signal(
                daily, current_price=10000, current_volume=600, volume_ratio_override=2.0
            )
            is False
        )
