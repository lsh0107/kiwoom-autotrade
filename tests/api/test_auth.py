"""인증 API 테스트."""

from httpx import AsyncClient
from src.models.user import User


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
