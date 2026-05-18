"""reconcile_cross_momentum_orders 단위 테스트."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.reconcile_cross_momentum_orders import (
    ReconcileResult,
    fetch_stale_orders,
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
        status=OrderStatus.SUBMITTED,
        broker_order_no=broker_order_no,
        is_mock=True,
        reason="cross_momentum",
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
    """ReconcileResult 데이터 클래스."""

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
    """reconcile_order: 4가지 분기 검증."""

    def test_buy_filled_when_holdings_sufficient(self) -> None:
        """BUY + holdings 수량 충분 → FILLED."""
        order = _make_order(symbol="005930", side=OrderSide.BUY, quantity=10)
        holdings_map = {"005930": _make_holding(quantity=10, avg_price=50_000)}
        result = ReconcileResult()

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10
        assert order.filled_price == 50_000
        assert order.id in result.buy_filled

    def test_buy_filled_when_holdings_exceed(self) -> None:
        """BUY + holdings 수량 > order 수량 → FILLED."""
        order = _make_order(symbol="005930", side=OrderSide.BUY, quantity=5)
        holdings_map = {"005930": _make_holding(quantity=20, avg_price=60_000)}
        result = ReconcileResult()

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 5
        assert order.filled_price == 60_000

    def test_buy_filled_fallback_price_when_avg_zero(self) -> None:
        """BUY + avg_price=0 → eval_amount // quantity 로 fallback."""
        order = _make_order(symbol="005930", side=OrderSide.BUY, quantity=10)
        holdings_map = {"005930": _make_holding(quantity=10, avg_price=0, eval_amount=500_000)}
        result = ReconcileResult()

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FILLED
        assert order.filled_price == 50_000  # 500_000 // 10

    def test_buy_failed_when_no_holdings(self) -> None:
        """BUY + holdings 없음 → FAILED."""
        order = _make_order(symbol="005930", side=OrderSide.BUY, quantity=10)
        holdings_map: dict = {}
        result = ReconcileResult()

        reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FAILED
        assert "broker holdings 없음" in (order.error_message or "")
        assert order.id in result.buy_failed

    def test_buy_failed_when_holdings_insufficient(self) -> None:
        """BUY + holdings 수량 부족 → FAILED."""
        order = _make_order(symbol="005930", side=OrderSide.BUY, quantity=10)
        holdings_map = {"005930": _make_holding(quantity=5)}
        result = ReconcileResult()

        reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FAILED
        assert order.id in result.buy_failed

    def test_buy_cancelled_when_quantity_zero(self) -> None:
        """BUY + order.quantity == 0 → CANCELLED (fake row, 실 체결 없음)."""
        order = _make_order(symbol="000720", side=OrderSide.BUY, quantity=0)
        # 같은 symbol 에 holdings 가 있어도 quantity=0 fake row 는 무조건 CANCELLED.
        holdings_map = {"000720": _make_holding(quantity=29, avg_price=167_500)}
        result = ReconcileResult()

        reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.CANCELLED
        assert order.filled_quantity == 0
        assert "quantity=0 fake row" in (order.error_message or "")
        assert order.id in result.buy_cancelled
        assert order.id not in result.buy_filled
        assert order.id not in result.buy_failed

    def test_buy_cancelled_when_quantity_zero_no_holdings(self) -> None:
        """BUY + order.quantity == 0 + holdings 없음 → CANCELLED (FAILED 아님)."""
        order = _make_order(symbol="000720", side=OrderSide.BUY, quantity=0)
        holdings_map: dict = {}
        result = ReconcileResult()

        reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.CANCELLED
        assert order.id in result.buy_cancelled
        assert order.id not in result.buy_failed

    def test_sell_filled_when_no_holdings(self) -> None:
        """SELL + holdings 없음 → FILLED (매도 완료 간주)."""
        order = _make_order(symbol="005930", side=OrderSide.SELL, quantity=10)
        holdings_map: dict = {}
        result = ReconcileResult()

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10
        assert order.filled_price == 0
        assert order.id in result.sell_filled

    def test_sell_filled_when_holdings_zero(self) -> None:
        """SELL + holdings 수량 0 → FILLED."""
        order = _make_order(symbol="005930", side=OrderSide.SELL, quantity=5)
        holdings_map = {"005930": _make_holding(quantity=0)}
        result = ReconcileResult()

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.FILLED
        assert order.id in result.sell_filled

    def test_sell_skipped_when_holdings_remain(self) -> None:
        """SELL + holdings 잔량 존재 → 상태 유지 + 스킵."""
        order = _make_order(symbol="005930", side=OrderSide.SELL, quantity=10)
        holdings_map = {"005930": _make_holding(quantity=5)}
        result = ReconcileResult()

        reconcile_order(order, holdings_map, result)

        assert order.status == OrderStatus.SUBMITTED  # 상태 변경 없음
        assert order.id in result.sell_skipped


# ── fetch_stale_orders ─────────────────────────────────────────────────────


class TestFetchStaleOrders:
    """fetch_stale_orders: DB 조회 검증."""

    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        """조회 결과가 리스트로 반환."""
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
        """대상 주문 없으면 빈 리스트."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        orders = await fetch_stale_orders(mock_session)

        assert orders == []


# ── run_reconcile 통합 ────────────────────────────────────────────────────


class TestRunReconcile:
    """run_reconcile: dry-run / apply 분기."""

    @pytest.mark.asyncio
    async def test_dry_run_rollback(self) -> None:
        """dry-run (기본) 시 rollback 호출."""
        buy_order = _make_order(symbol="A", side=OrderSide.BUY, quantity=10)
        sell_order = _make_order(symbol="B", side=OrderSide.SELL, quantity=5)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [buy_order, sell_order]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_balance = MagicMock()
        mock_balance.holdings = [
            _make_holding(symbol="A", quantity=10, avg_price=50_000),
            # B 없음 → SELL FILLED
        ]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            result = await run_reconcile(mock_session, mock_client, apply=False)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        assert len(result.buy_filled) == 1
        assert len(result.sell_filled) == 1

    @pytest.mark.asyncio
    async def test_apply_commit(self) -> None:
        """--apply 시 commit 호출."""
        order = _make_order(symbol="A", side=OrderSide.BUY, quantity=5)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [order]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_balance = MagicMock()
        mock_balance.holdings = [_make_holding(symbol="A", quantity=10)]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            result = await run_reconcile(mock_session, mock_client, apply=True)

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        assert result.total_changed == 1

    @pytest.mark.asyncio
    async def test_no_stale_orders(self) -> None:
        """대상 주문 없으면 즉시 종료."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_client = MagicMock()

        result = await run_reconcile(mock_session, mock_client, apply=False)

        assert result.total_changed == 0
        mock_client.get_balance.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_orders(self) -> None:
        """BUY + SELL 혼합 시나리오."""
        buy_ok = _make_order(symbol="A", side=OrderSide.BUY, quantity=10)
        buy_fail = _make_order(symbol="B", side=OrderSide.BUY, quantity=10)
        sell_ok = _make_order(symbol="C", side=OrderSide.SELL, quantity=5)
        sell_skip = _make_order(symbol="D", side=OrderSide.SELL, quantity=5)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [buy_ok, buy_fail, sell_ok, sell_skip]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_balance = MagicMock()
        mock_balance.holdings = [
            _make_holding(symbol="A", quantity=15, avg_price=50_000),
            # B 없음 → FAILED
            # C 없음 → SELL FILLED
            _make_holding(symbol="D", quantity=3),  # 잔량 → 스킵
        ]
        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        with patch("src.utils.time.now_kst") as mock_now:
            mock_now.return_value = MagicMock()
            result = await run_reconcile(mock_session, mock_client, apply=False)

        assert len(result.buy_filled) == 1
        assert len(result.buy_failed) == 1
        assert len(result.sell_filled) == 1
        assert len(result.sell_skipped) == 1
        assert result.total_changed == 3  # skipped 제외
