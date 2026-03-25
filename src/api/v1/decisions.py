"""LLM 투자 결정 관리 라우터."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import CurrentUser, DBSession
from src.models.llm_decision import LLMDecision
from src.utils.time import now_kst

router = APIRouter(prefix="/decisions", tags=["LLM 결정"])


# ── Pydantic 스키마 ──────────────────────────────────────


class DecisionResponse(BaseModel):
    """LLM 결정 응답."""

    id: uuid.UUID
    date: date
    decision_type: str
    context_source: str
    content: dict
    confidence: float | None
    status: str
    applied_at: datetime | None
    evaluation: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 헬퍼 ─────────────────────────────────────────────────


async def _get_decision_or_404(
    db: DBSession,
    decision_id: uuid.UUID,
) -> LLMDecision:
    """결정을 조회하고 없으면 404."""
    result = await db.execute(select(LLMDecision).where(LLMDecision.id == decision_id))
    decision = result.scalar_one_or_none()
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="결정을 찾을 수 없습니다",
        )
    return decision


# ── 엔드포인트 ────────────────────────────────────────────


@router.get("", response_model=list[DecisionResponse])
async def list_decisions(
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
    status_filter: str | None = Query(None, alias="status"),
    date_filter: date | None = Query(None, alias="date"),
    limit: int = Query(50, ge=1, le=200),
) -> list[DecisionResponse]:
    """LLM 결정 목록을 조회한다."""
    stmt = select(LLMDecision).order_by(LLMDecision.created_at.desc())

    if status_filter:
        stmt = stmt.where(LLMDecision.status == status_filter)
    if date_filter:
        stmt = stmt.where(LLMDecision.date == date_filter)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    decisions = result.scalars().all()
    return [DecisionResponse.model_validate(d) for d in decisions]


@router.post("/{decision_id}/approve", response_model=DecisionResponse)
async def approve_decision(
    decision_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> DecisionResponse:
    """결정을 승인한다."""
    decision = await _get_decision_or_404(db, decision_id)

    if decision.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 처리된 결정입니다 (현재 상태: {decision.status})",
        )

    decision.status = "approved"
    decision.applied_at = now_kst()

    await db.flush()
    await db.refresh(decision)
    return DecisionResponse.model_validate(decision)


@router.post("/{decision_id}/reject", response_model=DecisionResponse)
async def reject_decision(
    decision_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> DecisionResponse:
    """결정을 거부한다."""
    decision = await _get_decision_or_404(db, decision_id)

    if decision.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 처리된 결정입니다 (현재 상태: {decision.status})",
        )

    decision.status = "rejected"

    await db.flush()
    await db.refresh(decision)
    return DecisionResponse.model_validate(decision)
