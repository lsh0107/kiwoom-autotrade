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

    async def test_create_order_manual_no_amount_cap(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """수동 주문(strategy_id None)은 금액 cap 없이 통과한다."""
        # 200만원 — 과거 수동 cap(1M)을 넘는 금액이지만 통과해야 함
        order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.BUY,
                price=200000,
                quantity=10,
                is_mock=True,
                check_market_hours=False,
            ),
        )
        assert order.status == OrderStatus.CREATED
        assert order.price * order.quantity == 2_000_000

    async def test_create_order_price_limit_still_enforced(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """수동 주문이라도 가격제한폭(±30%)·가격>0 같은 안전장치는 유지된다."""
        from src.utils.exceptions import KillSwitchError

        with pytest.raises(KillSwitchError, match="가격"):
            await create_order(
                db=db,
                params=CreateOrderParams(
                    user_id=test_user.id,
                    symbol="005930",
                    symbol_name="삼성전자",
                    side=OrderSide.BUY,
                    price=200_000,
                    quantity=10,
                    prev_close=100_000,  # +100% — 제한폭 초과
                    is_mock=True,
                    check_market_hours=False,
                ),
            )


    async def test_create_order_strategy_sell_unaffected_by_max_investment(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """전략 SELL은 투자금 한도를 초과한 상태에서도 통과한다."""
        from src.models.strategy import Strategy

        strategy = Strategy(
            user_id=test_user.id,
            name="test-sell-strategy",
            description="테스트",
            max_investment=1_000_000,
            max_loss_pct=-3.0,
        )
        db.add(strategy)
        await db.flush()

        # 기존 BUY 주문으로 투자금 80만원 사용 상태 만들기
        buy_order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.BUY,
                price=80000,
                quantity=10,
                strategy_id=strategy.id,
                is_mock=True,
                check_market_hours=False,
            ),
        )
        buy_order.status = OrderStatus.FILLED
        await db.flush()

        # SELL 주문 — 노출 축소이므로 한도 초과 상태에서도 통과
        sell_order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.SELL,
                price=80000,
                quantity=5,
                strategy_id=strategy.id,
                is_mock=True,
                check_market_hours=False,
            ),
        )
        assert sell_order.status == OrderStatus.CREATED
        assert sell_order.side == OrderSide.SELL

    async def test_create_order_manual_sell_passes(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """수동 SELL 주문도 정상 통과한다 (회귀 방지)."""
        order = await create_order(
            db=db,
            params=CreateOrderParams(
                user_id=test_user.id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.SELL,
                price=70000,
                quantity=10,
                is_mock=True,
                check_market_hours=False,
            ),
        )
        assert order.status == OrderStatus.CREATED
        assert order.side == OrderSide.SELL


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
            side="buy",
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
            side="buy",
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
