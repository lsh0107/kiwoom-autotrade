"""LLM 클라이언트 테스트 (외부 API 완전 모킹)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.ai.llm.anthropic_client import ANTHROPIC_PRICING, AnthropicClient
from src.ai.llm.openai_client import OPENAI_PRICING, OpenAIClient
from src.ai.llm.provider import LLMRequest, LLMResponse


class TestOpenAIClient:
    """OpenAI 클라이언트 테스트."""

    def _make_client(self) -> OpenAIClient:
        """모킹된 OpenAI 클라이언트 생성."""
        with patch("src.ai.llm.openai_client.AsyncOpenAI"):
            return OpenAIClient(api_key="test-key", model="gpt-4o-mini")

    def test_provider_name(self) -> None:
        """프로바이더 이름 확인."""
        client = self._make_client()
        assert client.provider_name == "openai"

    def test_calc_cost_gpt4o_mini(self) -> None:
        """GPT-4o-mini 비용 계산."""
        client = self._make_client()
        # 1000 input, 500 output
        cost = client._calc_cost(1000, 500)
        expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_calc_cost_unknown_model_uses_default(self) -> None:
        """알 수 없는 모델은 gpt-4o-mini 가격 사용."""
        with patch("src.ai.llm.openai_client.AsyncOpenAI"):
            client = OpenAIClient(api_key="test-key", model="unknown-model")
        cost = client._calc_cost(1000, 500)
        default_pricing = OPENAI_PRICING["gpt-4o-mini"]
        expected = (1000 * default_pricing["input"] + 500 * default_pricing["output"]) / 1_000_000
        assert cost == pytest.approx(expected)

    async def test_complete(self) -> None:
        """complete() 정상 호출."""
        client = self._make_client()

        # openai 응답 모킹
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50

        mock_message = MagicMock()
        mock_message.content = "분석 결과입니다."

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(
            system_prompt="시스템 프롬프트",
            user_prompt="분석 요청",
            temperature=0.3,
            max_tokens=2000,
        )

        result = await client.complete(request)

        assert isinstance(result, LLMResponse)
        assert result.content == "분석 결과입니다."
        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cost_usd > 0
        assert result.latency_ms >= 0

    async def test_complete_without_system_prompt(self) -> None:
        """system_prompt 없이 complete() 호출."""
        client = self._make_client()

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 30

        mock_message = MagicMock()
        mock_message.content = "응답"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(user_prompt="질문")
        result = await client.complete(request)

        assert result.content == "응답"
        # system_prompt가 비어있으므로 messages에 system 없음 확인
        call_args = client._client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 1  # user만
        assert messages[0]["role"] == "user"

    async def test_complete_no_usage(self) -> None:
        """usage가 None인 경우 토큰 0."""
        client = self._make_client()

        mock_message = MagicMock()
        mock_message.content = "결과"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(user_prompt="질문")
        result = await client.complete(request)

        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0

    async def test_complete_json(self) -> None:
        """complete_json() JSON 파싱 검증."""
        from src.ai.analysis.models import TradingSignal

        client = self._make_client()

        json_response = json.dumps(
            {
                "symbol": "005930",
                "action": "BUY",
                "confidence": 0.85,
                "target_price": 72000,
                "position_size_pct": 0.1,
                "reasoning": "상승 추세",
                "risk_level": "MEDIUM",
            }
        )

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 200
        mock_usage.completion_tokens = 100

        mock_message = MagicMock()
        mock_message.content = json_response

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(user_prompt="종목 분석")
        parsed, response = await client.complete_json(request, TradingSignal)

        assert isinstance(parsed, TradingSignal)
        assert parsed.symbol == "005930"
        assert parsed.action == "BUY"
        assert parsed.confidence == 0.85
        assert response.provider == "openai"

    async def test_complete_json_with_markdown_wrapper(self) -> None:
        """마크다운 코드 블록으로 감싼 JSON도 파싱."""
        from src.ai.analysis.models import TradingSignal

        client = self._make_client()

        json_body = json.dumps(
            {
                "symbol": "005930",
                "action": "HOLD",
                "confidence": 0.5,
            }
        )
        wrapped = f"```json\n{json_body}\n```"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50

        mock_message = MagicMock()
        mock_message.content = wrapped

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(user_prompt="분석")
        parsed, _ = await client.complete_json(request, TradingSignal)

        assert isinstance(parsed, TradingSignal)
        assert parsed.action == "HOLD"


class TestAnthropicClient:
    """Anthropic 클라이언트 테스트."""

    def _make_client(self) -> AnthropicClient:
        """모킹된 Anthropic 클라이언트 생성."""
        with patch("src.ai.llm.anthropic_client.AsyncAnthropic"):
            return AnthropicClient(api_key="test-key", model="claude-sonnet-4-20250514")

    def test_provider_name(self) -> None:
        """프로바이더 이름 확인."""
        client = self._make_client()
        assert client.provider_name == "anthropic"

    def test_calc_cost_claude_sonnet(self) -> None:
        """Claude Sonnet 비용 계산."""
        client = self._make_client()
        cost = client._calc_cost(1000, 500)
        pricing = ANTHROPIC_PRICING["claude-sonnet-4-20250514"]
        expected = (1000 * pricing["input"] + 500 * pricing["output"]) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_calc_cost_unknown_model_uses_default(self) -> None:
        """알 수 없는 모델은 claude-sonnet 가격 사용."""
        with patch("src.ai.llm.anthropic_client.AsyncAnthropic"):
            client = AnthropicClient(api_key="test-key", model="unknown-model")
        cost = client._calc_cost(1000, 500)
        default_pricing = ANTHROPIC_PRICING["claude-sonnet-4-20250514"]
        expected = (1000 * default_pricing["input"] + 500 * default_pricing["output"]) / 1_000_000
        assert cost == pytest.approx(expected)

    async def test_complete(self) -> None:
        """complete() 정상 호출."""
        client = self._make_client()

        mock_text_block = MagicMock()
        mock_text_block.text = "분석 결과입니다."

        mock_usage = MagicMock()
        mock_usage.input_tokens = 150
        mock_usage.output_tokens = 80

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = mock_usage

        client._client.messages.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(
            system_prompt="시스템 프롬프트",
            user_prompt="분석 요청",
        )

        result = await client.complete(request)

        assert isinstance(result, LLMResponse)
        assert result.content == "분석 결과입니다."
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.input_tokens == 150
        assert result.output_tokens == 80
        assert result.cost_usd > 0

    async def test_complete_empty_content(self) -> None:
        """응답 content가 비어있는 경우."""
        client = self._make_client()

        mock_usage = MagicMock()
        mock_usage.input_tokens = 50
        mock_usage.output_tokens = 0

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage = mock_usage

        client._client.messages.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(user_prompt="빈 응답 테스트")
        result = await client.complete(request)

        assert result.content == ""

    async def test_complete_json(self) -> None:
        """complete_json() JSON 파싱 검증."""
        from src.ai.analysis.models import TradingSignal

        client = self._make_client()

        json_response = json.dumps(
            {
                "symbol": "000660",
                "action": "SELL",
                "confidence": 0.75,
                "reasoning": "하락 추세",
                "risk_level": "HIGH",
            }
        )

        mock_text_block = MagicMock()
        mock_text_block.text = json_response

        mock_usage = MagicMock()
        mock_usage.input_tokens = 200
        mock_usage.output_tokens = 100

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = mock_usage

        client._client.messages.create = AsyncMock(return_value=mock_response)

        request = LLMRequest(user_prompt="종목 분석")
        parsed, response = await client.complete_json(request, TradingSignal)

        assert isinstance(parsed, TradingSignal)
        assert parsed.symbol == "000660"
        assert parsed.action == "SELL"
        assert response.provider == "anthropic"
