"""한국 공휴일 체크 모듈 테스트."""

from datetime import date

import pytest
from scripts.korean_holidays import (
    get_holidays,
    is_holiday,
    is_market_closed,
    is_weekend,
)


class TestGetHolidays:
    """공휴일 목록 조회 테스트."""

    def test_2026_holidays_count(self) -> None:
        """2026년 공휴일 15개."""
        holidays = get_holidays(2026)
        assert len(holidays) == 15

    def test_2026_new_year(self) -> None:
        """신정 포함 확인."""
        holidays = get_holidays(2026)
        assert date(2026, 1, 1) in holidays
        assert holidays[date(2026, 1, 1)] == "신정"

    def test_2026_seollal(self) -> None:
        """설날 연휴 3일 포함."""
        holidays = get_holidays(2026)
        assert date(2026, 2, 16) in holidays
        assert date(2026, 2, 17) in holidays
        assert date(2026, 2, 18) in holidays

    def test_2026_chuseok(self) -> None:
        """추석 연휴 3일 포함."""
        holidays = get_holidays(2026)
        assert date(2026, 9, 24) in holidays
        assert date(2026, 9, 25) in holidays
        assert date(2026, 9, 26) in holidays

    def test_2026_christmas(self) -> None:
        """성탄절 포함."""
        holidays = get_holidays(2026)
        assert date(2026, 12, 25) in holidays

    def test_unsupported_year_empty(self) -> None:
        """지원하지 않는 연도는 빈 딕셔너리."""
        assert get_holidays(2025) == {}
        assert get_holidays(2027) == {}


class TestIsHoliday:
    """개별 날짜 공휴일 확인 테스트."""

    def test_holiday_true(self) -> None:
        """공휴일이면 (True, 이름)."""
        result, name = is_holiday(date(2026, 3, 1))
        assert result is True
        assert name == "삼일절"

    def test_holiday_false(self) -> None:
        """평일이면 (False, '')."""
        result, name = is_holiday(date(2026, 3, 2))
        assert result is False
        assert name == ""

    def test_children_day(self) -> None:
        """어린이날."""
        result, name = is_holiday(date(2026, 5, 5))
        assert result is True
        assert name == "어린이날"

    def test_buddha_birthday(self) -> None:
        """부처님오신날."""
        result, name = is_holiday(date(2026, 5, 24))
        assert result is True
        assert name == "부처님오신날"


class TestIsWeekend:
    """주말 확인 테스트."""

    def test_saturday(self) -> None:
        """토요일은 주말."""
        # 2026-03-07은 토요일
        assert is_weekend(date(2026, 3, 7)) is True

    def test_sunday(self) -> None:
        """일요일은 주말."""
        # 2026-03-08은 일요일
        assert is_weekend(date(2026, 3, 8)) is True

    def test_weekday(self) -> None:
        """평일은 주말 아님."""
        # 2026-03-09은 월요일
        assert is_weekend(date(2026, 3, 9)) is False


class TestIsMarketClosed:
    """장 휴무일 통합 테스트."""

    def test_holiday(self) -> None:
        """공휴일은 장 휴무 (평일 공휴일: 한글날 10/9 금요일)."""
        closed, reason = is_market_closed(date(2026, 10, 9))
        assert closed is True
        assert reason == "한글날"

    def test_weekend(self) -> None:
        """주말은 장 휴무."""
        closed, reason = is_market_closed(date(2026, 3, 7))
        assert closed is True
        assert reason == "주말"

    def test_normal_weekday(self) -> None:
        """평일 영업일."""
        closed, reason = is_market_closed(date(2026, 3, 9))
        assert closed is False
        assert reason == ""

    def test_holiday_on_weekday(self) -> None:
        """평일 공휴일 (6/6 토요일 아닌지 확인)."""
        # 2026-06-06은 토요일이므로 주말로 먼저 잡힘
        closed, _reason = is_market_closed(date(2026, 6, 6))
        assert closed is True

    @pytest.mark.parametrize(
        ("month", "day"),
        [(1, 1), (3, 1), (5, 5), (5, 24), (8, 15), (10, 3), (10, 9), (12, 25)],
    )
    def test_all_single_holidays(self, month: int, day: int) -> None:
        """모든 단일 공휴일 확인."""
        closed, _ = is_market_closed(date(2026, month, day))
        assert closed is True


class TestCLI:
    """CLI 동작 테스트."""

    def test_check_date_holiday_via_flag(self) -> None:
        """공휴일 날짜를 --date로 지정 시 SystemExit(1)."""
        import unittest.mock

        with (
            pytest.raises(SystemExit) as exc_info,
            unittest.mock.patch("sys.argv", ["korean_holidays.py", "--date", "2026-01-01"]),
        ):
            from scripts.korean_holidays import main

            main()

        assert exc_info.value.code == 1

    def test_check_specific_date_workday(self) -> None:
        """영업일 --date 시 SystemExit(0)."""
        import unittest.mock

        with (
            pytest.raises(SystemExit) as exc_info,
            unittest.mock.patch("sys.argv", ["korean_holidays.py", "--date", "2026-03-09"]),
        ):
            from scripts.korean_holidays import main

            main()

        assert exc_info.value.code == 0

    def test_check_specific_date_holiday(self) -> None:
        """공휴일 --date 시 SystemExit(1)."""
        import unittest.mock

        with (
            pytest.raises(SystemExit) as exc_info,
            unittest.mock.patch("sys.argv", ["korean_holidays.py", "--date", "2026-03-01"]),
        ):
            from scripts.korean_holidays import main

            main()

        assert exc_info.value.code == 1

    def test_list_holidays(self) -> None:
        """--list 시 공휴일 목록 출력 후 exit 0."""
        import unittest.mock

        with (
            pytest.raises(SystemExit) as exc_info,
            unittest.mock.patch("sys.argv", ["korean_holidays.py", "--list"]),
        ):
            from scripts.korean_holidays import main

            main()

        assert exc_info.value.code == 0
