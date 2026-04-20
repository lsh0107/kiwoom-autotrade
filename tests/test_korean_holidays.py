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

    def test_unsupported_year_empty(self) -> None:
        """지원하지 않는 연도는 빈 딕셔너리."""
        assert get_holidays(2025) == {}
        assert get_holidays(2027) == {}

    def test_supported_year_nonempty(self) -> None:
        """지원 연도(2026)는 공휴일 목록을 반환한다."""
        holidays = get_holidays(2026)
        assert len(holidays) > 0

    def test_holiday_names_are_strings(self) -> None:
        """공휴일 이름은 비어있지 않은 문자열이다."""
        holidays = get_holidays(2026)
        for name in holidays.values():
            assert isinstance(name, str) and name


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
