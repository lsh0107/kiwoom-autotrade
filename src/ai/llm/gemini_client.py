"""Google Gemini 클라이언트 (3번째 fallback)."""

import json
import time

import google.generativeai as genai
import structlog
from pydantic import BaseModel

from src.ai.llm.provider import LLMRequest, LLMResponse

logger = structlog.get_logger(__name__)

# Gemini 가격 (per 1M tokens)
# 출처: https://ai.google.dev/pricing
GEMINI_PRICING: dict[str, dict[str, float]] = {
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}

DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiClient:
    """Google Gemini 클라이언트."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """클라이언트 초기화.

        Args:
            api_key: Google AI Studio API 키
            model: 모델 ID (기본 gemini-1.5-flash)
        """
        genai.configure(api_key=api_key)
        self._model_name = model
        self._model = genai.GenerativeModel(model)

    @property
    def provider_name(self) -> str:
        """프로바이더 이름."""
        return "gemini"

    def _calc_cost(self, input_tokens: int, output_tokens: int) -> float:
        """비용 계산."""
        pricing = GEMINI_PRICING.get(self._model_name, GEMINI_PRICING[DEFAULT_MODEL])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    def _build_prompt(self, request: LLMRequest) -> str:
        """system_prompt를 user_prompt 앞에 합성.

        Gemini는 OpenAI처럼 별도 system role을 지원하지 않으므로
        프롬프트 앞에 시스템 지시문을 붙인다.
        """
        if request.system_prompt:
            return f"{request.system_prompt}\n\n{request.user_prompt}"
        return request.user_prompt

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """텍스트 완성."""
        prompt = self._build_prompt(request)
        generation_config = genai.GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        start = time.monotonic()
        response = await self._model.generate_content_async(
            prompt,
            generation_config=generation_config,
        )
        latency = int((time.monotonic() - start) * 1000)

        # 텍스트 추출 — response.text가 기본 접근자
        content: str = ""
        try:
            content = response.text or ""
        except (ValueError, AttributeError):
            # candidates가 비어있거나 safety filter 차단 시
            content = ""

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        return LLMResponse(
            content=content,
            provider="gemini",
            model=self._model_name,
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
