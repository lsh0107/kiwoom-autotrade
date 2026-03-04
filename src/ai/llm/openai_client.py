"""OpenAI GPT 클라이언트."""

import json
import time

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from src.ai.llm.provider import LLMRequest, LLMResponse

logger = structlog.get_logger(__name__)

# GPT-4o-mini 가격 (per 1M tokens)
OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


class OpenAIClient:
    """OpenAI GPT 클라이언트."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        """프로바이더 이름."""
        return "openai"

    def _calc_cost(self, input_tokens: int, output_tokens: int) -> float:
        """비용 계산."""
        pricing = OPENAI_PRICING.get(self._model, OPENAI_PRICING["gpt-4o-mini"])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """텍스트 완성."""
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})

        start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        latency = int((time.monotonic() - start) * 1000)

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            content=response.choices[0].message.content or "",
            provider="openai",
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
                    f"반드시 다음 JSON 스키마로만 응답하세요:\n{schema_str}"
                )
            }
        )
        response = await self.complete(json_prompt)

        # JSON 파싱
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = schema.model_validate_json(content)

        return parsed, response
