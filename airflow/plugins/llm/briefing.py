"""장전 브리핑 생성 — DART 공시 + 해외지수 + VIX/금리 → 테마 스코어 + 가중치."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 한국 주식 시장 전문 AI 애널리스트입니다.
장전 데이터를 분석해 당일 매매 전략에 활용할 브리핑을 생성합니다.
반드시 다음 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요."""

_USER_PROMPT_TEMPLATE = """다음 장전 데이터를 분석해 브리핑을 생성하세요.

## DART 공시 (최근 1일)
{dart_section}

## 해외 지수
{overseas_section}

## 거시경제 (VIX / 금리 / 환율 / 유가)
{macro_section}

## 응답 형식 (JSON만 출력)
{{
  "summary": "시장 요약 (한글, 300자 이내)",
  "theme_scores": {{
    "테마명": 0.0~1.0,
    ...
  }},
  "risk_flags": ["리스크 항목1", "리스크 항목2"],
  "weight_adjustments": {{
    "테마명": -0.2~0.2,
    ...
  }}
}}
"""

_WEIGHT_LIMIT = 0.20  # 가중치 조정 ±20% 제한


@dataclass
class BriefingResult:
    """장전 브리핑 결과."""

    summary: str  # 시장 요약 (한글, 300자 이내)
    theme_scores: dict[str, float]  # {"반도체": 0.8, "2차전지": 0.6, ...}
    risk_flags: list[str]  # ["삼성전자 대규모 공시", "VIX 30 초과"]
    weight_adjustments: dict[str, float]  # {"반도체": +0.1, "바이오": -0.05}
    raw_response: str
    provider: str = ""
    model: str = ""


def _default_briefing_result(raw: str = "") -> BriefingResult:
    """파싱 실패 시 기본값 반환."""
    return BriefingResult(
        summary="데이터 분석 중 오류 발생. 기본값 사용.",
        theme_scores={},
        risk_flags=[],
        weight_adjustments={},
        raw_response=raw,
    )


def _format_dart(dart: list[dict]) -> str:
    """DART 공시 목록을 프롬프트용 텍스트로 변환."""
    if not dart:
        return "공시 없음"
    lines = []
    for item in dart[:20]:  # 최대 20건
        corp = item.get("corp_name", "")
        report = item.get("report_nm", "")
        lines.append(f"- {corp}: {report}")
    return "\n".join(lines)


def _format_overseas(overseas: dict) -> str:
    """해외지수 딕셔너리를 프롬프트용 텍스트로 변환."""
    if not overseas:
        return "데이터 없음"
    lines = []
    for name, val in overseas.items():
        if isinstance(val, dict) and not val.get("error"):
            close = val.get("close", "N/A")
            chg = val.get("change_pct", "N/A")
            lines.append(
                f"- {name}: {close} ({chg:+.2f}%)"
                if isinstance(chg, float)
                else f"- {name}: {close}"
            )
        else:
            lines.append(f"- {name}: 데이터 없음")
    return "\n".join(lines)


def _format_macro(fred: dict) -> str:
    """FRED 거시경제 데이터를 프롬프트용 텍스트로 변환."""
    if not fred:
        return "데이터 없음"
    lines = []
    label_map = {
        "vix": "VIX",
        "us_rate_10y": "미국 10년 국채",
        "usd_krw": "USD/KRW",
        "wti": "WTI 유가",
    }
    for key, label in label_map.items():
        val = fred.get(key)
        lines.append(f"- {label}: {val}" if val is not None else f"- {label}: N/A")
    return "\n".join(lines)


def _clamp_weights(adjustments: dict[str, float]) -> dict[str, float]:
    """가중치 조정값을 ±20% 범위로 제한."""
    return {k: max(-_WEIGHT_LIMIT, min(_WEIGHT_LIMIT, float(v))) for k, v in adjustments.items()}


def _parse_briefing_response(raw: str) -> BriefingResult | None:
    """LLM 응답 JSON 파싱.

    Returns:
        파싱 성공 시 BriefingResult, 실패 시 None.
    """
    # JSON 블록 추출
    text = raw.strip()
    if "```" in text:
        # 마크다운 코드블록 제거
        import re

        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 첫 번째 { ~ 마지막 } 추출 시도
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.warning("브리핑 JSON 파싱 실패")
                return None
        else:
            logger.warning("브리핑 JSON 블록 없음")
            return None

    try:
        summary = str(data.get("summary", ""))[:300]
        theme_scores = {
            str(k): float(max(0.0, min(1.0, v))) for k, v in data.get("theme_scores", {}).items()
        }
        risk_flags = [str(r) for r in data.get("risk_flags", [])]
        weight_adjustments = _clamp_weights(
            {str(k): v for k, v in data.get("weight_adjustments", {}).items()}
        )
        return BriefingResult(
            summary=summary,
            theme_scores=theme_scores,
            risk_flags=risk_flags,
            weight_adjustments=weight_adjustments,
            raw_response=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("브리핑 데이터 변환 실패: %s", exc)
        return None


def generate_briefing(premarket_data: dict) -> BriefingResult:
    """장전 데이터를 분석해 LLM 브리핑 생성.

    Args:
        premarket_data: 장전 수집 데이터.
            dart, fred, overseas 키를 포함.

    Returns:
        BriefingResult. LLM 실패 또는 파싱 실패 시 기본값 반환.
    """
    from llm.client import LLMError, generate

    dart = premarket_data.get("dart", [])
    fred = premarket_data.get("fred", {})
    overseas = premarket_data.get("overseas", {})

    prompt = _USER_PROMPT_TEMPLATE.format(
        dart_section=_format_dart(dart),
        overseas_section=_format_overseas(overseas),
        macro_section=_format_macro(fred),
    )

    try:
        response = generate(prompt=prompt, system=_SYSTEM_PROMPT, max_tokens=2048)
    except LLMError as exc:
        logger.error("LLM 호출 실패 (브리핑): %s", exc)
        return _default_briefing_result()

    result = _parse_briefing_response(response.content)
    if result is None:
        result = _default_briefing_result(response.content)

    result.provider = response.provider
    result.model = response.model
    return result
