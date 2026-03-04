"""계좌 잔고 API 테스트."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from src.api.v1.account import _get_kiwoom_client
from src.broker.schemas import AccountBalance, Holding
from src.models.user import User


@pytest.fixture
def _mock_kiwoom(app: FastAPI) -> None:
    """KiwoomClient 의존성을 모킹한다."""
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

    app.dependency_overrides[_get_kiwoom_client] = lambda: mock_client


@pytest.mark.usefixtures("_mock_kiwoom")
class TestGetBalance:
    """잔고 조회 테스트."""

    async def test_get_balance(self, auth_client: AsyncClient, test_user: User) -> None:
        """인증된 사용자가 잔고를 조회하면 200 응답."""
        resp = await auth_client.get("/api/v1/account/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_eval"] == 10000000
        assert data["available_cash"] == 5000000
        assert data["total_profit"] == 500000
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "005930"
        assert data["holdings"][0]["name"] == "삼성전자"


class TestAccountUnauthenticated:
    """미인증 계좌 API 테스트."""

    async def test_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 잔고 조회 → 401."""
        resp = await client.get("/api/v1/account/balance")
        assert resp.status_code == 401
