"""장전 브리핑 단위 테스트.

프롬프트 구성, JSON 파싱, 기본값 fallback, 가중치 범위 검증.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

SAMPLE_PREMARKET_DATA = {
    "dart": [
        {"corp_name": "삼성전자", "report_nm": "주요사항보고서"},
        {"corp_name": "SK하이닉스", "report_nm": "단일판매공급계약"},
    ],
    "fred": {
        "vix": 18.5,
        "us_rate_10y": 4.2,
        "usd_krw": 1350.0,
        "wti": 78.5,
    },
    "overseas": {
        "SP500": {"close": 5000.0, "change_pct": 1.2, "date": "2026-03-14"},
        "NASDAQ": {"close": 17000.0, "change_pct": 0.8, "date": "2026-03-14"},
        "VIX": {"close": 18.5, "change_pct": -0.5, "date": "2026-03-14"},
    },
}

VALID_BRIEFING_JSON = """{
  "summary": "미국 증시 상승세로 국내 증시 긍정적 출발 예상. 반도체 섹터 강세.",
  "theme_scores": {"반도체": 0.85, "2차전지": 0.5, "바이오": 0.3},
  "risk_flags": ["삼성전자 주요사항보고서 공시", "VIX 18 수준"],
  "weight_adjustments": {"반도체": 0.15, "2차전지": -0.05}
}"""


def _make_llm_response(content: str) -> MagicMock:
    """LLMResponse mock 생성."""
    resp = MagicMock()
    resp.content = content
    resp.provider = "claude"
    resp.model = "claude-sonnet-4-20250514"
    return resp


# ── BriefingResult 기본값 ─────────────────────────────────────────────────────


class TestDefaultBriefingResult:
    """기본값 반환 테스트."""

    def test_default_result_has_expected_structure(self) -> None:
        """기본값 BriefingResult가 올바른 구조를 가져야 한다."""
        from llm.briefing import _default_briefing_result

        result = _default_briefing_result("raw text")

        assert isinstance(result.summary, str)
        assert isinstance(result.theme_scores, dict)
        assert isinstance(result.risk_flags, list)
        assert isinstance(result.weight_adjustments, dict)
        assert result.raw_response == "raw text"


# ── 프롬프트 포맷 ─────────────────────────────────────────────────────────────


class TestPromptFormatting:
    """프롬프트 포맷 함수 테스트."""

    def test_format_dart_includes_corp_name(self) -> None:
        """DART 포맷에 기업명이 포함되어야 한다."""
        from llm.briefing import _format_dart

        dart = [
            {"corp_name": "삼성전자", "report_nm": "주요사항보고서"},
            {"corp_name": "SK하이닉스", "report_nm": "공급계약"},
        ]
        result = _format_dart(dart)

        assert "삼성전자" in result
        assert "SK하이닉스" in result

    def test_format_dart_empty_returns_placeholder(self) -> None:
        """빈 DART 목록이면 '공시 없음'을 반환해야 한다."""
        from llm.briefing import _format_dart

        result = _format_dart([])
        assert result == "공시 없음"

    def test_format_overseas_includes_index_names(self) -> None:
        """해외지수 포맷에 지수 이름이 포함되어야 한다."""
        from llm.briefing import _format_overseas

        overseas = {
            "SP500": {"close": 5000.0, "change_pct": 1.2},
            "NASDAQ": {"close": 17000.0, "change_pct": 0.8},
        }
        result = _format_overseas(overseas)

        assert "SP500" in result
        assert "NASDAQ" in result

    def test_format_overseas_empty_returns_placeholder(self) -> None:
        """빈 해외지수이면 '데이터 없음'을 반환해야 한다."""
        from llm.briefing import _format_overseas

        result = _format_overseas({})
        assert result == "데이터 없음"

    def test_format_macro_includes_vix(self) -> None:
        """거시경제 포맷에 VIX가 포함되어야 한다."""
        from llm.briefing import _format_macro

        fred = {"vix": 18.5, "us_rate_10y": 4.2, "usd_krw": 1350.0, "wti": 78.5}
        result = _format_macro(fred)

        assert "VIX" in result
        assert "18.5" in result

    def test_format_dart_limits_to_20_items(self) -> None:
        """DART 목록이 20건을 초과하면 20건만 포함해야 한다."""
        from llm.briefing import _format_dart

        dart = [{"corp_name": f"기업{i}", "report_nm": "보고서"} for i in range(30)]
        result = _format_dart(dart)

        # 21번째 이후 기업은 포함되지 않아야 한다
        assert "기업20" not in result
        assert "기업0" in result


# ── JSON 파싱 ─────────────────────────────────────────────────────────────────


class TestParseBriefingResponse:
    """JSON 파싱 테스트."""

    def test_valid_json_parses_correctly(self) -> None:
        """유효한 JSON이 올바르게 파싱되어야 한다."""
        from llm.briefing import _parse_briefing_response

        result = _parse_briefing_response(VALID_BRIEFING_JSON)

        assert result is not None
        assert result.summary == "미국 증시 상승세로 국내 증시 긍정적 출발 예상. 반도체 섹터 강세."
        assert result.theme_scores["반도체"] == pytest.approx(0.85)
        assert "삼성전자 주요사항보고서 공시" in result.risk_flags
        assert result.weight_adjustments["반도체"] == pytest.approx(0.15)

    def test_json_in_markdown_block_parses(self) -> None:
        """마크다운 코드블록 안의 JSON도 파싱되어야 한다."""
        from llm.briefing import _parse_briefing_response

        markdown_response = f"```json\n{VALID_BRIEFING_JSON}\n```"
        result = _parse_briefing_response(markdown_response)

        assert result is not None
        assert result.theme_scores["반도체"] == pytest.approx(0.85)

    def test_invalid_json_returns_none(self) -> None:
        """유효하지 않은 JSON이면 None을 반환해야 한다."""
        from llm.briefing import _parse_briefing_response

        result = _parse_briefing_response("이건 JSON이 아닙니다")
        assert result is None

    def test_summary_truncated_to_300_chars(self) -> None:
        """summary가 300자를 초과하면 잘라야 한다."""
        from llm.briefing import _parse_briefing_response

        long_summary = "A" * 400
        json_str = (
            f'{{"summary": "{long_summary}", '
            '"theme_scores": {}, "risk_flags": [], "weight_adjustments": {}}'
        )
        result = _parse_briefing_response(json_str)

        assert result is not None
        assert len(result.summary) <= 300

    def test_theme_scores_clamped_to_0_1(self) -> None:
        """테마 스코어가 0~1 범위로 제한되어야 한다."""
        from llm.briefing import _parse_briefing_response

        json_str = (
            '{"summary": "요약", '
            '"theme_scores": {"반도체": 1.5, "바이오": -0.3}, '
            '"risk_flags": [], "weight_adjustments": {}}'
        )
        result = _parse_briefing_response(json_str)

        assert result is not None
        assert result.theme_scores["반도체"] == pytest.approx(1.0)
        assert result.theme_scores["바이오"] == pytest.approx(0.0)

    def test_empty_fields_use_defaults(self) -> None:
        """누락된 필드는 기본값을 사용해야 한다."""
        from llm.briefing import _parse_briefing_response

        result = _parse_briefing_response('{"summary": "요약"}')

        assert result is not None
        assert result.theme_scores == {}
        assert result.risk_flags == []
        assert result.weight_adjustments == {}


# ── 가중치 범위 제한 ──────────────────────────────────────────────────────────


class TestClampWeights:
    """가중치 ±20% 제한 테스트."""

    def test_weight_over_20_clamped_to_20(self) -> None:
        """20%를 초과하는 가중치는 20%로 제한되어야 한다."""
        from llm.briefing import _clamp_weights

        result = _clamp_weights({"반도체": 0.5, "바이오": -0.4})

        assert result["반도체"] == pytest.approx(0.20)
        assert result["바이오"] == pytest.approx(-0.20)

    def test_weight_within_range_unchanged(self) -> None:
        """±20% 이내의 가중치는 변경되지 않아야 한다."""
        from llm.briefing import _clamp_weights

        result = _clamp_weights({"반도체": 0.10, "바이오": -0.15})

        assert result["반도체"] == pytest.approx(0.10)
        assert result["바이오"] == pytest.approx(-0.15)

    def test_weight_adjustment_in_briefing_clamped(self) -> None:
        """generate_briefing 파이프라인에서도 가중치가 제한되어야 한다."""
        from llm.briefing import _parse_briefing_response

        json_str = (
            '{"summary": "요약", "theme_scores": {}, "risk_flags": [], '
            '"weight_adjustments": {"반도체": 0.99}}'
        )
        result = _parse_briefing_response(json_str)

        assert result is not None
        assert result.weight_adjustments["반도체"] == pytest.approx(0.20)


# ── generate_briefing 통합 ───────────────────────────────────────────────────


class TestGenerateBriefing:
    """generate_briefing 함수 통합 테스트."""

    def test_success_returns_briefing_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 응답 시 BriefingResult를 반환해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_BRIEFING_JSON)

            from llm.briefing import BriefingResult, generate_briefing

            result = generate_briefing(SAMPLE_PREMARKET_DATA)

        assert isinstance(result, BriefingResult)
        assert result.provider == "claude"
        assert result.theme_scores["반도체"] == pytest.approx(0.85)

    def test_llm_error_returns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 에러 시 기본값 BriefingResult를 반환해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            from llm.client import LLMError

            mock_generate.side_effect = LLMError("모든 provider 실패")

            from llm.briefing import generate_briefing

            result = generate_briefing(SAMPLE_PREMARKET_DATA)

        assert result.theme_scores == {}
        assert result.risk_flags == []

    def test_invalid_json_returns_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM이 유효하지 않은 JSON 반환 시 기본값을 반환해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response("이건 JSON이 아닙니다")

            from llm.briefing import generate_briefing

            result = generate_briefing(SAMPLE_PREMARKET_DATA)

        assert result.theme_scores == {}

    def test_empty_data_still_calls_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """빈 데이터도 LLM을 호출해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_BRIEFING_JSON)

            from llm.briefing import generate_briefing

            generate_briefing({})

        mock_generate.assert_called_once()

    def test_prompt_contains_dart_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """프롬프트에 DART 데이터가 포함되어야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_BRIEFING_JSON)

            from llm.briefing import generate_briefing

            generate_briefing(SAMPLE_PREMARKET_DATA)

        call_kwargs = mock_generate.call_args.kwargs
        prompt = call_kwargs.get("prompt", "")
        assert "삼성전자" in prompt

    def test_prompt_contains_vix_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """프롬프트에 VIX 데이터가 포함되어야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("llm.client.generate") as mock_generate:
            mock_generate.return_value = _make_llm_response(VALID_BRIEFING_JSON)

            from llm.briefing import generate_briefing

            generate_briefing(SAMPLE_PREMARKET_DATA)

        call_kwargs = mock_generate.call_args.kwargs
        prompt = call_kwargs.get("prompt", "")
        assert "VIX" in prompt or "18.5" in prompt
