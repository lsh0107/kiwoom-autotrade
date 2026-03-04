"""FastAPI 공통 의존성."""

import uuid
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db
from src.models.user import User, UserRole
from src.utils.exceptions import (
    InsufficientPermissionError,
    InvalidTokenError,
)
from src.utils.jwt import decode_token

# DB 세션 의존성 re-export
DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DBSession,
    access_token: str | None = Cookie(default=None),
) -> User:
    """JWT 쿠키에서 현재 사용자를 추출한다.

    access_token httpOnly 쿠키를 읽어 디코딩 후 DB에서 사용자를 조회한다.
    토큰 없음, 유효하지 않음, 사용자 없음, 비활성 시 예외 발생.
    """
    if access_token is None:
        raise InvalidTokenError

    payload = decode_token(access_token)

    if payload.get("type") != "access":
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
        raise InvalidTokenError

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_admin_user(
    current_user: CurrentUser,
) -> User:
    """관리자 권한을 확인한다.

    현재 사용자가 admin role이 아니면 InsufficientPermissionError 발생.
    """
    if current_user.role != UserRole.ADMIN:
        raise InsufficientPermissionError
    return current_user


AdminUser = Annotated[User, Depends(get_admin_user)]
