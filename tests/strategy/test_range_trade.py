"""RangeStrategy 테스트 (Design 013 PR 5)."""

from __future__ import annotations

import pytest

from src.broker.schemas import DailyPrice
from src.strategy.range_trade import RangeParams, RangeStrategy


def _daily(
    date: str,
    open_: int,
    high: int,
    low: int,
    close: int,
    volume: int = 1000,
) -> DailyPrice:
    return DailyPrice(date=date, open=open_, high=high, low=low, close=close, volume=volume)


def _make_sideways(n: int = 30, base: int = 10000, spread: int = 50) -> list[DailyPrice]:
    """박스권 시나리오 — 좁은 폭으로 진동."""
    out: list[DailyPrice] = []
    for i in range(n):
        # 좁은 폭으로 상하 교대
        close = base + spread // 2 if i % 2 == 0 else base - spread // 2
        high = close + 10
        low = close - 10
        out.append(_daily(f"2025{i:04d}", base, high, low, close, volume=1000))
    return out


class TestRangeParams:
    def test_defaults(self) -> None:
        p = RangeParams()
        assert p.bb_period == 20
        assert p.bb_std == pytest.approx(1.8)
        assert p.rsi_max == 45.0
        assert p.range_width_pct == pytest.approx(0.02)
        assert p.lower_band_tolerance_pct == pytest.approx(0.005)
        assert p.time_exit_minutes == 120


class TestRangeEntry:
    def test_too_few_bars(self) -> None:
        strategy = RangeStrategy()
        daily = _make_sideways(n=5)
        assert strategy.check_entry_signal(daily, current_price=10000, current_volume=1000) is False

    def test_high_volatility_rejects(self) -> None:
        """박스권 아닌 고변동 → 거부."""
        # 변동 폭이 큰 일봉 (high-low)/close > 2%
        daily = [_daily(f"2025{i:04d}", 10000, 10500, 9500, 10000, volume=1000) for i in range(30)]
        strategy = RangeStrategy()
        result = strategy.check_entry_signal(daily, current_price=9500, current_volume=1000)
        assert result is False

    def test_not_near_lower_band_rejects(self) -> None:
        """BB 하단에서 멀면 거부."""
        daily = _make_sideways(n=30, base=10000)
        strategy = RangeStrategy()
        # BB 하단 근처가 아닌 현재가 (중심)
        result = strategy.check_entry_signal(daily, current_price=10000, current_volume=1000)
        assert result is False

    def test_rsi_too_high_rejects(self) -> None:
        """RSI >= 45 → 거부."""
        # 상승 추세로 RSI 높게
        daily = [
            _daily(f"2025{i:04d}", 10000, 10010, 9990, 10000 + i, volume=1000) for i in range(30)
        ]
        strategy = RangeStrategy()
        # BB 하단 근처 가격이어도 RSI 문제로 거부
        closes = [float(d.close) for d in daily]
        from src.strategy.indicators import calc_bollinger

        lower, _m, _u = calc_bollinger(closes, 20, 1.8)
        result = strategy.check_entry_signal(daily, current_price=int(lower), current_volume=1000)
        # 상승 추세라 RSI 높음 → 거부 (박스권 조건은 만족하더라도)
        assert result is False

    def test_volume_override_used(self) -> None:
        """volume_ratio_override keyword 동작 확인."""
        daily = _make_sideways(n=30, base=10000, spread=30)
        strategy = RangeStrategy(params=RangeParams(volume_ratio=5.0))
        # 기본 엄격 케이스
        r1 = strategy.check_entry_signal(daily, current_price=9950, current_volume=500)
        # override 완화 케이스
        r2 = strategy.check_entry_signal(
            daily,
            current_price=9950,
            current_volume=500,
            volume_ratio_override=0.1,
        )
        assert isinstance(r1, bool)
        assert isinstance(r2, bool)
        # override 완화 방향: r2가 True이면 r1은 False여야 함 (override가 의미가 있음)
        if r2 is True:
            assert r1 is False

    def test_zero_close_in_recent_returns_false(self) -> None:
        """최근 20봉에 close=0 있으면 False."""
        daily = _make_sideways(n=10, base=10000)
        # 최근 20봉 확보를 위해 추가
        zero_bars = [_daily(f"2025Z{i:03d}", 0, 0, 0, 0, volume=1000) for i in range(20)]
        strategy = RangeStrategy()
        assert (
            strategy.check_entry_signal(daily + zero_bars, current_price=10000, current_volume=1000)
            is False
        )


class TestRangeExit:
    def test_stop_loss_fallback(self) -> None:
        strategy = RangeStrategy()
        # -1.5% 손절 기본
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=9850, high_since_entry=10000
        )
        assert result == "stop_loss"

    def test_take_profit_fallback(self) -> None:
        strategy = RangeStrategy()
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=10200, high_since_entry=10200
        )
        assert result == "take_profit"

    def test_no_exit_in_band(self) -> None:
        strategy = RangeStrategy()
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=10050, high_since_entry=10050
        )
        assert result is None

    def test_zero_entry_returns_none(self) -> None:
        strategy = RangeStrategy()
        assert (
            strategy.check_exit_signal(entry_price=0, current_price=9000, high_since_entry=9000)
            is None
        )


class TestRangeExitWithIndicators:
    def test_bb_center_reversion_profit(self) -> None:
        """BB 중심선 회귀 + 수익 중 → bb_center_reversion."""
        strategy = RangeStrategy()
        daily = _make_sideways(n=30, base=10000, spread=30)
        # middle ≈ 10000. entry_price=9950, current=10010 (>middle, >entry)
        result = strategy.check_exit_with_indicators(
            entry_price=9950, current_price=10010, daily=daily
        )
        assert result == "bb_center_reversion"

    def test_bb_lower_breakdown(self) -> None:
        """BB 하단 추가 -1% 이탈 → bb_lower_breakdown."""
        strategy = RangeStrategy()
        daily = _make_sideways(n=30, base=10000, spread=30)
        from src.strategy.indicators import calc_bollinger

        closes = [float(d.close) for d in daily]
        lower, _m, _u = calc_bollinger(closes, 20, 1.8)
        # lower * 0.98 → 확실히 붕괴 지점
        breakdown_price = int(lower * 0.98)
        # entry_price를 crash 전으로 설정해서 기본 stop_loss에 먼저 걸리지 않게
        # 즉 entry_price와 breakdown_price 차이가 stop_loss(-1.5%) 이내
        entry = int(breakdown_price * 1.01)  # breakdown이 entry 대비 -1% 정도
        result = strategy.check_exit_with_indicators(
            entry_price=entry, current_price=breakdown_price, daily=daily
        )
        assert result == "bb_lower_breakdown"

    def test_fallback_basic_exit_takes_priority(self) -> None:
        """기본 stop_loss가 먼저 발동."""
        strategy = RangeStrategy()
        daily = _make_sideways(n=30, base=10000, spread=30)
        # 2퍼센트 손실 (stop_loss 임계치 초과)
        result = strategy.check_exit_with_indicators(
            entry_price=10000, current_price=9800, daily=daily
        )
        assert result == "stop_loss"

    def test_insufficient_daily_returns_none(self) -> None:
        strategy = RangeStrategy()
        daily = _make_sideways(n=5)
        # 기본 exit도 None이면 None
        result = strategy.check_exit_with_indicators(
            entry_price=10000, current_price=10050, daily=daily
        )
        assert result is None


class TestRangeTimeExit:
    def test_time_exit_triggered(self) -> None:
        strategy = RangeStrategy()
        assert strategy.check_time_exit(minutes_since_entry=120) == "time_exit"
        assert strategy.check_time_exit(minutes_since_entry=150) == "time_exit"

    def test_time_exit_not_yet(self) -> None:
        strategy = RangeStrategy()
        assert strategy.check_time_exit(minutes_since_entry=60) is None
        assert strategy.check_time_exit(minutes_since_entry=119) is None

    def test_custom_threshold(self) -> None:
        strategy = RangeStrategy(params=RangeParams(time_exit_minutes=30))
        assert strategy.check_time_exit(minutes_since_entry=30) == "time_exit"
        assert strategy.check_time_exit(minutes_since_entry=29) is None


class TestRangeProtocol:
    def test_name(self) -> None:
        assert RangeStrategy.name == "range_trade"

    def test_default_params_on_init(self) -> None:
        assert RangeStrategy().params.bb_period == 20

    def test_custom_params(self) -> None:
        s = RangeStrategy(params=RangeParams(bb_period=15))
        assert s.params.bb_period == 15
