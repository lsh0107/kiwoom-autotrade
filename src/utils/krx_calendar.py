"""KRX 공휴일 캘린더 유틸 (ADR-023).

data/krx_holidays.json을 로드해 영업일 판정·계산을 수행한다.
pykrx 의존 없음 — 프로세스 시작 시 1회 로드 후 메모리 유지.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

_HOLIDAYS_FILE = Path(__file__).parents[2] / "data" / "krx_holidays.json"

# 일봉 ready 기준 시각 (HHMM). 장 마감 15:30 + provider/backfill 지연 여유.
# env DAILY_CANDLE_READY_HHMM 로 override 가능.
_DEFAULT_DAILY_CANDLE_READY_HHMM = "1700"


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


def latest_completed_business_day(
    as_of: date,
    *,
    now_kst: datetime | None = None,
    ready_hhmm: str | None = None,
) -> date:
    """검증 시점 기준 마지막으로 완성된 일봉 날짜.

    PR A2 (2026-06-17 도입): preflight / cross_momentum 등이 daily_candles 의
    최신성을 검사할 때 "오늘 영업일이면 무조건 today" 가 아니라 "장 마감 +
    provider/backfill 지연 후에야 today 일봉이 완성된다" 는 현실을 반영한다.

    정책:
        - as_of 가 휴장일 → 직전 영업일.
        - as_of 가 영업일 + now_kst 가 ready_hhmm **이후** → as_of (today).
        - as_of 가 영업일 + now_kst 가 ready_hhmm 이전 → 직전 영업일 (장중).
        - now_kst 의 date 가 as_of 와 다르면 시간대 판정 미적용 (보수적으로 as_of 가
          영업일이면 그대로 as_of, 휴장이면 직전 영업일).

    Args:
        as_of: 기준일 (보통 오늘 또는 검증 대상일).
        now_kst: 현재 KST 시각. None 이면 ``datetime.now(KST)``. 장중/장후 판정용.
        ready_hhmm: 일봉 ready 기준 시각 HHMM. None 이면 env
            ``DAILY_CANDLE_READY_HHMM`` (없으면 "1700").

    Returns:
        max(daily_candles.date) 가 이 값 이상이면 freshness PASS.

    Examples:
        영업일 09:32 (장중) → 직전 영업일
        영업일 17:00 (장 후) → 오늘
        토요일 09:00 (휴장) → 직전 금요일
    """
    if not is_business_day(as_of):
        return previous_business_day(as_of)

    if ready_hhmm is None:
        ready_hhmm = os.environ.get("DAILY_CANDLE_READY_HHMM", _DEFAULT_DAILY_CANDLE_READY_HHMM)

    if now_kst is None:
        from src.utils.time import KST

        now_kst = datetime.now(tz=KST)

    # 시간대 판정은 now_kst.date() == as_of 일 때만 의미가 있음.
    # 다른 날짜면 보수적으로 as_of (영업일) 그대로 사용.
    if now_kst.date() != as_of:
        return as_of

    current_hhmm = f"{now_kst.hour:02d}{now_kst.minute:02d}"
    if current_hhmm < ready_hhmm:
        # 장중 — 오늘 일봉 아직 미완성. 직전 영업일까지 fresh 면 OK.
        return previous_business_day(as_of)
    return as_of


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
