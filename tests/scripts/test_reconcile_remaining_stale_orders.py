"""reconcile_remaining_stale_orders 단위 테스트 (F.9)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.reconcile_remaining_stale_orders import (
    ReconcileResult,
    fetch_stale_orders,
    reconcile_order,
    run_reconcile,
)
from src.models.order import Order, OrderSide, OrderStatus


def _make_order(
    *,
    symbol: str = "005930",
    side: OrderSide = OrderSide.BUY,
    quantity: int = 10,
    broker_order_no: str | None = "0013341",
    reason: str | None = "momentum",
) -> Order:
    return Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        symbol=symbol,
        side=side,
        price=0,
        quantity=quantity,
        filled_quantity=0,
        filled_price=0,
        status=OrderStatus.SUBMITTED,
        broker_order_no=broker_order_no,
        is_mock=True,
        reason=reason,
    )


def _make_holding(
    symbol: str = "005930",
    quantity: int = 10,
    avg_price: int = 50_000,
    eval_amount: int = 500_000,
) -> MagicMock:
    h = MagicMock()
    h.symbol = symbol
    h.quantity = quantity
    h.avg_price = avg_price
    h.eval_amount = eval_amount
    return h


class TestReconcileResult:
    def test_total_changed_excludes_skipped(self) -> None:
        r = ReconcileResult()
        r.buy_filled = [uuid.uuid4()]
        r.buy_failed = [uuid.uuid4()]
        r.mock_qa_cancelled = [uuid.uuid4()]
        r.sell_filled = [uuid.uuid4()]
        r.sell_skipped = [uuid.uuid4(), uuid.uuid4()]
        assert r.total_changed == 4
        assert "mock_qa→CANCELLED: 1" in r.summary()


class TestReconcileOrder:
    @pytest.mark.asyncio
    async def test_mock_qa_test_cancelled(self) -> None:
        """reason='mock_qa_test' → 항상 CANCELLED."""
        order = _make_order(reason="mock_qa_test")
        result = ReconcileResult()
        # broker 보유 있어도 CANCELLED
        holdings_map = {"005930": _make_holding(quantity=617)}
        await reconcile_order(order, holdings_map, result)
        assert order.status == OrderStatus.CANCELLED
        assert order.id in result.mock_qa_cancelled

    @pytest.mark.asyncio
    async def test_mock_qa_sell_cancelled(self) -> None:
        order = _make_order(reason="mock_qa_sell", side=OrderSide.SELL)
        result = ReconcileResult()
        await reconcile_order(order, {}, result)
        assert order.status == OrderStatus.CANCELLED
        assert order.id in result.mock_qa_cancelled

    @pytest.mark.asyncio
    async def test_momentum_buy_filled_when_holdings_sufficient(self) -> None:
        order = _make_order(reason="momentum", quantity=12)
        holdings_map = {"005930": _make_holding(quantity=20, avg_price=47_900)}
        result = ReconcileResult()
        with patch("src.utils.time.now_kst"):
            await reconcile_order(order, holdings_map, result)
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 12
        assert order.filled_price == 47_900
        assert order.id in result.buy_filled

    @pytest.mark.asyncio
    async def test_momentum_buy_failed_when_no_holdings(self) -> None:
        order = _make_order(reason="momentum", quantity=10)
        result = ReconcileResult()
        await reconcile_order(order, {}, result)
        assert order.status == OrderStatus.FAILED
        assert order.id in result.buy_failed

    @pytest.mark.asyncio
    async def test_null_reason_buy_filled(self) -> None:
        """reason=NULL 도 BUY 분기 적용 (수동 주문)."""
        order = _make_order(reason=None, quantity=600)
        holdings_map = {"005930": _make_holding(quantity=617, avg_price=285_454)}
        result = ReconcileResult()
        with patch("src.utils.time.now_kst"):
            await reconcile_order(order, holdings_map, result)
        assert order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_null_reason_buy_failed_when_insufficient(self) -> None:
        """수동 BUY 100주 vs broker 99주 (부족) → FAILED."""
        order = _make_order(reason=None, symbol="000660", quantity=100)
        holdings_map = {"000660": _make_holding(symbol="000660", quantity=99)}
        result = ReconcileResult()
        await reconcile_order(order, holdings_map, result)
        assert order.status == OrderStatus.FAILED

    @pytest.mark.asyncio
    async def test_momentum_sell_filled_when_no_holdings(self) -> None:
        order = _make_order(reason="momentum", side=OrderSide.SELL, quantity=12)
        result = ReconcileResult()
        with patch("src.utils.time.now_kst"):
            await reconcile_order(order, {}, result)
        assert order.status == OrderStatus.FILLED
        assert order.id in result.sell_filled

    @pytest.mark.asyncio
    async def test_momentum_sell_skipped_when_holdings_remain(self) -> None:
        order = _make_order(reason="momentum", side=OrderSide.SELL, quantity=2)
        holdings_map = {"005930": _make_holding(quantity=617)}
        result = ReconcileResult()
        await reconcile_order(order, holdings_map, result)
        assert order.status == OrderStatus.SUBMITTED
        assert order.id in result.sell_skipped

    @pytest.mark.asyncio
    async def test_trade_log_emitted_on_filled(self) -> None:
        order = _make_order(reason="momentum", quantity=10)
        holdings_map = {"005930": _make_holding(quantity=10)}
        result = ReconcileResult()
        mock_session = AsyncMock()
        with (
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log,
            patch("src.utils.time.now_kst"),
        ):
            await reconcile_order(order, holdings_map, result, session=mock_session)
        assert mock_log.await_count == 1
        assert mock_log.await_args.kwargs["event_type"] == "order_filled"

    @pytest.mark.asyncio
    async def test_trade_log_emitted_on_mock_qa_cancelled(self) -> None:
        order = _make_order(reason="mock_qa_test")
        result = ReconcileResult()
        mock_session = AsyncMock()
        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            await reconcile_order(order, {}, result, session=mock_session)
        assert mock_log.await_count == 1
        assert mock_log.await_args.kwargs["event_type"] == "order_cancelled"


class TestRunReconcile:
    @pytest.mark.asyncio
    async def test_apply_commits(self) -> None:
        order = _make_order(reason="momentum", quantity=10)
        scalars = MagicMock()
        scalars.all.return_value = [order]
        select_result = MagicMock()
        select_result.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=select_result)

        balance = MagicMock()
        balance.holdings = [_make_holding(quantity=10)]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=balance)

        with (
            patch("src.utils.time.now_kst"),
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock),
        ):
            result = await run_reconcile(mock_session, mock_client, apply=True)

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        assert result.total_changed == 1

    @pytest.mark.asyncio
    async def test_dry_run_rollback(self) -> None:
        order = _make_order(reason="momentum", quantity=10)
        scalars = MagicMock()
        scalars.all.return_value = [order]
        select_result = MagicMock()
        select_result.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=select_result)

        balance = MagicMock()
        balance.holdings = [_make_holding(quantity=10)]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=balance)

        with (
            patch("src.utils.time.now_kst"),
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock),
        ):
            await run_reconcile(mock_session, mock_client, apply=False)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_stale_returns_empty(self) -> None:
        scalars = MagicMock()
        scalars.all.return_value = []
        select_result = MagicMock()
        select_result.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=select_result)
        mock_client = MagicMock()

        result = await run_reconcile(mock_session, mock_client, apply=False)
        assert result.total_changed == 0
        mock_client.get_balance.assert_not_called()


class TestFetchStaleOrders:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        scalars = MagicMock()
        scalars.all.return_value = [_make_order(reason="momentum")]
        select_result = MagicMock()
        select_result.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=select_result)

        orders = await fetch_stale_orders(mock_session)
        assert len(orders) == 1
        assert orders[0].reason == "momentum"
