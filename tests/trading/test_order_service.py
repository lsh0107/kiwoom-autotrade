"""주문 서비스 테스트."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.broker.schemas import BrokerOrderResponse
from src.models.order import OrderSide, OrderStatus
from src.models.user import User
from src.trading.order_service import (
    CreateOrderParams,
    cancel_order,
    create_order,
    get_user_orders,
    submit_order,
)
from src.utils.exceptions import NotFoundError


class TestCreateOrder:
    """주문 생성 테스트."""

    async def test_create_order_success(self, db: AsyncSession, test_user: User) -> None:
        """정상 주문 생성 (check_market_hours=False)."""
        order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.BUY,
                price=70000,
                quantity=10,
                is_mock=True,
                check_market_hours=False,
            ),
        )

        assert order.symbol == "005930"
        assert order.symbol_name == "삼성전자"
        assert order.side == OrderSide.BUY
        assert order.price == 70000
        assert order.quantity == 10
        assert order.status == OrderStatus.CREATED
        assert order.user_id == test_user.id
        assert order.is_mock is True

    async def test_create_order_kill_switch_blocks(self, db: AsyncSession, test_user: User) -> None:
        """킬스위치 차단 (금액 초과)."""
        from src.utils.exceptions import KillSwitchError

        with pytest.raises(KillSwitchError, match="한도"):
            await create_order(
                db=db,
                params=CreateOrderParams(
                    user_id=test_user.id,
                    symbol="005930",
                    symbol_name="삼성전자",
                    side=OrderSide.BUY,
                    price=200000,
                    quantity=10,  # 200만원 > 100만원 한도
                    is_mock=True,
                    check_market_hours=False,
                ),
            )


class TestSubmitOrder:
    """주문 제출 테스트."""

    async def test_submit_order_success(self, db: AsyncSession, test_user: User) -> None:
        """주문 제출 성공."""
        order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.BUY,
                price=70000,
                quantity=10,
                is_mock=True,
                check_market_hours=False,
            ),
        )

        broker_resp = BrokerOrderResponse(
            order_no="00001",
            symbol="005930",
            side="BUY",
            price=70000,
            quantity=10,
            status="submitted",
            message="주문 접수 완료",
        )

        result = await submit_order(db=db, order=order, broker_response=broker_resp)

        assert result.status == OrderStatus.SUBMITTED
        assert result.broker_order_no == "00001"
        assert result.submitted_at is not None

    async def test_submit_order_failure(self, db: AsyncSession, test_user: User) -> None:
        """주문 제출 실패."""
        order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.BUY,
                price=70000,
                quantity=10,
                is_mock=True,
                check_market_hours=False,
            ),
        )

        broker_resp = BrokerOrderResponse(
            order_no="",
            symbol="005930",
            side="BUY",
            price=70000,
            quantity=10,
            status="failed",
            message="잔고 부족",
        )

        result = await submit_order(db=db, order=order, broker_response=broker_resp)

        assert result.status == OrderStatus.FAILED
        assert result.error_message == "잔고 부족"


class TestCancelOrder:
    """주문 취소 테스트."""

    async def test_cancel_order_success(self, db: AsyncSession, test_user: User) -> None:
        """주문 취소 성공 (ACCEPTED 상태에서)."""
        order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.BUY,
                price=70000,
                quantity=10,
                is_mock=True,
                check_market_hours=False,
            ),
        )
        # CREATED → SUBMITTED → ACCEPTED로 전이
        order.status = OrderStatus.SUBMITTED
        order.status = OrderStatus.ACCEPTED
        await db.flush()

        result = await cancel_order(db=db, order_id=order.id, user_id=test_user.id)

        assert result.status == OrderStatus.CANCELLED

    async def test_cancel_order_not_found(self, db: AsyncSession, test_user: User) -> None:
        """존재하지 않는 주문 취소 시 NotFoundError."""
        fake_id = uuid.uuid4()

        with pytest.raises(NotFoundError):
            await cancel_order(db=db, order_id=fake_id, user_id=test_user.id)


class TestGetUserOrders:
    """주문 목록 조회 테스트."""

    async def test_get_user_orders(self, db: AsyncSession, test_user: User) -> None:
        """사용자 주문 목록 조회."""
        # 주문 2개 생성
        for i in range(2):
            await create_order(
                db=db,
                params=CreateOrderParams(
                    user_id=test_user.id,
                    symbol=f"00593{i}",
                    symbol_name=f"테스트종목{i}",
                    side=OrderSide.BUY,
                    price=10000,
                    quantity=1,
                    is_mock=True,
                    check_market_hours=False,
                ),
            )
        await db.flush()

        orders = await get_user_orders(db=db, user_id=test_user.id)

        assert len(orders) == 2

    async def test_get_user_orders_empty(self, db: AsyncSession, test_user: User) -> None:
        """주문 없는 사용자 목록 조회."""
        orders = await get_user_orders(db=db, user_id=test_user.id)

        assert orders == []
