"""관리자 API 테스트."""

from httpx import AsyncClient

from src.models.user import User


class TestCreateInvite:
    """초대 코드 생성 테스트."""

    async def test_create_invite_as_admin(
        self, admin_client: AsyncClient, admin_user: User
    ) -> None:
        """관리자가 초대 코드를 생성하면 201 응답."""
        resp = await admin_client.post(
            "/api/v1/admin/invites",
            json={"expires_hours": 48},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "code" in data
        assert data["is_used"] is False
        assert data["created_by"] == str(admin_user.id)

    async def test_create_invite_as_user(self, auth_client: AsyncClient, test_user: User) -> None:
        """일반 사용자가 초대 코드 생성 시 403."""
        resp = await auth_client.post(
            "/api/v1/admin/invites",
            json={"expires_hours": 48},
        )
        assert resp.status_code == 403


class TestListInvites:
    """초대 코드 목록 테스트."""

    async def test_list_invites(self, admin_client: AsyncClient, admin_user: User) -> None:
        """관리자가 초대 목록을 조회하면 빈 목록 반환."""
        resp = await admin_client.get("/api/v1/admin/invites")
        assert resp.status_code == 200
        data = resp.json()
        assert "invites" in data
        assert "total" in data
        assert data["total"] == 0

    async def test_list_invites_after_create(
        self, admin_client: AsyncClient, admin_user: User
    ) -> None:
        """초대 코드 생성 후 목록에 포함 확인."""
        # 초대 코드 생성
        await admin_client.post(
            "/api/v1/admin/invites",
            json={"expires_hours": 24},
        )
        # 목록 조회
        resp = await admin_client.get("/api/v1/admin/invites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["invites"]) == 1


class TestAdminUnauthenticated:
    """미인증 관리자 API 테스트."""

    async def test_unauthenticated_create(self, client: AsyncClient) -> None:
        """미인증 시 초대 코드 생성 401."""
        resp = await client.post(
            "/api/v1/admin/invites",
            json={"expires_hours": 48},
        )
        assert resp.status_code == 401

    async def test_unauthenticated_list(self, client: AsyncClient) -> None:
        """미인증 시 초대 목록 조회 401."""
        resp = await client.get("/api/v1/admin/invites")
        assert resp.status_code == 401
