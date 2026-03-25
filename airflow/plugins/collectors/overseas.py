"""해외지수 수집기 (yfinance)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 장전 수집용 (premarket_data_collection)
TICKERS = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "NIKKEI": "^N225",
    "HSI": "^HSI",
    "VIX": "^VIX",
    "USDKRW": "USDKRW=X",
}

# 야간 수집용 (overnight_index_collection) — 선물·미국채 포함
OVERNIGHT_TICKERS = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "VIX": "^VIX",
    "SP500_FUT": "ES=F",
    "NASDAQ_FUT": "NQ=F",
    "USDKRW": "KRW=X",
    "US10Y": "^TNX",
    "EUROSTOXX50": "^STOXX50E",
    "NIKKEI": "^N225",
}


def _fetch_ticker(ticker: str) -> dict[str, Any]:
    """단일 티커의 최근 종가 + 등락률 조회."""
    import yfinance as yf

    data = yf.Ticker(ticker)
    hist = data.history(period="2d")
    if len(hist) >= 2:
        prev, last = hist.iloc[-2], hist.iloc[-1]
        change_pct = (last["Close"] - prev["Close"]) / prev["Close"] * 100
        return {
            "close": round(float(last["Close"]), 2),
            "change_pct": round(change_pct, 2),
            "date": str(last.name.date()),
        }
    if len(hist) == 1:
        return {
            "close": round(float(hist.iloc[-1]["Close"]), 2),
            "change_pct": 0.0,
            "date": str(hist.iloc[-1].name.date()),
        }
    return {"close": None, "change_pct": None, "error": True}


def _collect(tickers: dict[str, str]) -> dict[str, Any]:
    """티커 딕셔너리를 순회하며 데이터 수집."""
    result: dict[str, Any] = {}
    for name, ticker in tickers.items():
        try:
            result[name] = _fetch_ticker(ticker)
        except Exception:
            logger.warning("해외지수 %s 수집 실패", name, exc_info=True)
            result[name] = {"close": None, "change_pct": None, "error": True}
    return result


def collect_indices() -> dict[str, Any]:
    """전일 해외지수 종가 + 등락률 수집 (장전용).

    Returns:
        지수별 종가·등락률 딕셔너리.
        예: {"SP500": {"close": 5000.0, "change_pct": 1.2, "date": "2025-01-01"}}
        수집 실패 시 해당 지수의 close/change_pct는 None, error=True.
    """
    return _collect(TICKERS)


def collect_overnight_indices() -> dict[str, Any]:
    """야간 해외지수 + 선물 수집 (overnight DAG용).

    미국장 시간대(KST 22:30~06:00)에 3회 수집.
    S&P/NASDAQ 선물(ES=F, NQ=F)은 거의 24시간 거래되어
    익일 KOSPI 갭 예측에 활용.

    Returns:
        지수별 종가·등락률 딕셔너리 (OVERNIGHT_TICKERS 기반).
    """
    return _collect(OVERNIGHT_TICKERS)
