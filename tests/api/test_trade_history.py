"""매매 이력 API 테스트."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.trade_log import TradeLog
from src.models.user import User


@pytest.fixture
async def trade_logs(db: AsyncSession, test_user: User) -> list[TradeLog]:
    """테스트용 매매 이력 생성."""
    now = datetime.now(tz=UTC)
    logs = [
        TradeLog(
            user_id=test_user.id,
            event_type="BUY",
            symbol="005930",
            side="buy",
            price=75000,
            quantity=10,
            message="삼성전자 매수",
            is_mock=True,
            created_at=now,
        ),
        TradeLog(
            user_id=test_user.id,
            event_type="SELL",
            symbol="000660",
            side="sell",
            price=150000,
            quantity=5,
            message="SK하이닉스 매도",
            is_mock=True,
            created_at=now,
        ),
    ]
    for log in logs:
        db.add(log)
    await db.commit()
    return logs


class TestTradeHistory:
    """매매 이력 API 테스트."""

    async def test_get_trade_history_success(
        self,
        auth_client: AsyncClient,
        test_user: User,
        trade_logs: list[TradeLog],
    ) -> None:
        """인증된 사용자가 당일 매매 이력을 조회한다."""
        resp = await auth_client.get("/api/v1/bot/trade-history")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # 응답 필드 검증
        first = data[0]
        assert "id" in first
        assert "symbol" in first
        assert "side" in first
        assert "price" in first
        assert "quantity" in first
        assert "event_type" in first
        assert "message" in first
        assert "is_mock" in first
        assert "created_at" in first

    async def test_get_trade_history_limit(
        self,
        auth_client: AsyncClient,
        test_user: User,
        trade_logs: list[TradeLog],
    ) -> None:
        """limit=1 파라미터로 1건만 반환된다."""
        resp = await auth_client.get("/api/v1/bot/trade-history?limit=1")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_get_trade_history_empty(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        """이력이 없으면 빈 리스트 반환."""
        resp = await auth_client.get("/api/v1/bot/trade-history")

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_trade_history_unauthenticated(
        self,
        client: AsyncClient,
    ) -> None:
        """미인증 시 401."""
        resp = await client.get("/api/v1/bot/trade-history")
        assert resp.status_code == 401

    async def test_get_trade_history_response_format(
        self,
        auth_client: AsyncClient,
        test_user: User,
        trade_logs: list[TradeLog],
    ) -> None:
        """응답 형식이 TradeHistoryResponse 스펙과 일치한다."""
        resp = await auth_client.get("/api/v1/bot/trade-history")
        data = resp.json()

        # 삼성전자 BUY 이력 확인 (최신 순이므로 첫 번째 또는 두 번째)
        symbols = {item["symbol"] for item in data}
        assert "005930" in symbols
        assert "000660" in symbols

        buy_log = next(item for item in data if item["symbol"] == "005930")
        assert buy_log["event_type"] == "BUY"
        assert buy_log["price"] == 75000
        assert buy_log["quantity"] == 10
        assert buy_log["is_mock"] is True
