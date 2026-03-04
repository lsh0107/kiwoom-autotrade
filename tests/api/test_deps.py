"""FastAPI 공통 의존성 테스트."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_admin_user, get_current_user
from src.models.user import User, UserRole
from src.utils.exceptions import InsufficientPermissionError, InvalidTokenError
from src.utils.jwt import create_access_token


class TestGetCurrentUser:
    """get_current_user 함수 테스트."""

    async def test_get_current_user_valid(self, db: AsyncSession, test_user: User) -> None:
        """유효한 토큰 → 사용자 반환."""
        token = create_access_token(test_user.id)
        user = await get_current_user(db=db, access_token=token)

        assert user.id == test_user.id
        assert user.email == "test@example.com"

    async def test_get_current_user_no_token(self, db: AsyncSession) -> None:
        """토큰 없음 → InvalidTokenError."""
        with pytest.raises(InvalidTokenError):
            await get_current_user(db=db, access_token=None)

    async def test_get_current_user_invalid_token(self, db: AsyncSession) -> None:
        """잘못된 토큰 → InvalidTokenError."""
        with pytest.raises(InvalidTokenError):
            await get_current_user(db=db, access_token="invalid.token.here")

    async def test_get_current_user_refresh_token(self, db: AsyncSession, test_user: User) -> None:
        """리프레시 토큰(type=refresh) → InvalidTokenError."""
        from src.utils.jwt import create_refresh_token

        token = create_refresh_token(test_user.id)
        with pytest.raises(InvalidTokenError):
            await get_current_user(db=db, access_token=token)

    async def test_get_current_user_nonexistent_user(self, db: AsyncSession) -> None:
        """존재하지 않는 사용자 ID → InvalidTokenError."""
        fake_id = uuid.uuid4()
        token = create_access_token(fake_id)
        with pytest.raises(InvalidTokenError):
            await get_current_user(db=db, access_token=token)

    async def test_get_current_user_inactive(self, db: AsyncSession, test_user: User) -> None:
        """비활성 사용자 → InvalidTokenError."""
        test_user.is_active = False
        await db.commit()

        token = create_access_token(test_user.id)
        with pytest.raises(InvalidTokenError):
            await get_current_user(db=db, access_token=token)


class TestGetAdminUser:
    """get_admin_user 함수 테스트."""

    async def test_get_admin_user(self, admin_user: User) -> None:
        """관리자 사용자 → 사용자 반환."""
        result = await get_admin_user(current_user=admin_user)
        assert result.id == admin_user.id
        assert result.role == UserRole.ADMIN

    async def test_get_admin_user_non_admin(self, test_user: User) -> None:
        """일반 사용자 → InsufficientPermissionError."""
        with pytest.raises(InsufficientPermissionError):
            await get_admin_user(current_user=test_user)
