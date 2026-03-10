"""기술 지표 계산 유틸 테스트."""

import pytest
from src.broker.schemas import DailyPrice
from src.strategy.indicators import calc_atr, calc_bollinger, calc_rsi


def _make_daily(close: int, high: int | None = None, low: int | None = None) -> DailyPrice:
    """테스트용 DailyPrice 생성 헬퍼."""
    return DailyPrice(
        date="20250101",
        open=close,
        high=high if high is not None else close + 10,
        low=low if low is not None else close - 10,
        close=close,
        volume=1000,
    )


class TestCalcRsi:
    """RSI 계산 테스트."""

    def test_insufficient_data_returns_neutral(self) -> None:
        """데이터 부족(period+1 미만)이면 50.0 반환."""
        prices = [100.0] * 14  # period=14, 15개 필요
        assert calc_rsi(prices) == 50.0

    def test_all_gains_returns_100(self) -> None:
        """전부 상승이면 RSI = 100."""
        prices = [float(i) for i in range(1, 30)]  # 계속 상승
        result = calc_rsi(prices, period=14)
        assert result == 100.0

    def test_all_losses_returns_0(self) -> None:
        """전부 하락이면 RSI = 0."""
        prices = [float(30 - i) for i in range(30)]  # 계속 하락
        result = calc_rsi(prices, period=14)
        assert result == pytest.approx(0.0, abs=1.0)

    def test_midpoint_returns_50(self) -> None:
        """등락 균등이면 RSI 약 50."""
        # 상승/하락 교대
        prices = []
        val = 100.0
        for i in range(30):
            val += 1.0 if i % 2 == 0 else -1.0
            prices.append(val)
        result = calc_rsi(prices, period=14)
        assert 40.0 < result < 60.0

    def test_rsi_value_in_range(self) -> None:
        """RSI 값은 항상 0~100 사이."""
        prices = [
            100.0,
            102.0,
            98.0,
            105.0,
            99.0,
            103.0,
            101.0,
            107.0,
            95.0,
            110.0,
            88.0,
            112.0,
            90.0,
            115.0,
            85.0,
            120.0,
        ]
        result = calc_rsi(prices, period=14)
        assert 0.0 <= result <= 100.0

    def test_custom_period(self) -> None:
        """커스텀 period 동작 확인."""
        prices = [float(i) for i in range(1, 15)]  # 14개
        result = calc_rsi(prices, period=7)
        assert 0.0 <= result <= 100.0


class TestCalcBollinger:
    """볼린저밴드 계산 테스트."""

    def test_insufficient_data_returns_last_price(self) -> None:
        """데이터 부족이면 upper=middle=lower=last price."""
        prices = [100.0] * 5  # period=20 미만
        lower, middle, upper = calc_bollinger(prices)
        assert lower == 100.0
        assert middle == 100.0
        assert upper == 100.0

    def test_empty_prices(self) -> None:
        """빈 리스트이면 0.0 반환."""
        lower, middle, upper = calc_bollinger([])
        assert lower == 0.0
        assert middle == 0.0
        assert upper == 0.0

    def test_lower_lt_middle_lt_upper(self) -> None:
        """lower < middle < upper 순서."""
        prices = [float(100 + (i % 5)) for i in range(25)]
        lower, middle, upper = calc_bollinger(prices)
        assert lower < middle < upper

    def test_constant_prices_zero_band(self) -> None:
        """모든 가격이 동일하면 밴드 폭 = 0."""
        prices = [100.0] * 25
        lower, middle, upper = calc_bollinger(prices)
        assert lower == middle == upper == 100.0

    def test_middle_is_average(self) -> None:
        """middle은 최근 period개 평균."""
        prices = list(range(1, 26))  # 1~25
        _lower, middle, _upper = calc_bollinger(prices, period=5)
        assert middle == pytest.approx(sum(range(21, 26)) / 5)

    def test_custom_std_multiplier(self) -> None:
        """num_std=1 vs 2: 좁은 밴드."""
        prices = [float(100 + (i % 10)) for i in range(25)]
        _, _m1, u1 = calc_bollinger(prices, num_std=1.0)
        _, _m2, u2 = calc_bollinger(prices, num_std=2.0)
        assert u1 < u2


class TestCalcAtr:
    """ATR 계산 테스트."""

    def test_insufficient_data_returns_zero(self) -> None:
        """데이터 1개 이하이면 0.0."""
        assert calc_atr([]) == 0.0
        assert calc_atr([_make_daily(100)]) == 0.0

    def test_simple_atr(self) -> None:
        """단순 ATR 계산 — high-low만 있는 경우."""
        daily = [
            DailyPrice(date="20250101", open=100, high=110, low=90, close=100, volume=1000),
            DailyPrice(date="20250102", open=100, high=115, low=95, close=105, volume=1000),
            DailyPrice(date="20250103", open=105, high=120, low=100, close=110, volume=1000),
        ]
        result = calc_atr(daily, period=2)
        # TR[1] = max(115-95, |115-100|, |95-100|) = max(20, 15, 5) = 20
        # TR[2] = max(120-100, |120-105|, |100-105|) = max(20, 15, 5) = 20
        assert result == pytest.approx(20.0)

    def test_atr_uses_prev_close(self) -> None:
        """갭이 있을 때 prev_close 기반 TR이 반영된다."""
        daily = [
            DailyPrice(date="20250101", open=100, high=105, low=95, close=100, volume=1000),
            # 갭 상승: prev_close=100, high=120, low=110 → TR = max(10, 20, 10) = 20
            DailyPrice(date="20250102", open=110, high=120, low=110, close=115, volume=1000),
        ]
        result = calc_atr(daily, period=1)
        assert result == pytest.approx(20.0)

    def test_atr_period_clamp(self) -> None:
        """데이터가 period보다 적으면 전체 평균."""
        daily = [_make_daily(100 + i * 5, high=110 + i * 5, low=90 + i * 5) for i in range(5)]
        result_full = calc_atr(daily, period=20)  # period > 데이터
        result_exact = calc_atr(daily, period=4)
        # period=20이어도 가능한 모든 TR 사용
        assert result_full > 0.0
        assert result_exact > 0.0
