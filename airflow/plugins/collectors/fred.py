"""FRED (Federal Reserve Economic Data) 거시경제 지표 수집기."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

try:
    from fredapi import Fred
except ImportError:
    Fred = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# 수집 대상 시리즈 ID
_SERIES = {
    "vix": "VIXCLS",  # CBOE Volatility Index
    "us_rate_10y": "DGS10",  # 미국 10년 국채 수익률
    "us_rate_2y": "DGS2",  # 미국 2년 국채 수익률
    "usd_krw": "DEXKOUS",  # 원달러 환율
    "wti": "DCOILWTICO",  # WTI 원유 가격
    "fed_funds": "FEDFUNDS",  # 연방기금금리
}


def _get_api_key() -> str:
    """FRED API 키 조회. Airflow Variable 우선, 없으면 환경변수."""
    try:
        from airflow.models import Variable

        return Variable.get("FRED_API_KEY")
    except (ImportError, Exception):
        key = os.environ.get("FRED_API_KEY", "")
        if not key:
            raise ValueError("FRED_API_KEY 미설정") from None
        return key


def collect_macro(days: int = 5) -> dict:
    """최근 N일간 주요 거시경제 지표 수집.

    VIX, 미국 금리(10y/2y), 원달러 환율, WTI, 연방기금금리를 수집한다.
    주말/공휴일에는 FRED가 값을 제공하지 않으므로 최신 유효값을 반환한다.

    Args:
        days: 조회 기간 (일). 최근 유효값 확보를 위해 5 이상 권장.

    Returns:
        지표별 최신값 딕셔너리.
        예: {"vix": 18.5, "us_rate_10y": 4.2, "usd_krw": 1340.0, ...}

    Raises:
        ValueError: FRED_API_KEY 미설정 시.
    """
    api_key = _get_api_key()
    fred = Fred(api_key=api_key)

    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)

    result: dict[str, float | None] = {}

    for name, series_id in _SERIES.items():
        try:
            series = fred.get_series(
                series_id,
                observation_start=start.strftime("%Y-%m-%d"),
                observation_end=end.strftime("%Y-%m-%d"),
            )
            if series is not None and not series.empty:
                # 가장 최근 유효값 (NaN 제외)
                valid = series.dropna()
                result[name] = float(valid.iloc[-1]) if not valid.empty else None
            else:
                result[name] = None
            logger.debug("FRED %s (%s): %s", name, series_id, result[name])
        except Exception as exc:
            logger.warning("FRED 수집 실패: %s (%s) — %s", name, series_id, exc)
            result[name] = None

    logger.info("FRED 거시경제 수집 완료: %s", list(result.keys()))
    return result
