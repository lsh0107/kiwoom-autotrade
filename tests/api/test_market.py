"""시세 조회 API 테스트."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from src.api.v1.market import _get_kiwoom_client
from src.broker.schemas import Quote
from src.models.user import User


@pytest.fixture
def _mock_kiwoom(app: FastAPI) -> None:
    """KiwoomClient 의존성을 모킹한다."""
    mock_client = AsyncMock()
    mock_client.get_quote.return_value = Quote(
        symbol="005930",
        name="삼성전자",
        price=70000,
        change=1000,
        change_pct=1.45,
        volume=10000000,
        high=71000,
        low=69000,
        open=69500,
        prev_close=69000,
    )
    mock_client.close.return_value = None

    app.dependency_overrides[_get_kiwoom_client] = lambda: mock_client


@pytest.mark.usefixtures("_mock_kiwoom")
class TestGetQuote:
    """시세 조회 테스트."""

    async def test_get_quote(self, auth_client: AsyncClient, test_user: User) -> None:
        """인증된 사용자가 시세를 조회하면 200 응답."""
        resp = await auth_client.get("/api/v1/market/quote/005930")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "005930"
        assert data["name"] == "삼성전자"
        assert data["price"] == 70000
        assert data["change"] == 1000
        assert data["volume"] == 10000000


class TestMarketUnauthenticated:
    """미인증 시세 조회 테스트."""

    async def test_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 시세 조회 → 401."""
        resp = await client.get("/api/v1/market/quote/005930")
        assert resp.status_code == 401
