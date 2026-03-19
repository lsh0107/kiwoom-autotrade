"""전략 파라미터 설정 + 제안 관리 라우터."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import AdminUser, CurrentUser, DBSession
from src.models.strategy_config import StrategyConfig, StrategyConfigSuggestion
from src.utils.time import now_kst

router = APIRouter(prefix="/settings", tags=["전략 설정"])


# ── Pydantic 스키마 ──────────────────────────────────────


class StrategyConfigItem(BaseModel):
    """단일 전략 파라미터 항목."""

    key: str
    value: object = Field(description="파라미터 값 (숫자/문자열/리스트)")
    description: str = ""
    updated_by: str = "user"


class StrategyConfigResponse(BaseModel):
    """전략 파라미터 응답."""

    id: uuid.UUID
    key: str
    value: object
    description: str
    updated_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StrategyConfigUpdateRequest(BaseModel):
    """전략 파라미터 수정 요청 (배열)."""

    items: list[StrategyConfigItem] = Field(min_length=1, description="수정할 파라미터 목록")


class SuggestionResponse(BaseModel):
    """전략 파라미터 제안 응답."""

    id: uuid.UUID
    config_key: str
    current_value: object
    suggested_value: object
    reason: str
    source: str
    status: str
    reviewed_at: datetime | None
    reviewed_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewRequest(BaseModel):
    """제안 검토 요청."""

    reviewed_by: str = Field(default="user", description="검토자 식별자")


# ── 헬퍼 ─────────────────────────────────────────────────


async def _get_suggestion_or_404(
    db: AsyncSession,
    suggestion_id: uuid.UUID,
) -> StrategyConfigSuggestion:
    """제안을 조회하고 없으면 404."""
    result = await db.execute(
        select(StrategyConfigSuggestion).where(StrategyConfigSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="제안을 찾을 수 없습니다",
        )
    return suggestion


# ── 엔드포인트 ────────────────────────────────────────────


@router.get(
    "/strategy",
    response_model=list[StrategyConfigResponse],
)
async def get_strategy_config(
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> list[StrategyConfigResponse]:
    """전체 전략 파라미터를 조회한다."""
    result = await db.execute(select(StrategyConfig).order_by(StrategyConfig.key))
    configs = result.scalars().all()
    return [StrategyConfigResponse.model_validate(c) for c in configs]


@router.put(
    "/strategy",
    response_model=list[StrategyConfigResponse],
)
async def update_strategy_config(
    body: StrategyConfigUpdateRequest,
    db: DBSession,
    current_user: AdminUser,  # noqa: ARG001 — AdminUser 의존성이 관리자 권한 검증
) -> list[StrategyConfigResponse]:
    """전략 파라미터를 수정한다 (관리자 전용).

    존재하는 key는 value/description/updated_by 업데이트.
    존재하지 않는 key는 새로 생성.
    """
    updated: list[StrategyConfig] = []

    for item in body.items:
        result = await db.execute(select(StrategyConfig).where(StrategyConfig.key == item.key))
        config = result.scalar_one_or_none()

        if config is None:
            config = StrategyConfig(
                key=item.key,
                value=item.value,
                description=item.description,
                updated_by=item.updated_by,
            )
            db.add(config)
        else:
            config.value = item.value
            if item.description:
                config.description = item.description
            config.updated_by = item.updated_by

        updated.append(config)

    await db.flush()
    for c in updated:
        await db.refresh(c)

    return [StrategyConfigResponse.model_validate(c) for c in updated]


@router.get(
    "/strategy/suggestions",
    response_model=list[SuggestionResponse],
)
async def list_pending_suggestions(
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> list[SuggestionResponse]:
    """미승인(pending) 전략 파라미터 제안 목록을 조회한다."""
    result = await db.execute(
        select(StrategyConfigSuggestion)
        .where(StrategyConfigSuggestion.status == "pending")
        .order_by(StrategyConfigSuggestion.created_at.desc())
    )
    suggestions = result.scalars().all()
    return [SuggestionResponse.model_validate(s) for s in suggestions]


@router.post(
    "/strategy/suggestions/{suggestion_id}/approve",
    response_model=SuggestionResponse,
)
async def approve_suggestion(
    suggestion_id: uuid.UUID,
    body: ReviewRequest,
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> SuggestionResponse:
    """제안을 승인하고 strategy_config를 업데이트한다."""
    suggestion = await _get_suggestion_or_404(db, suggestion_id)

    if suggestion.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 처리된 제안입니다 (현재 상태: {suggestion.status})",
        )

    # strategy_config 업데이트
    result = await db.execute(
        select(StrategyConfig).where(StrategyConfig.key == suggestion.config_key)
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = StrategyConfig(
            key=suggestion.config_key,
            value=suggestion.suggested_value,
            description="",
            updated_by="llm",
        )
        db.add(config)
    else:
        config.value = suggestion.suggested_value
        config.updated_by = "llm"

    # 제안 상태 갱신
    suggestion.status = "approved"
    suggestion.reviewed_at = now_kst()
    suggestion.reviewed_by = body.reviewed_by

    await db.flush()
    await db.refresh(suggestion)
    return SuggestionResponse.model_validate(suggestion)


@router.post(
    "/strategy/suggestions/{suggestion_id}/reject",
    response_model=SuggestionResponse,
)
async def reject_suggestion(
    suggestion_id: uuid.UUID,
    body: ReviewRequest,
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> SuggestionResponse:
    """제안을 거부한다."""
    suggestion = await _get_suggestion_or_404(db, suggestion_id)

    if suggestion.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 처리된 제안입니다 (현재 상태: {suggestion.status})",
        )

    suggestion.status = "rejected"
    suggestion.reviewed_at = now_kst()
    suggestion.reviewed_by = body.reviewed_by

    await db.flush()
    await db.refresh(suggestion)
    return SuggestionResponse.model_validate(suggestion)
