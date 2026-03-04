"""LLM 클라이언트 Protocol + 공통 모델."""

from typing import Protocol

from pydantic import BaseModel


class LLMRequest(BaseModel):
    """LLM 요청."""

    system_prompt: str = ""
    user_prompt: str
    temperature: float = 0.3
    max_tokens: int = 2000


class LLMResponse(BaseModel):
    """LLM 응답."""

    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class LLMClient(Protocol):
    """LLM 클라이언트 인터페이스."""

    @property
    def provider_name(self) -> str:
        """프로바이더 이름."""
        ...

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """텍스트 완성."""
        ...

    async def complete_json(
        self, request: LLMRequest, schema: type[BaseModel]
    ) -> tuple[BaseModel, LLMResponse]:
        """JSON 구조화 응답."""
        ...
