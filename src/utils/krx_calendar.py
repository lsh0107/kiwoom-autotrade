"""KRX 공휴일 캘린더 유틸 (ADR-023).

data/krx_holidays.json을 로드해 영업일 판정·계산을 수행한다.
pykrx 의존 없음 — 프로세스 시작 시 1회 로드 후 메모리 유지.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

_HOLIDAYS_FILE = Path(__file__).parents[2] / "data" / "krx_holidays.json"


def _load_holidays() -> set[date]:
    """krx_holidays.json에서 공휴일을 로드한다.

    Returns:
        공휴일 날짜 집합 (date 객체).

    Raises:
        FileNotFoundError: data/krx_holidays.json가 없는 경우.
    """
    with _HOLIDAYS_FILE.open(encoding="utf-8") as f:
        data: dict[str, list[str]] = json.load(f)
    holidays: set[date] = set()
    for _year_str, days in data.items():
        for day_str in days:
            holidays.add(date.fromisoformat(day_str))
    return holidays


_HOLIDAYS: set[date] = _load_holidays()


def is_business_day(d: date) -> bool:
    """오늘이 KRX 영업일인지 반환한다.

    Args:
        d: 판정 기준일.

    Returns:
        True이면 영업일 (평일 + 공휴일 아님).
    """
    return d.weekday() < 5 and d not in _HOLIDAYS


def previous_business_day(d: date) -> date:
    """d 이전의 가장 가까운 영업일을 반환한다.

    Args:
        d: 기준일 (exclusive).

    Returns:
        d 직전 영업일.
    """
    cur = d - timedelta(days=1)
    while not is_business_day(cur):
        cur -= timedelta(days=1)
    return cur


def next_business_day(d: date) -> date:
    """d 이후의 가장 가까운 영업일을 반환한다.

    Args:
        d: 기준일 (exclusive).

    Returns:
        d 직후 영업일.
    """
    cur = d + timedelta(days=1)
    while not is_business_day(cur):
        cur += timedelta(days=1)
    return cur


def is_last_business_day_of_month(d: date) -> bool:
    """d가 해당 월의 마지막 영업일인지 반환한다.

    d가 영업일이고, d의 다음 영업일이 다음 달이면 True.

    Args:
        d: 판정 기준일.

    Returns:
        True이면 이번 달 마지막 영업일.
    """
    if not is_business_day(d):
        return False
    nxt = next_business_day(d)
    return nxt.month != d.month


def add_business_days(d: date, n: int) -> date:
    """d에서 n 영업일 이후의 날짜를 반환한다.

    Args:
        d: 기준일.
        n: 더할 영업일 수.

    Returns:
        n 영업일 후 날짜.
    """
    cur = d
    for _ in range(n):
        cur = next_business_day(cur)
    return cur
