"""감성 분류 단위 테스트."""

from __future__ import annotations


class TestClassifySentiment:
    """classify_sentiment 테스트."""

    def test_positive_text_returns_positive(self) -> None:
        """긍정 키워드 포함 텍스트는 positive를 반환해야 한다."""
        from analysis.sentiment import classify_sentiment

        assert classify_sentiment("삼성전자 주가 급등") == "positive"
        assert classify_sentiment("신고가 돌파 호재") == "positive"

    def test_negative_text_returns_negative(self) -> None:
        """부정 키워드 포함 텍스트는 negative를 반환해야 한다."""
        from analysis.sentiment import classify_sentiment

        assert classify_sentiment("주가 급락 악재") == "negative"
        assert classify_sentiment("적자 전환 약세") == "negative"

    def test_neutral_text_returns_neutral(self) -> None:
        """키워드 없는 텍스트는 neutral을 반환해야 한다."""
        from analysis.sentiment import classify_sentiment

        assert classify_sentiment("오늘 날씨가 좋다") == "neutral"
        assert classify_sentiment("") == "neutral"

    def test_mixed_returns_dominant_sentiment(self) -> None:
        """긍정/부정 혼재 시 많은 쪽을 반환해야 한다."""
        from analysis.sentiment import classify_sentiment

        # 긍정 2개 vs 부정 1개
        assert classify_sentiment("상승 급등 하락") == "positive"
        # 부정 2개 vs 긍정 1개
        assert classify_sentiment("하락 급락 상승") == "negative"

    def test_equal_counts_returns_neutral(self) -> None:
        """긍정/부정 수가 같으면 neutral을 반환해야 한다."""
        from analysis.sentiment import classify_sentiment

        assert classify_sentiment("상승 하락") == "neutral"


class TestAnalyzeNewsSentiment:
    """analyze_news_sentiment 테스트."""

    def test_adds_sentiment_field(self) -> None:
        """각 기사에 sentiment 필드가 추가되어야 한다."""
        from analysis.sentiment import analyze_news_sentiment

        articles = [
            {"title": "삼성전자 급등", "description": "주가 상승"},
            {"title": "시장 조정", "description": "주가 하락 우려"},
        ]

        result = analyze_news_sentiment(articles)

        assert result[0]["sentiment"] == "positive"
        assert result[1]["sentiment"] == "negative"

    def test_returns_same_list(self) -> None:
        """원본 리스트를 수정하고 반환해야 한다."""
        from analysis.sentiment import analyze_news_sentiment

        articles = [{"title": "뉴스", "description": "내용"}]
        result = analyze_news_sentiment(articles)

        assert result is articles

    def test_empty_list_returns_empty(self) -> None:
        """빈 리스트 입력 시 빈 리스트를 반환해야 한다."""
        from analysis.sentiment import analyze_news_sentiment

        assert analyze_news_sentiment([]) == []

    def test_missing_fields_handled(self) -> None:
        """title/description 필드 없는 기사도 처리해야 한다."""
        from analysis.sentiment import analyze_news_sentiment

        articles = [{"link": "http://example.com"}]
        result = analyze_news_sentiment(articles)

        assert result[0]["sentiment"] == "neutral"
