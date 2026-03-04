"""인증 API 테스트."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user import Invite, User
from src.utils.jwt import create_refresh_token


class TestRegister:
    """회원가입 테스트."""

    async def test_first_user_auto_admin(self, client: AsyncClient) -> None:
        """첫 번째 사용자는 자동 admin."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "first@example.com",
                "password": "password123",
                "nickname": "첫사용자",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "admin"
        assert data["email"] == "first@example.com"

    async def test_duplicate_email(self, client: AsyncClient, test_user: User) -> None:
        """이메일 중복 가입 차단."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "password123",
                "nickname": "중복",
            },
        )
        assert resp.status_code == 409

    async def test_second_user_needs_invite(self, client: AsyncClient, test_user: User) -> None:
        """두 번째 사용자는 초대 코드 필요."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "second@example.com",
                "password": "password123",
                "nickname": "두번째",
            },
        )
        assert resp.status_code == 401


class TestLogin:
    """로그인 테스트."""

    async def test_login_success(self, client: AsyncClient, test_user: User) -> None:
        """로그인 성공 → 쿠키 설정."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "testpassword123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.cookies

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User) -> None:
        """비밀번호 틀림."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        """존재하지 않는 이메일로 로그인 시 401."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )
        assert resp.status_code == 401


class TestLogout:
    """로그아웃 테스트."""

    async def test_logout(self, client: AsyncClient) -> None:
        """로그아웃 시 200 응답 및 쿠키 삭제."""
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "로그아웃 되었습니다"
        # 쿠키 삭제 확인 (max-age=0 또는 삭제 지시)
        set_cookie_headers = resp.headers.get_list("set-cookie")
        assert any("access_token" in h for h in set_cookie_headers)


class TestRefresh:
    """토큰 갱신 테스트."""

    async def test_refresh_token(self, client: AsyncClient, test_user: User) -> None:
        """유효한 refresh_token으로 새 토큰 발급."""
        refresh_token = create_refresh_token(test_user.id)
        client.cookies.set("refresh_token", refresh_token)
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == test_user.email
        # 새 쿠키 설정 확인
        set_cookie_headers = resp.headers.get_list("set-cookie")
        assert any("access_token" in h for h in set_cookie_headers)


class TestRegisterWithInvite:
    """초대 코드 기반 회원가입 테스트."""

    async def test_register_with_valid_invite(
        self, client: AsyncClient, test_user: User, db: AsyncSession
    ) -> None:
        """유효한 초대 코드로 회원가입 성공."""
        invite = Invite(
            code="valid-invite-code-123",
            created_by=test_user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=72),
        )
        db.add(invite)
        await db.flush()

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "invited@example.com",
                "password": "password123",
                "nickname": "초대받은사용자",
                "invite_code": "valid-invite-code-123",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "invited@example.com"
        assert data["role"] == "user"

    async def test_register_with_expired_invite(
        self, client: AsyncClient, test_user: User, db: AsyncSession
    ) -> None:
        """만료된 초대 코드로 회원가입 실패."""
        invite = Invite(
            code="expired-invite-code",
            created_by=test_user.id,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db.add(invite)
        await db.flush()

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "expired@example.com",
                "password": "password123",
                "nickname": "만료초대",
                "invite_code": "expired-invite-code",
            },
        )
        assert resp.status_code == 401


class TestMe:
    """현재 사용자 정보 테스트."""

    async def test_me_authenticated(self, auth_client: AsyncClient, test_user: User) -> None:
        """인증된 사용자 정보 조회."""
        resp = await auth_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == test_user.email

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 401."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401
