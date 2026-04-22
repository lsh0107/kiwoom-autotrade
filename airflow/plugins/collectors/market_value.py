"""시장 전체 거래대금(market trading value) 수집기.

Design 013 PR 2 — KOSPI 일간 거래대금과 최근 5거래일 평균 거래대금을 산출해
MarketContext가 detect_style에 넘길 `market_value_ratio` 계산 원천 데이터를 생성한다.

pykrx get_market_ohlcv_by_date 사용.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

try:
    from pykrx import stock
except ImportError:
    stock = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# pykrx rate limit 준수 간격 (초)
_SLEEP_INTERVAL = 1.5

# 평균 산출 윈도우 (거래일 기준)
_ROLLING_WINDOW = 5

# 최근 5거래일 확보를 위한 조회 기간 (달력일 버퍼 — 주말/공휴일 고려)
_FETCH_DAYS = 14


def collect_market_value(date: str, market: str = "KOSPI") -> dict[str, Any]:
    """시장 전체 일간 거래대금 + 최근 5거래일 평균 수집.

    KOSPI(또는 지정 시장) 전체 종목의 거래대금 합계를 추출하며,
    최근 _ROLLING_WINDOW(기본 5)거래일 평균을 함께 계산한다.

    Args:
        date: 기준 날짜 (YYYYMMDD)
        market: 시장 구분. "KOSPI" | "KOSDAQ"

    Returns:
        거래대금 딕셔너리.
        예: {
            "value_today": 8_500_000_000_000.0,
            "value_avg_5d": 10_200_000_000_000.0,
            "ratio": 0.83,
            "date": "20260421",
            "market": "KOSPI",
            "available": True,
            "data_points": 5,
        }
        수집 불가 시 value_today/value_avg_5d/ratio=None, available=False, reason 포함.

    Raises:
        ImportError: pykrx 미설치 시.

    Note:
        pykrx `get_market_ohlcv_by_date(..., ticker="KOSPI")`는 시장 전체 일봉을
        직접 제공하지 않아, 실제로는 지수 티커(1001 KOSPI)로 거래대금 조회.
        fallback: 지수에 '거래대금' 컬럼이 없으면 `get_market_cap_by_date`의
        '거래대금' 컬럼을 합산.
    """
    if stock is None:
        raise ImportError("pykrx 패키지 미설치 — pip install pykrx")

    end_dt = datetime.strptime(date, "%Y%m%d")  # noqa: DTZ007 — pykrx는 문자열 사용
    start_dt = end_dt - timedelta(days=_FETCH_DAYS)

    try:
        # pykrx 지수 OHLCV는 '거래대금' 컬럼을 포함 (KOSPI 티커=1001)
        ticker = "1001" if market == "KOSPI" else "2001"
        df = stock.get_index_ohlcv_by_date(
            fromdate=start_dt.strftime("%Y%m%d"),
            todate=date,
            ticker=ticker,
        )
    except Exception as exc:
        logger.warning("market_value 조회 실패: date=%s market=%s — %s", date, market, exc)
        return {
            "value_today": None,
            "value_avg_5d": None,
            "ratio": None,
            "date": date,
            "market": market,
            "available": False,
            "reason": str(exc),
        }
    time.sleep(_SLEEP_INTERVAL)

    if df is None or df.empty:
        logger.warning("market_value 데이터 없음: date=%s market=%s", date, market)
        return {
            "value_today": None,
            "value_avg_5d": None,
            "ratio": None,
            "date": date,
            "market": market,
            "available": False,
            "reason": "no_data",
        }

    # pykrx 컬럼명(한글/영문 대비)
    value_col = None
    for candidate in ("거래대금", "Trading Value", "trading_value"):
        if candidate in df.columns:
            value_col = candidate
            break
    if value_col is None:
        logger.warning("market_value 거래대금 컬럼 없음 — 컬럼: %s", list(df.columns))
        return {
            "value_today": None,
            "value_avg_5d": None,
            "ratio": None,
            "date": date,
            "market": market,
            "available": False,
            "reason": "column_missing",
        }

    values = df[value_col].astype(float)
    if values.empty:
        return {
            "value_today": None,
            "value_avg_5d": None,
            "ratio": None,
            "date": date,
            "market": market,
            "available": False,
            "reason": "empty_values",
        }

    value_today = float(values.iloc[-1])
    window = min(_ROLLING_WINDOW, len(values))
    value_avg = float(values.iloc[-window:].mean())
    ratio: float | None = None
    if value_avg > 0:
        ratio = round(value_today / value_avg, 4)

    result: dict[str, Any] = {
        "value_today": round(value_today, 2),
        "value_avg_5d": round(value_avg, 2),
        "ratio": ratio,
        "date": date,
        "market": market,
        "available": True,
        "data_points": window,
    }
    logger.info(
        "market_value 수집 완료: market=%s today=%.0f avg=%.0f ratio=%.3f",
        market,
        value_today,
        value_avg,
        ratio if ratio is not None else -1,
    )
    return result
