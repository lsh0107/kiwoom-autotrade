"""reconcile_cross_momentum_orders 단위 테스트.

F.7 변경 반영:
- reconcile_order async 화 + trade_logs insert + order_type='market' 보정
- fix_existing_filled_orders 신규 함수 (이미 FILLED 된 row 사후 보강)
- run_reconcile 가 stale 없어도 broker holdings 조회 + 사후 보강 수행
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.reconcile_cross_momentum_orders import (
    ReconcileResult,
    fetch_stale_orders,
    fix_existing_filled_orders,
    reconcile_order,
    run_reconcile,
)
from src.models.order import Order, OrderSide, OrderStatus

# ── 헬퍼 ──────────────────────────────────────────────────────────────────


def _make_order(
    *,
    symbol: str = "005930",
    side: OrderSide = OrderSide.BUY,
    quantity: int = 10,
    broker_order_no: str = "rebalance_20260515_005930",
    order_type: str = "limit",
    status: OrderStatus = OrderStatus.SUBMITTED,
) -> Order:
    """테스트용 Order 인스턴스 생성."""
    return Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        symbol=symbol,
        side=side,
        price=0,
        quantity=quantity,
        filled_quantity=0,
        filled_price=0,
        status=status,
        broker_order_no=broker_order_no,
        is_mock=True,
        reason="cross_momentum",
        order_type=order_type,
    )


def _make_holding(
    symbol: str = "005930",
    quantity: int = 10,
    avg_price: int = 50_000,
    eval_amount: int = 500_000,
) -> MagicMock:
    """테스트용 Holding mock."""
    h = MagicMock()
    h.symbol = symbol
    h.quantity = quantity
    h.avg_price = avg_price
    h.eval_amount = eval_amount
    return h


# ── ReconcileResult ─────────────────────────────────────────────────────────


class TestReconcileResult:
    def test_empty_result(self) -> None:
        r = ReconcileResult()
        assert r.total_changed == 0
        assert "BUY→FILLED: 0" in r.summary()

    def test_total_changed(self) -> None:
        r = ReconcileResult()
        r.buy_filled = [uuid.uuid4()]
        r.buy_failed = [uuid.uuid4(), uuid.uuid4()]
        r.sell_filled = [uuid.uuid4()]
        r.sell_skipped = [uuid.uuid4()]
        assert r.total_changed == 4  # skipped 제외
        assert "BUY→FAILED: 2" in r.summary()


# ── reconcile_order 분기 검증 ─────────────────────────────────────────────


class TestReconcileOrder:
    """reconcile_order: 각 분기 검증 (async)."""

    @pytest.mark.asyncio
    async def test_buy_filled_when_holdings_sufficient(self) -> None:
        order = _make_order(side=OrderSide.BUY, quantity=10)
        holdings_map = {"005930": _make_holding(quantity=10, avg_price=50_000)}
        result = ReconcileResult()

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            await reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10
        assert order.filled_price == 50_000
        # F.7: cross_momentum 은 시장가 → order_type 'market' 보정
        assert order.order_type == "market"
        assert order.id in result.buy_filled

    @pytest.mark.asyncio
    async def test_buy_filled_emits_trade_log(self) -> None:
        """F.7: BUY FILLED 시 trade_logs row insert."""
        order = _make_order(quantity=10)
        holdings_map = {"005930": _make_holding(quantity=10, avg_price=50_000)}
        result = ReconcileResult()
        mock_session = AsyncMock()

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            await reconcile_order(order, holdings_map, result, session=mock_session)

        assert mock_log.await_count == 1
        kwargs = mock_log.await_args.kwargs
        assert kwargs["event_type"] == "order_filled"
        assert kwargs["order_id"] == order.id
        assert kwargs["symbol"] == "005930"

    @pytest.mark.asyncio
    async def test_buy_failed_when_no_holdings_emits_trade_log(self) -> None:
        """F.7: BUY FAILED 도 trade_logs insert."""
        order = _make_order(quantity=10)
        result = ReconcileResult()
        mock_session = AsyncMock()

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            await reconcile_order(order, {}, result, session=mock_session)

        assert order.status == OrderStatus.FAILED
        assert mock_log.await_count == 1
        assert mock_log.await_args.kwargs["event_type"] == "order_failed"

    @pytest.mark.asyncio
    async def test_buy_cancelled_when_quantity_zero_emits_trade_log(self) -> None:
        """F.7: CANCELLED 도 trade_logs insert."""
        order = _make_order(quantity=0)
        result = ReconcileResult()
        mock_session = AsyncMock()

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            await reconcile_order(order, {}, result, session=mock_session)

        assert order.status == OrderStatus.CANCELLED
        assert order.id in result.buy_cancelled
        assert mock_log.await_count == 1
        assert mock_log.await_args.kwargs["event_type"] == "order_cancelled"

    @pytest.mark.asyncio
    async def test_buy_failed_when_no_holdings(self) -> None:
        order = _make_order(quantity=10)
        result = ReconcileResult()

        await reconcile_order(order, {}, result)

        assert order.status == OrderStatus.FAILED
        assert "broker holdings 없음" in (order.error_message or "")
        assert order.id in result.buy_failed

    @pytest.mark.asyncio
    async def test_buy_cancelled_when_quantity_zero(self) -> None:
        order = _make_order(symbol="000720", quantity=0)
        holdings_map = {"000720": _make_holding(quantity=29, avg_price=167_500)}
        result = ReconcileResult()

        await reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.CANCELLED
        assert order.id in result.buy_cancelled

    @pytest.mark.asyncio
    async def test_sell_filled_when_no_holdings(self) -> None:
        order = _make_order(side=OrderSide.SELL, quantity=10)
        result = ReconcileResult()

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            await reconcile_order(order, {}, result)

        assert order.status == OrderStatus.FILLED
        assert order.order_type == "market"  # F.7
        assert order.id in result.sell_filled

    @pytest.mark.asyncio
    async def test_sell_skipped_when_holdings_remain(self) -> None:
        order = _make_order(side=OrderSide.SELL, quantity=10)
        holdings_map = {"005930": _make_holding(quantity=5)}
        result = ReconcileResult()

        await reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.SUBMITTED
        assert order.id in result.sell_skipped

    @pytest.mark.asyncio
    async def test_session_none_skips_trade_log(self) -> None:
        """session=None 이면 trade_logs insert 건너뛴다 (silent skip)."""
        order = _make_order(quantity=10)
        result = ReconcileResult()
        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            await reconcile_order(order, {}, result)
        mock_log.assert_not_awaited()


# ── fetch_stale_orders ─────────────────────────────────────────────────────


class TestFetchStaleOrders:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [_make_order()]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        orders = await fetch_stale_orders(mock_session)
        assert len(orders) == 1
        assert orders[0].reason == "cross_momentum"

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        orders = await fetch_stale_orders(mock_session)
        assert orders == []


# ── fix_existing_filled_orders (F.7 신규) ───────────────────────────────────


class TestFixExistingFilledOrders:
    """이미 FILLED 된 cross_momentum row 사후 보강."""

    @pytest.mark.asyncio
    async def test_fixes_order_type_limit_to_market(self) -> None:
        already_filled = _make_order(
            quantity=10,
            order_type="limit",
            status=OrderStatus.FILLED,
        )
        already_filled.filled_quantity = 10
        already_filled.filled_price = 50_000

        # 1번째 execute: select(Order) → [already_filled]
        # 2번째 execute: select(TradeLog.id) → trade_log 없음 (first()=None)
        scalars_orders = MagicMock()
        scalars_orders.all.return_value = [already_filled]
        result_orders = MagicMock()
        result_orders.scalars.return_value = scalars_orders

        result_log = MagicMock()
        result_log.first.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[result_orders, result_log])

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            fixed = await fix_existing_filled_orders(mock_session)

        assert fixed == 1
        assert already_filled.order_type == "market"
        # trade_logs insert 호출 확인
        assert mock_log.await_count == 1

    @pytest.mark.asyncio
    async def test_skips_when_already_market_and_trade_log_exists(self) -> None:
        order_ok = _make_order(
            quantity=10,
            order_type="market",  # 이미 보정됨
            status=OrderStatus.FILLED,
        )

        scalars_orders = MagicMock()
        scalars_orders.all.return_value = [order_ok]
        result_orders = MagicMock()
        result_orders.scalars.return_value = scalars_orders

        result_log = MagicMock()
        result_log.first.return_value = (uuid.uuid4(),)  # 이미 trade_log 존재

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[result_orders, result_log])

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            fixed = await fix_existing_filled_orders(mock_session)

        # order_type 도 'market' 이고 trade_log 도 있으니 보강 0건
        assert fixed == 0
        mock_log.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_existing_rows(self) -> None:
        scalars_orders = MagicMock()
        scalars_orders.all.return_value = []
        result_orders = MagicMock()
        result_orders.scalars.return_value = scalars_orders
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=result_orders)

        fixed = await fix_existing_filled_orders(mock_session)
        assert fixed == 0


# ── run_reconcile 통합 ────────────────────────────────────────────────────


class TestRunReconcile:
    @pytest.mark.asyncio
    async def test_dry_run_rollback(self) -> None:
        buy_order = _make_order(symbol="A", side=OrderSide.BUY, quantity=10)
        sell_order = _make_order(symbol="B", side=OrderSide.SELL, quantity=5)

        # fetch_stale_orders 의 execute → [buy, sell]
        scalars_stale = MagicMock()
        scalars_stale.all.return_value = [buy_order, sell_order]
        result_stale = MagicMock()
        result_stale.scalars.return_value = scalars_stale

        # fix_existing_filled_orders 의 execute → []
        scalars_existing = MagicMock()
        scalars_existing.all.return_value = []
        result_existing = MagicMock()
        result_existing.scalars.return_value = scalars_existing

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[result_stale, result_existing])

        mock_balance = MagicMock()
        mock_balance.holdings = [
            _make_holding(symbol="A", quantity=10, avg_price=50_000),
        ]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        with (
            patch("src.utils.time.now_kst") as mock_now,
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock),
        ):
            mock_now.return_value = MagicMock()
            result = await run_reconcile(mock_session, mock_client, apply=False)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        assert len(result.buy_filled) == 1
        assert len(result.sell_filled) == 1

    @pytest.mark.asyncio
    async def test_apply_commit(self) -> None:
        order = _make_order(symbol="A", side=OrderSide.BUY, quantity=5)

        scalars_stale = MagicMock()
        scalars_stale.all.return_value = [order]
        result_stale = MagicMock()
        result_stale.scalars.return_value = scalars_stale

        scalars_existing = MagicMock()
        scalars_existing.all.return_value = []
        result_existing = MagicMock()
        result_existing.scalars.return_value = scalars_existing

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[result_stale, result_existing])

        mock_balance = MagicMock()
        mock_balance.holdings = [_make_holding(symbol="A", quantity=10)]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        with (
            patch("src.utils.time.now_kst") as mock_now,
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock),
        ):
            mock_now.return_value = MagicMock()
            result = await run_reconcile(mock_session, mock_client, apply=True)

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        assert result.total_changed == 1

    @pytest.mark.asyncio
    async def test_no_stale_still_calls_fix_existing(self) -> None:
        """F.7: stale 없어도 broker holdings 조회 + 사후 보강 수행."""
        scalars_stale = MagicMock()
        scalars_stale.all.return_value = []
        result_stale = MagicMock()
        result_stale.scalars.return_value = scalars_stale

        scalars_existing = MagicMock()
        scalars_existing.all.return_value = []
        result_existing = MagicMock()
        result_existing.scalars.return_value = scalars_existing

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[result_stale, result_existing])

        mock_balance = MagicMock()
        mock_balance.holdings = []
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        result = await run_reconcile(mock_session, mock_client, apply=False)

        # stale 없어도 broker get_balance 호출됨 (사후 보강용)
        mock_client.get_balance.assert_called_once()
        assert result.total_changed == 0
