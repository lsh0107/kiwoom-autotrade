"""KST 시간 유틸리티 테스트."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.utils.time import (
    is_extended_hours,
    is_market_open,
    is_trading_hours,
    now_kst,
    today_kst,
)

KST_TZ = ZoneInfo("Asia/Seoul")


def _make_kst(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    weekday: int | None = None,
) -> datetime:
    """테스트용 KST datetime 생성. weekday가 지정되면 해당 요일의 날짜를 찾는다."""
    dt = datetime(year, month, day, hour, minute, tzinfo=KST_TZ)
    if weekday is not None:
        # 원하는 요일까지 날짜 이동
        while dt.weekday() != weekday:
            dt = dt.replace(day=dt.day + 1)
    return dt


class TestNowKst:
    """now_kst 함수 테스트."""

    def test_now_kst(self) -> None:
        """KST 시각 반환 확인."""
        result = now_kst()

        assert result.tzinfo is not None
        assert str(result.tzinfo) == "Asia/Seoul"


class TestIsMarketOpen:
    """is_market_open 함수 테스트."""

    @patch("src.utils.time.now_kst")
    def test_is_market_open_during_hours(self, mock_now: object) -> None:
        """장중(평일 10:00) True 반환."""
        # 2026-03-02는 월요일
        mock_now.return_value = datetime(2026, 3, 2, 10, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_market_open() is True

    @patch("src.utils.time.now_kst")
    def test_is_market_open_outside_hours(self, mock_now: object) -> None:
        """장외(평일 07:00) False 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 7, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_market_open() is False

    @patch("src.utils.time.now_kst")
    def test_is_market_open_after_close(self, mock_now: object) -> None:
        """장 마감 후(평일 16:00) False 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 16, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_market_open() is False

    @patch("src.utils.time.now_kst")
    def test_is_market_open_weekend(self, mock_now: object) -> None:
        """주말 False 반환."""
        # 2026-03-07은 토요일
        mock_now.return_value = datetime(2026, 3, 7, 10, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_market_open() is False

    @patch("src.utils.time.now_kst")
    def test_is_market_open_at_open(self, mock_now: object) -> None:
        """장 시작 시각(09:00) 정확히 True 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 9, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_market_open() is True

    @patch("src.utils.time.now_kst")
    def test_is_market_open_at_close(self, mock_now: object) -> None:
        """장 마감 시각(15:30) 정확히 True 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 15, 30, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_market_open() is True


class TestIsTradingHours:
    """is_trading_hours 함수 테스트."""

    @patch("src.utils.time.now_kst")
    def test_is_trading_hours_pre_market(self, mock_now: object) -> None:
        """프리마켓 시간(08:30) True 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 8, 30, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_trading_hours() is True

    @patch("src.utils.time.now_kst")
    def test_is_trading_hours_before_pre_market(self, mock_now: object) -> None:
        """프리마켓 전(07:59) False 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 7, 59, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_trading_hours() is False

    @patch("src.utils.time.now_kst")
    def test_is_trading_hours_weekend(self, mock_now: object) -> None:
        """주말 프리마켓 시간이어도 False 반환."""
        # 2026-03-08은 일요일
        mock_now.return_value = datetime(2026, 3, 8, 9, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_trading_hours() is False


class TestIsExtendedHours:
    """is_extended_hours 함수 테스트."""

    @patch("src.utils.time.now_kst")
    def test_is_extended_hours_after_close(self, mock_now: object) -> None:
        """시간외 거래(16:00) True 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 16, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_extended_hours() is True

    @patch("src.utils.time.now_kst")
    def test_is_extended_hours_at_boundary(self, mock_now: object) -> None:
        """시간외 종료 시각(18:00) 정확히 True 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 18, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_extended_hours() is True

    @patch("src.utils.time.now_kst")
    def test_is_extended_hours_after_boundary(self, mock_now: object) -> None:
        """시간외 종료 후(18:01) False 반환."""
        mock_now.return_value = datetime(2026, 3, 2, 18, 1, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_extended_hours() is False

    @patch("src.utils.time.now_kst")
    def test_is_extended_hours_weekend(self, mock_now: object) -> None:
        """주말 시간외 시간이어도 False 반환."""
        mock_now.return_value = datetime(2026, 3, 7, 10, 0, tzinfo=KST_TZ)  # type: ignore[attr-defined]

        assert is_extended_hours() is False


class TestTodayKst:
    """today_kst 함수 테스트."""

    def test_today_kst(self) -> None:
        """오늘 KST 시작 시각(00:00:00) 반환."""
        result = today_kst()

        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0
        assert str(result.tzinfo) == "Asia/Seoul"
