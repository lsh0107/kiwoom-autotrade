"""Anthropic Claude 클라이언트."""

import json
import time

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel

from src.ai.llm.provider import LLMRequest, LLMResponse

logger = structlog.get_logger(__name__)

# Claude 가격 (per 1M tokens)
ANTHROPIC_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
}


class AnthropicClient:
    """Anthropic Claude 클라이언트."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        """프로바이더 이름."""
        return "anthropic"

    def _calc_cost(self, input_tokens: int, output_tokens: int) -> float:
        """비용 계산."""
        pricing = ANTHROPIC_PRICING.get(self._model, ANTHROPIC_PRICING["claude-sonnet-4-20250514"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """텍스트 완성."""
        start = time.monotonic()
        response = await self._client.messages.create(
            model=self._model,
            system=request.system_prompt or "You are a helpful assistant.",
            messages=[{"role": "user", "content": request.user_prompt}],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        latency = int((time.monotonic() - start) * 1000)

        content = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return LLMResponse(
            content=content,
            provider="anthropic",
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calc_cost(input_tokens, output_tokens),
            latency_ms=latency,
        )

    async def complete_json(
        self, request: LLMRequest, schema: type[BaseModel]
    ) -> tuple[BaseModel, LLMResponse]:
        """JSON 구조화 응답."""
        schema_str = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        json_prompt = request.model_copy(
            update={
                "user_prompt": (
                    f"{request.user_prompt}\n\n"
                    f"반드시 다음 JSON 스키마로만 응답하세요 (순수 JSON만):\n{schema_str}"
                )
            }
        )
        response = await self.complete(json_prompt)

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = schema.model_validate_json(content)

        return parsed, response
