"""장후 매매 리뷰 생성 — 매매기록 + 시장 + 뉴스 → 성과분석 + 파라미터 제안."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 한국 주식 자동매매 시스템의 전문 리뷰 AI입니다.
당일 매매 결과를 분석해 성과를 평가하고 전략 파라미터 개선 방향을 제안합니다.
반드시 다음 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요."""

_USER_PROMPT_TEMPLATE = """다음 당일 매매 데이터를 분석해 리뷰를 생성하세요.

## 매매 기록
{trades_section}

## 시장 데이터 (OHLCV / 투자자 매매)
{market_section}

## 뉴스 감성
{news_section}

## 응답 형식 (JSON만 출력)
{{
  "summary": "매매 리뷰 요약 (한글, 300자 이내)",
  "performance_analysis": "성과 분석 (한글, 500자 이내)",
  "risk_assessment": "리스크 평가 (한글, 300자 이내)",
  "suggestions": [
    {{
      "key": "strategy_config_key",
      "current_value": 현재값,
      "suggested_value": 제안값,
      "reason": "제안 근거 (한글)",
      "confidence": 0.0~1.0
    }}
  ]
}}
"""

_MIN_CONFIDENCE = 0.5  # 낮은 신뢰도 제안 필터 기준


@dataclass
class ParamSuggestion:
    """파라미터 조정 제안."""

    key: str  # strategy_config 키
    current_value: Any
    suggested_value: Any
    reason: str  # 제안 근거
    confidence: float  # 0.0 ~ 1.0


@dataclass
class ReviewResult:
    """장후 리뷰 결과."""

    summary: str  # 매매 리뷰 요약
    performance_analysis: str  # 성과 분석
    suggestions: list[ParamSuggestion]  # 파라미터 조정 제안
    risk_assessment: str  # 리스크 평가
    raw_response: str
    provider: str = ""
    model: str = ""


def _default_review_result(raw: str = "") -> ReviewResult:
    """파싱 실패 시 기본값 반환."""
    return ReviewResult(
        summary="데이터 분석 중 오류 발생. 기본값 사용.",
        performance_analysis="",
        suggestions=[],
        risk_assessment="",
        raw_response=raw,
    )


def _format_trades(trades: list[dict]) -> str:
    """매매 기록을 프롬프트용 텍스트로 변환."""
    if not trades:
        return "당일 매매 기록 없음"
    lines = []
    for t in trades[:30]:  # 최대 30건
        ticker = t.get("ticker", "")
        side = t.get("side", "")
        qty = t.get("quantity", 0)
        price = t.get("price", 0)
        pnl = t.get("pnl", None)
        pnl_str = f", 손익={pnl:+.0f}원" if pnl is not None else ""
        lines.append(f"- {ticker} {side} {qty}주 @{price:,}원{pnl_str}")
    return "\n".join(lines)


def _format_market(market_data: dict) -> str:
    """시장 데이터를 프롬프트용 텍스트로 변환."""
    if not market_data:
        return "데이터 없음"
    lines = []

    ohlcv = market_data.get("ohlcv", [])
    if ohlcv:
        lines.append(f"OHLCV 수집 종목 수: {len(ohlcv)}개")

    investor = market_data.get("investor", [])
    if investor:
        lines.append("투자자 매매:")
        for item in investor[:5]:
            inv = item.get("투자자", item.get("investor", ""))
            net = item.get("순매수", item.get("net", 0))
            lines.append(
                f"  - {inv}: 순매수 {net:,}원" if isinstance(net, int | float) else f"  - {inv}"
            )

    return "\n".join(lines) if lines else "데이터 없음"


def _format_news(news_data: list[dict]) -> str:
    """뉴스 감성 데이터를 프롬프트용 텍스트로 변환."""
    if not news_data:
        return "뉴스 데이터 없음"
    pos = sum(1 for n in news_data if n.get("sentiment") == "positive")
    neg = sum(1 for n in news_data if n.get("sentiment") == "negative")
    neu = len(news_data) - pos - neg
    lines = [
        f"뉴스 총 {len(news_data)}건: 긍정={pos}, 부정={neg}, 중립={neu}",
    ]
    # 주요 뉴스 제목 (최대 5건)
    for article in news_data[:5]:
        title = article.get("title", "")
        sentiment = article.get("sentiment", "")
        if title:
            lines.append(f"- [{sentiment}] {title}")
    return "\n".join(lines)


def _parse_review_response(raw: str) -> ReviewResult | None:
    """LLM 응답 JSON 파싱.

    Returns:
        파싱 성공 시 ReviewResult, 실패 시 None.
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
                logger.warning("리뷰 JSON 파싱 실패")
                return None
        else:
            logger.warning("리뷰 JSON 블록 없음")
            return None

    try:
        summary = str(data.get("summary", ""))[:300]
        performance_analysis = str(data.get("performance_analysis", ""))[:500]
        risk_assessment = str(data.get("risk_assessment", ""))[:300]

        raw_suggestions = data.get("suggestions", [])
        suggestions: list[ParamSuggestion] = []
        for s in raw_suggestions:
            confidence = float(s.get("confidence", 0.0))
            if confidence < _MIN_CONFIDENCE:
                logger.debug("신뢰도 낮은 제안 제외: %s (%.2f)", s.get("key"), confidence)
                continue
            suggestions.append(
                ParamSuggestion(
                    key=str(s.get("key", "")),
                    current_value=s.get("current_value"),
                    suggested_value=s.get("suggested_value"),
                    reason=str(s.get("reason", "")),
                    confidence=confidence,
                )
            )

        return ReviewResult(
            summary=summary,
            performance_analysis=performance_analysis,
            suggestions=suggestions,
            risk_assessment=risk_assessment,
            raw_response=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("리뷰 데이터 변환 실패: %s", exc)
        return None


def generate_review(
    trade_data: dict,
    market_data: dict,
    news_data: dict | list,
) -> ReviewResult:
    """장후 매매 데이터를 분석해 LLM 리뷰 생성.

    Args:
        trade_data: 당일 매매 기록. trades 키에 list[dict] 포함 또는 직접 list[dict].
        market_data: 시장 데이터 (ohlcv, investor).
        news_data: 뉴스 감성 데이터. list[dict] 또는 {"articles": list[dict]}.

    Returns:
        ReviewResult. LLM 실패 또는 파싱 실패 시 기본값 반환.
    """
    from llm.client import LLMError, generate

    # trade_data 정규화
    if isinstance(trade_data, list):
        trades = trade_data
    else:
        trades = trade_data.get("trades", list(trade_data.values()) if trade_data else [])

    # news_data 정규화
    news_list = news_data if isinstance(news_data, list) else news_data.get("articles", [])

    prompt = _USER_PROMPT_TEMPLATE.format(
        trades_section=_format_trades(trades),
        market_section=_format_market(market_data),
        news_section=_format_news(news_list),
    )

    try:
        response = generate(prompt=prompt, system=_SYSTEM_PROMPT, max_tokens=3000)
    except LLMError as exc:
        logger.error("LLM 호출 실패 (리뷰): %s", exc)
        return _default_review_result()

    result = _parse_review_response(response.content)
    if result is None:
        result = _default_review_result(response.content)

    result.provider = response.provider
    result.model = response.model
    return result
