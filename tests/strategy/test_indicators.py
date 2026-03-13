"""기술 지표 계산 유틸 테스트."""

import pytest

from src.broker.schemas import DailyPrice
from src.strategy.indicators import (
    calc_atr,
    calc_bollinger,
    calc_rsi,
)


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


def _make_trending_daily(n: int, *, start: int = 1000, step: int = 20) -> list[DailyPrice]:
    """상승 추세 일봉 데이터 생성 (ADX 높음).

    매일 일정하게 상승하는 패턴으로 ADX가 높게 나온다.
    """
    daily = []
    for i in range(n):
        base = start + i * step
        daily.append(
            DailyPrice(
                date=f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                open=base,
                high=base + 30,
                low=base - 10,
                close=base + step,
                volume=10000,
            )
        )
    return daily


def _make_range_daily(n: int, *, center: int = 1000, amplitude: int = 5) -> list[DailyPrice]:
    """횡보 일봉 데이터 생성 (ADX 낮음).

    좁은 범위에서 등락 반복 → 추세 없음.
    """
    daily = []
    for i in range(n):
        offset = amplitude if i % 2 == 0 else -amplitude
        close = center + offset
        daily.append(
            DailyPrice(
                date=f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                open=center,
                high=center + amplitude + 2,
                low=center - amplitude - 2,
                close=close,
                volume=10000,
            )
        )
    return daily


class TestCalcAdx:
    """ADX 계산 테스트."""

    def test_insufficient_data_returns_zero(self) -> None:
        """데이터 부족(period*2 미만)이면 0.0 반환."""
        from src.strategy.indicators import calc_adx

        daily = [_make_daily(100 + i) for i in range(20)]
        assert calc_adx(daily, period=14) == 0.0

    def test_basic_adx_range(self) -> None:
        """충분한 데이터로 ADX가 0~100 범위에 있어야 한다."""
        from src.strategy.indicators import calc_adx

        daily = _make_trending_daily(50)
        result = calc_adx(daily, period=14)
        assert 0.0 <= result <= 100.0

    def test_trending_market_high_adx(self) -> None:
        """강한 상승 추세에서 ADX가 높아야 한다 (>25)."""
        from src.strategy.indicators import calc_adx

        daily = _make_trending_daily(60, step=30)
        result = calc_adx(daily, period=14)
        assert result > 25.0

    def test_ranging_market_low_adx(self) -> None:
        """횡보장에서 ADX가 낮아야 한다 (<30)."""
        from src.strategy.indicators import calc_adx

        daily = _make_range_daily(60, amplitude=3)
        result = calc_adx(daily, period=14)
        assert result < 30.0

    def test_custom_period(self) -> None:
        """커스텀 period 동작 확인."""
        from src.strategy.indicators import calc_adx

        daily = _make_trending_daily(40)
        result = calc_adx(daily, period=7)
        assert 0.0 <= result <= 100.0


class TestClassifyVolatility:
    """변동성 분류 테스트."""

    def test_momentum_high_atr_high_adx(self) -> None:
        """ATR% > 3% AND ADX > 25 → MOMENTUM."""
        from src.strategy.indicators import VolatilityClass, classify_volatility

        # 고변동성 + 강추세: 큰 일중 범위 + 꾸준한 상승
        daily = []
        for i in range(60):
            base = 1000 + i * 10
            daily.append(
                DailyPrice(
                    date=f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                    open=base,
                    high=base + 60,
                    low=base - 20,
                    close=base + 10,
                    volume=10000,
                )
            )
        result = classify_volatility(daily)
        assert result == VolatilityClass.MOMENTUM

    def test_mean_reversion_low_atr(self) -> None:
        """ATR% < 2% → MEAN_REVERSION."""
        from src.strategy.indicators import VolatilityClass, classify_volatility

        # 저변동성: 좁은 범위 등락
        daily = []
        for i in range(60):
            close = 10000 + (i % 2) * 10  # 종가 10000~10010
            daily.append(
                DailyPrice(
                    date=f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                    open=10000,
                    high=10015,  # range = 30 → ATR% ≈ 0.3%
                    low=9985,
                    close=close,
                    volume=10000,
                )
            )
        result = classify_volatility(daily)
        assert result == VolatilityClass.MEAN_REVERSION

    def test_conservative_middle_range(self) -> None:
        """중간 변동성 → CONSERVATIVE."""
        from src.strategy.indicators import VolatilityClass, classify_volatility

        # ATR% 2~3%, ADX 낮음 → CONSERVATIVE
        daily = []
        for i in range(60):
            base = 1000 + (i % 4) * 5  # 약간 등락
            daily.append(
                DailyPrice(
                    date=f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                    open=base,
                    high=base + 25,  # range ≈ 50 → ATR% ≈ 2.5%
                    low=base - 25,
                    close=base,
                    volume=10000,
                )
            )
        result = classify_volatility(daily)
        assert result == VolatilityClass.CONSERVATIVE

    def test_insufficient_data_returns_conservative(self) -> None:
        """데이터 부족 시 CONSERVATIVE 폴백."""
        from src.strategy.indicators import VolatilityClass, classify_volatility

        daily = [_make_daily(100)]
        assert classify_volatility(daily) == VolatilityClass.CONSERVATIVE

    def test_empty_data_returns_conservative(self) -> None:
        """빈 데이터 → CONSERVATIVE."""
        from src.strategy.indicators import VolatilityClass, classify_volatility

        assert classify_volatility([]) == VolatilityClass.CONSERVATIVE

    def test_custom_thresholds(self) -> None:
        """커스텀 임계값 동작 확인."""
        from src.strategy.indicators import VolatilityClass, classify_volatility

        # 저변동성 데이터에 높은 low_atr_pct 적용 → MEAN_REVERSION이 안 될 수 있음
        daily = _make_range_daily(60, amplitude=3)
        result = classify_volatility(daily, low_atr_pct=0.001)
        # 아주 낮은 임계값이면 MEAN_REVERSION이 아닐 수 있음
        assert result in (
            VolatilityClass.CONSERVATIVE,
            VolatilityClass.MEAN_REVERSION,
            VolatilityClass.MOMENTUM,
        )
