"""브로커 자격증명 설정 API 테스트."""

from httpx import AsyncClient

from src.models.user import User


class TestCreateBrokerCredential:
    """브로커 자격증명 등록 테스트."""

    async def test_create_broker_credential(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """브로커 자격증명 등록 → 201, 마스킹된 응답."""
        resp = await auth_client.post(
            "/api/v1/settings/broker",
            json={
                "app_key": "test-app-key-12345",
                "app_secret": "test-app-secret-67890",
                "account_no": "12345678",
                "is_mock": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["broker_name"] == "kiwoom"
        assert data["account_no"] == "12345678"
        assert data["is_mock"] is True
        assert data["is_active"] is True
        # 마스킹 확인 (앞 4자리만 보임)
        assert data["app_key_masked"].startswith("test")
        assert "*" in data["app_key_masked"]


class TestListBrokerCredentials:
    """브로커 자격증명 목록 테스트."""

    async def test_list_broker_credentials_empty(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """자격증명이 없으면 빈 목록 반환."""
        resp = await auth_client.get("/api/v1/settings/broker")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    async def test_list_broker_credentials(self, auth_client: AsyncClient, test_user: User) -> None:
        """자격증명 등록 후 목록에 포함."""
        # 등록
        await auth_client.post(
            "/api/v1/settings/broker",
            json={
                "app_key": "test-key-abc",
                "app_secret": "test-secret-xyz",
                "account_no": "99887766",
                "is_mock": True,
            },
        )
        # 목록 조회
        resp = await auth_client.get("/api/v1/settings/broker")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["account_no"] == "99887766"


class TestUpdateBrokerCredential:
    """브로커 자격증명 수정 테스트."""

    async def test_update_broker_credential(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """자격증명 수정 → 200."""
        # 등록
        create_resp = await auth_client.post(
            "/api/v1/settings/broker",
            json={
                "app_key": "original-key",
                "app_secret": "original-secret",
                "account_no": "11112222",
                "is_mock": True,
            },
        )
        cred_id = create_resp.json()["id"]

        # 수정
        resp = await auth_client.put(
            f"/api/v1/settings/broker/{cred_id}",
            json={
                "account_no": "33334444",
                "is_mock": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_no"] == "33334444"
        assert data["is_mock"] is False


class TestDeleteBrokerCredential:
    """브로커 자격증명 삭제 테스트."""

    async def test_delete_broker_credential(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """자격증명 삭제 → 200, 메시지 확인."""
        # 등록
        create_resp = await auth_client.post(
            "/api/v1/settings/broker",
            json={
                "app_key": "delete-key",
                "app_secret": "delete-secret",
                "account_no": "55556666",
                "is_mock": True,
            },
        )
        cred_id = create_resp.json()["id"]

        # 삭제
        resp = await auth_client.delete(f"/api/v1/settings/broker/{cred_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "자격증명이 삭제되었습니다"

        # 삭제 후 목록에서 사라짐 확인
        list_resp = await auth_client.get("/api/v1/settings/broker")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 0


class TestSettingsUnauthenticated:
    """미인증 설정 API 테스트."""

    async def test_unauthenticated_create(self, client: AsyncClient) -> None:
        """미인증 시 자격증명 등록 → 401."""
        resp = await client.post(
            "/api/v1/settings/broker",
            json={
                "app_key": "key",
                "app_secret": "secret",
                "account_no": "12345678",
                "is_mock": True,
            },
        )
        assert resp.status_code == 401

    async def test_unauthenticated_list(self, client: AsyncClient) -> None:
        """미인증 시 자격증명 목록 조회 → 401."""
        resp = await client.get("/api/v1/settings/broker")
        assert resp.status_code == 401
