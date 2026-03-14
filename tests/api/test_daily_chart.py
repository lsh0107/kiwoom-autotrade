"""일봉 차트 API 테스트."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.broker.schemas import DailyPrice
from src.models.broker import BrokerCredential
from src.models.user import User


@pytest.fixture
def mock_kiwoom_client() -> AsyncMock:
    """KiwoomClient 모킹."""
    client = AsyncMock()
    client.get_daily_chart.return_value = [
        DailyPrice(
            date="20260314",
            open=74000,
            high=76000,
            low=73500,
            close=75500,
            volume=1234567,
        ),
        DailyPrice(
            date="20260313",
            open=73000,
            high=74500,
            low=72000,
            close=73800,
            volume=987654,
        ),
    ]
    client.close = AsyncMock()
    return client


class TestDailyChart:
    """일봉 차트 API 테스트."""

    async def test_get_daily_chart_success(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        mock_kiwoom_client: AsyncMock,
    ) -> None:
        """인증된 사용자가 일봉 차트를 조회하면 DailyPrice 리스트 반환."""
        with patch(
            "src.api.v1.market._create_kiwoom_client",
            return_value=mock_kiwoom_client,
        ):
            resp = await auth_client.get("/api/v1/market/chart/005930/daily")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

        first = data[0]
        assert first["date"] == "20260314"
        assert first["open"] == 74000
        assert first["high"] == 76000
        assert first["low"] == 73500
        assert first["close"] == 75500
        assert first["volume"] == 1234567

    async def test_get_daily_chart_days_limit(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        mock_kiwoom_client: AsyncMock,
    ) -> None:
        """days=1 파라미터로 결과가 1건으로 제한된다."""
        with patch(
            "src.api.v1.market._create_kiwoom_client",
            return_value=mock_kiwoom_client,
        ):
            resp = await auth_client.get("/api/v1/market/chart/005930/daily?days=1")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["date"] == "20260314"

    async def test_get_daily_chart_no_credential(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        """자격증명 없으면 422."""
        resp = await auth_client.get("/api/v1/market/chart/005930/daily")
        assert resp.status_code == 422
        assert resp.json()["error"] == "NO_CREDENTIALS"

    async def test_get_daily_chart_unauthenticated(
        self,
        client: AsyncClient,
    ) -> None:
        """미인증 시 401."""
        resp = await client.get("/api/v1/market/chart/005930/daily")
        assert resp.status_code == 401

    async def test_get_daily_chart_closes_client(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        mock_kiwoom_client: AsyncMock,
    ) -> None:
        """클라이언트가 항상 close()를 호출한다."""
        with patch(
            "src.api.v1.market._create_kiwoom_client",
            return_value=mock_kiwoom_client,
        ):
            await auth_client.get("/api/v1/market/chart/005930/daily")

        mock_kiwoom_client.close.assert_called_once()
