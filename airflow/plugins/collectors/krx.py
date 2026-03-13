"""pykrx 기반 KRX 시장 데이터 수집기."""

from __future__ import annotations

import logging
import time

try:
    from pykrx import stock
except ImportError:
    stock = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# pykrx rate limit 준수 간격 (초)
_SLEEP_INTERVAL = 1.5


def collect_ohlcv(
    date: str,
    market: str = "KOSPI",
) -> list[dict]:
    """특정 일자의 전 종목 OHLCV 수집.

    Args:
        date: 조회 날짜 (YYYYMMDD 형식).
        market: 시장 구분. "KOSPI" | "KOSDAQ" | "KONEX".

    Returns:
        OHLCV 레코드 목록. 각 항목은 ticker, open, high, low, close, volume 포함.
    """
    df = stock.get_market_ohlcv(date, market=market)
    time.sleep(_SLEEP_INTERVAL)

    if df is None or df.empty:
        logger.info("OHLCV 없음: %s %s", date, market)
        return []

    df = df.reset_index()
    df.columns = [col.lower() for col in df.columns]

    # 티커 컬럼명 통일
    if "티커" in df.columns:
        df = df.rename(columns={"티커": "ticker"})

    records = df.to_dict("records")
    logger.info("OHLCV 수집 완료: %s %s — %d종목", date, market, len(records))
    return records


def collect_investor_trading(
    date: str,
    market: str = "KOSPI",
) -> list[dict]:
    """특정 일자의 투자자별 매매 데이터 수집.

    Args:
        date: 조회 날짜 (YYYYMMDD 형식).
        market: 시장 구분. "KOSPI" | "KOSDAQ" | "KONEX".

    Returns:
        투자자별 매매 레코드 목록. 개인/기관/외국인 순매수 포함.
    """
    df = stock.get_market_trading_value_by_investor(date, date, market)
    time.sleep(_SLEEP_INTERVAL)

    if df is None or df.empty:
        logger.info("투자자 매매 없음: %s %s", date, market)
        return []

    df = df.reset_index()
    records = df.to_dict("records")
    logger.info("투자자 매매 수집 완료: %s %s — %d행", date, market, len(records))
    return records


def collect_market_cap(
    date: str,
    market: str = "KOSPI",
) -> list[dict]:
    """특정 일자의 시가총액 데이터 수집.

    Args:
        date: 조회 날짜 (YYYYMMDD 형식).
        market: 시장 구분. "KOSPI" | "KOSDAQ" | "KONEX".

    Returns:
        시가총액 레코드 목록. ticker, 시가총액, 상장주식수 포함.
    """
    df = stock.get_market_cap(date, market=market)
    time.sleep(_SLEEP_INTERVAL)

    if df is None or df.empty:
        logger.info("시가총액 없음: %s %s", date, market)
        return []

    df = df.reset_index()
    records = df.to_dict("records")
    logger.info("시가총액 수집 완료: %s %s — %d종목", date, market, len(records))
    return records
