"""한국은행 ECOS (Economic Statistics System) 거시경제 수집기.

ECOS Open API를 requests로 직접 호출한다.
API 문서: https://ecos.bok.or.kr/api/#/DevGuide/StatisticsTermService
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://ecos.bok.or.kr/api"
_TIMEOUT = 30  # 초

# 기준금리 통계 코드: 기준금리 (월별)
_BASE_RATE_STAT_CODE = "722Y001"
_BASE_RATE_ITEM_CODE = "0101000"


def _get_api_key() -> str:
    """ECOS API 키 조회. Airflow Variable 우선, 없으면 환경변수."""
    try:
        from airflow.models import Variable

        return Variable.get("ECOS_API_KEY")
    except (ImportError, Exception):
        key = os.environ.get("ECOS_API_KEY", "")
        if not key:
            raise ValueError("ECOS_API_KEY 미설정") from None
        return key


def collect_base_rate(months: int = 3) -> dict:
    """한국은행 기준금리 수집.

    Args:
        months: 조회 기간 (개월). 기본값 3.

    Returns:
        최신 기준금리 딕셔너리.
        예: {"base_rate": 3.5, "period": "202501", "collected_at": "2025-01-15T08:00:00"}

    Raises:
        ValueError: ECOS_API_KEY 미설정 시.
        requests.HTTPError: API 호출 실패 시.
    """
    api_key = _get_api_key()

    now = datetime.now(tz=UTC)
    # 월 단위 조회 (YYYYMM)
    end_period = now.strftime("%Y%m")

    # months개월 전 계산 (단순 연산, 월 경계 처리)
    start_year = now.year
    start_month = now.month - months
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start_period = f"{start_year}{start_month:02d}"

    url = (
        f"{_BASE_URL}/StatisticSearch"
        f"/{api_key}/json/kr/1/10"
        f"/{_BASE_RATE_STAT_CODE}/MM"
        f"/{start_period}/{end_period}"
        f"/{_BASE_RATE_ITEM_CODE}"
    )

    response = requests.get(url, timeout=_TIMEOUT)
    response.raise_for_status()

    data = response.json()

    # ECOS API 응답 구조: {"StatisticSearch": {"row": [...]}}
    rows = data.get("StatisticSearch", {}).get("row", [])

    if not rows:
        logger.warning("ECOS 기준금리 데이터 없음: %s ~ %s", start_period, end_period)
        return {"base_rate": None, "period": None, "collected_at": now.isoformat()}

    # 가장 최근 행
    latest = rows[-1]
    base_rate_str = latest.get("DATA_VALUE", "")

    try:
        base_rate = float(base_rate_str) if base_rate_str else None
    except ValueError:
        logger.warning("기준금리 파싱 실패: %s", base_rate_str)
        base_rate = None

    result = {
        "base_rate": base_rate,
        "period": latest.get("TIME", ""),
        "collected_at": now.isoformat(),
    }

    logger.info("ECOS 기준금리 수집 완료: %s%% (%s)", base_rate, result["period"])
    return result


def collect_macro_indicators() -> dict:
    """주요 거시경제 지표 수집 (기준금리 포함).

    Returns:
        거시경제 지표 딕셔너리.
    """
    return {
        "base_rate": collect_base_rate(),
    }
