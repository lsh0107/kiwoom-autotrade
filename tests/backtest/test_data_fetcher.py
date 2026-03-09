"""데이터 수집 모듈 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.backtest.data_fetcher import fetch_daily_data, fetch_minute_data
from src.broker.schemas import DailyPrice, MinutePrice


@pytest.fixture
def mock_client() -> MagicMock:
    """모의 키움 클라이언트."""
    client = MagicMock()
    client.get_daily_chart = AsyncMock()
    client.get_minute_price = AsyncMock()
    return client


class TestFetchDailyData:
    """일봉 데이터 수집 테스트."""

    @pytest.mark.asyncio
    async def test_fetch_and_filter(self, mock_client: MagicMock) -> None:
        """기간 내 데이터만 필터링."""
        mock_client.get_daily_chart.return_value = [
            DailyPrice(date="20250101", open=100, high=110, low=90, close=105, volume=1000),
            DailyPrice(date="20250102", open=105, high=115, low=95, close=110, volume=1200),
            DailyPrice(date="20250103", open=110, high=120, low=100, close=115, volume=1100),
            DailyPrice(date="20250104", open=115, high=125, low=105, close=120, volume=1300),
        ]

        result = await fetch_daily_data(mock_client, "005930", "20250102", "20250103")

        assert len(result) == 2
        assert result[0].date == "20250102"
        assert result[1].date == "20250103"

    @pytest.mark.asyncio
    async def test_ascending_order(self, mock_client: MagicMock) -> None:
        """결과가 날짜 오름차순."""
        mock_client.get_daily_chart.return_value = [
            DailyPrice(date="20250103", open=110, high=120, low=100, close=115, volume=1100),
            DailyPrice(date="20250102", open=105, high=115, low=95, close=110, volume=1200),
        ]

        result = await fetch_daily_data(mock_client, "005930", "20250102", "20250103")

        assert result[0].date == "20250102"
        assert result[1].date == "20250103"

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_client: MagicMock) -> None:
        """데이터 없으면 빈 리스트."""
        mock_client.get_daily_chart.return_value = []
        result = await fetch_daily_data(mock_client, "005930", "20250101", "20250103")
        assert result == []


class TestFetchMinuteData:
    """분봉 데이터 수집 테스트."""

    @pytest.mark.asyncio
    async def test_filter_by_date(self, mock_client: MagicMock) -> None:
        """지정 일자 데이터만 필터링."""
        mock_client.get_minute_price.return_value = [
            MinutePrice(
                datetime="20250102093000", open=100, high=110, low=90, close=105, volume=500
            ),
            MinutePrice(
                datetime="20250102094000", open=105, high=115, low=95, close=110, volume=600
            ),
            MinutePrice(datetime="20250101153000", open=90, high=100, low=85, close=95, volume=400),
        ]

        result = await fetch_minute_data(mock_client, "005930", "20250102", 5)

        assert len(result) == 2
        assert all(r.datetime.startswith("20250102") for r in result)

    @pytest.mark.asyncio
    async def test_ascending_order(self, mock_client: MagicMock) -> None:
        """결과가 시간 오름차순."""
        mock_client.get_minute_price.return_value = [
            MinutePrice(
                datetime="20250102100000", open=110, high=120, low=100, close=115, volume=700
            ),
            MinutePrice(
                datetime="20250102093000", open=100, high=110, low=90, close=105, volume=500
            ),
        ]

        result = await fetch_minute_data(mock_client, "005930", "20250102", 5)

        assert result[0].datetime == "20250102093000"
        assert result[1].datetime == "20250102100000"

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_client: MagicMock) -> None:
        """데이터 없으면 빈 리스트."""
        mock_client.get_minute_price.return_value = []
        result = await fetch_minute_data(mock_client, "005930", "20250102", 5)
        assert result == []
