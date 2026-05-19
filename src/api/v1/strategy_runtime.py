"""전략 런타임 토글 + budget API (design-025 3/N).

GET  /api/v1/strategy/runtime           — 전체 전략 토글 상태 조회
PATCH /api/v1/strategy/runtime/{strategy} — 단일 전략 enabled/budget_pct/max_* 갱신

변경 시 strategy_runtime.budget_pct 합이 1.0 초과 불가 (검증).
admin 권한 필요.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.deps import AdminUser, DBSession
from src.models.strategy_runtime import StrategyRuntime
from src.utils.time import now_kst

router = APIRouter(prefix="/strategy/runtime", tags=["전략 런타임"])


# ── Pydantic 스키마 ──────────────────────────────────────


class StrategyRuntimeView(BaseModel):
    """단일 전략 런타임 상태."""

    id: uuid.UUID
    strategy: str
    enabled: bool
    budget_pct: float
    max_order_amount: int
    max_daily_orders: int
    updated_at: datetime
    updated_by: str | None

    model_config = {"from_attributes": True}


class StrategyRuntimePatchRequest(BaseModel):
    """전략 런타임 patch 요청."""

    enabled: bool | None = Field(default=None)
    budget_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    max_order_amount: int | None = Field(default=None, ge=0)
    max_daily_orders: int | None = Field(default=None, ge=0)


# ── 헬퍼 ────────────────────────────────────────────────


def _to_view(row: StrategyRuntime) -> StrategyRuntimeView:
    return StrategyRuntimeView(
        id=row.id,
        strategy=row.strategy,
        enabled=row.enabled,
        budget_pct=float(row.budget_pct),
        max_order_amount=row.max_order_amount,
        max_daily_orders=row.max_daily_orders,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


async def _validate_total_budget(
    db, strategy: str, *, new_enabled: bool | None, new_budget_pct: float | None
) -> None:
    """변경 후 enabled 전략들의 budget_pct 합이 1.0 초과인지 검증."""
    result = await db.execute(select(StrategyRuntime))
    rows = list(result.scalars().all())
    total = Decimal("0")
    for row in rows:
        enabled = row.enabled
        budget = float(row.budget_pct)
        if row.strategy == strategy:
            if new_enabled is not None:
                enabled = new_enabled
            if new_budget_pct is not None:
                budget = new_budget_pct
        if enabled:
            total += Decimal(str(budget))
    if total > Decimal("1.0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"enabled 전략의 budget_pct 합이 1.0 초과 ({total}). 다른 전략 비율을 줄여야 함."
            ),
        )


# ── 라우트 ──────────────────────────────────────────────


@router.get("", response_model=list[StrategyRuntimeView])
async def list_strategy_runtime(
    db: DBSession,
    _user: AdminUser,
) -> list[StrategyRuntimeView]:
    """모든 전략 런타임 상태 조회."""
    result = await db.execute(select(StrategyRuntime).order_by(StrategyRuntime.strategy))
    rows = list(result.scalars().all())
    return [_to_view(row) for row in rows]


@router.patch("/{strategy}", response_model=StrategyRuntimeView)
async def patch_strategy_runtime(
    strategy: str,
    payload: StrategyRuntimePatchRequest,
    db: DBSession,
    user: AdminUser,
) -> StrategyRuntimeView:
    """단일 전략 런타임 갱신.

    enabled / budget_pct / max_order_amount / max_daily_orders 중 명시된 필드만 갱신.
    enabled 전략들의 budget_pct 합이 1.0 초과 시 400.
    """
    result = await db.execute(select(StrategyRuntime).where(StrategyRuntime.strategy == strategy))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"strategy={strategy} 미존재",
        )

    # budget_pct / enabled 변경 시 합계 검증
    if payload.enabled is not None or payload.budget_pct is not None:
        await _validate_total_budget(
            db,
            strategy,
            new_enabled=payload.enabled,
            new_budget_pct=payload.budget_pct,
        )

    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.budget_pct is not None:
        row.budget_pct = Decimal(str(payload.budget_pct))
    if payload.max_order_amount is not None:
        row.max_order_amount = payload.max_order_amount
    if payload.max_daily_orders is not None:
        row.max_daily_orders = payload.max_daily_orders
    row.updated_by = user.email
    row.updated_at = now_kst()

    await db.commit()
    await db.refresh(row)
    return _to_view(row)
