"""LLM 매니저 — 라우팅, 비용 추적, fallback 체인.

Fallback 순서: primary → fallback → gemini (키 미설정 시 자동 제외).
"""

from datetime import datetime

import structlog
from pydantic import BaseModel

from src.ai.llm.anthropic_client import AnthropicClient
from src.ai.llm.gemini_client import GeminiClient
from src.ai.llm.openai_client import OpenAIClient
from src.ai.llm.provider import LLMClient, LLMRequest, LLMResponse
from src.config.settings import get_settings
from src.utils.exceptions import AIError, LLMRateLimitError
from src.utils.time import KST

logger = structlog.get_logger(__name__)


def _today() -> datetime:
    return datetime.now(tz=KST).date()  # type: ignore[return-value]


class LLMManager:
    """LLM 라우팅 + 비용 관리 + 다단 fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self._clients: dict[str, LLMClient] = {}
        self._primary = settings.llm_primary_provider
        self._fallback = settings.llm_fallback_provider
        self._max_daily_cost = settings.max_daily_llm_cost_usd

        # 클라이언트 초기화 — 키가 있는 프로바이더만 등록
        if settings.openai_api_key:
            self._clients["openai"] = OpenAIClient(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        if settings.anthropic_api_key:
            self._clients["anthropic"] = AnthropicClient(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            )
        if settings.gemini_api_key:
            try:
                self._clients["gemini"] = GeminiClient(
                    api_key=settings.gemini_api_key,
                    model=settings.gemini_model,
                )
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Gemini 클라이언트 초기화 실패 — 비활성화", error=str(e))

        # 일일 비용 추적
        self._daily_cost: float = 0.0
        self._cost_date = _today()

    def _check_daily_cost(self) -> None:
        """일일 비용 한도 체크."""
        today = _today()
        if self._cost_date != today:
            self._daily_cost = 0.0
            self._cost_date = today

        if self._daily_cost >= self._max_daily_cost:
            raise LLMRateLimitError(
                f"일일 LLM 비용 한도 ${self._max_daily_cost:.2f} 도달"
                f" (현재: ${self._daily_cost:.2f})"
            )

    def _track_cost(self, response: LLMResponse) -> None:
        """비용 추적."""
        self._daily_cost += response.cost_usd

    def _get_client(self, provider: str) -> LLMClient:
        """프로바이더별 클라이언트 반환."""
        client = self._clients.get(provider)
        if not client:
            raise AIError(f"LLM 프로바이더 '{provider}' 미설정")
        return client

    def _fallback_chain(self, mode: str) -> list[str]:
        """모드에 따른 fallback 체인 반환.

        - quick: primary → fallback → gemini
        - deep:  fallback → primary → gemini

        설정되지 않은(클라이언트 미등록) 프로바이더는 자동 제외.
        중복 제거 순서 유지.
        """
        first = self._primary if mode == "quick" else self._fallback
        second = self._fallback if mode == "quick" else self._primary
        raw: list[str] = [first, second, "gemini"]

        chain: list[str] = []
        for name in raw:
            if name in chain:
                continue
            if name not in self._clients:
                continue
            chain.append(name)
        return chain

    async def complete(
        self,
        request: LLMRequest,
        *,
        mode: str = "quick",
    ) -> LLMResponse:
        """LLM 호출 (fallback 체인 순회)."""
        self._check_daily_cost()

        chain = self._fallback_chain(mode)
        if not chain:
            raise AIError("사용 가능한 LLM 프로바이더가 없습니다")

        last_exc: Exception | None = None
        for idx, provider in enumerate(chain):
            try:
                client = self._get_client(provider)
                response = await client.complete(request)
            except AIError:
                raise
            except Exception as e:
                last_exc = e
                next_provider = chain[idx + 1] if idx + 1 < len(chain) else None
                if next_provider:
                    await logger.awarning(
                        "LLM fallback 전환",
                        from_provider=provider,
                        to_provider=next_provider,
                        error=str(e),
                    )
                continue
            else:
                self._track_cost(response)
                return response

        raise AIError(f"LLM 호출 실패: {last_exc}") from last_exc

    async def complete_json(
        self,
        request: LLMRequest,
        schema: type[BaseModel],
        *,
        mode: str = "quick",
    ) -> tuple[BaseModel, LLMResponse]:
        """JSON 구조화 응답 (fallback 체인 순회)."""
        self._check_daily_cost()

        chain = self._fallback_chain(mode)
        if not chain:
            raise AIError("사용 가능한 LLM 프로바이더가 없습니다")

        last_exc: Exception | None = None
        for idx, provider in enumerate(chain):
            try:
                client = self._get_client(provider)
                parsed, response = await client.complete_json(request, schema)
            except AIError:
                raise
            except Exception as e:
                last_exc = e
                next_provider = chain[idx + 1] if idx + 1 < len(chain) else None
                if next_provider:
                    await logger.awarning(
                        "LLM JSON fallback 전환",
                        from_provider=provider,
                        to_provider=next_provider,
                        error=str(e),
                    )
                continue
            else:
                self._track_cost(response)
                return parsed, response

        raise AIError(f"LLM JSON 호출 실패: {last_exc}") from last_exc

    @property
    def daily_cost(self) -> float:
        """오늘 누적 비용."""
        today = _today()
        if self._cost_date != today:
            return 0.0
        return self._daily_cost

    @property
    def daily_cost_remaining(self) -> float:
        """오늘 남은 비용."""
        return max(0.0, self._max_daily_cost - self.daily_cost)
