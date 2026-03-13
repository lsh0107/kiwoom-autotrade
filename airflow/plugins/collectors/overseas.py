"""해외지수 수집기 (yfinance)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

TICKERS = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "NIKKEI": "^N225",
    "HSI": "^HSI",
    "VIX": "^VIX",
    "USDKRW": "USDKRW=X",
}


def collect_indices() -> dict[str, Any]:
    """전일 해외지수 종가 + 등락률 수집.

    Returns:
        지수별 종가·등락률 딕셔너리.
        예: {"SP500": {"close": 5000.0, "change_pct": 1.2, "date": "2025-01-01"}}
        수집 실패 시 해당 지수의 close/change_pct는 None, error=True.
    """
    import yfinance as yf

    result: dict[str, Any] = {}
    for name, ticker in TICKERS.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="2d")
            if len(hist) >= 2:
                prev, last = hist.iloc[-2], hist.iloc[-1]
                change_pct = (last["Close"] - prev["Close"]) / prev["Close"] * 100
                result[name] = {
                    "close": round(float(last["Close"]), 2),
                    "change_pct": round(change_pct, 2),
                    "date": str(last.name.date()),
                }
            elif len(hist) == 1:
                result[name] = {
                    "close": round(float(hist.iloc[-1]["Close"]), 2),
                    "change_pct": 0.0,
                    "date": str(hist.iloc[-1].name.date()),
                }
            else:
                logger.warning("해외지수 %s 데이터 없음", name)
                result[name] = {"close": None, "change_pct": None, "error": True}
        except Exception:
            logger.warning("해외지수 %s 수집 실패", name, exc_info=True)
            result[name] = {"close": None, "change_pct": None, "error": True}
    return result
