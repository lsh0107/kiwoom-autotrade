"""인증 라우터 (회원가입, 로그인, 로그아웃, 토큰 갱신)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from src.api.deps import CurrentUser, DBSession
from src.models.user import Invite, User, UserRole
from src.utils.exceptions import (
    AuthError,
    DuplicateError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
)
from src.utils.jwt import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_auth_cookies,
)
from src.utils.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["인증"])


# ── Pydantic 스키마 ──────────────────────────────


class RegisterRequest(BaseModel):
    """회원가입 요청."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=2, max_length=50)
    invite_code: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    """로그인 요청."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """사용자 응답."""

    id: uuid.UUID
    email: str
    nickname: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """메시지 응답."""

    message: str


# ── 엔드포인트 ───────────────────────────────────


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: DBSession,
) -> User:
    """회원가입.

    첫 번째 사용자는 초대 코드 없이 자동 admin으로 가입.
    이후 사용자는 유효한 초대 코드가 필요.
    """
    # 이메일 중복 체크
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise DuplicateError("이메일")

    # 첫 번째 사용자 여부 확인
    user_count_result = await db.execute(select(func.count()).select_from(User))
    user_count = user_count_result.scalar_one()
    is_first_user = user_count == 0

    if is_first_user:
        # 첫 번째 사용자: 초대 코드 불필요, 자동 admin
        role = UserRole.ADMIN
    else:
        # 이후 사용자: 초대 코드 필수
        if not body.invite_code:
            raise AuthError("초대 코드가 필요합니다", "INVITE_REQUIRED")

        invite_result = await db.execute(select(Invite).where(Invite.code == body.invite_code))
        invite = invite_result.scalar_one_or_none()

        if invite is None:
            raise NotFoundError("초대 코드")

        if invite.is_used:
            raise AuthError("이미 사용된 초대 코드입니다", "INVITE_USED")

        if invite.expires_at < datetime.now(UTC):
            raise AuthError("만료된 초대 코드입니다", "INVITE_EXPIRED")

        role = UserRole.USER

    # 사용자 생성
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        nickname=body.nickname,
        role=role,
    )
    db.add(user)
    await db.flush()

    # 초대 코드 사용 처리 (첫 번째 사용자가 아닌 경우)
    if not is_first_user and body.invite_code:
        invite_result = await db.execute(select(Invite).where(Invite.code == body.invite_code))
        invite = invite_result.scalar_one_or_none()
        if invite is not None:
            invite.is_used = True
            invite.used_by = user.id
            invite.used_at = datetime.now(UTC)

    return user


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    db: DBSession,
    response: Response,
) -> User:
    """로그인. 성공 시 access_token + refresh_token을 httpOnly 쿠키로 설정."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidCredentialsError

    if not verify_password(body.password, user.hashed_password):
        raise InvalidCredentialsError

    if not user.is_active:
        raise AuthError("비활성화된 계정입니다", "ACCOUNT_DISABLED")

    # JWT 토큰 생성 + 쿠키 설정
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, refresh_token)

    return user


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
) -> dict[str, str]:
    """로그아웃. 인증 쿠키를 삭제한다."""
    clear_auth_cookies(response)
    return {"message": "로그아웃 되었습니다"}


@router.post("/refresh", response_model=UserResponse)
async def refresh(
    db: DBSession,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
) -> User:
    """리프레시 토큰으로 새 액세스 토큰을 발급한다."""
    if refresh_token is None:
        raise InvalidTokenError

    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise InvalidTokenError

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as e:
        raise InvalidTokenError from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidTokenError

    if not user.is_active:
        raise AuthError("비활성화된 계정입니다", "ACCOUNT_DISABLED")

    # 새 토큰 발급
    new_access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)
    set_auth_cookies(response, new_access_token, new_refresh_token)

    return user


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: CurrentUser,
) -> User:
    """현재 로그인한 사용자 정보를 반환한다."""
    return current_user
