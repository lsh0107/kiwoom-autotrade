"""JWT 토큰 생성/검증 + httpOnly cookie 헬퍼."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Response
from jose import JWTError, jwt

from src.config.settings import get_settings
from src.utils.exceptions import InvalidTokenError, TokenExpiredError


def create_access_token(user_id: uuid.UUID) -> str:
    """액세스 토큰 생성 (sub=user_id, exp=30분)."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """리프레시 토큰 생성 (sub=user_id, exp=7일, type=refresh)."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """토큰 디코딩 및 검증. 만료/무효 시 예외 발생."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        error_msg = str(e).lower()
        if "expired" in error_msg:
            raise TokenExpiredError from e
        raise InvalidTokenError from e

    if "sub" not in payload or "type" not in payload:
        raise InvalidTokenError

    return payload


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """응답에 httpOnly 인증 쿠키를 설정한다."""
    settings = get_settings()
    is_secure = not settings.debug

    # access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    # refresh token cookie (경로 제한)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth/refresh",
    )


def clear_auth_cookies(response: Response) -> None:
    """인증 쿠키를 삭제한다."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth/refresh")
