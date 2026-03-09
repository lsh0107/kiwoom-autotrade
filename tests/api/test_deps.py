"""FastAPI 공통 의존성 테스트."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_admin_user, get_broker_credential, get_current_user
from src.models.broker import BrokerCredential
from src.models.user import User, UserRole
from src.utils.crypto import encrypt
from src.utils.exceptions import InsufficientPermissionError, InvalidTokenError, NotFoundError
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


class TestGetBrokerCredential:
    """get_broker_credential 함수 테스트."""

    async def test_get_broker_credential_found(self, db: AsyncSession, test_user: User) -> None:
        """활성 자격증명 존재 → 자격증명 반환."""
        cred = BrokerCredential(
            user_id=test_user.id,
            broker_name="kiwoom",
            encrypted_app_key=encrypt("test_key"),
            encrypted_app_secret=encrypt("test_secret"),
            account_no="1234567890",
            is_mock=True,
            is_active=True,
        )
        db.add(cred)
        await db.commit()

        result = await get_broker_credential(db=db, current_user=test_user)
        assert result.user_id == test_user.id
        assert result.is_active is True

    async def test_get_broker_credential_not_found(self, db: AsyncSession, test_user: User) -> None:
        """활성 자격증명 없음 → NotFoundError."""
        with pytest.raises(NotFoundError):
            await get_broker_credential(db=db, current_user=test_user)

    async def test_get_broker_credential_inactive_ignored(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """비활성 자격증명만 존재 → HTTPException 404."""
        cred = BrokerCredential(
            user_id=test_user.id,
            broker_name="kiwoom",
            encrypted_app_key=encrypt("test_key"),
            encrypted_app_secret=encrypt("test_secret"),
            account_no="1234567890",
            is_mock=True,
            is_active=False,
        )
        db.add(cred)
        await db.commit()

        with pytest.raises(NotFoundError):
            await get_broker_credential(db=db, current_user=test_user)

    async def test_get_broker_credential_multiple_active_returns_latest(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """활성 자격증명이 여러 개일 때 → 가장 최근 반환 (MultipleResultsFound 없음)."""
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import update

        cred1 = BrokerCredential(
            user_id=test_user.id,
            broker_name="kiwoom",
            encrypted_app_key=encrypt("old_key"),
            encrypted_app_secret=encrypt("old_secret"),
            account_no="0000000001",
            is_mock=True,
            is_active=True,
        )
        cred2 = BrokerCredential(
            user_id=test_user.id,
            broker_name="kiwoom",
            encrypted_app_key=encrypt("new_key"),
            encrypted_app_secret=encrypt("new_secret"),
            account_no="9999999999",
            is_mock=True,
            is_active=True,
        )
        db.add(cred1)
        db.add(cred2)
        await db.flush()
        await db.refresh(cred1)
        await db.refresh(cred2)

        # cred2가 최신이 되도록 timestamps를 명시적으로 설정
        old_time = datetime.now(UTC) - timedelta(hours=1)
        new_time = datetime.now(UTC)
        await db.execute(
            update(BrokerCredential)
            .where(BrokerCredential.id == cred1.id)
            .values(created_at=old_time)
        )
        await db.execute(
            update(BrokerCredential)
            .where(BrokerCredential.id == cred2.id)
            .values(created_at=new_time)
        )
        await db.commit()

        result = await get_broker_credential(db=db, current_user=test_user)
        assert result.account_no == cred2.account_no
