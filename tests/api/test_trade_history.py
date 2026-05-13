"""매매 이력 API 테스트."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order, OrderSide, OrderStatus
from src.models.trade_log import TradeLog
from src.models.user import User


@pytest.fixture
async def trade_logs(db: AsyncSession, test_user: User) -> list[TradeLog]:
    """테스트용 매매 이력 생성.

    삼성전자: order_submitted + 일부 체결 (filled_qty=10)
    SK하이닉스: order_submitted (미체결)
    감사용 order_created 1건은 결과에서 제외돼야 함.
    """
    now = datetime.now(tz=UTC)
    samsung_order = Order(
        user_id=test_user.id,
        symbol="005930",
        symbol_name="삼성전자",
        side=OrderSide.BUY,
        price=75000,
        quantity=10,
        filled_quantity=10,
        filled_price=75100,
        status=OrderStatus.FILLED,
        is_mock=True,
    )
    sk_order = Order(
        user_id=test_user.id,
        symbol="000660",
        symbol_name="SK하이닉스",
        side=OrderSide.SELL,
        price=150000,
        quantity=5,
        status=OrderStatus.SUBMITTED,
        is_mock=True,
    )
    db.add(samsung_order)
    db.add(sk_order)
    await db.flush()

    logs = [
        TradeLog(
            user_id=test_user.id,
            order_id=samsung_order.id,
            event_type="order_created",
            symbol="005930",
            side="buy",
            price=75000,
            quantity=10,
            message="주문 생성",
            is_mock=True,
            created_at=now,
        ),
        TradeLog(
            user_id=test_user.id,
            order_id=samsung_order.id,
            event_type="order_submitted",
            symbol="005930",
            side="buy",
            price=75000,
            quantity=10,
            message="삼성전자 매수 제출",
            is_mock=True,
            created_at=now,
        ),
        TradeLog(
            user_id=test_user.id,
            order_id=sk_order.id,
            event_type="order_submitted",
            symbol="000660",
            side="sell",
            price=150000,
            quantity=5,
            message="SK하이닉스 매도 제출",
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
        # order_created 는 감사 로그라 결과에서 제외됨 → 2건
        assert len(data) == 2
        assert all(item["event_type"] != "order_created" for item in data)

        # 응답 필드 검증
        first = data[0]
        for key in (
            "id",
            "symbol",
            "side",
            "price",
            "quantity",
            "order_amount",
            "filled_price",
            "filled_quantity",
            "filled_amount",
            "event_type",
            "message",
            "is_mock",
            "created_at",
        ):
            assert key in first

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
        assert data[0]["event_type"] != "order_created"

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
        assert buy_log["event_type"] == "order_submitted"
        assert buy_log["price"] == 75000
        assert buy_log["quantity"] == 10
        assert buy_log["order_amount"] == 75000 * 10
        # Order LEFT JOIN 으로 체결 정보 동봉
        assert buy_log["filled_price"] == 75100
        assert buy_log["filled_quantity"] == 10
        assert buy_log["filled_amount"] == 75100 * 10
        assert buy_log["is_mock"] is True

        # 미체결 SK하이닉스
        sell_log = next(item for item in data if item["symbol"] == "000660")
        assert sell_log["filled_quantity"] == 0
        assert sell_log["filled_amount"] == 0
        assert sell_log["order_amount"] == 150000 * 5
