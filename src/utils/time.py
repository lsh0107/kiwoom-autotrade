"""KST 시간 유틸리티 + 장 운영시간 체크."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 장 시간
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 30)
PRE_MARKET_OPEN = time(8, 0)
AFTER_MARKET_CLOSE = time(18, 0)


def now_kst() -> datetime:
    """현재 KST 시각."""
    return datetime.now(tz=KST)


def is_market_open() -> bool:
    """정규장 운영 중인지 (09:00~15:30)."""
    now = now_kst()
    if now.weekday() >= 5:  # 토/일
        return False
    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def is_trading_hours() -> bool:
    """프리마켓~정규장 포함 거래 가능 시간 (08:00~15:30)."""
    now = now_kst()
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    return PRE_MARKET_OPEN <= current_time <= MARKET_CLOSE


def is_extended_hours() -> bool:
    """시간외 거래 포함 전체 (08:00~18:00)."""
    now = now_kst()
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    return PRE_MARKET_OPEN <= current_time <= AFTER_MARKET_CLOSE


def today_kst() -> datetime:
    """오늘 KST 날짜 (시작 시각)."""
    return now_kst().replace(hour=0, minute=0, second=0, microsecond=0)
