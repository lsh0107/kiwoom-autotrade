"""expire_stale_old_submissions 단위 테스트 (F.10)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.expire_stale_old_submissions import (
    ExpireResult,
    expire_order,
    fetch_stale_submissions,
    run_expire,
)
from src.models.order import Order, OrderSide, OrderStatus
from src.utils.time import now_kst


def _make_order(
    *,
    symbol: str = "005930",
    side: OrderSide = OrderSide.SELL,
    quantity: int = 10,
    submitted_at=None,
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
        broker_order_no="0095893",
        is_mock=True,
        reason=reason,
        submitted_at=submitted_at or (now_kst() - timedelta(days=10)),
    )


class TestExpireOrder:
    @pytest.mark.asyncio
    async def test_expire_marks_status_and_message(self) -> None:
        order = _make_order()
        result = ExpireResult()
        await expire_order(order, result, session=None)
        assert order.status == OrderStatus.EXPIRED
        assert "broker 자동 만료" in (order.error_message or "")
        assert order.id in result.expired

    @pytest.mark.asyncio
    async def test_trade_log_emitted(self) -> None:
        order = _make_order()
        result = ExpireResult()
        mock_session = AsyncMock()
        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock) as mock_log:
            await expire_order(order, result, session=mock_session)
        assert mock_log.await_count == 1
        assert mock_log.await_args.kwargs["event_type"] == "order_expired"


class TestRunExpire:
    @pytest.mark.asyncio
    async def test_apply_commits(self) -> None:
        order = _make_order()
        scalars = MagicMock()
        scalars.all.return_value = [order]
        select_result = MagicMock()
        select_result.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=select_result)

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock):
            result = await run_expire(mock_session, days=1, apply=True)

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        assert len(result.expired) == 1
        assert order.status == OrderStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_dry_run_rollback(self) -> None:
        order = _make_order()
        scalars = MagicMock()
        scalars.all.return_value = [order]
        select_result = MagicMock()
        select_result.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=select_result)

        with patch("src.trading.trade_logger.log_trade_event", new_callable=AsyncMock):
            await run_expire(mock_session, days=1, apply=False)

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

        result = await run_expire(mock_session, days=1, apply=False)
        assert len(result.expired) == 0


class TestFetchStaleSubmissions:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        scalars = MagicMock()
        scalars.all.return_value = [_make_order()]
        select_result = MagicMock()
        select_result.scalars.return_value = scalars
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=select_result)

        orders = await fetch_stale_submissions(mock_session, days=1)
        assert len(orders) == 1
