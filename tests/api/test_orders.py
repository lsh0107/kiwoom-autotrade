"""주문 API 엔드포인트 테스트."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.broker.schemas import OrderResponse as BrokerOrderResponse
from src.models.broker import BrokerCredential
from src.models.order import Order, OrderStatus
from src.models.user import User


@pytest.fixture
def _mock_kiwoom_client() -> AsyncMock:
    """주문용 KiwoomClient 모킹."""
    mock_client = AsyncMock()
    mock_client.place_order.return_value = BrokerOrderResponse(
        order_no="K00001",
        symbol="005930",
        side="BUY",
        price=70000,
        quantity=10,
        status="submitted",
        message="주문 접수",
    )
    mock_client.close.return_value = None
    return mock_client


class TestCreateOrderEndpoint:
    """POST /api/v1/orders 테스트."""

    async def test_create_order(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
    ) -> None:
        """인증된 사용자 주문 생성."""
        with patch(
            "src.api.v1.orders._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            resp = await auth_client.post(
                "/api/v1/orders",
                json={
                    "symbol": "005930",
                    "symbol_name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 10,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "005930"
        assert data["side"] == "buy"
        assert data["price"] == 70000
        assert data["quantity"] == 10
        assert data["status"] == "submitted"
        assert data["is_mock"] is True


class TestListOrdersEndpoint:
    """GET /api/v1/orders 테스트."""

    async def test_list_orders(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
    ) -> None:
        """주문 목록 조회."""
        # 주문 생성
        with patch(
            "src.api.v1.orders._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            await auth_client.post(
                "/api/v1/orders",
                json={
                    "symbol": "005930",
                    "symbol_name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 10,
                },
            )

        resp = await auth_client.get("/api/v1/orders")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["symbol"] == "005930"


class TestGetOrderEndpoint:
    """GET /api/v1/orders/{id} 테스트."""

    async def test_get_order_detail(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
    ) -> None:
        """주문 상세 조회."""
        # 주문 생성
        with patch(
            "src.api.v1.orders._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            create_resp = await auth_client.post(
                "/api/v1/orders",
                json={
                    "symbol": "005930",
                    "symbol_name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 10,
                },
            )
        order_id = create_resp.json()["id"]

        resp = await auth_client.get(f"/api/v1/orders/{order_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == order_id
        assert data["symbol"] == "005930"


class TestCancelOrderEndpoint:
    """POST /api/v1/orders/{id}/cancel 테스트."""

    async def test_cancel_order(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
        db: AsyncSession,
    ) -> None:
        """주문 취소 (ACCEPTED 상태에서)."""
        # 주문 생성
        with patch(
            "src.api.v1.orders._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            create_resp = await auth_client.post(
                "/api/v1/orders",
                json={
                    "symbol": "005930",
                    "symbol_name": "삼성전자",
                    "side": "buy",
                    "price": 70000,
                    "quantity": 10,
                },
            )
        order_id = create_resp.json()["id"]

        # DB에서 주문 상태를 ACCEPTED로 변경 (cancel 가능 상태)
        result = await db.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        order = result.scalar_one()
        order.status = OrderStatus.ACCEPTED
        await db.flush()

        resp = await auth_client.post(f"/api/v1/orders/{order_id}/cancel")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"


class TestUnauthenticated:
    """미인증 테스트."""

    async def test_create_order_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 401."""
        resp = await client.post(
            "/api/v1/orders",
            json={
                "symbol": "005930",
                "symbol_name": "삼성전자",
                "side": "buy",
                "price": 70000,
                "quantity": 10,
            },
        )
        assert resp.status_code == 401

    async def test_list_orders_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 목록 조회 401."""
        resp = await client.get("/api/v1/orders")
        assert resp.status_code == 401
