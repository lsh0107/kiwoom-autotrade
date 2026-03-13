"""네이버 뉴스 검색 수집기."""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _get_naver_credentials() -> tuple[str, str]:
    """네이버 API 인증 정보 조회. Airflow Variable 우선, 없으면 환경변수."""
    try:
        from airflow.models import Variable

        return Variable.get("NAVER_CLIENT_ID"), Variable.get("NAVER_CLIENT_SECRET")
    except (ImportError, Exception):
        cid = os.environ.get("NAVER_CLIENT_ID", "")
        secret = os.environ.get("NAVER_CLIENT_SECRET", "")
        if not cid or not secret:
            raise ValueError("NAVER_CLIENT_ID/SECRET 미설정") from None
        return cid, secret


def collect_news(keywords: list[str], display: int = 10) -> list[dict[str, Any]]:
    """키워드별 네이버 뉴스 검색.

    Args:
        keywords: 검색 키워드 목록.
        display: 키워드당 최대 결과 수 (기본값 10, 최대 100).

    Returns:
        뉴스 기사 목록. 각 항목에 keyword 필드가 추가됨.

    Raises:
        ValueError: NAVER_CLIENT_ID/SECRET 미설정 시.
    """
    import requests

    cid, secret = _get_naver_credentials()
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    all_items: list[dict[str, Any]] = []

    for kw in keywords:
        url = (
            f"https://openapi.naver.com/v1/search/news.json"
            f"?query={quote(kw)}&display={display}&sort=date"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            for item in items:
                item["keyword"] = kw
            all_items.extend(items)
        except Exception:
            logger.warning("뉴스 검색 실패: %s", kw, exc_info=True)
        time.sleep(0.5)

    return all_items
