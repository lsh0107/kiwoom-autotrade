"""LLM 투자 결정 관리 라우터."""

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from src.api.deps import CurrentUser, DBSession
from src.models.llm_decision import LLMDecision

router = APIRouter(prefix="/decisions", tags=["LLM 결정"])


# ── bias vocabulary (lab ↔ kiwoom 정합) ──────────────────
# canonical sell-side 어휘 정합. lab export 와 kiwoom validator 가 동일 집합을 쓴다.
#   - block_buy  : 매수 금지
#   - boost_buy  : 매수 강화/우선
#   - review_sell: 사람이 검토할 매도 (현재 유일하게 사람 review queue 로 연결)
#   - boost_sell : 매도 강화/우선 제안. **자동 주문/자동 매도 소비 금지** (validator 수용만).
# ``block_sell`` 은 의미가 애매(매도 금지 vs 강화)해 deprecated — 신규 생성 비권장,
# 기존 호환을 위해 수용(accepted)만 유지한다.
# 주의: validator 수용 != 자동 소비. loader(apply_universe_decisions)는 여전히
# universe.exclude + symbol_bias.block_buy 만 소비하며, boost_sell 등은 소비하지 않는다.
_DEPRECATED_BIAS: frozenset[str] = frozenset({"block_sell"})
_ALLOWED_BIAS: frozenset[str] = (
    frozenset({"block_buy", "boost_buy", "review_sell", "boost_sell"}) | _DEPRECATED_BIAS
)


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


class DecisionDraftCreate(BaseModel):
    """AI proposal layer가 생성한 pending LLMDecision draft."""

    date: date
    decision_type: Literal["universe_adjust", "symbol_bias", "strategy_param_hint"]
    context_source: str = Field(min_length=1, max_length=20)
    content: dict
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: Literal["pending"] = "pending"
    raw_response: str = ""

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: dict) -> dict:
        """decision_type별 상세 검증은 model_validator에서 수행한다."""
        if not value:
            raise ValueError("content must not be empty")
        return value

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "DecisionDraftCreate":
        """현재 loader가 안전하게 소비 가능한 draft만 허용한다."""
        if self.decision_type == "symbol_bias":
            symbol = self.content.get("symbol")
            bias = self.content.get("bias")
            if not isinstance(symbol, str) or len(symbol) != 6 or not symbol.isdigit():
                raise ValueError("symbol_bias.content.symbol must be a six-digit symbol")
            if bias not in _ALLOWED_BIAS:
                raise ValueError("symbol_bias.content.bias is not allowed")

        if self.decision_type == "universe_adjust":
            exclude = self.content.get("exclude")
            if not isinstance(exclude, list):
                raise ValueError("universe_adjust.content.exclude must be a list")
            valid_symbols = (
                isinstance(symbol, str) and len(symbol) == 6 and symbol.isdigit()
                for symbol in exclude
            )
            if not all(valid_symbols):
                raise ValueError("universe_adjust.content.exclude must contain six-digit symbols")

        if self.decision_type == "strategy_param_hint":
            params = self.content.get("params", self.content)
            if not isinstance(params, dict):
                raise ValueError("strategy_param_hint params must be an object")

        return self


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


@router.post("/drafts", response_model=list[DecisionResponse], status_code=status.HTTP_201_CREATED)
async def create_decision_drafts(
    drafts: list[DecisionDraftCreate],
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> list[DecisionResponse]:
    """AI proposal draft를 pending LLMDecision으로 저장한다.

    이 엔드포인트는 주문을 만들지 않는다. 승인도 하지 않는다. 외부 AI proposal
    layer가 만든 검토 후보를 기존 `/decisions` 승인 플로우에 올리는 역할만 한다.
    """
    if not drafts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="drafts must not be empty",
        )

    rows: list[LLMDecision] = []
    for draft in drafts:
        decision = LLMDecision(
            date=draft.date,
            decision_type=draft.decision_type,
            context_source=draft.context_source,
            content=draft.content,
            confidence=draft.confidence,
            status="pending",
            raw_response=draft.raw_response,
        )
        db.add(decision)
        rows.append(decision)

    await db.flush()
    for row in rows:
        await db.refresh(row)
    return [DecisionResponse.model_validate(row) for row in rows]


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
