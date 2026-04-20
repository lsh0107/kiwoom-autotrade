"""VKOSPI(한국 변동성지수) 및 KOSPI 레짐 수집기.

pykrx를 사용하며 Airflow Docker 환경에서만 실행 가능하다.
로컬 .venv에는 pykrx 미설치이므로 ImportError를 처리한다.
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

# KOSPI 지수 티커 (pykrx 고정값)
_KOSPI_TICKER = "1001"

# 12개월 이동평균 기준 거래일 수 (약 252거래일 = 12개월)
_MA12_WINDOW = 252

# MA12 계산에 필요한 데이터 확보를 위한 조회 기간 버퍼 (달력일 기준)
_MA12_FETCH_DAYS = 420  # ≈ 14개월 (주말·공휴일 포함 여유)


def _find_vkospi_ticker() -> str | None:
    """pykrx 지수 목록에서 VKOSPI 티커를 동적으로 탐색한다.

    KRX가 변동성 지수 티커를 변경하는 경우를 대비해 하드코딩하지 않고
    '변동성' 키워드로 탐색한다.

    Returns:
        VKOSPI 티커 문자열. 탐색 실패 시 None.
    """
    if stock is None:
        return None
    try:
        tickers = stock.get_index_ticker_list(market="KOSPI")
        for ticker in tickers:
            name = stock.get_index_ticker_name(ticker)
            if "변동성" in name:
                logger.info("VKOSPI 티커 발견: %s (%s)", ticker, name)
                return ticker
        logger.warning("VKOSPI 티커 없음 — KOSPI 지수 목록: %s", tickers[:10])
    except Exception as exc:
        logger.warning("VKOSPI 티커 탐색 실패: %s", exc)
    return None


def collect_vkospi(date: str) -> dict[str, Any]:
    """VKOSPI(한국 변동성지수) 당일 값 수집.

    pykrx 지수 목록에서 '변동성' 키워드로 티커를 탐색한 후
    해당 티커의 OHLCV 데이터를 조회해 종가와 등락을 반환한다.

    Args:
        date: 조회 날짜 (YYYYMMDD 형식).

    Returns:
        VKOSPI 데이터 딕셔너리.
        예: {
            "value": 20.5,
            "change": -0.5,
            "change_pct": -2.38,
            "date": "20250101",
            "available": True,
        }
        수집 불가 시 value/change/change_pct=None, available=False, reason 포함.

    Raises:
        ImportError: pykrx 미설치 시.
    """
    if stock is None:
        raise ImportError("pykrx 패키지 미설치 — pip install pykrx")

    ticker = _find_vkospi_ticker()
    if not ticker:
        logger.warning("VKOSPI 티커를 찾을 수 없어 수집 불가")
        return {
            "value": None,
            "change": None,
            "change_pct": None,
            "date": date,
            "available": False,
            "reason": "ticker_not_found",
        }

    # 등락 계산을 위해 최대 7일 전부터 조회 (주말·공휴일 고려)
    end_dt = datetime.strptime(date, "%Y%m%d")  # noqa: DTZ007 — pykrx는 날짜 문자열만 사용
    start_dt = end_dt - timedelta(days=7)

    try:
        df = stock.get_index_ohlcv_by_date(
            fromdate=start_dt.strftime("%Y%m%d"),
            todate=date,
            ticker=ticker,
        )
    except Exception as exc:
        logger.warning("VKOSPI 조회 실패: date=%s — %s", date, exc)
        return {
            "value": None,
            "change": None,
            "change_pct": None,
            "date": date,
            "available": False,
            "reason": str(exc),
        }
    time.sleep(_SLEEP_INTERVAL)

    if df is None or df.empty:
        logger.warning("VKOSPI 데이터 없음: date=%s", date)
        return {
            "value": None,
            "change": None,
            "change_pct": None,
            "date": date,
            "available": False,
            "reason": "no_data",
        }

    # pykrx 컬럼명은 한글 또는 영어
    close_col = "종가" if "종가" in df.columns else "Close"
    last_close = float(df[close_col].iloc[-1])

    change: float | None = None
    change_pct: float | None = None
    if len(df) >= 2:
        prev_close = float(df[close_col].iloc[-2])
        if prev_close != 0:
            change = round(last_close - prev_close, 2)
            change_pct = round((last_close - prev_close) / prev_close * 100, 2)

    result: dict[str, Any] = {
        "value": round(last_close, 2),
        "change": change,
        "change_pct": change_pct,
        "date": date,
        "available": True,
    }
    logger.info("VKOSPI 수집 완료: %.2f (전일비 %s%%)", last_close, change_pct)
    return result


def collect_kospi_regime(date: str) -> dict[str, Any]:
    """KOSPI 레짐 판단 — 현재가 vs MA12(12개월 이동평균).

    최근 14개월(약 420 달력일) 분량의 KOSPI 일봉 데이터를 조회해
    252거래일 단순이동평균(MA12)을 계산하고, 현재 종가가
    MA12 위에 있으면 상승 레짐, 아래면 하락 레짐으로 판단한다.

    데이터가 252거래일 미만일 경우 있는 만큼 사용해 MA를 계산하며
    data_points 필드로 실제 사용 거래일 수를 반환한다.

    Args:
        date: 기준 날짜 (YYYYMMDD 형식).

    Returns:
        KOSPI 레짐 딕셔너리.
        예: {
            "kospi_close": 2700.0,
            "ma12": 2580.0,
            "above_ma12": True,
            "date": "20250101",
            "available": True,
            "data_points": 252,
        }
        수집 불가 시 available=False, reason 포함.

    Raises:
        ImportError: pykrx 미설치 시.
    """
    if stock is None:
        raise ImportError("pykrx 패키지 미설치 — pip install pykrx")

    end_dt = datetime.strptime(date, "%Y%m%d")  # noqa: DTZ007 — pykrx는 날짜 문자열만 사용
    start_dt = end_dt - timedelta(days=_MA12_FETCH_DAYS)

    try:
        df = stock.get_index_ohlcv_by_date(
            fromdate=start_dt.strftime("%Y%m%d"),
            todate=date,
            ticker=_KOSPI_TICKER,
        )
    except Exception as exc:
        logger.warning("KOSPI 레짐 조회 실패: date=%s — %s", date, exc)
        return {
            "kospi_close": None,
            "ma12": None,
            "above_ma12": None,
            "date": date,
            "available": False,
            "reason": str(exc),
        }
    time.sleep(_SLEEP_INTERVAL)

    if df is None or df.empty:
        logger.warning("KOSPI 데이터 없음: date=%s", date)
        return {
            "kospi_close": None,
            "ma12": None,
            "above_ma12": None,
            "date": date,
            "available": False,
            "reason": "no_data",
        }

    close_col = "종가" if "종가" in df.columns else "Close"
    closes = df[close_col].astype(float)

    current_close = round(float(closes.iloc[-1]), 2)

    # 252거래일 미만이면 있는 만큼 사용
    window = min(_MA12_WINDOW, len(closes))
    ma12 = round(float(closes.iloc[-window:].mean()), 2)
    above_ma12 = current_close > ma12

    result: dict[str, Any] = {
        "kospi_close": current_close,
        "ma12": ma12,
        "above_ma12": above_ma12,
        "date": date,
        "available": True,
        "data_points": window,
    }

    regime_label = "상승" if above_ma12 else "하락"
    logger.info(
        "KOSPI 레짐: %s장 (종가=%.1f, MA12=%.1f, %d거래일 기준)",
        regime_label,
        current_close,
        ma12,
        window,
    )
    return result
