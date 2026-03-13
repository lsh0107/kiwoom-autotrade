"""장후 리뷰 단위 테스트.

리뷰 생성, 제안 파싱, confidence 필터링, edge case 검증.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

SAMPLE_TRADES = [
    {"ticker": "005930", "side": "BUY", "quantity": 10, "price": 70000, "pnl": 50000},
    {"ticker": "000660", "side": "SELL", "quantity": 5, "price": 130000, "pnl": -20000},
]

SAMPLE_MARKET = {
    "ohlcv": [{"티커": "005930", "종가": 70500}],
    "investor": [{"투자자": "외국인", "순매수": 1000000000}],
}

SAMPLE_NEWS = [
    {"title": "반도체 수출 급증", "sentiment": "positive"},
    {"title": "금리 인상 우려", "sentiment": "negative"},
    {"title": "코스피 강보합 마감", "sentiment": "neutral"},
]

VALID_REVIEW_JSON = """{
  "summary": "당일 반도체 섹터 중심 상승, 매수 포지션 소폭 수익.",
  "performance_analysis": "외국인 순매수 1조 원 유입으로 반도체 섹터 강세. 삼성전자 BUY 수익.",
  "risk_assessment": "금리 불확실성으로 성장주 변동성 주의.",
  "suggestions": [
    {
      "key": "stop_loss_pct",
      "current_value": 0.03,
      "suggested_value": 0.025,
      "reason": "최근 변동성 감소로 손절 기준 강화",
      "confidence": 0.75
    },
    {
      "key": "position_size_pct",
      "current_value": 0.1,
      "suggested_value": 0.12,
      "reason": "외국인 유입 긍정적 신호",
      "confidence": 0.6
    }
  ]
}"""


def _make_llm_response(content: str) -> MagicMock:
    """LLMResponse mock 생성."""
    resp = MagicMock()
    resp.content = content
    resp.provider = "claude"
    resp.model = "claude-sonnet-4-20250514"
    return resp


# ── 프롬프트 포맷 ─────────────────────────────────────────────────────────────


class TestPromptFormatting:
    """프롬프트 포맷 함수 테스트."""

    def test_format_trades_includes_ticker(self) -> None:
        """매매 기록 포맷에 티커가 포함되어야 한다."""
        from llm.review import _format_trades

        result = _format_trades(SAMPLE_TRADES)

        assert "005930" in result
        assert "000660" in result

    def test_format_trades_empty_returns_placeholder(self) -> None:
        """빈 매매 기록이면 안내 문자열을 반환해야 한다."""
        from llm.review import _format_trades

        result = _format_trades([])
        assert "당일 매매 기록 없음" in result

    def test_format_market_includes_investor(self) -> None:
        """시장 데이터 포맷에 투자자 정보가 포함되어야 한다."""
        from llm.review import _format_market

        result = _format_market(SAMPLE_MARKET)
        assert "외국인" in result

    def test_format_market_empty_returns_placeholder(self) -> None:
        """빈 시장 데이터이면 '데이터 없음'을 반환해야 한다."""
        from llm.review import _format_market

        result = _format_market({})
        assert result == "데이터 없음"

    def test_format_news_shows_sentiment_counts(self) -> None:
        """뉴스 포맷에 긍/부정 건수가 포함되어야 한다."""
        from llm.review import _format_news

        result = _format_news(SAMPLE_NEWS)

        assert "긍정=1" in result
        assert "부정=1" in result

    def test_format_news_empty_returns_placeholder(self) -> None:
        """빈 뉴스 목록이면 '뉴스 데이터 없음'을 반환해야 한다."""
        from llm.review import _format_news

        result = _format_news([])
        assert result == "뉴스 데이터 없음"

    def test_format_trades_limits_to_30_items(self) -> None:
        """매매 기록이 30건을 초과하면 30건만 포함해야 한다."""
        from llm.review import _format_trades

        trades = [
            {"ticker": f"TICK{i:03d}", "side": "BUY", "quantity": 1, "price": 1000}
            for i in range(50)
        ]
        result = _format_trades(trades)

        assert "TICK030" not in result
        assert "TICK000" in result


# ── JSON 파싱 ─────────────────────────────────────────────────────────────────


class TestParseReviewResponse:
    """리뷰 JSON 파싱 테스트."""

    def test_valid_json_parses_correctly(self) -> None:
        """유효한 JSON이 올바르게 파싱되어야 한다."""
        from llm.review import _parse_review_response

        result = _parse_review_response(VALID_REVIEW_JSON)

        assert result is not None
        assert "반도체" in result.summary
        assert "외국인" in result.performance_analysis
        assert "금리" in result.risk_assessment
        assert len(result.suggestions) == 2

    def test_json_in_markdown_block_parses(self) -> None:
        """마크다운 코드블록 안의 JSON도 파싱되어야 한다."""
        from llm.review import _parse_review_response

        markdown_response = f"```json\n{VALID_REVIEW_JSON}\n```"
        result = _parse_review_response(markdown_response)

        assert result is not None
        assert len(result.suggestions) == 2

    def test_invalid_json_returns_none(self) -> None:
        """유효하지 않은 JSON이면 None을 반환해야 한다."""
        from llm.review import _parse_review_response

        result = _parse_review_response("이건 JSON이 아닙니다")
        assert result is None

    def test_suggestion_fields_parsed(self) -> None:
        """ParamSuggestion 필드가 올바르게 파싱되어야 한다."""
        from llm.review import _parse_review_response

        result = _parse_review_response(VALID_REVIEW_JSON)

        assert result is not None
        sug = result.suggestions[0]
        assert sug.key == "stop_loss_pct"
        assert sug.current_value == pytest.approx(0.03)
        assert sug.suggested_value == pytest.approx(0.025)
        assert "손절" in sug.reason
        assert sug.confidence == pytest.approx(0.75)

    def test_empty_suggestions_list_ok(self) -> None:
        """제안 목록이 비어있어도 파싱 성공해야 한다."""
        from llm.review import _parse_review_response

        json_str = (
            '{"summary": "요약", "performance_analysis": "분석", '
            '"risk_assessment": "평가", "suggestions": []}'
        )
        result = _parse_review_response(json_str)

        assert result is not None
        assert result.suggestions == []


# ── confidence 필터링 ─────────────────────────────────────────────────────────


class TestConfidenceFilter:
    """낮은 confidence 제안 필터 테스트."""

    def test_low_confidence_suggestion_excluded(self) -> None:
        """confidence 0.5 미만인 제안은 제외되어야 한다."""
        from llm.review import _parse_review_response

        json_str = """{
          "summary": "요약",
          "performance_analysis": "분석",
          "risk_assessment": "평가",
          "suggestions": [
            {"key": "high_conf", "current_value": 0.1,
             "suggested_value": 0.2, "reason": "근거", "confidence": 0.8},
            {"key": "low_conf", "current_value": 0.1,
             "suggested_value": 0.2, "reason": "근거", "confidence": 0.3}
          ]
        }"""
        result = _parse_review_response(json_str)

        assert result is not None
        assert len(result.suggestions) == 1
        assert result.suggestions[0].key == "high_conf"

    def test_exactly_0_5_confidence_included(self) -> None:
        """confidence가 정확히 0.5이면 포함되어야 한다."""
        from llm.review import _parse_review_response

        json_str = """{
          "summary": "요약",
          "performance_analysis": "분석",
          "risk_assessment": "평가",
          "suggestions": [
            {"key": "boundary", "current_value": 0.1,
             "suggested_value": 0.2, "reason": "근거", "confidence": 0.5}
          ]
        }"""
        result = _parse_review_response(json_str)

        assert result is not None
        assert len(result.suggestions) == 1

    def test_all_low_confidence_returns_empty_list(self) -> None:
        """모든 제안이 낮은 confidence면 빈 리스트를 반환해야 한다."""
        from llm.review import _parse_review_response

        json_str = """{
          "summary": "요약",
          "performance_analysis": "분석",
          "risk_assessment": "평가",
          "suggestions": [
            {"key": "low1", "current_value": 0.1,
             "suggested_value": 0.2, "reason": "근거", "confidence": 0.1},
            {"key": "low2", "current_value": 0.1,
             "suggested_value": 0.2, "reason": "근거", "confidence": 0.4}
          ]
        }"""
        result = _parse_review_response(json_str)

        assert result is not None
        assert result.suggestions == []


# ── generate_review 통합 ─────────────────────────────────────────────────────


class TestGenerateReview:
    """generate_review 함수 통합 테스트."""

    def test_success_returns_review_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 응답 시 ReviewResult를 반환해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_REVIEW_JSON)

            from llm.review import ReviewResult, generate_review

            result = generate_review(SAMPLE_TRADES, SAMPLE_MARKET, SAMPLE_NEWS)

        assert isinstance(result, ReviewResult)
        assert result.provider == "claude"
        assert len(result.suggestions) > 0

    def test_llm_error_returns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 에러 시 기본값 ReviewResult를 반환해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            from llm.client import LLMError

            mock_generate.side_effect = LLMError("모든 provider 실패")

            from llm.review import generate_review

            result = generate_review(SAMPLE_TRADES, SAMPLE_MARKET, SAMPLE_NEWS)

        assert result.suggestions == []
        assert result.performance_analysis == ""

    def test_invalid_json_returns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """유효하지 않은 JSON 응답 시 기본값을 반환해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response("이건 JSON이 아닙니다")

            from llm.review import generate_review

            result = generate_review(SAMPLE_TRADES, SAMPLE_MARKET, SAMPLE_NEWS)

        assert result.suggestions == []

    def test_list_trade_data_normalized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """trade_data가 list 형식이어도 올바르게 처리해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_REVIEW_JSON)

            from llm.review import generate_review

            # list를 직접 넘겨도 동작해야 한다
            result = generate_review(SAMPLE_TRADES, SAMPLE_MARKET, SAMPLE_NEWS)

        assert result is not None

    def test_empty_trade_data_calls_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """매매 기록이 없어도 LLM을 호출해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_REVIEW_JSON)

            from llm.review import generate_review

            generate_review([], {}, [])

        mock_generate.assert_called_once()

    def test_prompt_contains_trade_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """프롬프트에 매매 정보가 포함되어야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_REVIEW_JSON)

            from llm.review import generate_review

            generate_review(SAMPLE_TRADES, SAMPLE_MARKET, SAMPLE_NEWS)

        call_kwargs = mock_generate.call_args.kwargs
        prompt = call_kwargs.get("prompt", "")
        assert "005930" in prompt

    def test_dict_news_data_normalized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """news_data가 dict 형식 {"articles": [...]} 이어도 처리해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_REVIEW_JSON)

            from llm.review import generate_review

            result = generate_review(
                SAMPLE_TRADES,
                SAMPLE_MARKET,
                {"articles": SAMPLE_NEWS},
            )

        assert result is not None
