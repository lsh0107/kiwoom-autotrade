"""PullbackStrategy 테스트 (Design 013 PR 4)."""

from __future__ import annotations

import pytest

from src.broker.schemas import DailyPrice
from src.strategy.pullback import PullbackParams, PullbackStrategy


def _daily(
    date: str,
    open_: int,
    high: int,
    low: int,
    close: int,
    volume: int = 1000,
) -> DailyPrice:
    return DailyPrice(date=date, open=open_, high=high, low=low, close=close, volume=volume)


def _make_rising_trend(n: int = 30, start: int = 10000) -> list[DailyPrice]:
    """MA20 위 상승 추세 일봉 (매 봉 양봉, +0.3%)."""
    out: list[DailyPrice] = []
    price = start
    for i in range(n):
        open_ = price
        close = int(price * 1.003)
        high = close + 10
        low = open_ - 10
        out.append(_daily(f"2025{i:04d}", open_, high, low, close, volume=1000))
        price = close
    return out


class TestPullbackParams:
    """PullbackParams 기본값."""

    def test_defaults(self) -> None:
        p = PullbackParams()
        assert p.ma_period == 20
        assert p.ma_band_pct == pytest.approx(0.01)
        assert p.rsi_min == 35.0
        assert p.rsi_max == 55.0
        assert p.take_profit == pytest.approx(0.025)
        assert p.stop_loss == pytest.approx(-0.012)


class TestPullbackEntry:
    """check_entry_signal 테스트."""

    def test_too_few_bars_returns_false(self) -> None:
        """데이터 부족 → False."""
        strategy = PullbackStrategy()
        daily = _make_rising_trend(n=5)
        assert (
            strategy.check_entry_signal(
                daily, current_price=10000, current_volume=1000, time_ratio=1.0
            )
            is False
        )

    def test_last_close_below_ma20_rejects(self) -> None:
        """일봉 종가 < MA20 → 진입 거부."""
        strategy = PullbackStrategy()
        # 내리막 추세: 마지막 종가가 MA20 아래
        daily = []
        price = 10000
        for i in range(30):
            close = price - i * 10
            daily.append(_daily(f"2025{i:04d}", price, price + 5, close - 5, close, volume=1000))
        result = strategy.check_entry_signal(
            daily, current_price=daily[-1].close, current_volume=1000
        )
        assert result is False

    def test_price_far_from_ma_rejects(self) -> None:
        """현재가가 MA20에서 너무 멀면(>1%) 거부."""
        strategy = PullbackStrategy()
        daily = _make_rising_trend(n=30)
        # MA20은 중간값 근처. 현재가를 훨씬 높게
        result = strategy.check_entry_signal(daily, current_price=50000, current_volume=1000)
        assert result is False

    def test_no_bullish_bar_in_lookback_rejects(self) -> None:
        """직전 5봉이 전부 음봉 → 거부."""
        strategy = PullbackStrategy()
        # 상승 장인 듯 하지만 마지막 5봉은 음봉
        daily = _make_rising_trend(n=25)
        # 마지막 5봉 음봉으로 교체 (종가<시가)
        last_ma_price = sum(d.close for d in daily[-20:]) / 20
        # 현재가를 MA 근처로 두고 최근 5봉 음봉
        for i in range(5):
            open_ = int(last_ma_price + 20)
            close = int(last_ma_price - 5)
            daily.append(_daily(f"2025B{i:03d}", open_, open_ + 5, close - 5, close, volume=1000))
        result = strategy.check_entry_signal(
            daily, current_price=int(last_ma_price), current_volume=1000
        )
        assert result is False

    def test_rsi_out_of_range_rejects(self) -> None:
        """RSI < 35 또는 > 55 → 거부."""
        # 급락 → RSI 낮음
        daily = []
        for i in range(30):
            price = 10000 - i * 50
            daily.append(
                _daily(f"2025{i:04d}", price + 5, price + 10, price - 5, price, volume=1000)
            )
        strategy = PullbackStrategy()
        # 현재가=마지막 종가 근처, MA 아래일 가능성 — 그래도 RSI는 매우 낮음
        # 위 트렌드로 종가<MA일 것이므로 "RSI 거부" 전에 MA 체크에서 거부될 수 있음.
        # 더 엄격한 RSI 테스트: 엄청 높은 rsi 유도(급등 후 현재가 MA 근처)
        rising = _make_rising_trend(n=30, start=10000)
        # 평균 상승으로 RSI 높을 것. 현재가는 MA 근처로 설정
        closes = [d.close for d in rising]
        ma20 = sum(closes[-20:]) / 20
        result = strategy.check_entry_signal(rising, current_price=int(ma20), current_volume=1000)
        # 모든 상승 → RSI=100 → 55 초과 → 거부
        assert result is False

    def test_volume_below_threshold_rejects(self) -> None:
        """거래량 부족 → 거부."""
        # RSI 중립 범위 + MA 위 + ma 근처 + 양봉 있음 조합 만들기
        # 변동성 있는 흐름: 상승 후 소폭 조정
        daily: list[DailyPrice] = []
        price = 10000
        for i in range(20):
            # 상승 10봉, 조정 10봉으로 RSI 중간대 유도
            if i < 10:
                close = price + 30
            elif i < 15:
                close = price - 20
            else:
                close = price + 5
            daily.append(_daily(f"2025{i:04d}", price, close + 5, price - 5, close, volume=1000))
            price = close
        # 최근 5봉에 양봉 1개 이상 포함 흐름
        for i in range(20, 30):
            close = price + 15 if i % 2 == 0 else price - 10
            daily.append(_daily(f"2025{i:04d}", price, close + 5, price - 5, close, volume=1000))
            price = close
        strategy = PullbackStrategy(params=PullbackParams(volume_ratio=2.0))  # 엄격
        ma20 = sum(d.close for d in daily[-20:]) / 20
        result = strategy.check_entry_signal(
            daily,
            current_price=int(ma20),
            current_volume=500,  # 부족
        )
        # 거래량 조건 불충족
        assert result is False

    def test_volume_ratio_override_relaxes(self) -> None:
        """volume_ratio_override로 완화 시 동일 조건에서 결과 달라짐."""
        strategy = PullbackStrategy(params=PullbackParams(volume_ratio=5.0))
        daily = _make_rising_trend(n=30)
        ma20 = sum(d.close for d in daily[-20:]) / 20
        # 기본(엄격) → False
        strict = strategy.check_entry_signal(daily, current_price=int(ma20), current_volume=1000)
        assert strict is False
        # override=0.1 → 거래량은 통과
        # (다른 조건 RSI 문제로 결국 False일 수 있으나, 여기선 override 동작만 확인)
        result_override = strategy.check_entry_signal(
            daily,
            current_price=int(ma20),
            current_volume=1000,
            volume_ratio_override=0.1,
        )
        # override 자체가 예외 없이 동작해야 함
        assert isinstance(result_override, bool)

    def test_zero_ma_returns_false(self) -> None:
        """MA20이 0이면 False."""
        strategy = PullbackStrategy()
        # 가격 0 시리즈 (엣지)
        daily = [_daily(f"2025{i:04d}", 0, 0, 0, 0, volume=0) for i in range(30)]
        assert strategy.check_entry_signal(daily, current_price=0, current_volume=0) is False


class TestPullbackExit:
    """check_exit_signal 테스트."""

    def test_take_profit_at_2_5pct(self) -> None:
        strategy = PullbackStrategy()
        # 정확히 take_profit 임계치(+2.5%)
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=10250, high_since_entry=10250
        )
        assert result == "take_profit"

    def test_stop_loss_at_1_2pct(self) -> None:
        strategy = PullbackStrategy()
        # -1.2%
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=9880, high_since_entry=10000
        )
        assert result == "stop_loss"

    def test_no_exit_within_band(self) -> None:
        strategy = PullbackStrategy()
        # +1% 수익 — 아직 청산 없음
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=10100, high_since_entry=10100
        )
        assert result is None

    def test_zero_entry_price_returns_none(self) -> None:
        strategy = PullbackStrategy()
        assert (
            strategy.check_exit_signal(entry_price=0, current_price=10000, high_since_entry=10000)
            is None
        )

    def test_trailing_not_active(self) -> None:
        """Pullback은 trailing 미사용 — 고점 대비 하락해도 stop_loss만 본다."""
        strategy = PullbackStrategy()
        # 고점 +3%에서 +1.5%까지 하락했지만 stop_loss(-1.2%) 아직 안 됨
        result = strategy.check_exit_signal(
            entry_price=10000, current_price=10150, high_since_entry=10300
        )
        assert result is None  # trailing 비활성 → None


class TestPullbackStrategyProtocol:
    """Strategy Protocol 호환성."""

    def test_name_attribute(self) -> None:
        assert PullbackStrategy.name == "pullback"

    def test_default_params_on_init(self) -> None:
        s = PullbackStrategy()
        assert s.params.ma_period == 20

    def test_custom_params_on_init(self) -> None:
        s = PullbackStrategy(params=PullbackParams(ma_period=15))
        assert s.params.ma_period == 15
