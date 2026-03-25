"""LLM DB 컨텍스트 빌더 — 오케스트레이션."""

from __future__ import annotations

import logging
from typing import Any

from context.formatter import (
    format_briefing_history,
    format_market_summary,
    format_overnight_indices,
    format_review_history,
    format_sentiment_trend,
)
from context.history import get_latest_review, get_recent_briefings, get_recent_reviews
from context.market import get_market_summary, get_news_sentiment_trend, get_overnight_indices

logger = logging.getLogger(__name__)


def build_premarket_context(days: int = 7) -> dict[str, Any]:
    """장전 브리핑용 통합 DB 컨텍스트.

    llm_briefing DAG의 prepare_data 태스크에서 호출.
    과거 7일 시장 데이터, 뉴스 감성, 이전 브리핑/리뷰를 조합.

    Args:
        days: 조회 일수 (기본 7일).

    Returns:
        raw + formatted 딕셔너리.
    """
    market = get_market_summary(days)
    sentiment = get_news_sentiment_trend(days)
    briefings = get_recent_briefings(5)
    reviews = get_recent_reviews(3)
    overnight = get_overnight_indices()

    return {
        "raw": {
            "market_summary": market,
            "sentiment_trend": sentiment,
            "recent_briefings": briefings,
            "recent_reviews": reviews,
            "overnight_indices": overnight,
        },
        "formatted": "\n\n".join(
            [
                format_market_summary(market),
                format_overnight_indices(overnight),
                format_sentiment_trend(sentiment),
                format_briefing_history(briefings),
                format_review_history(reviews),
            ]
        ),
    }


def build_overnight_context() -> dict[str, Any]:
    """야간 분석용 통합 DB 컨텍스트.

    overnight_analysis DAG에서 호출.
    야간 해외지수 + 당일 장후 리뷰 + 최근 시장 요약 조합.

    Returns:
        raw + formatted 딕셔너리.
    """
    overnight = get_overnight_indices()
    review = get_latest_review()
    market = get_market_summary(5)

    return {
        "raw": {
            "overnight_indices": overnight,
            "today_review": review,
            "market_summary": market,
        },
        "formatted": "\n\n".join(
            [
                format_overnight_indices(overnight),
                format_market_summary(market),
                format_review_history([review] if review else []),
            ]
        ),
    }
