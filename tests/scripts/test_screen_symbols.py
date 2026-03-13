"""screen_symbols 스크리닝 보너스 조건 테스트."""

import sys
from pathlib import Path

import pytest

# scripts/ 경로를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.broker.schemas import DailyPrice

from scripts.screen_symbols import (
    calc_prev_day_change,
    check_screen_condition,
    check_volume_surge,
    count_consecutive_bullish,
    is_52w_new_high,
)

# ── 헬퍼: DailyPrice 팩토리 ──────────────────────────


def _make_daily(
    close: int,
    open_: int = 0,
    high: int = 0,
    volume: int = 1000,
    date: str = "20260101",
) -> DailyPrice:
    """DailyPrice 간편 생성. open 미지정 시 close와 동일."""
    open_ = open_ or close
    high = high or max(close, open_)
    return DailyPrice(
        date=date,
        open=open_,
        high=high,
        low=min(close, open_),
        close=close,
        volume=volume,
    )


def _make_daily_series(
    prices: list[tuple[int, int]],
    volume: int = 1000,
    base_date: int = 20260101,
) -> list[DailyPrice]:
    """(open, close) 튜플 리스트 → DailyPrice 리스트."""
    return [
        _make_daily(
            close=close,
            open_=open_,
            high=max(open_, close) + 100,
            volume=volume,
            date=str(base_date + i),
        )
        for i, (open_, close) in enumerate(prices)
    ]


# ── calc_prev_day_change ─────────────────────────────


class TestCalcPrevDayChange:
    """전일 등락률 계산 테스트."""

    def test_positive_change(self) -> None:
        """상승 시 양수 등락률."""
        daily = [
            _make_daily(10000, date="20260101"),
            _make_daily(10500, date="20260102"),
        ]
        result = calc_prev_day_change(daily)
        assert result == pytest.approx(5.0, rel=1e-3)

    def test_negative_change(self) -> None:
        """하락 시 음수 등락률."""
        daily = [
            _make_daily(10000, date="20260101"),
            _make_daily(9500, date="20260102"),
        ]
        result = calc_prev_day_change(daily)
        assert result == pytest.approx(-5.0, rel=1e-3)

    def test_insufficient_data(self) -> None:
        """데이터 1일 미만 시 0.0."""
        assert calc_prev_day_change([]) == 0.0
        assert calc_prev_day_change([_make_daily(10000)]) == 0.0

    def test_zero_prev_close(self) -> None:
        """전전일 종가 0이면 0.0."""
        daily = [
            _make_daily(0, date="20260101"),
            _make_daily(10000, date="20260102"),
        ]
        assert calc_prev_day_change(daily) == 0.0


# ── check_volume_surge ───────────────────────────────


class TestCheckVolumeSurge:
    """전일 거래량 폭증 테스트."""

    def test_surge_detected(self) -> None:
        """20일 평균의 2배 이상이면 True."""
        # 19일: 1000, 마지막 1일: 3000 → 평균 ~1100, 3000/1100 > 2
        daily = [_make_daily(100, volume=1000, date=str(20260101 + i)) for i in range(19)]
        daily.append(_make_daily(100, volume=3000, date="20260120"))
        assert check_volume_surge(daily) is True

    def test_no_surge(self) -> None:
        """평균 미만이면 False."""
        daily = [_make_daily(100, volume=1000, date=str(20260101 + i)) for i in range(20)]
        assert check_volume_surge(daily) is False

    def test_insufficient_data(self) -> None:
        """20일 미만 데이터면 False."""
        daily = [_make_daily(100, volume=5000, date=str(20260101 + i)) for i in range(10)]
        assert check_volume_surge(daily) is False

    def test_custom_multiplier(self) -> None:
        """커스텀 배수 기준."""
        daily = [_make_daily(100, volume=1000, date=str(20260101 + i)) for i in range(19)]
        daily.append(_make_daily(100, volume=1600, date="20260120"))
        # 평균: (19*1000 + 1600)/20 = 1030, 1600/1030 ≈ 1.55 → 1.5배 이상
        assert check_volume_surge(daily, multiplier=1.5) is True
        assert check_volume_surge(daily, multiplier=2.0) is False


# ── count_consecutive_bullish ────────────────────────


class TestCountConsecutiveBullish:
    """연속 양봉 수 테스트."""

    def test_five_consecutive(self) -> None:
        """5일 연속 양봉."""
        prices = [(100, 110)] * 5  # 모두 close > open
        daily = _make_daily_series(prices)
        assert count_consecutive_bullish(daily) == 5

    def test_broken_streak(self) -> None:
        """중간에 음봉이면 끊김."""
        prices = [
            (100, 110),  # 양봉
            (100, 110),  # 양봉
            (110, 100),  # 음봉 → 끊김
            (100, 110),  # 양봉
            (100, 110),  # 양봉
        ]
        daily = _make_daily_series(prices)
        assert count_consecutive_bullish(daily) == 2

    def test_empty_data(self) -> None:
        """데이터 없으면 0."""
        assert count_consecutive_bullish([]) == 0

    def test_all_bearish(self) -> None:
        """전부 음봉이면 0."""
        prices = [(110, 100)] * 5
        daily = _make_daily_series(prices)
        assert count_consecutive_bullish(daily) == 0

    def test_doji_not_counted(self) -> None:
        """보합(open==close)은 양봉이 아님."""
        prices = [(100, 110), (100, 100)]  # 양봉, 보합
        daily = _make_daily_series(prices)
        assert count_consecutive_bullish(daily) == 0


# ── is_52w_new_high ──────────────────────────────────


class TestIs52wNewHigh:
    """52주 신고가 테스트."""

    def test_new_high(self) -> None:
        """전일 종가가 52주 최고가면 True."""
        daily = [
            _make_daily(10000, high=10000, date="20250301"),
            _make_daily(9500, high=9500, date="20250401"),
            _make_daily(10000, high=10000, date="20260301"),  # 52주 고가와 동일
        ]
        assert is_52w_new_high(daily) is True

    def test_not_new_high(self) -> None:
        """전일 종가가 52주 최고가 미만이면 False."""
        daily = [
            _make_daily(10000, high=11000, date="20250301"),
            _make_daily(9000, high=9000, date="20260301"),
        ]
        assert is_52w_new_high(daily) is False

    def test_empty_data(self) -> None:
        """데이터 없으면 False."""
        assert is_52w_new_high([]) is False


# ── check_screen_condition + 보너스 ──────────────────


def _make_screening_data(
    *,
    days: int = 30,
    base_close: int = 10000,
    latest_close: int = 10000,
    latest_volume: int = 1000,
    avg_volume: int = 1000,
    high_52w: int = 10000,
    prev_close: int = 9500,
    consecutive_bullish_days: int = 0,
) -> list[DailyPrice]:
    """스크리닝 테스트용 DailyPrice 리스트 생성.

    최소 20일 데이터를 만들되, 마지막 2일(전전일/전일)과 최고가를 제어.
    """
    result: list[DailyPrice] = []
    for i in range(days - 2 - consecutive_bullish_days):
        result.append(
            DailyPrice(
                date=str(20260101 + i),
                open=base_close,
                high=high_52w if i == 0 else base_close,
                low=base_close - 100,
                close=base_close,
                volume=avg_volume,
            )
        )
    # 전전일
    result.append(
        DailyPrice(
            date=str(20260101 + days - 2 - consecutive_bullish_days),
            open=prev_close,
            high=prev_close + 100,
            low=prev_close - 100,
            close=prev_close,
            volume=avg_volume,
        )
    )
    # 연속 양봉 일수만큼 양봉 삽입
    for j in range(consecutive_bullish_days):
        idx = days - 1 - consecutive_bullish_days + j
        bull_close = prev_close + (j + 1) * 100
        result.append(
            DailyPrice(
                date=str(20260101 + idx),
                open=bull_close - 50,
                high=bull_close + 100,
                low=bull_close - 100,
                close=bull_close,
                volume=avg_volume,
            )
        )
    result.append(  # 최종일
        DailyPrice(
            date=str(20260101 + days - 1),
            open=latest_close - 50,  # 양봉
            high=max(latest_close, high_52w)
            if consecutive_bullish_days > 0
            else latest_close + 100,
            low=latest_close - 100,
            close=latest_close,
            volume=latest_volume,
        )
    )
    return result


class TestCheckScreenConditionWithBonus:
    """보너스 점수가 포함된 스크리닝 결과 테스트."""

    def test_basic_pass_no_bonus(self) -> None:
        """기본 조건만 통과, 보너스 0점."""
        daily = _make_screening_data(
            days=30,
            base_close=10000,
            latest_close=9500,  # 95% of 10000
            high_52w=10000,
            latest_volume=1000,
            avg_volume=1000,
            prev_close=9500,  # 0% 변동
        )
        result = check_screen_condition(daily, threshold=0.75, volume_ratio=0.8)
        assert result is not None
        assert result["passed"] is True
        assert result["bonus_score"] == 0

    def test_prev_day_change_bonus(self) -> None:
        """전일 등락률 3%+ → 보너스 +1."""
        daily = _make_screening_data(
            days=30,
            latest_close=10300,
            high_52w=10500,
            prev_close=10000,  # 3% 상승
            latest_volume=1000,
            avg_volume=1000,
        )
        result = check_screen_condition(daily, threshold=0.75, volume_ratio=0.8)
        assert result is not None
        assert result["prev_day_change_pct"] >= 3.0
        assert result["bonus_score"] >= 1

    def test_all_bonus_conditions(self) -> None:
        """모든 보너스 조건 충족 시 4점."""
        daily = _make_screening_data(
            days=30,
            latest_close=11000,  # 52주 신고가
            high_52w=11000,
            prev_close=10000,  # +10% 상승
            latest_volume=5000,  # 거래량 폭증 (avg 1000의 5배)
            avg_volume=1000,
            consecutive_bullish_days=5,
        )
        result = check_screen_condition(daily, threshold=0.75, volume_ratio=0.8)
        assert result is not None
        assert result["bonus_score"] == 4
        assert result["prev_day_change_pct"] >= 3.0
        assert result["prev_day_vol_surge"] is True
        assert result["consecutive_bullish"] >= 5
        assert result["is_52w_high"] is True

    def test_insufficient_data_returns_none(self) -> None:
        """20일 미만 데이터면 None."""
        daily = [_make_daily(10000, date=str(20260101 + i)) for i in range(10)]
        result = check_screen_condition(daily, threshold=0.75, volume_ratio=0.8)
        assert result is None

    def test_backward_compatible_fields(self) -> None:
        """기존 필드(close, high_52w 등)가 여전히 존재."""
        daily = _make_screening_data(days=30, latest_close=9000, high_52w=10000)
        result = check_screen_condition(daily, threshold=0.75, volume_ratio=0.8)
        assert result is not None
        for key in (
            "close",
            "high_52w",
            "price_ratio",
            "volume",
            "avg_volume",
            "vol_ratio",
            "date",
            "daily_bars",
            "passed",
        ):
            assert key in result


class TestScreenSortingByBonus:
    """보너스 점수 기반 정렬 테스트."""

    def test_bonus_takes_priority_over_price_ratio(self) -> None:
        """보너스 점수가 높은 종목이 price_ratio보다 우선 정렬."""
        # 높은 bonus, 낮은 price_ratio
        entry_a = {"bonus_score": 3, "price_ratio": 0.80, "symbol": "A"}
        # 낮은 bonus, 높은 price_ratio
        entry_b = {"bonus_score": 1, "price_ratio": 0.95, "symbol": "B"}
        # 같은 bonus, price_ratio로 비교
        entry_c = {"bonus_score": 3, "price_ratio": 0.90, "symbol": "C"}

        items = [entry_b, entry_a, entry_c]
        sorted_items = sorted(
            items,
            key=lambda x: (x.get("bonus_score", 0), x["price_ratio"]),
            reverse=True,
        )
        assert sorted_items[0]["symbol"] == "C"  # bonus 3, pr 0.90
        assert sorted_items[1]["symbol"] == "A"  # bonus 3, pr 0.80
        assert sorted_items[2]["symbol"] == "B"  # bonus 1, pr 0.95
