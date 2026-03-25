"""LLM 프롬프트용 텍스트 포매터 — 토큰 예산 관리."""

from __future__ import annotations

import json
from typing import Any

# 섹션별 토큰 예산 (대략 1토큰 ≈ 4자)
TOKEN_BUDGET: dict[str, int] = {
    "market_summary": 2000,
    "sentiment_trend": 1500,
    "recent_briefings": 2000,
    "recent_reviews": 1500,
    "overnight_indices": 1500,
    "raw_data": 5000,
    "system_prompt": 1000,
}

# 최대 문자 수 (토큰 예산 * 4)
MAX_CHARS: dict[str, int] = {k: v * 4 for k, v in TOKEN_BUDGET.items()}


def _truncate(text: str, max_chars: int) -> str:
    """텍스트를 최대 문자 수로 자르고, 잘렸으면 표시."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


def format_market_summary(data: dict[str, Any]) -> str:
    """시장 데이터 요약을 LLM 프롬프트 텍스트로 변환."""
    if not data:
        return "[시장 데이터 없음]"

    lines = ["## 시장 데이터 요약"]

    # 해외지수
    if "overseas" in data:
        lines.append("\n### 해외지수")
        for name, info in data["overseas"].items():
            sign = "+" if info.get("change_pct", 0) >= 0 else ""
            lines.append(f"- {name}: {info['close']} ({sign}{info.get('change_pct', 0):.2f}%)")

    # VIX
    if "vix" in data:
        vix = data["vix"]
        level = "위험" if vix["current"] >= 30 else "경계" if vix["current"] >= 20 else "안정"
        lines.append(f"\n### VIX: {vix['current']} ({level})")

    # 거시경제
    if "macro" in data:
        lines.append("\n### 거시경제")
        lines.append(json.dumps(data["macro"], ensure_ascii=False, indent=2)[:500])

    return _truncate("\n".join(lines), MAX_CHARS["market_summary"])


def format_sentiment_trend(data: dict[str, Any]) -> str:
    """뉴스 감성 추세를 LLM 프롬프트 텍스트로 변환."""
    if not data:
        return "[뉴스 감성 데이터 없음]"

    lines = ["## 뉴스 감성 추세 (최근 7일)"]
    for keyword, counts in data.items():
        total = sum(counts.values())
        if total == 0:
            continue
        pos_ratio = counts.get("positive", 0) / total * 100
        neg_ratio = counts.get("negative", 0) / total * 100
        mood = "긍정" if pos_ratio > 60 else "부정" if neg_ratio > 40 else "중립"
        lines.append(
            f"- {keyword}: {mood} (긍정 {pos_ratio:.0f}%, 부정 {neg_ratio:.0f}%, 총 {total}건)"
        )

    return _truncate("\n".join(lines), MAX_CHARS["sentiment_trend"])


def format_briefing_history(briefings: list[dict]) -> str:
    """과거 브리핑 이력을 LLM 프롬프트 텍스트로 변환."""
    if not briefings:
        return "[과거 브리핑 없음 — 첫 분석]"

    lines = ["## 과거 브리핑 (최근 5건, 최신순)"]
    for b in briefings:
        lines.append(f"\n### {b['date']}")
        lines.append(f"요약: {b['summary']}")
        if b.get("weight_adjustments"):
            lines.append(f"비중 조정: {json.dumps(b['weight_adjustments'], ensure_ascii=False)}")
        if b.get("risk_flags"):
            lines.append(f"리스크: {json.dumps(b['risk_flags'], ensure_ascii=False)}")

    return _truncate("\n".join(lines), MAX_CHARS["recent_briefings"])


def format_review_history(reviews: list[dict]) -> str:
    """과거 리뷰 이력을 LLM 프롬프트 텍스트로 변환."""
    if not reviews:
        return "[과거 매매 리뷰 없음]"

    lines = ["## 과거 매매 리뷰 (최근 5건, 최신순)"]
    for r in reviews:
        lines.append(f"\n### {r['date']}")
        lines.append(f"요약: {r['summary']}")
        if r.get("suggestions"):
            lines.append(f"제안: {json.dumps(r['suggestions'], ensure_ascii=False)}")

    return _truncate("\n".join(lines), MAX_CHARS["recent_reviews"])


def format_overnight_indices(data: dict[str, Any]) -> str:
    """야간 해외지수를 LLM 프롬프트 텍스트로 변환."""
    if not data:
        return "[야간 해외지수 데이터 없음]"

    lines = ["## 야간 해외지수 (최신)"]
    for name, info in data.items():
        if isinstance(info, dict) and info.get("close") is not None:
            sign = "+" if info.get("change_pct", 0) >= 0 else ""
            lines.append(f"- {name}: {info['close']} ({sign}{info.get('change_pct', 0):.2f}%)")

    return _truncate("\n".join(lines), MAX_CHARS["overnight_indices"])
