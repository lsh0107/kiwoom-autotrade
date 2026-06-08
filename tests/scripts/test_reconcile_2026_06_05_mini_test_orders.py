"""reconcile_2026_06_05_mini_test_orders 단위 테스트.

핵심 검증: 케이스 3 (holdings 잔량 있음 → 수량 정합성 검증) 이 실제로 동작하는지.
이전 버전은 "수량 검증" 이라 설명하면서 잔량만 있으면 무조건 FILLED 처리했고
``sell_skipped_quantity_mismatch`` 는 코드상 발생하지 않았다. 본 테스트는 그
회귀를 막는다.

- holdings 0 → FILLED (sell_filled)
- 잔량 + sell == expected_pre_qty → FILLED (sell_filled_partial_holdings)
- 잔량 + sell != expected_pre_qty → 스킵 (sell_skipped_quantity_mismatch)
- 잔량 있으나 EXPECTED_PRE_QTY 에 없는 종목 → 스킵
- filled_price 는 항상 0 (체결가 복원 불가 — PnL 산출용 아님)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.reconcile_2026_06_05_mini_test_orders import (
    EXPECTED_PRE_QTY,
    ReconcileResult,
    reconcile_sell_order,
    run_reconcile,
)
from src.models.order import Order, OrderSide, OrderStatus

# ── 헬퍼 ──────────────────────────────────────────────────────────────────


def _make_order(
    *,
    symbol: str = "000720",
    quantity: int = 10,
    broker_order_no: str = "0137829",
    status: OrderStatus = OrderStatus.SUBMITTED,
) -> Order:
    """테스트용 6/5 mini test sell 주문."""
    return Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        symbol=symbol,
        side=OrderSide.SELL,
        price=0,
        quantity=quantity,
        filled_quantity=0,
        filled_price=0,
        status=status,
        broker_order_no=broker_order_no,
        is_mock=True,
        reason="cross_momentum",
        order_type="limit",
    )


def _make_holding(symbol: str, quantity: int) -> MagicMock:
    """테스트용 Holding mock."""
    h = MagicMock()
    h.symbol = symbol
    h.quantity = quantity
    return h


# ── ReconcileResult ─────────────────────────────────────────────────────────


class TestReconcileResult:
    def test_empty_result(self) -> None:
        r = ReconcileResult()
        assert r.total_changed == 0
        assert "SELL→FILLED (holdings 0): 0" in r.summary()

    def test_total_changed_excludes_skipped(self) -> None:
        r = ReconcileResult()
        r.sell_filled = [uuid.uuid4()]
        r.sell_filled_partial_holdings = [uuid.uuid4()]
        r.sell_skipped_quantity_mismatch = [(uuid.uuid4(), "000720", 10, 99)]
        # skipped 는 total_changed 에 포함 안 됨
        assert r.total_changed == 2


# ── reconcile_sell_order 분기 검증 ─────────────────────────────────────────


class TestReconcileSellOrder:
    @pytest.mark.asyncio
    async def test_filled_when_no_holdings(self) -> None:
        """케이스 1: holdings 0 → FILLED."""
        order = _make_order(symbol="005930", quantity=10)
        result = ReconcileResult()

        with patch("src.utils.time.now_kst", return_value=MagicMock()):
            await reconcile_sell_order(order, {}, result)

        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10
        assert order.filled_price == 0  # 체결가 복원 불가
        assert order.order_type == "market"
        assert order.id in result.sell_filled

    @pytest.mark.asyncio
    async def test_filled_when_quantity_matches(self) -> None:
        """케이스 2: 잔량 + sell == expected_pre_qty → FILLED.

        000720: pre 29, sell 10, current 19 → 19 + 10 == 29 통과.
        """
        order = _make_order(symbol="000720", quantity=10)
        holdings_map = {"000720": _make_holding("000720", 19)}
        result = ReconcileResult()

        with patch("src.utils.time.now_kst", return_value=MagicMock()):
            await reconcile_sell_order(order, holdings_map, result)

        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10
        assert order.filled_price == 0
        assert order.id in result.sell_filled_partial_holdings
        assert result.sell_skipped_quantity_mismatch == []

    @pytest.mark.asyncio
    async def test_skipped_when_quantity_mismatch(self) -> None:
        """케이스 3: 잔량 + sell != expected_pre_qty → 스킵 (FILLED 금지).

        000720: pre 29 이지만 현재 잔량이 20 이면 20 + 10 = 30 != 29 → 스킵.
        """
        order = _make_order(symbol="000720", quantity=10)
        holdings_map = {"000720": _make_holding("000720", 20)}
        result = ReconcileResult()

        await reconcile_sell_order(order, holdings_map, result)

        assert order.status == OrderStatus.SUBMITTED  # FILLED 안 됨
        assert order.id not in result.sell_filled_partial_holdings
        assert len(result.sell_skipped_quantity_mismatch) == 1
        rec = result.sell_skipped_quantity_mismatch[0]
        assert rec == (order.id, "000720", 10, 20)

    @pytest.mark.asyncio
    async def test_skipped_when_symbol_not_in_map(self) -> None:
        """케이스 3: 잔량 있으나 EXPECTED_PRE_QTY 에 없는 종목 → 스킵."""
        order = _make_order(symbol="999999", quantity=10)
        holdings_map = {"999999": _make_holding("999999", 5)}
        result = ReconcileResult()

        await reconcile_sell_order(order, holdings_map, result)

        assert order.status == OrderStatus.SUBMITTED
        assert len(result.sell_skipped_quantity_mismatch) == 1
        assert result.sell_skipped_quantity_mismatch[0][1] == "999999"

    @pytest.mark.asyncio
    async def test_all_four_mapped_symbols_match(self) -> None:
        """비중↓ 4 종목 각각의 (current, sell) 조합이 expected_pre 와 일치."""
        cases = {
            "000720": (19, 10),  # pre 29
            "006800": (37, 24),  # pre 61
            "047040": (91, 64),  # pre 155
            "240810": (25, 10),  # pre 35
        }
        for symbol, (current, sell) in cases.items():
            order = _make_order(symbol=symbol, quantity=sell)
            holdings_map = {symbol: _make_holding(symbol, current)}
            result = ReconcileResult()
            with patch("src.utils.time.now_kst", return_value=MagicMock()):
                await reconcile_sell_order(order, holdings_map, result)
            assert order.status == OrderStatus.FILLED, symbol
            assert current + sell == EXPECTED_PRE_QTY[symbol], symbol
            assert order.id in result.sell_filled_partial_holdings, symbol

    @pytest.mark.asyncio
    async def test_filled_emits_trade_log(self) -> None:
        """FILLED 시 trade_logs insert."""
        order = _make_order(symbol="005930", quantity=10)
        result = ReconcileResult()
        mock_session = AsyncMock()

        with (
            patch("src.utils.time.now_kst", return_value=MagicMock()),
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log,
        ):
            await reconcile_sell_order(order, {}, result, session=mock_session)

        assert mock_log.await_count == 1
        assert mock_log.await_args.kwargs["event_type"] == "order_filled"
        assert mock_log.await_args.kwargs["order_id"] == order.id

    @pytest.mark.asyncio
    async def test_skipped_does_not_emit_trade_log(self) -> None:
        """스킵 (수량 불일치) 시 trade_logs insert 안 함."""
        order = _make_order(symbol="000720", quantity=10)
        holdings_map = {"000720": _make_holding("000720", 20)}
        result = ReconcileResult()
        mock_session = AsyncMock()

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            await reconcile_sell_order(order, holdings_map, result, session=mock_session)

        mock_log.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_session_none_skips_trade_log(self) -> None:
        order = _make_order(symbol="005930", quantity=10)
        result = ReconcileResult()
        with (
            patch("src.utils.time.now_kst", return_value=MagicMock()),
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log,
        ):
            await reconcile_sell_order(order, {}, result)
        mock_log.assert_not_awaited()


# ── run_reconcile 통합 ────────────────────────────────────────────────────


class TestRunReconcile:
    @pytest.mark.asyncio
    async def test_dry_run_rollback(self) -> None:
        order_filled = _make_order(symbol="005930", quantity=10)  # holdings 0
        order_match = _make_order(symbol="000720", quantity=10)  # 19+10==29
        order_mismatch = _make_order(symbol="006800", quantity=24)  # 잔량 어긋남

        scalars = MagicMock()
        scalars.all.return_value = [order_filled, order_match, order_mismatch]
        result_orders = MagicMock()
        result_orders.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=result_orders)

        mock_balance = MagicMock()
        mock_balance.holdings = [
            _make_holding("000720", 19),  # match
            _make_holding("006800", 99),  # mismatch (99+24 != 61)
        ]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        with (
            patch("src.utils.time.now_kst", return_value=MagicMock()),
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock),
        ):
            result = await run_reconcile(mock_session, mock_client, apply=False)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        assert len(result.sell_filled) == 1
        assert len(result.sell_filled_partial_holdings) == 1
        assert len(result.sell_skipped_quantity_mismatch) == 1

    @pytest.mark.asyncio
    async def test_apply_commit(self) -> None:
        order = _make_order(symbol="005930", quantity=10)
        scalars = MagicMock()
        scalars.all.return_value = [order]
        result_orders = MagicMock()
        result_orders.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=result_orders)

        mock_balance = MagicMock()
        mock_balance.holdings = []
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        with (
            patch("src.utils.time.now_kst", return_value=MagicMock()),
            patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock),
        ):
            result = await run_reconcile(mock_session, mock_client, apply=True)

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        assert result.total_changed == 1

    @pytest.mark.asyncio
    async def test_no_target_orders(self) -> None:
        scalars = MagicMock()
        scalars.all.return_value = []
        result_orders = MagicMock()
        result_orders.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=result_orders)
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock()

        result = await run_reconcile(mock_session, mock_client, apply=False)

        # 대상 없으면 broker 조회 없이 빈 결과
        mock_client.get_balance.assert_not_called()
        assert result.total_changed == 0
