"""LLM 클라이언트 단위 테스트.

외부 API 전부 mock. fallback 동작, 에러 처리, 응답 파싱 검증.
lazy import 패턴이므로 patch는 실제 라이브러리 경로를 사용한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────


def _make_claude_response(text: str = "테스트 응답") -> MagicMock:
    """anthropic API 응답 mock 생성."""
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage.input_tokens = 100
    resp.usage.output_tokens = 50
    return resp


def _make_openai_response(text: str = "테스트 응답") -> MagicMock:
    """openai API 응답 mock 생성."""
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=text))]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    return resp


def _make_gemini_response(text: str = "테스트 응답") -> MagicMock:
    """google-generativeai API 응답 mock 생성."""
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata.prompt_token_count = 100
    resp.usage_metadata.candidates_token_count = 50
    return resp


# ── _get_api_key ─────────────────────────────────────────────────────────────


class TestGetApiKey:
    """API 키 조회 테스트."""

    def test_env_var_returns_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """환경변수에서 키를 조회해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-from-env")

        # Airflow Variable import를 실패시켜 env fallback 경로 진입
        with patch.dict("sys.modules", {"airflow.models": None}):
            from llm.client import _get_api_key

            result = _get_api_key("ANTHROPIC_API_KEY")

        assert result == "test-key-from-env"

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """키 미설정 시 ValueError를 발생시켜야 한다."""
        monkeypatch.delenv("MISSING_KEY_XYZ", raising=False)

        from llm.client import _get_api_key

        with pytest.raises(ValueError, match="MISSING_KEY_XYZ"):
            _get_api_key("MISSING_KEY_XYZ")

    def test_airflow_variable_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Airflow Variable이 설정되어 있으면 환경변수보다 우선해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        mock_variable = MagicMock()
        mock_variable.get.return_value = "airflow-var-key"
        mock_airflow_models = MagicMock()
        mock_airflow_models.Variable = mock_variable

        with patch.dict("sys.modules", {"airflow.models": mock_airflow_models}):
            from llm.client import _get_api_key

            result = _get_api_key("ANTHROPIC_API_KEY")

        assert result == "airflow-var-key"


# ── generate (fallback 동작) ──────────────────────────────────────────────────


class TestGenerate:
    """generate 함수 fallback 및 에러 처리 테스트."""

    def test_claude_success_returns_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claude 호출 성공 시 LLMResponse를 반환해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_resp = _make_claude_response("분석 결과입니다")

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic, "airflow.models": None}):
            from llm.client import generate

            result = generate("테스트 프롬프트")

        assert result.content == "분석 결과입니다"
        assert result.provider == "claude"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.latency_ms >= 0

    def test_claude_fails_falls_back_to_gpt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claude 실패 시 GPT로 fallback해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_openai_resp = _make_openai_response("GPT 응답")
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_openai_resp

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.side_effect = Exception("Claude API 오류")

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_openai_client

        with patch.dict(
            "sys.modules",
            {"anthropic": mock_anthropic, "openai": mock_openai, "airflow.models": None},
        ):
            from llm.client import generate

            result = generate("테스트 프롬프트")

        assert result.provider == "gpt"
        assert result.content == "GPT 응답"

    def test_claude_gpt_fail_falls_back_to_gemini(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Claude + GPT 실패 시 Gemini로 fallback해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        mock_gemini_resp = _make_gemini_response("Gemini 응답")

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.side_effect = Exception("Claude 실패")

        mock_openai = MagicMock()
        mock_openai.OpenAI.side_effect = Exception("GPT 실패")

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_gemini_resp

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        with patch.dict(
            "sys.modules",
            {
                "anthropic": mock_anthropic,
                "openai": mock_openai,
                "google.generativeai": mock_genai,
                "airflow.models": None,
            },
        ):
            from llm.client import generate

            result = generate("테스트 프롬프트")

        assert result.provider == "gemini"
        assert result.content == "Gemini 응답"

    def test_all_providers_fail_raises_llm_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """모든 provider 실패 시 LLMError를 발생시켜야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.side_effect = Exception("Claude 실패")

        mock_openai = MagicMock()
        mock_openai.OpenAI.side_effect = Exception("GPT 실패")

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.side_effect = Exception("Gemini 실패")

        with patch.dict(
            "sys.modules",
            {
                "anthropic": mock_anthropic,
                "openai": mock_openai,
                "google.generativeai": mock_genai,
                "airflow.models": None,
            },
        ):
            from llm.client import LLMError, generate

            with pytest.raises(LLMError, match="모든 LLM provider 실패"):
                generate("테스트 프롬프트")

    def test_system_prompt_passed_to_claude(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """system 파라미터가 Claude API에 올바르게 전달되어야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_claude_response()

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic, "airflow.models": None}):
            from llm.client import generate

            generate("프롬프트", system="시스템 프롬프트")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" in call_kwargs
        assert call_kwargs["system"] == "시스템 프롬프트"

    def test_empty_system_not_passed_to_claude(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """system이 빈 문자열이면 Claude API에 system 키를 전달하지 않아야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_claude_response()

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic, "airflow.models": None}):
            from llm.client import generate

            generate("프롬프트", system="")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs

    def test_missing_api_key_skips_to_next_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 키 미설정 provider는 건너뛰고 다음 provider를 시도해야 한다."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_openai_resp = _make_openai_response("GPT 응답")
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_openai_resp

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_openai_client

        with patch.dict(
            "sys.modules",
            {"openai": mock_openai, "airflow.models": None},
        ):
            from llm.client import generate

            result = generate("테스트 프롬프트")

        assert result.provider == "gpt"


# ── Gemini 응답 파싱 ──────────────────────────────────────────────────────────


class TestGeminiResponseParsing:
    """Gemini 응답 파싱 테스트."""

    def test_gemini_text_and_tokens_extracted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Gemini 응답에서 text와 토큰 정보를 올바르게 추출해야 한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        mock_resp = MagicMock()
        mock_resp.text = "Gemini 텍스트 응답"
        mock_resp.usage_metadata.prompt_token_count = 80
        mock_resp.usage_metadata.candidates_token_count = 30

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.side_effect = Exception("Claude 실패")

        mock_openai = MagicMock()
        mock_openai.OpenAI.side_effect = Exception("GPT 실패")

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_resp

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        with patch.dict(
            "sys.modules",
            {
                "anthropic": mock_anthropic,
                "openai": mock_openai,
                "google.generativeai": mock_genai,
                "airflow.models": None,
            },
        ):
            from llm.client import generate

            result = generate("테스트")

        assert result.content == "Gemini 텍스트 응답"
        assert result.input_tokens == 80
        assert result.output_tokens == 30
