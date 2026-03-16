#!/usr/bin/env python3
"""한국 공휴일 체크 스크립트.

매년 초에 공휴일 목록을 갱신한다.
cron 스크립트에서 장 시작 전에 호출하여 공휴일이면 스킵한다.

사용법:
    python scripts/korean_holidays.py --check-today
    # exit 0: 공휴일 아님 (정상 진행)
    # exit 1: 공휴일 (스킵)

    python scripts/korean_holidays.py --list
    # 공휴일 목록 출력
"""

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

# 2026년 한국 공휴일 (매년 초 갱신 필요)
HOLIDAYS_2026: list[tuple[int, int, str]] = [
    (1, 1, "신정"),
    (2, 16, "설날 연휴"),
    (2, 17, "설날"),
    (2, 18, "설날 연휴"),
    (3, 1, "삼일절"),
    (5, 5, "어린이날"),
    (5, 24, "부처님오신날"),
    (6, 6, "현충일"),
    (8, 15, "광복절"),
    (9, 24, "추석 연휴"),
    (9, 25, "추석"),
    (9, 26, "추석 연휴"),
    (10, 3, "개천절"),
    (10, 9, "한글날"),
    (12, 25, "성탄절"),
]


def get_holidays(year: int) -> dict[date, str]:
    """해당 연도의 공휴일 딕셔너리 반환.

    Args:
        year: 연도

    Returns:
        공휴일 날짜 → 이름 매핑
    """
    if year == 2026:
        return {date(year, m, d): name for m, d, name in HOLIDAYS_2026}
    # 지원하지 않는 연도
    return {}


def is_holiday(check_date: date) -> tuple[bool, str]:
    """주어진 날짜가 공휴일인지 확인.

    Args:
        check_date: 확인할 날짜

    Returns:
        (공휴일 여부, 공휴일 이름)
    """
    holidays = get_holidays(check_date.year)
    name = holidays.get(check_date, "")
    return (bool(name), name)


def is_weekend(check_date: date) -> bool:
    """주말 여부 확인.

    Args:
        check_date: 확인할 날짜

    Returns:
        토요일(5) 또는 일요일(6)이면 True
    """
    return check_date.weekday() >= 5


def is_market_closed(check_date: date) -> tuple[bool, str]:
    """장 휴무일인지 확인 (주말 + 공휴일).

    Args:
        check_date: 확인할 날짜

    Returns:
        (휴무 여부, 사유)
    """
    if is_weekend(check_date):
        return (True, "주말")
    holiday, name = is_holiday(check_date)
    if holiday:
        return (True, name)
    return (False, "")


def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(description="한국 공휴일 체크")
    parser.add_argument(
        "--check-today",
        action="store_true",
        help="오늘이 공휴일이면 exit 1, 아니면 exit 0",
    )
    parser.add_argument("--list", action="store_true", help="공휴일 목록 출력")
    parser.add_argument("--date", default=None, help="특정 날짜 체크 (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.list:
        holidays = get_holidays(2026)
        for d, name in sorted(holidays.items()):
            print(f"{d.isoformat()}  {name}")  # noqa: T201
        sys.exit(0)

    if args.check_today or args.date:
        kst = timezone(timedelta(hours=9))
        check_date = date.fromisoformat(args.date) if args.date else datetime.now(kst).date()

        closed, reason = is_market_closed(check_date)
        if closed:
            print(f"휴무일: {check_date.isoformat()} ({reason})")  # noqa: T201
            sys.exit(1)
        else:
            print(f"영업일: {check_date.isoformat()}")  # noqa: T201
            sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
