"""LLM 통합 클라이언트 — OpenAI 단독.

사용자가 Anthropic/Gemini 키를 발급하지 않은 상황을 반영하여
OpenAI(GPT)만 호출한다. 다른 provider로 확장이 필요하면 별도 PR로 재도입한다.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 호출 실패 시 발생."""


@dataclass
class LLMResponse:
    """LLM 응답 데이터클래스."""

    content: str
    provider: str  # 현재는 "gpt" 고정
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def _get_api_key(name: str) -> str:
    """API 키 조회. 환경변수 우선, 없으면 Airflow Variable.

    Args:
        name: 키 이름 (예: "OPENAI_API_KEY").

    Returns:
        API 키 문자열.

    Raises:
        ValueError: 키가 설정되어 있지 않을 때.
    """
    val = os.environ.get(name, "")
    if val:
        return val

    try:
        from airflow.models import Variable

        val = Variable.get(name, default_var=None)
        if val:
            return val
    except Exception:
        logger.debug("Airflow Variable 조회 실패: %s", name)

    raise ValueError(f"{name} 미설정")


def _call_gpt(prompt: str, system: str, max_tokens: int, timeout: int) -> LLMResponse:
    """GPT API 호출.

    Args:
        prompt: 사용자 프롬프트.
        system: 시스템 프롬프트 (빈 문자열이면 전달하지 않음).
        max_tokens: 최대 출력 토큰 수.
        timeout: 타임아웃 (초).

    Returns:
        LLMResponse.
    """
    import openai

    api_key = _get_api_key("OPENAI_API_KEY")
    model = "gpt-4o"

    client = openai.OpenAI(api_key=api_key, timeout=timeout)
    start = time.monotonic()

    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,  # type: ignore[arg-type]
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    content = response.choices[0].message.content or "" if response.choices else ""
    usage = response.usage
    return LLMResponse(
        content=content,
        provider="gpt",
        model=model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
    )


def generate(
    prompt: str,
    system: str = "",
    max_tokens: int = 4096,
    timeout: int = 30,
) -> LLMResponse:
    """LLM 호출 — OpenAI(GPT) 단독.

    Args:
        prompt: 사용자 프롬프트.
        system: 시스템 프롬프트.
        max_tokens: 최대 출력 토큰 수.
        timeout: 타임아웃 (초).

    Returns:
        LLMResponse.

    Raises:
        LLMError: OpenAI 호출 실패 또는 키 미설정.
    """
    try:
        logger.info("LLM 호출 시도: gpt")
        response = _call_gpt(prompt, system, max_tokens, timeout)
    except Exception as exc:
        logger.warning("LLM gpt 실패: %s", exc)
        raise LLMError(f"OpenAI 호출 실패: {exc}") from exc

    logger.info(
        "LLM 호출 성공: gpt (%dms, in=%d, out=%d)",
        response.latency_ms,
        response.input_tokens,
        response.output_tokens,
    )
    return response
