"""브로커 자격증명 관리 라우터."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DBSession
from src.models.broker import BrokerCredential
from src.utils.crypto import decrypt, encrypt, mask_value

router = APIRouter(prefix="/settings", tags=["설정"])


# ── Pydantic 스키마 ──────────────────────────────────


class BrokerCredentialCreate(BaseModel):
    """브로커 자격증명 등록 요청."""

    app_key: str = Field(min_length=1, description="키움 App Key")
    app_secret: str = Field(min_length=1, description="키움 App Secret")
    account_no: str = Field(min_length=8, max_length=20, description="계좌번호")
    is_mock: bool = Field(default=True, description="모의투자 여부")


class BrokerCredentialUpdate(BaseModel):
    """브로커 자격증명 수정 요청."""

    app_key: str | None = Field(default=None, description="키움 App Key")
    app_secret: str | None = Field(default=None, description="키움 App Secret")
    account_no: str | None = Field(default=None, description="계좌번호")
    is_mock: bool | None = Field(default=None, description="모의투자 여부")


class BrokerCredentialResponse(BaseModel):
    """브로커 자격증명 응답 (마스킹)."""

    id: uuid.UUID
    broker_name: str
    app_key_masked: str = Field(description="마스킹된 App Key")
    app_secret_masked: str = Field(description="마스킹된 App Secret")
    account_no: str
    is_mock: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """메시지 응답."""

    message: str


# ── 헬퍼 ─────────────────────────────────────────────


_DECRYPT_FALLBACK = "***복호화실패***"


def _to_response(cred: BrokerCredential) -> BrokerCredentialResponse:
    """BrokerCredential DB 모델을 마스킹된 응답으로 변환한다."""
    try:
        decrypted_key = decrypt(cred.encrypted_app_key)
        decrypted_appsec = decrypt(cred.encrypted_app_secret)
    except Exception:
        decrypted_key = _DECRYPT_FALLBACK
        decrypted_appsec = _DECRYPT_FALLBACK

    return BrokerCredentialResponse(
        id=cred.id,
        broker_name=cred.broker_name,
        app_key_masked=mask_value(decrypted_key),
        app_secret_masked=mask_value(decrypted_appsec),
        account_no=cred.account_no,
        is_mock=cred.is_mock,
        is_active=cred.is_active,
        created_at=cred.created_at,
    )


async def _get_credential_or_404(
    db: AsyncSession,
    credential_id: uuid.UUID,
    user_id: uuid.UUID,
) -> BrokerCredential:
    """ID와 소유자로 자격증명을 조회하고, 없으면 404 예외."""
    result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.id == credential_id,
            BrokerCredential.user_id == user_id,
        )
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자격증명을 찾을 수 없습니다",
        )
    return cred


# ── 엔드포인트 ───────────────────────────────────────


@router.post(
    "/broker",
    response_model=BrokerCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broker_credential(
    body: BrokerCredentialCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> BrokerCredentialResponse:
    """브로커 자격증명을 등록한다 (AES 암호화 저장). 기존 활성 자격증명은 비활성화."""
    # 기존 활성 자격증명 비활성화
    result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.user_id == current_user.id,
            BrokerCredential.is_active.is_(True),
        )
    )
    for existing in result.scalars().all():
        existing.is_active = False

    cred = BrokerCredential(
        user_id=current_user.id,
        broker_name="kiwoom",
        encrypted_app_key=encrypt(body.app_key),
        encrypted_app_secret=encrypt(body.app_secret),
        account_no=body.account_no,
        is_mock=body.is_mock,
    )
    db.add(cred)
    await db.flush()
    await db.refresh(cred)

    return _to_response(cred)


@router.get(
    "/broker",
    response_model=list[BrokerCredentialResponse],
)
async def list_broker_credentials(
    db: DBSession,
    current_user: CurrentUser,
) -> list[BrokerCredentialResponse]:
    """현재 사용자의 브로커 자격증명 목록을 조회한다 (마스킹)."""
    result = await db.execute(
        select(BrokerCredential)
        .where(BrokerCredential.user_id == current_user.id)
        .order_by(BrokerCredential.created_at.desc())
    )
    creds = result.scalars().all()
    return [_to_response(c) for c in creds]


@router.put(
    "/broker/{credential_id}",
    response_model=BrokerCredentialResponse,
)
async def update_broker_credential(
    credential_id: uuid.UUID,
    body: BrokerCredentialUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> BrokerCredentialResponse:
    """브로커 자격증명을 수정한다."""
    cred = await _get_credential_or_404(db, credential_id, current_user.id)

    if body.app_key is not None:
        cred.encrypted_app_key = encrypt(body.app_key)
    if body.app_secret is not None:
        cred.encrypted_app_secret = encrypt(body.app_secret)
    if body.account_no is not None:
        cred.account_no = body.account_no
    if body.is_mock is not None:
        cred.is_mock = body.is_mock

    await db.flush()
    await db.refresh(cred)

    return _to_response(cred)


@router.delete(
    "/broker/{credential_id}",
    response_model=MessageResponse,
)
async def delete_broker_credential(
    credential_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> dict[str, str]:
    """브로커 자격증명을 삭제한다."""
    cred = await _get_credential_or_404(db, credential_id, current_user.id)
    await db.delete(cred)
    await db.flush()

    return {"message": "자격증명이 삭제되었습니다"}
