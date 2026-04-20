"""Gemini 클라이언트 테스트 (외부 API 완전 모킹)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.llm.gemini_client import GEMINI_PRICING, GeminiClient
from src.ai.llm.provider import LLMRequest, LLMResponse

_FAKE_KEY = "x"  # 실제 키 아님. 모킹된 genai.configure로 호출됨.


def _make_client(model: str = "gemini-1.5-flash") -> GeminiClient:
    """모킹된 Gemini 클라이언트 생성."""
    with (
        patch("src.ai.llm.gemini_client.genai.configure"),
        patch("src.ai.llm.gemini_client.genai.GenerativeModel") as mock_model_cls,
    ):
        mock_model_cls.return_value = MagicMock()
        return GeminiClient(_FAKE_KEY, model=model)


class TestGeminiClient:
    """Gemini 클라이언트 단위 테스트."""

    def test_provider_name(self) -> None:
        """provider_name은 'gemini'."""
        client = _make_client()
        assert client.provider_name == "gemini"

    def test_calc_cost_flash(self) -> None:
        """gemini-1.5-flash 비용 계산."""
        client = _make_client()
        pricing = GEMINI_PRICING["gemini-1.5-flash"]
        expected = (1000 * pricing["input"] + 500 * pricing["output"]) / 1_000_000
        assert client._calc_cost(1000, 500) == pytest.approx(expected)

    def test_calc_cost_unknown_model_uses_default(self) -> None:
        """미지정 모델은 기본(flash) 가격 사용."""
        client = _make_client(model="gemini-unknown")
        pricing = GEMINI_PRICING["gemini-1.5-flash"]
        expected = (1000 * pricing["input"] + 500 * pricing["output"]) / 1_000_000
        assert client._calc_cost(1000, 500) == pytest.approx(expected)

    def test_build_prompt_with_system(self) -> None:
        """system_prompt가 user_prompt 앞에 붙는다."""
        client = _make_client()
        req = LLMRequest(system_prompt="너는 분석가", user_prompt="삼성전자")
        prompt = client._build_prompt(req)
        assert prompt.startswith("너는 분석가")
        assert "삼성전자" in prompt

    def test_build_prompt_without_system(self) -> None:
        """system_prompt 없으면 user_prompt만."""
        client = _make_client()
        req = LLMRequest(user_prompt="삼성전자")
        assert client._build_prompt(req) == "삼성전자"

    async def test_complete(self) -> None:
        """complete() 정상 호출."""
        client = _make_client()

        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 120
        mock_usage.candidates_token_count = 60

        mock_response = MagicMock()
        mock_response.text = "Gemini 응답입니다."
        mock_response.usage_metadata = mock_usage

        client._model.generate_content_async = AsyncMock(return_value=mock_response)

        request = LLMRequest(
            system_prompt="시스템",
            user_prompt="분석",
            temperature=0.2,
            max_tokens=500,
        )

        result = await client.complete(request)

        assert isinstance(result, LLMResponse)
        assert result.provider == "gemini"
        assert result.model == "gemini-1.5-flash"
        assert result.content == "Gemini 응답입니다."
        assert result.input_tokens == 120
        assert result.output_tokens == 60
        assert result.cost_usd > 0
        assert result.latency_ms >= 0

    async def test_complete_no_usage_metadata(self) -> None:
        """usage_metadata가 없을 때 토큰 0."""
        client = _make_client()

        mock_response = MagicMock(spec=["text"])
        mock_response.text = "응답"
        client._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await client.complete(LLMRequest(user_prompt="질문"))

        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0

    async def test_complete_safety_blocked(self) -> None:
        """response.text 접근 시 ValueError면 빈 content."""
        client = _make_client()

        mock_response = MagicMock()
        # text 프로퍼티가 ValueError를 발생 (safety filter 차단)
        type(mock_response).text = property(
            lambda _self: (_ for _ in ()).throw(ValueError("blocked"))
        )
        mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=0)

        client._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await client.complete(LLMRequest(user_prompt="차단 트리거"))
        assert result.content == ""
        assert result.input_tokens == 10

    async def test_complete_json(self) -> None:
        """complete_json() JSON 파싱."""
        from src.ai.analysis.models import TradingSignal

        client = _make_client()

        json_response = json.dumps(
            {
                "symbol": "005930",
                "action": "BUY",
                "confidence": 0.9,
                "reasoning": "상승",
                "risk_level": "LOW",
            }
        )

        mock_response = MagicMock()
        mock_response.text = json_response
        mock_response.usage_metadata = MagicMock(prompt_token_count=150, candidates_token_count=80)
        client._model.generate_content_async = AsyncMock(return_value=mock_response)

        parsed, resp = await client.complete_json(LLMRequest(user_prompt="분석"), TradingSignal)

        assert isinstance(parsed, TradingSignal)
        assert parsed.symbol == "005930"
        assert parsed.action == "BUY"
        assert resp.provider == "gemini"

    async def test_complete_json_with_markdown_wrapper(self) -> None:
        """마크다운 코드 블록으로 감싼 JSON도 파싱."""
        from src.ai.analysis.models import TradingSignal

        client = _make_client()

        body = json.dumps({"symbol": "000660", "action": "HOLD", "confidence": 0.4})
        wrapped = f"```json\n{body}\n```"

        mock_response = MagicMock()
        mock_response.text = wrapped
        mock_response.usage_metadata = MagicMock(prompt_token_count=90, candidates_token_count=40)
        client._model.generate_content_async = AsyncMock(return_value=mock_response)

        parsed, _ = await client.complete_json(LLMRequest(user_prompt="분석"), TradingSignal)

        assert isinstance(parsed, TradingSignal)
        assert parsed.action == "HOLD"

    async def test_generation_config_applied(self) -> None:
        """temperature/max_tokens가 GenerationConfig에 전달."""
        client = _make_client()

        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.usage_metadata = MagicMock(prompt_token_count=1, candidates_token_count=1)
        client._model.generate_content_async = AsyncMock(return_value=mock_response)

        request = LLMRequest(user_prompt="테스트", temperature=0.7, max_tokens=1234)
        await client.complete(request)

        call_kwargs = client._model.generate_content_async.call_args.kwargs
        gen_config = call_kwargs["generation_config"]
        assert gen_config.temperature == 0.7
        assert gen_config.max_output_tokens == 1234
