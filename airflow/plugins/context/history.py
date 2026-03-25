"""과거 LLM 결정 + 결과 DB 쿼리."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_db_conn() -> Any:
    """DB 연결."""
    from collectors.storage import _get_db_conn as get_conn

    return get_conn()


def get_recent_briefings(n: int = 5) -> list[dict[str, Any]]:
    """최근 N건 LLM 브리핑 요약.

    llm_briefings 테이블에서 date 역순 N건 조회.

    Args:
        n: 조회 건수 (기본 5건).

    Returns:
        브리핑 요약 리스트.
    """
    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT date, summary, theme_scores, risk_flags, weight_adjustments
                    FROM llm_briefings
                    ORDER BY date DESC
                    LIMIT %s
                    """,
                    (n,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        logger.warning("브리핑 이력 조회 실패", exc_info=True)
        return []

    return [
        {
            "date": str(row[0]),
            "summary": row[1][:200],  # 토큰 절약: 요약 200자 제한
            "theme_scores": json.loads(row[2]) if isinstance(row[2], str) else row[2],
            "risk_flags": json.loads(row[3]) if isinstance(row[3], str) else row[3],
            "weight_adjustments": json.loads(row[4]) if isinstance(row[4], str) else row[4],
        }
        for row in rows
    ]


def get_recent_reviews(n: int = 5) -> list[dict[str, Any]]:
    """최근 N건 매매 리뷰 요약.

    trade_reviews 테이블에서 date 역순 N건 조회.

    Args:
        n: 조회 건수.

    Returns:
        리뷰 요약 리스트.
    """
    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT date, summary, suggestions
                    FROM trade_reviews
                    ORDER BY date DESC
                    LIMIT %s
                    """,
                    (n,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        logger.warning("리뷰 이력 조회 실패", exc_info=True)
        return []

    return [
        {
            "date": str(row[0]),
            "summary": row[1][:200],
            "suggestions": json.loads(row[2]) if isinstance(row[2], str) else row[2],
        }
        for row in rows
    ]


def get_latest_review() -> dict[str, Any]:
    """가장 최근 매매 리뷰.

    Returns:
        리뷰 딕셔너리 또는 빈 딕셔너리.
    """
    reviews = get_recent_reviews(1)
    return reviews[0] if reviews else {}
