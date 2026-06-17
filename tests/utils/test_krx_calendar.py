"""krx_calendar 단위 테스트 (ADR-023)."""

from __future__ import annotations

from datetime import date


class TestIsBusinessDay:
    """is_business_day: 영업일 판정."""

    def test_weekday_not_holiday_is_business(self) -> None:
        """평일이고 공휴일 아닌 날 → True."""
        from src.utils.krx_calendar import is_business_day

        # 2026-04-27 (월) — 공휴일 아님
        assert is_business_day(date(2026, 4, 27)) is True

    def test_weekend_not_business_day(self) -> None:
        """주말은 영업일 아님."""
        from src.utils.krx_calendar import is_business_day

        assert is_business_day(date(2026, 4, 25)) is False  # 토요일
        assert is_business_day(date(2026, 4, 26)) is False  # 일요일

    def test_2026_seollal_holiday(self) -> None:
        """2026 설날 연휴 (2/16~18) → 영업일 아님."""
        from src.utils.krx_calendar import is_business_day

        assert is_business_day(date(2026, 2, 16)) is False
        assert is_business_day(date(2026, 2, 17)) is False
        assert is_business_day(date(2026, 2, 18)) is False

    def test_2026_new_year_holiday(self) -> None:
        """2026 신정 (1/1) → 영업일 아님."""
        from src.utils.krx_calendar import is_business_day

        assert is_business_day(date(2026, 1, 1)) is False

    def test_day_after_holiday_is_business(self) -> None:
        """공휴일 다음 평일 → 영업일."""
        from src.utils.krx_calendar import is_business_day

        # 2026-02-19 (목) — 설날 연휴 다음날
        assert is_business_day(date(2026, 2, 19)) is True


class TestPreviousBusinessDay:
    """previous_business_day: 직전 영업일 반환."""

    def test_previous_business_day_skips_holiday(self) -> None:
        """공휴일 다음 날 기준으로 이전 영업일 조회 시 공휴일 스킵."""
        from src.utils.krx_calendar import previous_business_day

        # 2026-02-19 → 이전 영업일 = 2026-02-13 (설날 연휴 2/16~18 스킵, 2/14~15 주말 스킵)
        result = previous_business_day(date(2026, 2, 19))
        assert result == date(2026, 2, 13)

    def test_previous_business_day_from_monday(self) -> None:
        """월요일에서 이전 영업일 → 금요일 (주말 스킵)."""
        from src.utils.krx_calendar import previous_business_day

        # 2026-04-27 (월) → 이전 영업일 = 2026-04-24 (금)
        result = previous_business_day(date(2026, 4, 27))
        assert result == date(2026, 4, 24)


class TestNextBusinessDay:
    """next_business_day: 직후 영업일 반환."""

    def test_next_business_day_skips_weekend(self) -> None:
        """금요일 다음 영업일 → 월요일."""
        from src.utils.krx_calendar import next_business_day

        # 2026-04-24 (금) → 2026-04-27 (월)
        result = next_business_day(date(2026, 4, 24))
        assert result == date(2026, 4, 27)

    def test_next_business_day_skips_holiday(self) -> None:
        """연휴 전날 다음 영업일 → 연휴 후 첫 평일."""
        from src.utils.krx_calendar import next_business_day

        # 2026-02-13 (금) → 다음 영업일은 2/16~18 설날 연휴 스킵 → 2026-02-19 (목)
        result = next_business_day(date(2026, 2, 13))
        assert result == date(2026, 2, 19)


class TestIsLastBusinessDayOfMonth:
    """is_last_business_day_of_month: 월말 마지막 영업일 판정."""

    def test_last_business_day_of_february_2026(self) -> None:
        """2026년 2월 마지막 영업일 판정."""
        from src.utils.krx_calendar import is_last_business_day_of_month

        # 2026-02-27 (금) — 2월 마지막 영업일
        assert is_last_business_day_of_month(date(2026, 2, 27)) is True

    def test_non_last_business_day_returns_false(self) -> None:
        """월 중간 날짜 → False."""
        from src.utils.krx_calendar import is_last_business_day_of_month

        assert is_last_business_day_of_month(date(2026, 4, 15)) is False

    def test_weekend_not_last_business_day(self) -> None:
        """주말은 영업일이 아니므로 False."""
        from src.utils.krx_calendar import is_last_business_day_of_month

        assert is_last_business_day_of_month(date(2026, 4, 25)) is False  # 토요일

    def test_last_business_day_of_april_2026(self) -> None:
        """2026-04-30 (목) → 4월 마지막 영업일."""
        from src.utils.krx_calendar import is_last_business_day_of_month

        assert is_last_business_day_of_month(date(2026, 4, 30)) is True

    def test_not_last_day_when_next_business_same_month(self) -> None:
        """다음 영업일이 같은 달이면 False."""
        from src.utils.krx_calendar import is_last_business_day_of_month

        # 2026-04-29 (수) — 다음 영업일은 4/30 (같은 달)
        assert is_last_business_day_of_month(date(2026, 4, 29)) is False


class TestAddBusinessDays:
    """add_business_days: N 영업일 후 날짜 계산."""

    def test_add_business_days(self) -> None:
        """2 영업일 후 날짜 계산 (T+2 결제일)."""
        from src.utils.krx_calendar import add_business_days

        # 2026-04-28 (화) + 2 영업일 = 2026-04-30 (목)
        result = add_business_days(date(2026, 4, 28), 2)
        assert result == date(2026, 4, 30)

    def test_add_business_days_skips_weekend(self) -> None:
        """영업일 추가 시 주말 스킵."""
        from src.utils.krx_calendar import add_business_days

        # 2026-04-24 (금) + 2 영업일 = 4/27(월) + 1 = 4/28(화)
        result = add_business_days(date(2026, 4, 24), 2)
        assert result == date(2026, 4, 28)

    def test_add_business_days_skips_holiday(self) -> None:
        """영업일 추가 시 공휴일 스킵."""
        from src.utils.krx_calendar import add_business_days

        # 2026-02-13 (금) + 2 영업일: 2/14~15(주말), 2/16~18(설날) 모두 스킵
        # → 2/19(목), 2/20(금)
        result = add_business_days(date(2026, 2, 13), 2)
        assert result == date(2026, 2, 20)

    def test_add_zero_business_days(self) -> None:
        """0 영업일 추가 → next_business_day 1회 적용."""
        from src.utils.krx_calendar import add_business_days

        # 0이면 루프 미실행 → d 그대로 반환
        d = date(2026, 4, 28)
        result = add_business_days(d, 0)
        assert result == d


class TestLatestCompletedBusinessDay:
    """PR A2: 검증 시점 기준 마지막으로 완성된 일봉 날짜."""

    def test_intraday_business_day_returns_previous(self) -> None:
        """영업일 09:32 (장중) → 직전 영업일."""
        from datetime import datetime

        from src.utils.krx_calendar import latest_completed_business_day
        from src.utils.time import KST

        as_of = date(2026, 6, 17)  # 수요일
        now = datetime(2026, 6, 17, 9, 32, tzinfo=KST)
        assert latest_completed_business_day(as_of, now_kst=now) == date(2026, 6, 16)

    def test_post_market_business_day_returns_today(self) -> None:
        """영업일 17:00 (ready_hhmm=1700 이후) → today."""
        from datetime import datetime

        from src.utils.krx_calendar import latest_completed_business_day
        from src.utils.time import KST

        as_of = date(2026, 6, 17)
        now = datetime(2026, 6, 17, 17, 0, tzinfo=KST)
        assert latest_completed_business_day(as_of, now_kst=now) == as_of

    def test_just_before_ready_returns_previous(self) -> None:
        """영업일 16:59 (ready_hhmm=1700 직전) → 직전 영업일."""
        from datetime import datetime

        from src.utils.krx_calendar import latest_completed_business_day
        from src.utils.time import KST

        now = datetime(2026, 6, 17, 16, 59, tzinfo=KST)
        assert latest_completed_business_day(date(2026, 6, 17), now_kst=now) == date(2026, 6, 16)

    def test_holiday_returns_previous_business_day(self) -> None:
        """as_of 가 휴장이면 시간대 무관 직전 영업일."""
        from datetime import datetime

        from src.utils.krx_calendar import latest_completed_business_day
        from src.utils.time import KST

        saturday = date(2026, 6, 13)
        now = datetime(2026, 6, 13, 9, 0, tzinfo=KST)
        assert latest_completed_business_day(saturday, now_kst=now) == date(2026, 6, 12)

    def test_custom_ready_hhmm_override(self) -> None:
        """ready_hhmm=1830 이면 17:00 도 직전 영업일."""
        from datetime import datetime

        from src.utils.krx_calendar import latest_completed_business_day
        from src.utils.time import KST

        now = datetime(2026, 6, 17, 17, 0, tzinfo=KST)
        assert latest_completed_business_day(
            date(2026, 6, 17), now_kst=now, ready_hhmm="1830"
        ) == date(2026, 6, 16)

    def test_env_var_override(self, monkeypatch) -> None:
        """DAILY_CANDLE_READY_HHMM env 가 기본값을 override."""
        from datetime import datetime

        from src.utils.krx_calendar import latest_completed_business_day
        from src.utils.time import KST

        monkeypatch.setenv("DAILY_CANDLE_READY_HHMM", "1800")
        now = datetime(2026, 6, 17, 17, 30, tzinfo=KST)
        # ready_hhmm=1800 (env) > 17:30 → 직전 영업일
        assert latest_completed_business_day(date(2026, 6, 17), now_kst=now) == date(2026, 6, 16)

    def test_now_kst_different_date_uses_as_of_business(self) -> None:
        """now_kst.date() != as_of 면 시간대 판정 미적용, as_of 영업일이면 그대로."""
        from datetime import datetime

        from src.utils.krx_calendar import latest_completed_business_day
        from src.utils.time import KST

        as_of = date(2026, 6, 16)  # 화요일 영업일
        now = datetime(2026, 6, 17, 9, 0, tzinfo=KST)  # 다른 날
        assert latest_completed_business_day(as_of, now_kst=now) == as_of
