"""시장 데이터 DB 쿼리 — LLM 컨텍스트용."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_db_conn() -> Any:
    """DB 연결 (collectors.storage와 동일 로직)."""
    from collectors.storage import _get_db_conn as get_conn

    return get_conn()


def get_market_summary(days: int = 7) -> dict[str, Any]:
    """최근 N일 시장 데이터 요약.

    market_data 테이블에서 카테고리별 최근 데이터를 집계.
    VIX 추세, 해외지수 변동률, 금리 변동 등을 계산.

    Args:
        days: 조회 일수 (기본 7일).

    Returns:
        카테고리별 요약 딕셔너리.
    """
    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT category, date::text, data
                    FROM market_data
                    WHERE date >= CURRENT_DATE - %s
                    ORDER BY category, date DESC
                    """,
                    (days,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        logger.warning("시장 데이터 조회 실패", exc_info=True)
        return {}

    # 카테고리별 그룹핑
    by_category: dict[str, list[dict]] = {}
    for category, date_str, data_raw in rows:
        data = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
        by_category.setdefault(category, []).append({"date": date_str, "data": data})

    result: dict[str, Any] = {}

    # 해외지수 요약
    if "overnight_index" in by_category or "overseas_index" in by_category:
        indices = by_category.get("overnight_index", by_category.get("overseas_index", []))
        if indices:
            latest = indices[0]["data"]
            result["overseas"] = {}
            for name, info in latest.items():
                if isinstance(info, dict) and info.get("close") is not None:
                    result["overseas"][name] = {
                        "close": info["close"],
                        "change_pct": info.get("change_pct", 0),
                    }

    # VIX 추출 (overseas에서)
    if "overseas" in result and "VIX" in result["overseas"]:
        vix = result["overseas"]["VIX"]
        result["vix"] = {
            "current": vix["close"],
            "change_pct": vix["change_pct"],
        }

    # FRED 거시경제 요약
    if "fred_macro" in by_category:
        fred_data = by_category["fred_macro"]
        if fred_data:
            result["macro"] = fred_data[0]["data"]

    # 데이터 건수 메타
    result["_meta"] = {
        "days": days,
        "categories": list(by_category.keys()),
        "total_records": len(rows),
    }

    return result


def get_news_sentiment_trend(days: int = 7) -> dict[str, Any]:
    """최근 N일 뉴스 감성 추세 (키워드별).

    news_articles 테이블에서 keyword별 sentiment를 집계.

    Args:
        days: 조회 일수.

    Returns:
        키워드별 감성 집계 딕셔너리.
    """
    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT keyword, sentiment, count(*)
                    FROM news_articles
                    WHERE collected_at >= NOW() - INTERVAL '%s days'
                      AND keyword IS NOT NULL AND keyword != ''
                    GROUP BY keyword, sentiment
                    ORDER BY keyword, count DESC
                    """,
                    (days,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        logger.warning("뉴스 감성 조회 실패", exc_info=True)
        return {}

    result: dict[str, dict[str, int]] = {}
    for keyword, sentiment, count in rows:
        result.setdefault(keyword, {"positive": 0, "neutral": 0, "negative": 0})
        if sentiment in ("positive", "neutral", "negative"):
            result[keyword][sentiment] = count

    return result


def get_overnight_indices() -> dict[str, Any]:
    """당일 야간 해외지수 데이터 (가장 최근 overnight_index).

    Returns:
        야간 수집 데이터 딕셔너리.
    """
    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT data FROM market_data
                    WHERE category = 'overnight_index'
                    ORDER BY date DESC LIMIT 1
                    """
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception:
        logger.warning("야간 지수 조회 실패", exc_info=True)
        return {}

    if not row:
        return {}
    return json.loads(row[0]) if isinstance(row[0], str) else row[0]
