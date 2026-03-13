"""간단한 키워드 기반 감성 분류."""

from __future__ import annotations

POSITIVE_KEYWORDS = ["상승", "급등", "호재", "신고가", "돌파", "수주", "흑자", "증가", "강세"]
NEGATIVE_KEYWORDS = ["하락", "급락", "악재", "신저가", "적자", "감소", "약세", "하향", "손실"]


def classify_sentiment(text: str) -> str:
    """텍스트 감성 분류.

    Args:
        text: 분류할 텍스트.

    Returns:
        감성 라벨: "positive" | "negative" | "neutral".
    """
    pos = sum(1 for k in POSITIVE_KEYWORDS if k in text)
    neg = sum(1 for k in NEGATIVE_KEYWORDS if k in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def analyze_news_sentiment(articles: list[dict]) -> list[dict]:
    """뉴스 기사 목록에 감성 라벨 추가.

    Args:
        articles: 뉴스 기사 목록. 각 항목은 title, description 필드를 포함해야 함.

    Returns:
        sentiment 필드가 추가된 기사 목록 (원본 수정).
    """
    for article in articles:
        text = f"{article.get('title', '')} {article.get('description', '')}"
        article["sentiment"] = classify_sentiment(text)
    return articles
