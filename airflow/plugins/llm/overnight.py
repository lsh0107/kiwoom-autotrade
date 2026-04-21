"""야간 분석 LLM — 해외지수 변동 분석 + 투자 결정 생성.

설계: docs/design/design-010-llm-decision-integration.md

생성하는 ``decisions`` 항목의 ``decision_type`` 은 live_trader 소비 스펙
(``src/trading/llm_decision_loader.py::SUPPORTED_DECISION_TYPES``)을 따른다.

- ``universe_adjust`` — 특정 종목 제외 제안 (content: {"exclude": [...]})
- ``symbol_bias`` — 개별 종목 매수 가산/차단 (content: {"symbol": ..., "bias": ...})
- ``strategy_param_hint`` — 전략 파라미터 조정 힌트
  (content: {"strategy": ..., "params": {화이트리스트 키}})

레거시 타입 (``weight_adjust`` / ``risk_mode`` / ``param_tune``) 은 더 이상
생성하지 않는다. 소비자(live_trader) 가 무시하기 때문에 매매 반영이 되지 않았다.

브리핑(summary / theme_scores / risk_flags / weight_adjustments) 은 참고 정보로만
저장되며, live_trader 가 아닌 UI / 대시보드 용도로 사용된다. 본 모듈은 브리핑 구조는
그대로 유지하되, ``decisions`` 만 새 스펙으로 전환한다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# live_trader 가 이해하는 decision_type (design-010 §3 소비 타입)
_SUPPORTED_DECISION_TYPES: frozenset[str] = frozenset(
    {
        "universe_adjust",
        "symbol_bias",
        "strategy_param_hint",
    }
)

# symbol_bias.bias 허용 값 (design-010 §3)
_SUPPORTED_BIASES: frozenset[str] = frozenset({"block_buy", "boost_buy", "block_sell"})

# strategy_param_hint.params 화이트리스트
# (soft check — live_trader loader 가 최종 검증하지만, LLM 에게도 명시적으로 알려준다)
_PARAM_WHITELIST: frozenset[str] = frozenset(
    {
        "volume_ratio",
        "atr_stop_mult",
        "atr_tp_mult",
        "gap_risk_threshold",
        "max_positions",
    }
)

# strategy_param_hint.strategy 허용 값
_SUPPORTED_STRATEGIES: frozenset[str] = frozenset({"momentum", "mean_reversion", "global"})

# 브리핑 weight_adjustments 범위 제한 (참고 정보, ±20%)
_WEIGHT_LIMIT = 0.20

# 신뢰도 기본값 (LLM 이 누락했을 때)
_DEFAULT_CONFIDENCE = 0.5

_SYSTEM_PROMPT = """당신은 한국 주식 시장 전문 AI 애널리스트입니다.
야간 해외지수 변동을 분석해 익일 한국 증시에 미칠 영향과 투자 전략을 제안합니다.

핵심 원칙:
- 추측하지 말고 제공된 수치 데이터에만 기반하여 판단하세요.
- VIX 20 미만: 안정, 20~30: 경계, 30 이상: 위험 모드 권고.
- 비중 조정(weight_adjustments)은 ±20% 이내로 제한하세요.
- 과거 브리핑 결과가 있으면 이전 판단의 적중 여부를 참고하세요.
- decisions 항목은 반드시 아래 3가지 decision_type 중 하나만 사용하세요.

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
  "decisions": [
    // 다음 3가지 decision_type 중 하나 이상 사용. 필요 없으면 빈 배열.
    //
    // 1) universe_adjust — 종목 제외 제안
    // {{
    //   "decision_type": "universe_adjust",
    //   "content": {{
    //     "exclude": ["005930", "000660"],
    //     "reason": "악재 뉴스 / 실적 우려 등 (한글, 80자 이내)"
    //   }},
    //   "confidence": 0.0~1.0
    // }}
    //
    // 2) symbol_bias — 개별 종목 매수 차단/가산
    // {{
    //   "decision_type": "symbol_bias",
    //   "content": {{
    //     "symbol": "005930",
    //     "bias": "block_buy" | "boost_buy" | "block_sell",
    //     "reason": "(한글, 80자 이내)"
    //   }},
    //   "confidence": 0.0~1.0
    // }}
    //
    // 3) strategy_param_hint — 전략 파라미터 조정 힌트
    //    params 는 반드시 아래 화이트리스트 키만 사용:
    //    - volume_ratio (0.5 ~ 2.0)
    //    - atr_stop_mult (0.5 ~ 3.0)
    //    - atr_tp_mult (1.0 ~ 5.0)
    //    - gap_risk_threshold (-0.10 ~ -0.01)
    //    - max_positions (1 ~ 10, 정수)
    // {{
    //   "decision_type": "strategy_param_hint",
    //   "content": {{
    //     "strategy": "momentum" | "mean_reversion" | "global",
    //     "params": {{"max_positions": 3, "volume_ratio": 1.2}},
    //     "reason": "(한글, 80자 이내)"
    //   }},
    //   "confidence": 0.0~1.0
    // }}
  ]
}}
"""


def _parse_response(raw: str) -> dict[str, Any] | None:
    """LLM 응답 JSON 파싱 (최소 가공).

    Args:
        raw: LLM 원문 응답.

    Returns:
        JSON dict 또는 파싱 실패 시 None.
    """
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

    if not isinstance(data, dict):
        logger.warning("야간 분석 JSON 최상위가 dict 아님: %s", type(data).__name__)
        return None

    # 브리핑용 weight_adjustments 는 ±20% 로 제한 (참고 정보)
    if isinstance(data.get("weight_adjustments"), dict):
        data["weight_adjustments"] = {
            k: max(-_WEIGHT_LIMIT, min(_WEIGHT_LIMIT, float(v)))
            for k, v in data["weight_adjustments"].items()
            if _is_number(v)
        }

    return data


def _is_number(value: Any) -> bool:
    """숫자로 캐스팅 가능한지 체크 (bool 제외)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False


def _coerce_confidence(value: Any) -> float:
    """confidence 를 [0, 1] 범위로 강제. 실패 시 기본값."""
    if not _is_number(value):
        return _DEFAULT_CONFIDENCE
    try:
        num = float(value)
    except (TypeError, ValueError):
        return _DEFAULT_CONFIDENCE
    if num < 0.0:
        return 0.0
    if num > 1.0:
        return 1.0
    return num


def _clean_str_list(value: Any) -> list[str]:
    """문자열 리스트를 정제 (비어있지 않은 str 만 포함)."""
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        s = str(item).strip()
        if s:
            result.append(s)
    return result


def _validate_universe_adjust(content: Any) -> dict[str, Any] | None:
    """universe_adjust content 검증 + 정규화.

    Args:
        content: LLM 가 생성한 content 딕셔너리.

    Returns:
        검증된 content (exclude 가 1개 이상 있을 때) 또는 None.
    """
    if not isinstance(content, dict):
        return None
    exclude = _clean_str_list(content.get("exclude"))
    if not exclude:
        logger.debug("universe_adjust: exclude 비어있음 — drop")
        return None
    cleaned: dict[str, Any] = {"exclude": exclude}
    reason = content.get("reason")
    if isinstance(reason, str) and reason.strip():
        cleaned["reason"] = reason.strip()
    return cleaned


def _validate_symbol_bias(content: Any) -> dict[str, Any] | None:
    """symbol_bias content 검증 + 정규화.

    Args:
        content: LLM 가 생성한 content 딕셔너리.

    Returns:
        검증된 content 또는 None.
    """
    if not isinstance(content, dict):
        return None
    symbol = content.get("symbol")
    bias = content.get("bias")
    if not isinstance(symbol, str) or not symbol.strip():
        logger.debug("symbol_bias: symbol 누락 — drop")
        return None
    if bias not in _SUPPORTED_BIASES:
        logger.warning("symbol_bias: bias=%r 미지원 — drop", bias)
        return None
    cleaned: dict[str, Any] = {"symbol": symbol.strip(), "bias": bias}
    reason = content.get("reason")
    if isinstance(reason, str) and reason.strip():
        cleaned["reason"] = reason.strip()
    return cleaned


def _validate_strategy_param_hint(content: Any) -> dict[str, Any] | None:
    """strategy_param_hint content 검증 + 정규화.

    화이트리스트 외 키는 제거하고 최종 검증은 live_trader loader 가 수행한다.

    Args:
        content: LLM 가 생성한 content 딕셔너리.

    Returns:
        검증된 content (params 가 1개 이상 있을 때) 또는 None.
    """
    if not isinstance(content, dict):
        return None
    strategy = content.get("strategy")
    if strategy not in _SUPPORTED_STRATEGIES:
        logger.warning("strategy_param_hint: strategy=%r 미지원 — drop", strategy)
        return None

    raw_params = content.get("params")
    if not isinstance(raw_params, dict) or not raw_params:
        logger.debug("strategy_param_hint: params 누락 — drop")
        return None

    filtered_params: dict[str, Any] = {}
    for key, val in raw_params.items():
        if key not in _PARAM_WHITELIST:
            logger.warning("strategy_param_hint: 화이트리스트 외 키=%s 제거", key)
            continue
        if not _is_number(val):
            logger.warning("strategy_param_hint: 숫자 아님 key=%s val=%r 제거", key, val)
            continue
        filtered_params[key] = val

    if not filtered_params:
        return None

    cleaned: dict[str, Any] = {"strategy": strategy, "params": filtered_params}
    reason = content.get("reason")
    if isinstance(reason, str) and reason.strip():
        cleaned["reason"] = reason.strip()
    return cleaned


_VALIDATORS: dict[str, Any] = {
    "universe_adjust": _validate_universe_adjust,
    "symbol_bias": _validate_symbol_bias,
    "strategy_param_hint": _validate_strategy_param_hint,
}


def _normalize_decisions(raw_decisions: Any) -> list[dict[str, Any]]:
    """LLM decisions 배열을 Design 010 스펙에 맞게 필터/정규화.

    각 항목은 ``{"decision_type": ..., "content": {...}, "confidence": 0..1}``
    형식이어야 하며, 화이트리스트에 없는 decision_type 이나 검증 실패 항목은
    제거된다.

    Args:
        raw_decisions: LLM 응답의 ``decisions`` 필드.

    Returns:
        정규화된 decision 리스트. 사용할 수 있는 항목이 없으면 빈 리스트.
    """
    if not isinstance(raw_decisions, list):
        return []

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_decisions):
        if not isinstance(item, dict):
            logger.warning("decisions[%d]: dict 아님 — drop", idx)
            continue
        dtype = item.get("decision_type")
        if dtype not in _SUPPORTED_DECISION_TYPES:
            logger.warning("decisions[%d]: decision_type=%r 미지원(legacy 포함) — drop", idx, dtype)
            continue
        validator = _VALIDATORS[dtype]
        validated_content = validator(item.get("content"))
        if validated_content is None:
            continue
        normalized.append(
            {
                "decision_type": dtype,
                "content": validated_content,
                "confidence": _coerce_confidence(item.get("confidence")),
            }
        )

    return normalized


def _default_result() -> dict[str, Any]:
    """LLM 실패 / 파싱 실패 시 기본 결과."""
    return {
        "summary": "응답 파싱 실패. 기본값 사용.",
        "theme_scores": {},
        "risk_flags": [],
        "weight_adjustments": {},
        "decisions": [],
    }


def generate_overnight_analysis(ctx: dict) -> dict[str, Any]:
    """야간 컨텍스트를 분석해 LLM 브리핑 + 결정 생성.

    Args:
        ctx: build_overnight_context() 결과.
            - raw: 원본 데이터
            - formatted: 포맷된 텍스트

    Returns:
        분석 결과 딕셔너리.
            - summary (str): 브리핑 요약
            - theme_scores (dict): 테마별 스코어 (참고)
            - risk_flags (list[str]): 리스크 항목 (참고)
            - weight_adjustments (dict): 비중 조정 제안 (참고, ±20% 제한)
            - decisions (list[dict]): Design 010 스펙 준수 결정 리스트
              (universe_adjust / symbol_bias / strategy_param_hint)
            - raw_response (str): LLM 원문
            - provider (str): LLM provider
            - model (str): 모델명
    """
    from llm.client import LLMError, generate

    context_text = ctx.get("formatted", "[컨텍스트 없음]")
    prompt = _USER_PROMPT_TEMPLATE.format(context_text=context_text)

    try:
        response = generate(prompt=prompt, system=_SYSTEM_PROMPT, max_tokens=2048)
    except LLMError as exc:
        logger.error("LLM 호출 실패 (야간 분석): %s", exc)
        fallback = _default_result()
        fallback.update(
            {
                "summary": "LLM 호출 실패. 기본값 사용.",
                "raw_response": "",
                "provider": "",
                "model": "",
            }
        )
        return fallback

    parsed = _parse_response(response.content)
    if parsed is None:
        result = _default_result()
    else:
        result = {
            "summary": str(parsed.get("summary", "")),
            "theme_scores": parsed.get("theme_scores", {})
            if isinstance(parsed.get("theme_scores"), dict)
            else {},
            "risk_flags": _clean_str_list(parsed.get("risk_flags")),
            "weight_adjustments": parsed.get("weight_adjustments", {})
            if isinstance(parsed.get("weight_adjustments"), dict)
            else {},
            "decisions": _normalize_decisions(parsed.get("decisions")),
        }

    result["raw_response"] = response.content
    result["provider"] = response.provider
    result["model"] = response.model

    logger.info(
        "overnight 분석 완료: decisions=%d (types=%s)",
        len(result["decisions"]),
        sorted({d["decision_type"] for d in result["decisions"]}),
    )
    return result
