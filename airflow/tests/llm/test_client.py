"""LLM 클라이언트 단위 테스트.

OpenAI 단독 호출 경로 검증. 외부 API는 전부 mock.
lazy import 패턴이므로 patch는 실제 라이브러리 경로를 사용한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────


def _make_openai_response(text: str = "테스트 응답") -> MagicMock:
    """openai API 응답 mock 생성."""
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=text))]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    return resp


# ── _get_api_key ─────────────────────────────────────────────────────────────


class TestGetApiKey:
    """API 키 조회 테스트."""

    def test_env_var_returns_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """환경변수에서 키를 조회해야 한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-from-env")

        # Airflow Variable import를 실패시켜 env fallback 경로 진입
        with patch.dict("sys.modules", {"airflow.models": None}):
            from llm.client import _get_api_key

            result = _get_api_key("OPENAI_API_KEY")

        assert result == "test-key-from-env"

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """키 미설정 시 ValueError를 발생시켜야 한다."""
        monkeypatch.delenv("MISSING_KEY_XYZ", raising=False)

        from llm.client import _get_api_key

        with pytest.raises(ValueError, match="MISSING_KEY_XYZ"):
            _get_api_key("MISSING_KEY_XYZ")

    def test_airflow_variable_used_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """환경변수가 없으면 Airflow Variable을 fallback으로 사용해야 한다."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        mock_variable = MagicMock()
        mock_variable.get.return_value = "airflow-var-key"
        mock_airflow_models = MagicMock()
        mock_airflow_models.Variable = mock_variable

        with patch.dict("sys.modules", {"airflow.models": mock_airflow_models}):
            from llm.client import _get_api_key

            result = _get_api_key("OPENAI_API_KEY")

        assert result == "airflow-var-key"


# ── generate (OpenAI 단독) ────────────────────────────────────────────────────


class TestGenerate:
    """generate 함수 호출/에러 처리 테스트."""

    def test_gpt_success_returns_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OpenAI 호출 성공 시 LLMResponse를 반환해야 한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_resp = _make_openai_response("분석 결과입니다")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai, "airflow.models": None}):
            from llm.client import generate

            result = generate("테스트 프롬프트")

        assert result.content == "분석 결과입니다"
        assert result.provider == "gpt"
        assert result.model == "gpt-4o"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.latency_ms >= 0

    def test_gpt_failure_raises_llm_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OpenAI 호출 실패 시 LLMError를 발생시켜야 한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_openai = MagicMock()
        mock_openai.OpenAI.side_effect = Exception("OpenAI API 오류")

        with patch.dict("sys.modules", {"openai": mock_openai, "airflow.models": None}):
            from llm.client import LLMError, generate

            with pytest.raises(LLMError, match="OpenAI 호출 실패"):
                generate("테스트 프롬프트")

    def test_missing_api_key_raises_llm_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENAI_API_KEY 미설정 시 LLMError로 감싸져야 한다(DAG가 graceful 처리)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with patch.dict("sys.modules", {"airflow.models": None}):
            from llm.client import LLMError, generate

            with pytest.raises(LLMError, match="OpenAI 호출 실패"):
                generate("테스트 프롬프트")

    def test_system_prompt_passed_to_gpt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """system 파라미터가 OpenAI API에 system role 메시지로 전달되어야 한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response()

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai, "airflow.models": None}):
            from llm.client import generate

            generate("프롬프트", system="시스템 프롬프트")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "시스템 프롬프트"}
        assert messages[1] == {"role": "user", "content": "프롬프트"}

    def test_empty_system_not_passed_to_gpt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """system이 빈 문자열이면 system role 메시지가 포함되지 않아야 한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response()

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai, "airflow.models": None}):
            from llm.client import generate

            generate("프롬프트", system="")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "프롬프트"}

    def test_max_tokens_and_model_passed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """max_tokens와 model이 OpenAI API에 전달되어야 한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response()

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai, "airflow.models": None}):
            from llm.client import generate

            generate("프롬프트", max_tokens=1024)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["max_tokens"] == 1024
