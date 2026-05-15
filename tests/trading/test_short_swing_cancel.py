"""Short Swing 미체결 주문 취소 테스트."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order, OrderSide, OrderStatus
from src.trading.short_swing_cancel import cancel_stale_buy_orders

KST = timezone(timedelta(hours=9))
_NOW = datetime(2026, 5, 15, 15, 20, 0, tzinfo=KST)
_USER_ID = uuid.uuid4()


def _make_order(
    *,
    reason: str = "short_swing",
    side: OrderSide = OrderSide.BUY,
    status: OrderStatus = OrderStatus.SUBMITTED,
    submitted_at: datetime | None = None,
    broker_order_no: str | None = "ORD001",
) -> MagicMock:
    """Order mock 생성."""
    order = MagicMock(spec=Order)
    order.id = uuid.uuid4()
    order.reason = reason
    order.side = side
    order.status = status
    order.submitted_at = submitted_at or (_NOW - timedelta(minutes=40))
    order.symbol = "005930"
    order.price = 70000
    order.quantity = 10
    order.is_mock = True
    order.broker_order_no = broker_order_no
    order.user_id = _USER_ID
    return order


class TestCancelStaleOrders:
    """미체결 주문 취소 로직 테스트."""

    @pytest.fixture()
    def mock_db(self) -> AsyncMock:
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture()
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        client.cancel_order = AsyncMock()
        return client

    async def test_cancel_stale_30min(self, mock_db: AsyncMock, mock_client: MagicMock) -> None:
        """30분 이상 미체결 → cancel API 호출 + DB 취소."""
        stale_order = _make_order(submitted_at=_NOW - timedelta(minutes=40))

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_order]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.trading.short_swing_cancel.cancel_order",
            new_callable=AsyncMock,
            return_value=stale_order,
        ) as mock_cancel:
            counts = await cancel_stale_buy_orders(mock_db, mock_client, user_id=_USER_ID, now=_NOW)

        assert counts["cancelled"] == 1
        assert counts["errors"] == 0
        mock_client.cancel_order.assert_awaited_once_with("ORD001")
        mock_cancel.assert_awaited_once()

    async def test_skip_under_30min(self, mock_db: AsyncMock, mock_client: MagicMock) -> None:
        """30분 미만 → 대상 없음 (쿼리에서 필터됨)."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        counts = await cancel_stale_buy_orders(mock_db, mock_client, user_id=_USER_ID, now=_NOW)

        assert counts["cancelled"] == 0
        assert counts["skipped"] == 0
        mock_client.cancel_order.assert_not_awaited()

    async def test_skip_non_submitted(self, mock_db: AsyncMock, mock_client: MagicMock) -> None:
        """status != SUBMITTED → 쿼리에서 제외됨."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        counts = await cancel_stale_buy_orders(mock_db, mock_client, user_id=_USER_ID, now=_NOW)

        assert counts["cancelled"] == 0

    async def test_skip_non_short_swing(self, mock_db: AsyncMock, mock_client: MagicMock) -> None:
        """reason != 'short_swing' → 쿼리에서 제외됨."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        counts = await cancel_stale_buy_orders(mock_db, mock_client, user_id=_USER_ID, now=_NOW)

        assert counts["cancelled"] == 0

    async def test_broker_cancel_failure_still_updates_db(
        self, mock_db: AsyncMock, mock_client: MagicMock
    ) -> None:
        """브로커 cancel API 실패해도 DB 상태는 취소로 갱신."""
        stale_order = _make_order(submitted_at=_NOW - timedelta(minutes=40))
        mock_client.cancel_order = AsyncMock(side_effect=Exception("broker timeout"))

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_order]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.trading.short_swing_cancel.cancel_order",
            new_callable=AsyncMock,
            return_value=stale_order,
        ) as mock_cancel:
            counts = await cancel_stale_buy_orders(mock_db, mock_client, user_id=_USER_ID, now=_NOW)

        # 브로커 실패해도 DB cancel은 수행
        assert counts["cancelled"] == 1
        mock_cancel.assert_awaited_once()

    async def test_threshold_0_cancels_all(
        self, mock_db: AsyncMock, mock_client: MagicMock
    ) -> None:
        """threshold=0 → 모든 미체결 즉시 취소 (15:20 일괄)."""
        recent_order = _make_order(submitted_at=_NOW - timedelta(minutes=5))

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [recent_order]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.trading.short_swing_cancel.cancel_order",
            new_callable=AsyncMock,
            return_value=recent_order,
        ):
            counts = await cancel_stale_buy_orders(
                mock_db, mock_client, user_id=_USER_ID, now=_NOW, threshold_minutes=0
            )

        assert counts["cancelled"] == 1
