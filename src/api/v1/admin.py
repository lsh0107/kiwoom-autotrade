"""관리자 라우터 (초대 코드 관리)."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.deps import AdminUser, DBSession
from src.models.user import Invite

router = APIRouter(prefix="/admin", tags=["관리자"])


# ── Pydantic 스키마 ──────────────────────────────


class CreateInviteRequest(BaseModel):
    """초대 코드 생성 요청."""

    expires_hours: int = Field(default=72, ge=1, le=720)


class InviteResponse(BaseModel):
    """초대 코드 응답."""

    id: uuid.UUID
    code: str
    created_by: uuid.UUID
    is_used: bool
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteListResponse(BaseModel):
    """초대 코드 목록 응답."""

    invites: list[InviteResponse]
    total: int


# ── 엔드포인트 ───────────────────────────────────


@router.post("/invites", response_model=InviteResponse, status_code=201)
async def create_invite(
    body: CreateInviteRequest,
    db: DBSession,
    admin: AdminUser,
) -> Invite:
    """초대 코드를 생성한다 (admin 전용)."""
    invite = Invite(
        code=secrets.token_urlsafe(16),
        created_by=admin.id,
        expires_at=datetime.now(UTC) + timedelta(hours=body.expires_hours),
    )
    db.add(invite)
    await db.flush()
    return invite


@router.get("/invites", response_model=InviteListResponse)
async def list_invites(
    db: DBSession,
    _admin: AdminUser,
) -> dict:
    """초대 코드 목록을 조회한다 (admin 전용)."""
    result = await db.execute(select(Invite).order_by(Invite.created_at.desc()))
    invites = list(result.scalars().all())
    return {"invites": invites, "total": len(invites)}
