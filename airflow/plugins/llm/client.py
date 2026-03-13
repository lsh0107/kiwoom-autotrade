"""LLM 통합 클라이언트 — Claude → GPT → Gemini fallback."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """모든 LLM provider 호출 실패 시 발생."""


@dataclass
class LLMResponse:
    """LLM 응답 데이터클래스."""

    content: str
    provider: str  # "claude" | "gpt" | "gemini"
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def _get_api_key(name: str) -> str:
    """API 키 조회. Airflow Variable 우선, 없으면 환경변수.

    Args:
        name: 키 이름 (예: "ANTHROPIC_API_KEY").

    Returns:
        API 키 문자열.

    Raises:
        ValueError: 키가 설정되어 있지 않을 때.
    """
    try:
        from airflow.models import Variable

        val = Variable.get(name, default_var=None)
        if val:
            return val
    except Exception:
        logger.debug("Airflow Variable 조회 실패, 환경변수 fallback: %s", name)

    val = os.environ.get(name, "")
    if not val:
        raise ValueError(f"{name} 미설정")
    return val


def _call_claude(prompt: str, system: str, max_tokens: int, timeout: int) -> LLMResponse:
    """Claude API 호출.

    Args:
        prompt: 사용자 프롬프트.
        system: 시스템 프롬프트.
        max_tokens: 최대 출력 토큰 수.
        timeout: 타임아웃 (초).

    Returns:
        LLMResponse.
    """
    import anthropic

    api_key = _get_api_key("ANTHROPIC_API_KEY")
    model = "claude-sonnet-4-20250514"

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    start = time.monotonic()

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    latency_ms = int((time.monotonic() - start) * 1000)

    content = response.content[0].text if response.content else ""
    return LLMResponse(
        content=content,
        provider="claude",
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )


def _call_gpt(prompt: str, system: str, max_tokens: int, timeout: int) -> LLMResponse:
    """GPT API 호출.

    Args:
        prompt: 사용자 프롬프트.
        system: 시스템 프롬프트.
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


def _call_gemini(
    prompt: str,
    system: str,
    max_tokens: int,
    timeout: int,  # noqa: ARG001
) -> LLMResponse:
    """Gemini API 호출.

    Args:
        prompt: 사용자 프롬프트.
        system: 시스템 프롬프트.
        max_tokens: 최대 출력 토큰 수.
        timeout: 타임아웃 (초, Gemini SDK는 직접 미지원으로 무시).

    Returns:
        LLMResponse.
    """
    import google.generativeai as genai

    api_key = _get_api_key("GOOGLE_API_KEY")
    model_name = "gemini-2.0-flash"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system if system else None,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
    )

    start = time.monotonic()
    response = model.generate_content(prompt)
    latency_ms = int((time.monotonic() - start) * 1000)

    content = response.text if hasattr(response, "text") else ""
    usage = response.usage_metadata if hasattr(response, "usage_metadata") else None

    return LLMResponse(
        content=content,
        provider="gemini",
        model=model_name,
        input_tokens=usage.prompt_token_count if usage else 0,
        output_tokens=usage.candidates_token_count if usage else 0,
        latency_ms=latency_ms,
    )


_PROVIDERS = [
    ("claude", _call_claude),
    ("gpt", _call_gpt),
    ("gemini", _call_gemini),
]


def generate(
    prompt: str,
    system: str = "",
    max_tokens: int = 4096,
    timeout: int = 30,
) -> LLMResponse:
    """LLM 호출 — Claude → GPT → Gemini fallback.

    Args:
        prompt: 사용자 프롬프트.
        system: 시스템 프롬프트.
        max_tokens: 최대 출력 토큰 수.
        timeout: provider별 타임아웃 (초).

    Returns:
        첫 번째 성공한 provider의 LLMResponse.

    Raises:
        LLMError: 모든 provider 실패 시.
    """
    errors: list[str] = []
    for name, caller in _PROVIDERS:
        try:
            logger.info("LLM 호출 시도: %s", name)
            response = caller(prompt, system, max_tokens, timeout)
            logger.info(
                "LLM 호출 성공: %s (%dms, in=%d, out=%d)",
                name,
                response.latency_ms,
                response.input_tokens,
                response.output_tokens,
            )
            return response
        except Exception as exc:
            logger.warning("LLM %s 실패: %s", name, exc)
            errors.append(f"{name}: {exc}")

    raise LLMError(f"모든 LLM provider 실패: {'; '.join(errors)}")
