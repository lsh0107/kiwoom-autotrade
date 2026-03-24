"""야간 분석 LLM — 해외지수 변동 분석 + 투자 결정 생성."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 한국 주식 시장 전문 AI 애널리스트입니다.
야간 해외지수 변동을 분석해 익일 한국 증시에 미칠 영향과 투자 전략을 제안합니다.

핵심 원칙:
- 추측하지 말고 제공된 수치 데이터에만 기반하여 판단하세요.
- VIX 20 미만: 안정, 20~30: 경계, 30 이상: 위험 모드 권고.
- 비중 조정은 ±20% 이내로 제한하세요.
- 과거 브리핑 결과가 있으면 이전 판단의 적중 여부를 참고하세요.

반드시 다음 JSON 형식으로만 응답하세요."""

_USER_PROMPT_TEMPLATE = """야간 해외지수 변동을 분석하고 익일 투자 전략을 제안하세요.

{context_text}

## 응답 형식 (JSON만 출력)
{{
  "summary": "야간 변동 분석 요약 (한글, 300자 이내)",
  "theme_scores": {{
    "테마명": 0.0~1.0
  }},
  "risk_flags": ["리스크 항목"],
  "weight_adjustments": {{
    "테마명": -0.2~0.2
  }},
  "risk_mode": "aggressive|neutral|defensive|crisis",
  "decisions": [
    {{
      "decision_type": "weight_adjust|risk_mode|param_tune",
      "content": {{"설명": "구체적 내용"}},
      "confidence": 0.0~1.0
    }}
  ]
}}
"""

_WEIGHT_LIMIT = 0.20


def _parse_response(raw: str) -> dict[str, Any] | None:
    """LLM 응답 JSON 파싱."""
    text = raw.strip()
    if "```" in text:
        import re

        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.warning("야간 분석 JSON 파싱 실패")
                return None
        else:
            return None

    # 가중치 제한
    if "weight_adjustments" in data:
        data["weight_adjustments"] = {
            k: max(-_WEIGHT_LIMIT, min(_WEIGHT_LIMIT, float(v)))
            for k, v in data["weight_adjustments"].items()
        }

    return data


def generate_overnight_analysis(ctx: dict) -> dict[str, Any]:
    """야간 컨텍스트를 분석해 LLM 브리핑 + 결정 생성.

    Args:
        ctx: build_overnight_context() 결과.
            - raw: 원본 데이터
            - formatted: 포맷된 텍스트

    Returns:
        분석 결과 딕셔너리 (summary, theme_scores, decisions 등).
    """
    from llm.client import LLMError, generate

    context_text = ctx.get("formatted", "[컨텍스트 없음]")
    prompt = _USER_PROMPT_TEMPLATE.format(context_text=context_text)

    try:
        response = generate(prompt=prompt, system=_SYSTEM_PROMPT, max_tokens=2048)
    except LLMError as exc:
        logger.error("LLM 호출 실패 (야간 분석): %s", exc)
        return {
            "summary": "LLM 호출 실패. 기본값 사용.",
            "theme_scores": {},
            "risk_flags": [],
            "weight_adjustments": {},
            "risk_mode": "neutral",
            "decisions": [],
            "raw_response": "",
            "provider": "",
            "model": "",
        }

    result = _parse_response(response.content)
    if result is None:
        result = {
            "summary": "응답 파싱 실패. 기본값 사용.",
            "theme_scores": {},
            "risk_flags": [],
            "weight_adjustments": {},
            "risk_mode": "neutral",
            "decisions": [],
        }

    result["raw_response"] = response.content
    result["provider"] = response.provider
    result["model"] = response.model
    return result
