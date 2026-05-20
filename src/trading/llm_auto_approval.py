"""LLM 결정 자동 승인 모듈 (Phase 1).

Airflow LLM DAG가 생성한 pending 결정을 안전 기준 통과 시 자동 approved로 전환.
사용자 수동 개입 우회 — design-010 §자동화.

안전 기준:
1. ``confidence >= min_confidence`` (None은 reject)
2. ``decision_type`` in ``SUPPORTED_DECISION_TYPES``
3. ``strategy_param_hint``: whitelist 키 + 범위 검증 통과
4. 같은 date+decision_type에 manual rejected 있으면 skip (사용자 의사 우선)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.llm_decision import LLMDecision
from src.trading.llm_decision_loader import (
    LLM_PARAM_WHITELIST,
    SUPPORTED_DECISION_TYPES,
)

log = logging.getLogger(__name__)

# 자동 승인 디폴트 임계값
DEFAULT_MIN_CONFIDENCE: float = 0.6

# 자동 승인/거부 대상에서 제외할 context_source 집합.
# 안전 경계상 사용자 수동 승인이 반드시 필요한 출처.
MANUAL_REVIEW_CONTEXT_SOURCES: frozenset[str] = frozenset({"ai_hedge"})


def _validate_strategy_param_hint(content: dict[str, Any]) -> tuple[bool, str]:
    """strategy_param_hint content를 whitelist + 범위로 검증.

    Args:
        content: LLMDecision.content (dict)

    Returns:
        (통과 여부, 사유). 사유는 reject 시에만 의미 있음.
    """
    # content 형식: {"strategy": ..., "params": {key: val}} 또는 {key: val}
    params = content.get("params") if isinstance(content, dict) else None
    if not isinstance(params, dict):
        params = content if isinstance(content, dict) else {}

    if not params:
        return (False, "params 비어있음")

    # whitelist 키 검증 + 범위 검증
    for key, value in params.items():
        if key in {"strategy", "reason", "rationale", "comment"}:
            continue
        if key not in LLM_PARAM_WHITELIST:
            return (False, f"whitelist 외 키: {key}")
        try:
            num = float(value)
        except (TypeError, ValueError):
            return (False, f"숫자 변환 실패: {key}={value!r}")
        lo, hi, _ = LLM_PARAM_WHITELIST[key]
        if not (lo <= num <= hi):
            return (False, f"범위 위반: {key}={num} not in [{lo}, {hi}]")
    return (True, "")


def _validate_decision(decision: LLMDecision, min_confidence: float) -> tuple[bool, str]:
    """단일 결정의 자동 승인 가능 여부 평가."""
    if decision.confidence is None or decision.confidence < min_confidence:
        return (False, f"confidence {decision.confidence} < {min_confidence}")
    if decision.decision_type not in SUPPORTED_DECISION_TYPES:
        return (False, f"unsupported type: {decision.decision_type}")
    if decision.decision_type == "strategy_param_hint":
        return _validate_strategy_param_hint(decision.content or {})
    # universe_adjust / symbol_bias는 컨텐츠 free-form, 추가 검증 없이 confidence만 사용
    return (True, "")


async def _has_manual_rejection(db: AsyncSession, decision: LLMDecision) -> bool:
    """같은 date + decision_type에 사용자가 reject한 결정이 있는지 확인.

    사용자 수동 거부 의사가 있으면 자동 승인 skip — 사용자 우선 정책.
    """
    stmt = select(
        exists().where(
            and_(
                LLMDecision.date == decision.date,
                LLMDecision.decision_type == decision.decision_type,
                LLMDecision.status == "rejected",
            )
        )
    )
    result = await db.execute(stmt)
    return bool(result.scalar())


async def auto_approve_pending(
    *,
    db: AsyncSession,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    max_per_run: int = 50,
) -> dict[str, int]:
    """pending 결정을 안전 기준 통과 시 approved로 전환.

    Args:
        db: AsyncSession
        min_confidence: 자동 승인 최소 신뢰도 (None은 reject)
        max_per_run: 한 번 실행에서 처리할 최대 건수

    Returns:
        {"approved": N, "rejected": M, "skipped": K}
    """
    stmt = (
        select(LLMDecision)
        .where(LLMDecision.status == "pending")
        .order_by(LLMDecision.created_at.desc())
        .limit(max_per_run)
    )
    result = await db.execute(stmt)
    pending = list(result.scalars().all())

    counts = {"approved": 0, "rejected": 0, "skipped": 0}
    approved_ids: list = []
    rejected_ids: list[tuple] = []  # (id, reason)

    for d in pending:
        if d.context_source in MANUAL_REVIEW_CONTEXT_SOURCES:
            counts["skipped"] += 1
            log.info(
                "[%s] %s context_source=%s requires manual review — 자동 승인/거부 skip",
                d.date,
                d.decision_type,
                d.context_source,
            )
            continue

        if await _has_manual_rejection(db, d):
            counts["skipped"] += 1
            log.info(
                "[%s] %s 자동 승인 skip — 같은 date+type에 manual rejected 존재",
                d.date,
                d.decision_type,
            )
            continue

        ok, reason = _validate_decision(d, min_confidence)
        if ok:
            approved_ids.append(d.id)
            counts["approved"] += 1
            log.info(
                "[%s] %s 자동 승인 (confidence=%.2f)",
                d.date,
                d.decision_type,
                d.confidence or 0.0,
            )
        else:
            rejected_ids.append((d.id, reason))
            counts["rejected"] += 1
            log.info(
                "[%s] %s 자동 거부 — %s (confidence=%.2f)",
                d.date,
                d.decision_type,
                reason,
                d.confidence or 0.0,
            )

    if approved_ids:
        await db.execute(
            update(LLMDecision).where(LLMDecision.id.in_(approved_ids)).values(status="approved")
        )
    if rejected_ids:
        await db.execute(
            update(LLMDecision)
            .where(LLMDecision.id.in_([r[0] for r in rejected_ids]))
            .values(status="auto_rejected")
        )
    await db.commit()

    log.info(
        "LLM 자동 승인 완료: approved=%d, rejected=%d, skipped=%d (총 %d건 검토)",
        counts["approved"],
        counts["rejected"],
        counts["skipped"],
        len(pending),
    )
    return counts
