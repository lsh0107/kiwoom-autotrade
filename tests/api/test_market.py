"""시세 조회 API 테스트."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from src.broker.schemas import Quote
from src.models.broker import BrokerCredential
from src.models.user import User


@pytest.fixture
def _mock_kiwoom_client() -> AsyncMock:
    """_create_kiwoom_client를 패치한 KiwoomClient 모킹."""
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
    return mock_client


class TestGetQuote:
    """시세 조회 테스트."""

    async def test_get_quote(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
    ) -> None:
        """인증된 사용자가 시세를 조회하면 200 응답."""
        with patch(
            "src.api.v1.market._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            resp = await auth_client.get("/api/v1/market/quote/005930")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "005930"
        assert data["name"] == "삼성전자"
        assert data["price"] == 70000
        assert data["change"] == 1000
        assert data["volume"] == 10000000

    async def test_get_quote_no_credential(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        """자격증명 없으면 404."""
        resp = await auth_client.get("/api/v1/market/quote/005930")
        assert resp.status_code == 404


class TestMarketUnauthenticated:
    """미인증 시세 조회 테스트."""

    async def test_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 시세 조회 → 401."""
        resp = await client.get("/api/v1/market/quote/005930")
        assert resp.status_code == 401
