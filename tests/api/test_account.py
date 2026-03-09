"""계좌 잔고 API 테스트."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from src.broker.schemas import AccountBalance, Holding
from src.models.broker import BrokerCredential
from src.models.user import User


@pytest.fixture
def _mock_kiwoom_client() -> AsyncMock:
    """_create_kiwoom_client를 패치한 KiwoomClient 모킹."""
    mock_client = AsyncMock()
    mock_client.get_balance.return_value = AccountBalance(
        total_eval=10000000,
        total_profit=500000,
        total_profit_pct=5.26,
        available_cash=5000000,
        holdings=[
            Holding(
                symbol="005930",
                name="삼성전자",
                quantity=10,
                avg_price=65000,
                current_price=70000,
                eval_amount=700000,
                profit=50000,
                profit_pct=7.69,
            )
        ],
    )
    mock_client.close.return_value = None
    return mock_client


class TestGetBalance:
    """잔고 조회 테스트."""

    async def test_get_balance(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
    ) -> None:
        """인증된 사용자가 잔고를 조회하면 200 응답."""
        with patch(
            "src.api.v1.account._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            resp = await auth_client.get("/api/v1/account/balance")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_eval"] == 10000000
        assert data["available_cash"] == 5000000
        assert data["total_profit"] == 500000
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "005930"
        assert data["holdings"][0]["name"] == "삼성전자"

    async def test_get_balance_no_credential(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        """자격증명 없으면 404."""
        resp = await auth_client.get("/api/v1/account/balance")
        assert resp.status_code == 404
        assert resp.json()["error"] == "NOT_FOUND"


class TestAccountUnauthenticated:
    """미인증 계좌 API 테스트."""

    async def test_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 잔고 조회 → 401."""
        resp = await client.get("/api/v1/account/balance")
        assert resp.status_code == 401
