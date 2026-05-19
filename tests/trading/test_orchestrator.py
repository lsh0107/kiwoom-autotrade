"""Orchestrator 단위 테스트.

design-025: 멀티 전략 오케스트레이터 — tick 흐름, handler dispatch, 에러 격리.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import AccountBalance, Holding
from src.models.strategy_runtime import StrategyRuntime
from src.trading.budget_manager import BudgetManager
from src.trading.orchestrator import Orchestrator
from src.trading.strategy_registry import StrategyRegistry

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _make_runtime(
    strategy: str,
    budget_pct: str = "0.5000",
    max_order: int = 5_000_000,
) -> StrategyRuntime:
    return StrategyRuntime(
        strategy=strategy,
        enabled=True,
        budget_pct=Decimal(budget_pct),
        max_order_amount=max_order,
        max_daily_orders=50,
    )


def _make_client(
    holdings: list[Holding] | None = None,
    available_cash: int = 10_000_000,
) -> AsyncMock:
    """mock BrokerClient."""
    client = AsyncMock()
    balance = AccountBalance(
        total_eval=10_000_000,
        total_profit=0,
        total_profit_pct=0.0,
        deposit=10_000_000,
        available_cash=available_cash,
        holdings=holdings or [],
    )
    client.get_balance = AsyncMock(return_value=balance)
    return client


# ── 테스트 ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tick_dispatches_enabled_handlers(db: AsyncSession) -> None:
    """활성 전략의 handler 가 호출되는지 확인."""
    db.add(_make_runtime("cross_momentum", budget_pct="0.6000"))
    db.add(_make_runtime("short_swing", budget_pct="0.3000"))
    await db.commit()

    handler_cm = AsyncMock(return_value={"executed": True})
    handler_ss = AsyncMock(return_value={"entries": 2})

    registry = StrategyRegistry(ttl_seconds=0.0)
    budget = BudgetManager()
    orch = Orchestrator(
        registry=registry,
        budget_manager=budget,
        handlers={"cross_momentum": handler_cm, "short_swing": handler_ss},
    )

    client = _make_client(available_cash=10_000_000)
    results = await orch.tick(db, client, "1455", date(2026, 5, 19))

    assert "cross_momentum" in results
    assert "short_swing" in results
    handler_cm.assert_awaited_once()
    handler_ss.assert_awaited_once()

    # handler 에 전달된 budget 확인
    cm_kwargs = handler_cm.call_args.kwargs
    assert cm_kwargs["allowed_budget"] == 6_000_000
    assert cm_kwargs["max_order_amount"] == 5_000_000

    ss_kwargs = handler_ss.call_args.kwargs
    assert ss_kwargs["allowed_budget"] == 3_000_000


@pytest.mark.asyncio
async def test_tick_no_enabled_strategies(db: AsyncSession) -> None:
    """활성 전략이 없으면 빈 dict 반환."""
    registry = StrategyRegistry(ttl_seconds=0.0)
    budget = BudgetManager()
    orch = Orchestrator(registry=registry, budget_manager=budget, handlers={})

    client = _make_client()
    results = await orch.tick(db, client, "1000", date(2026, 5, 19))

    assert results == {}
    client.get_balance.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_skips_unregistered_handler(db: AsyncSession) -> None:
    """handler 미등록 전략은 skip."""
    db.add(_make_runtime("multi_regime"))
    await db.commit()

    registry = StrategyRegistry(ttl_seconds=0.0)
    budget = BudgetManager()
    orch = Orchestrator(
        registry=registry,
        budget_manager=budget,
        handlers={},  # multi_regime handler 미등록
    )

    client = _make_client()
    results = await orch.tick(db, client, "1000", date(2026, 5, 19))

    assert results == {}


@pytest.mark.asyncio
async def test_tick_handler_error_isolated(db: AsyncSession) -> None:
    """한 handler 실패해도 다른 handler 정상 실행."""
    db.add(_make_runtime("cross_momentum", budget_pct="0.5000"))
    db.add(_make_runtime("short_swing", budget_pct="0.3000"))
    await db.commit()

    handler_cm = AsyncMock(side_effect=RuntimeError("boom"))
    handler_ss = AsyncMock(return_value={"ok": True})

    registry = StrategyRegistry(ttl_seconds=0.0)
    budget = BudgetManager()
    orch = Orchestrator(
        registry=registry,
        budget_manager=budget,
        handlers={"cross_momentum": handler_cm, "short_swing": handler_ss},
    )

    client = _make_client()
    results = await orch.tick(db, client, "1000", date(2026, 5, 19))

    assert results["cross_momentum"] == {"error": True}
    assert results["short_swing"] == {"ok": True}


@pytest.mark.asyncio
async def test_tick_calls_get_balance_once(db: AsyncSession) -> None:
    """브로커 잔고 조회는 tick 당 1회만."""
    db.add(_make_runtime("cross_momentum"))
    db.add(_make_runtime("short_swing"))
    await db.commit()

    handler_cm = AsyncMock(return_value={})
    handler_ss = AsyncMock(return_value={})

    registry = StrategyRegistry(ttl_seconds=0.0)
    budget = BudgetManager()
    orch = Orchestrator(
        registry=registry,
        budget_manager=budget,
        handlers={"cross_momentum": handler_cm, "short_swing": handler_ss},
    )

    client = _make_client()
    await orch.tick(db, client, "1000", date(2026, 5, 19))

    assert client.get_balance.await_count == 1


@pytest.mark.asyncio
async def test_tick_passes_holdings_map(db: AsyncSession) -> None:
    """보유종목이 handler 에 dict 형태로 전달."""
    db.add(_make_runtime("cross_momentum"))
    await db.commit()

    holding = Holding(
        symbol="005930",
        name="삼성전자",
        quantity=10,
        avg_price=70000,
        current_price=72000,
        eval_amount=720000,
        profit=20000,
        profit_pct=2.86,
    )

    handler = AsyncMock(return_value={})
    registry = StrategyRegistry(ttl_seconds=0.0)
    budget = BudgetManager()
    orch = Orchestrator(
        registry=registry,
        budget_manager=budget,
        handlers={"cross_momentum": handler},
    )

    client = _make_client(holdings=[holding], available_cash=5_000_000)
    await orch.tick(db, client, "1455", date(2026, 5, 19))

    kwargs = handler.call_args.kwargs
    assert "005930" in kwargs["holdings_map"]
    assert kwargs["holdings_map"]["005930"].quantity == 10
    assert kwargs["available_cash"] == 5_000_000
