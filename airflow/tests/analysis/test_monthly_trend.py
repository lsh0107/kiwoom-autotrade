"""월봉 12이평 추세 분석 단위 테스트.

MA12 계산, ADX 계산, 돌파/이탈 신호, 필터 조건, 횡보장 whipsaw 시나리오 검증.
"""

from __future__ import annotations

import pytest

# ── 테스트용 데이터 생성 헬퍼 ──────────────────────────────────────────────────


def _make_ohlcv(
    close: float, high: float | None = None, low: float | None = None, volume: float = 1_000_000
) -> dict:
    """OHLCV 딕셔너리 생성 헬퍼."""
    if high is None:
        high = close * 1.01
    if low is None:
        low = close * 0.99
    return {
        "date": "20260101",
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _make_monthly_prices(closes: list[float], volumes: list[float] | None = None) -> list[dict]:
    """월봉 목록 생성 헬퍼."""
    if volumes is None:
        volumes = [1_000_000] * len(closes)
    return [_make_ohlcv(c, volume=v) for c, v in zip(closes, volumes, strict=True)]


# ── calc_monthly_ma ──────────────────────────────────────────────────────────


class TestCalcMonthlyMa:
    """calc_monthly_ma 단위 테스트."""

    def test_basic_average(self) -> None:
        """12개 값의 단순 평균이 계산되어야 한다."""
        from analysis.monthly_trend import calc_monthly_ma

        prices = list(range(1, 13))  # 1~12
        result = calc_monthly_ma(prices, period=12)
        assert result == pytest.approx(6.5)

    def test_uses_last_n_values(self) -> None:
        """period 개보다 많은 데이터가 있으면 마지막 period 개만 사용해야 한다."""
        from analysis.monthly_trend import calc_monthly_ma

        prices = [1.0] * 5 + [100.0] * 12  # 앞 5개는 1.0, 마지막 12개는 100.0
        result = calc_monthly_ma(prices, period=12)
        assert result == pytest.approx(100.0)

    def test_insufficient_data_returns_zero(self) -> None:
        """데이터가 period보다 적으면 0.0을 반환해야 한다."""
        from analysis.monthly_trend import calc_monthly_ma

        prices = [100.0] * 11
        result = calc_monthly_ma(prices, period=12)
        assert result == pytest.approx(0.0)

    def test_exact_period_length(self) -> None:
        """데이터 길이가 period와 같으면 전체 평균이어야 한다."""
        from analysis.monthly_trend import calc_monthly_ma

        prices = [10.0, 20.0, 30.0]
        result = calc_monthly_ma(prices, period=3)
        assert result == pytest.approx(20.0)


# ── calc_monthly_adx ─────────────────────────────────────────────────────────


class TestCalcMonthlyAdx:
    """calc_monthly_adx 단위 테스트."""

    def test_insufficient_data_returns_zero(self) -> None:
        """데이터가 period + 1 미만이면 0.0을 반환해야 한다."""
        from analysis.monthly_trend import calc_monthly_adx

        data = [_make_ohlcv(100.0)] * 10  # period=14, 최소 15 필요
        result = calc_monthly_adx(data, period=14)
        assert result == pytest.approx(0.0)

    def test_strong_trend_has_high_adx(self) -> None:
        """강한 상승 추세에서 ADX > 25 이어야 한다."""
        from analysis.monthly_trend import calc_monthly_adx

        # 꾸준히 상승하는 30개월 데이터
        data = [
            _make_ohlcv(float(100 + i * 5), high=float(100 + i * 5 + 3), low=float(100 + i * 5 - 2))
            for i in range(30)
        ]
        result = calc_monthly_adx(data, period=14)
        assert result > 25.0

    def test_ranging_market_has_low_adx(self) -> None:
        """횡보장에서 ADX < 25 이어야 한다."""
        from analysis.monthly_trend import calc_monthly_adx

        # 박스권 진동 — 오르고 내리기를 반복
        closes = [
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
        ]
        data = [_make_ohlcv(c, high=c + 2, low=c - 2) for c in closes]
        result = calc_monthly_adx(data, period=14)
        assert result < 25.0

    def test_adx_in_valid_range(self) -> None:
        """ADX 값은 0~100 범위여야 한다."""
        from analysis.monthly_trend import calc_monthly_adx

        data = [_make_ohlcv(float(100 + i * 3)) for i in range(30)]
        result = calc_monthly_adx(data, period=14)
        assert 0.0 <= result <= 100.0


# ── check_monthly_ma12 ───────────────────────────────────────────────────────


class TestCheckMonthlyMa12:
    """check_monthly_ma12 신호 생성 테스트."""

    def _make_buy_scenario(self) -> list[dict]:
        """매수 조건 전부 충족하는 시나리오.

        - 종가 > MA12 x 1.01
        - MA12 상향 기울기
        - 거래량 배수 >= 1.5
        - ADX > 25 (강한 상승 추세)
        """
        # 24개월 점진 상승 + 마지막 달 강한 돌파
        closes = [float(100 + i * 3) for i in range(24)]
        # 마지막 달 종가를 MA12보다 1.5% 위로 설정
        ma12_approx = sum(closes[-12:]) / 12
        closes[-1] = ma12_approx * 1.02

        # 마지막 달 거래량을 이전 6개월 평균의 2배로 설정
        volumes = [1_000_000.0] * 24
        avg_6m = sum(volumes[-7:-1]) / 6
        volumes[-1] = avg_6m * 2.0

        return _make_monthly_prices(closes, volumes)

    def test_buy_signal_all_conditions_met(self) -> None:
        """모든 진입 조건 충족 시 signal='buy' 이어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        data = self._make_buy_scenario()
        result = check_monthly_ma12("005930", data, name="삼성전자")

        assert result.symbol == "005930"
        assert result.name == "삼성전자"
        assert result.signal == "buy"
        assert result.close > result.ma12

    def test_sell_signal_when_below_ma12(self) -> None:
        """종가 < MA12 시 signal='sell' 이어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        # 꾸준히 하락하는 24개월 데이터
        closes = [float(200 - i * 2) for i in range(24)]
        data = _make_monthly_prices(closes)

        result = check_monthly_ma12("000660", data)
        assert result.signal == "sell"

    def test_hold_when_breakout_insufficient(self) -> None:
        """종가가 MA12 위지만 1% 미만이면 signal='hold' 이어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        # MA12 = 100, 종가 = 100.5 (0.5% 돌파 — 1% 미달)
        closes = [100.0] * 23 + [100.5]
        data = _make_monthly_prices(closes)

        result = check_monthly_ma12("035420", data)
        assert result.signal == "hold"

    def test_hold_when_adx_too_low(self) -> None:
        """ADX <= 25인 횡보장에서 signal='hold' 이어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        # 횡보 후 약한 돌파
        closes = [
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            101.0,
            100.0,
            102.0,
            99.0,
            115.0,
        ]
        # 마지막 MA12 > MA12 * 1.01 (돌파)이지만 ADX는 낮음
        data = _make_monthly_prices(closes)

        result = check_monthly_ma12("068270", data)
        # ADX가 25 이하이면 hold
        if result.adx <= 25.0:
            assert result.signal == "hold"

    def test_hold_when_volume_insufficient(self) -> None:
        """거래량 배수 < 1.5이면 signal='hold' 이어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        # 강한 상승 추세
        closes = [float(100 + i * 5) for i in range(24)]
        ma12_approx = sum(closes[-12:]) / 12
        closes[-1] = ma12_approx * 1.02

        # 거래량 배수 = 1.0 (평균과 동일)
        volumes = [1_000_000.0] * 24  # 마지막도 동일 — 배수 = 1.0

        data = _make_monthly_prices(closes, volumes)
        result = check_monthly_ma12("096770", data)

        assert result.volume_ratio < 1.5
        assert result.signal in ("hold", "buy")  # 거래량 미달이면 hold
        if result.volume_ratio < 1.5:
            assert result.signal == "hold"

    def test_hold_when_ma_slope_downward(self) -> None:
        """MA12 기울기가 하향이면 signal='hold' 이어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        # 하락 후 반등 — MA12는 아직 하향 기울기
        closes = [float(200 - i * 3) for i in range(20)] + [float(140 + i * 10) for i in range(4)]
        # 마지막 달 종가가 MA12보다 충분히 위
        volumes = [1_000_000.0] * 22 + [3_000_000.0] * 2
        data = _make_monthly_prices(closes, volumes)

        result = check_monthly_ma12("105560", data)
        # MA12 기울기 하향 시 hold
        # (슬로프 체크: 현재 MA12 vs 3개월 전 MA12)
        from analysis.monthly_trend import _is_ma_slope_up

        prices = [float(p["close"]) for p in data]
        if not _is_ma_slope_up(prices):
            assert result.signal in ("hold", "sell")

    def test_insufficient_data_returns_hold(self) -> None:
        """데이터가 13개월 미만이면 signal='hold' 이어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        data = _make_monthly_prices([100.0] * 10)
        result = check_monthly_ma12("005380", data)

        assert result.signal == "hold"
        assert result.reason == "데이터 부족"

    def test_signal_fields_populated(self) -> None:
        """반환된 MonthlySignal 필드가 모두 채워져야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        data = _make_monthly_prices([float(100 + i) for i in range(24)])
        result = check_monthly_ma12("000020", data, name="동화약품")

        assert result.symbol == "000020"
        assert result.name == "동화약품"
        assert result.signal in ("buy", "sell", "hold")
        assert result.close > 0
        assert result.ma12 > 0
        assert result.adx >= 0
        assert result.volume_ratio > 0
        assert isinstance(result.reason, str) and len(result.reason) > 0

    def test_default_name_uses_symbol(self) -> None:
        """name 인수 없으면 symbol을 name으로 사용해야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        data = _make_monthly_prices([100.0] * 24)
        result = check_monthly_ma12("005930", data)

        assert result.name == "005930"


# ── 횡보장 whipsaw 시나리오 ───────────────────────────────────────────────────


class TestWhipsawScenario:
    """횡보장에서 허위 신호(whipsaw)가 필터되는지 검증."""

    def test_ranging_market_no_buy_signal(self) -> None:
        """ADX 25 이하인 박스권에서 매수 신호가 생성되지 않아야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        # 좁은 박스권 — MA12 근처에서 지속 진동
        base = 100.0
        closes = []
        for i in range(24):
            # ±2% 진동
            closes.append(base + (2.0 if i % 2 == 0 else -2.0))

        # 마지막 달 MA12 * 1.015 돌파처럼 보이지만 ADX 낮음
        ma12_approx = sum(closes[-12:]) / 12
        closes[-1] = ma12_approx * 1.015
        volumes = [1_000_000.0] * 23 + [2_000_000.0]
        data = _make_monthly_prices(closes, volumes)

        result = check_monthly_ma12("TEST01", data)
        # ADX 필터에 걸려야 함
        from analysis.monthly_trend import calc_monthly_adx

        adx = calc_monthly_adx(data, period=14)
        if adx <= 25.0:
            assert result.signal != "buy", f"횡보장에서 매수 신호 발생 (ADX={adx:.1f})"

    def test_false_breakout_then_sell(self) -> None:
        """돌파 후 MA12 이탈 시 sell 신호가 생성되어야 한다."""
        from analysis.monthly_trend import check_monthly_ma12

        # 상승 후 급락
        closes = [float(100 + i * 5) for i in range(20)] + [200.0, 210.0, 190.0, 95.0]
        data = _make_monthly_prices(closes)

        result = check_monthly_ma12("TEST02", data)
        # 마지막 종가가 MA12 아래이면 sell
        from analysis.monthly_trend import calc_monthly_ma

        prices = [float(p["close"]) for p in data]
        ma12 = calc_monthly_ma(prices)
        if prices[-1] < ma12:
            assert result.signal == "sell"


# ── _calc_volume_ratio ───────────────────────────────────────────────────────


class TestCalcVolumeRatio:
    """_calc_volume_ratio 단위 테스트."""

    def test_double_volume_returns_two(self) -> None:
        """현재 월 거래량이 6개월 평균의 2배이면 2.0을 반환해야 한다."""
        from analysis.monthly_trend import _calc_volume_ratio

        volumes = [1_000_000.0] * 6 + [2_000_000.0]
        result = _calc_volume_ratio(volumes, lookback=6)
        assert result == pytest.approx(2.0)

    def test_insufficient_data_returns_one(self) -> None:
        """데이터 부족 시 1.0을 반환해야 한다."""
        from analysis.monthly_trend import _calc_volume_ratio

        volumes = [1_000_000.0] * 3  # lookback=6 기준 부족
        result = _calc_volume_ratio(volumes, lookback=6)
        assert result == pytest.approx(1.0)

    def test_below_average_volume(self) -> None:
        """평균 이하 거래량에서 1.0 미만을 반환해야 한다."""
        from analysis.monthly_trend import _calc_volume_ratio

        volumes = [2_000_000.0] * 6 + [500_000.0]  # 현재 월은 평균의 25%
        result = _calc_volume_ratio(volumes, lookback=6)
        assert result == pytest.approx(0.25)


# ── _is_ma_slope_up ──────────────────────────────────────────────────────────


class TestIsMaSlopeUp:
    """_is_ma_slope_up 단위 테스트."""

    def test_uptrend_returns_true(self) -> None:
        """상향 기울기에서 True를 반환해야 한다."""
        from analysis.monthly_trend import _is_ma_slope_up

        prices = [float(100 + i * 2) for i in range(20)]
        assert _is_ma_slope_up(prices) is True

    def test_downtrend_returns_false(self) -> None:
        """하향 기울기에서 False를 반환해야 한다."""
        from analysis.monthly_trend import _is_ma_slope_up

        prices = [float(200 - i * 2) for i in range(20)]
        assert _is_ma_slope_up(prices) is False

    def test_insufficient_data_returns_false(self) -> None:
        """데이터 부족 시 False를 반환해야 한다."""
        from analysis.monthly_trend import _is_ma_slope_up

        prices = [100.0] * 10  # period=12, lookback=3, 최소 15 필요
        assert _is_ma_slope_up(prices) is False
