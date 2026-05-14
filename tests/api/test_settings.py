"""브로커 자격증명 설정 API 테스트."""

from unittest.mock import MagicMock, patch

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
        """자격증명 수정 (is_mock 유지) → 200."""
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

        # 수정 (is_mock 변경 없이 account_no만)
        resp = await auth_client.put(
            f"/api/v1/settings/broker/{cred_id}",
            json={
                "account_no": "33334444",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_no"] == "33334444"
        assert data["is_mock"] is True


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


def _mock_settings(
    allow_real_trading: bool = False,
    real_trading_confirm_phrase: str = "",
) -> MagicMock:
    """실거래 게이트 테스트용 Settings mock 생성."""
    s = MagicMock()
    s.allow_real_trading = allow_real_trading
    s.real_trading_confirm_phrase = real_trading_confirm_phrase
    return s


class TestRealTradingGateCreate:
    """POST /broker 실거래 전환 게이트 테스트."""

    async def test_is_mock_false_default_env_blocked(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """allow_real_trading=False (기본) → is_mock=False 시 403."""

        with patch(
            "src.config.settings.get_settings",
            return_value=_mock_settings(allow_real_trading=False),
        ):
            resp = await auth_client.post(
                "/api/v1/settings/broker",
                json={
                    "app_key": "key-12345678",
                    "app_secret": "secret-12345678",
                    "account_no": "12345678",
                    "is_mock": False,
                },
            )
        assert resp.status_code == 403

    async def test_allow_true_phrase_empty_blocked(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """allow=True, phrase 빈 문자열 → 403."""

        with patch(
            "src.config.settings.get_settings",
            return_value=_mock_settings(allow_real_trading=True, real_trading_confirm_phrase=""),
        ):
            resp = await auth_client.post(
                "/api/v1/settings/broker",
                json={
                    "app_key": "key-12345678",
                    "app_secret": "secret-12345678",
                    "account_no": "12345678",
                    "is_mock": False,
                },
            )
        assert resp.status_code == 403

    async def test_allow_true_phrase_mismatch_blocked(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """allow=True, phrase 불일치 → 403."""

        with patch(
            "src.config.settings.get_settings",
            return_value=_mock_settings(
                allow_real_trading=True, real_trading_confirm_phrase="real-secret"
            ),
        ):
            resp = await auth_client.post(
                "/api/v1/settings/broker",
                json={
                    "app_key": "key-12345678",
                    "app_secret": "secret-12345678",
                    "account_no": "12345678",
                    "is_mock": False,
                    "real_trading_confirm": "wrong-phrase",
                },
            )
        assert resp.status_code == 403

    async def test_allow_true_phrase_match_passes(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """allow=True + phrase 일치 → 201, DB에 is_mock=False."""

        with patch(
            "src.config.settings.get_settings",
            return_value=_mock_settings(
                allow_real_trading=True, real_trading_confirm_phrase="i-confirm-real"
            ),
        ):
            resp = await auth_client.post(
                "/api/v1/settings/broker",
                json={
                    "app_key": "key-12345678",
                    "app_secret": "secret-12345678",
                    "account_no": "12345678",
                    "is_mock": False,
                    "real_trading_confirm": "i-confirm-real",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_mock"] is False

    async def test_is_mock_true_always_passes(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """is_mock=True → 게이트 무관 201 (회귀)."""
        resp = await auth_client.post(
            "/api/v1/settings/broker",
            json={
                "app_key": "key-12345678",
                "app_secret": "secret-12345678",
                "account_no": "12345678",
                "is_mock": True,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["is_mock"] is True


class TestRealTradingGateUpdate:
    """PUT /broker/{id} 실거래 전환 게이트 테스트."""

    async def _create_mock_credential(self, auth_client: AsyncClient) -> str:
        """모의투자 자격증명 생성 후 ID 반환."""
        resp = await auth_client.post(
            "/api/v1/settings/broker",
            json={
                "app_key": "key-12345678",
                "app_secret": "secret-12345678",
                "account_no": "12345678",
                "is_mock": True,
            },
        )
        return resp.json()["id"]

    async def test_update_is_mock_false_default_env_blocked(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """PUT is_mock=False, allow=False → 403."""

        cred_id = await self._create_mock_credential(auth_client)
        with patch(
            "src.config.settings.get_settings",
            return_value=_mock_settings(allow_real_trading=False),
        ):
            resp = await auth_client.put(
                f"/api/v1/settings/broker/{cred_id}",
                json={"is_mock": False},
            )
        assert resp.status_code == 403

    async def test_update_is_mock_false_phrase_match_passes(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """PUT is_mock=False, allow=True + phrase 일치 → 200."""

        cred_id = await self._create_mock_credential(auth_client)
        with patch(
            "src.config.settings.get_settings",
            return_value=_mock_settings(
                allow_real_trading=True, real_trading_confirm_phrase="confirm-real"
            ),
        ):
            resp = await auth_client.put(
                f"/api/v1/settings/broker/{cred_id}",
                json={"is_mock": False, "real_trading_confirm": "confirm-real"},
            )
        assert resp.status_code == 200
        assert resp.json()["is_mock"] is False

    async def test_update_is_mock_none_no_gate(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """PUT is_mock 미전송 → 게이트 무관 200 (회귀)."""
        cred_id = await self._create_mock_credential(auth_client)
        resp = await auth_client.put(
            f"/api/v1/settings/broker/{cred_id}",
            json={"account_no": "99998888"},
        )
        assert resp.status_code == 200
        assert resp.json()["account_no"] == "99998888"

    async def test_response_does_not_leak_confirm_phrase(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """응답 JSON에 confirm phrase 가 노출되지 않는다."""

        cred_id = await self._create_mock_credential(auth_client)
        with patch(
            "src.config.settings.get_settings",
            return_value=_mock_settings(
                allow_real_trading=True, real_trading_confirm_phrase="secret-phrase"
            ),
        ):
            resp = await auth_client.put(
                f"/api/v1/settings/broker/{cred_id}",
                json={"is_mock": False, "real_trading_confirm": "secret-phrase"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "real_trading_confirm" not in data
        assert "confirm_phrase" not in data
        assert "secret-phrase" not in str(data)
