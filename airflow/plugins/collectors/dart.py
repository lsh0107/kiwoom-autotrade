"""DART 전자공시 수집기."""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime, timedelta

try:
    import opendartreader as odr
except ImportError:
    odr = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _get_api_key() -> str:
    """DART API 키 조회. Airflow Variable 우선, 없으면 환경변수."""
    try:
        from airflow.models import Variable

        return Variable.get("DART_API_KEY")
    except (ImportError, Exception):
        key = os.environ.get("DART_API_KEY", "")
        if not key:
            raise ValueError("DART_API_KEY 미설정") from None
        return key


def collect_disclosures(days: int = 1) -> list[dict]:
    """최근 N일간 주요 공시 수집.

    Args:
        days: 수집 기간 (일). 기본값 1.

    Returns:
        공시 레코드 목록. 각 항목은 rcept_no, corp_name, report_nm 등을 포함.

    Raises:
        ValueError: DART_API_KEY 미설정 시.
    """
    api_key = _get_api_key()
    api = odr.OpenDartReader(api_key)

    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)

    result = api.list(
        start=start.strftime("%Y%m%d"),
        end=end.strftime("%Y%m%d"),
    )

    # rate limit 준수
    time.sleep(0.1)

    if result is None or result.empty:
        logger.info("DART 공시 없음: %s ~ %s", start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        return []

    records = result.to_dict("records")
    logger.info("DART 공시 수집 완료: %d건", len(records))
    return records


def collect_financial_statements(
    corp_code: str, year: int, report_code: str = "11011"
) -> list[dict]:
    """기업 재무제표 수집.

    Args:
        corp_code: DART 기업 고유번호 (8자리).
        year: 사업 연도.
        report_code: 보고서 코드. 11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기.

    Returns:
        재무제표 레코드 목록.

    Raises:
        ValueError: DART_API_KEY 미설정 시.
    """
    api_key = _get_api_key()
    api = odr.OpenDartReader(api_key)

    result = api.finstate(corp_code, year, report_code)
    time.sleep(0.1)

    if result is None or result.empty:
        logger.info("재무제표 없음: %s %d", corp_code, year)
        return []

    records = result.to_dict("records")
    logger.info("재무제표 수집 완료: %s %d — %d행", corp_code, year, len(records))
    return records
