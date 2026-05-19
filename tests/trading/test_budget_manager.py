"""BudgetManager 단위 테스트.

design-025: strategy_runtime 기반 전략별 budget 할당.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_runtime import StrategyRuntime
from src.trading.budget_manager import BudgetManager

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _seed_runtime(
    strategy: str = "cross_momentum",
    budget_pct: str = "0.6000",
    max_order: int = 5_000_000,
    max_daily: int = 50,
) -> StrategyRuntime:
    """테스트용 StrategyRuntime 인스턴스."""
    return StrategyRuntime(
        strategy=strategy,
        enabled=True,
        budget_pct=Decimal(budget_pct),
        max_order_amount=max_order,
        max_daily_orders=max_daily,
    )


# ── 테스트 ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_allowed_cash_basic(db: AsyncSession) -> None:
    """budget_pct * available_cash 계산."""
    db.add(_seed_runtime("cross_momentum", budget_pct="0.6000"))
    await db.commit()

    bm = BudgetManager()
    result = await bm.allowed_cash(db, "cross_momentum", 10_000_000)
    assert result == 6_000_000


@pytest.mark.asyncio
async def test_allowed_cash_truncates_to_int(db: AsyncSession) -> None:
    """소수점 이하 내림."""
    db.add(_seed_runtime("short_swing", budget_pct="0.3333"))
    await db.commit()

    bm = BudgetManager()
    result = await bm.allowed_cash(db, "short_swing", 10_000_000)
    assert result == 3_333_000  # 10M * 0.3333 = 3,333,000


@pytest.mark.asyncio
async def test_allowed_cash_missing_strategy(db: AsyncSession) -> None:
    """미등록 전략이면 0 반환."""
    bm = BudgetManager()
    result = await bm.allowed_cash(db, "nonexistent", 10_000_000)
    assert result == 0


@pytest.mark.asyncio
async def test_max_order_amount(db: AsyncSession) -> None:
    """max_order_amount 반환."""
    db.add(_seed_runtime("cross_momentum", max_order=50_000_000))
    await db.commit()

    bm = BudgetManager()
    result = await bm.max_order_amount(db, "cross_momentum")
    assert result == 50_000_000


@pytest.mark.asyncio
async def test_max_order_amount_missing(db: AsyncSession) -> None:
    """미등록 전략이면 0."""
    bm = BudgetManager()
    assert await bm.max_order_amount(db, "nonexistent") == 0


@pytest.mark.asyncio
async def test_max_daily_orders(db: AsyncSession) -> None:
    """max_daily_orders 반환."""
    db.add(_seed_runtime("short_swing", max_daily=20))
    await db.commit()

    bm = BudgetManager()
    result = await bm.max_daily_orders(db, "short_swing")
    assert result == 20


@pytest.mark.asyncio
async def test_max_daily_orders_missing(db: AsyncSession) -> None:
    """미등록 전략이면 0."""
    bm = BudgetManager()
    assert await bm.max_daily_orders(db, "nonexistent") == 0


@pytest.mark.asyncio
async def test_zero_cash(db: AsyncSession) -> None:
    """가용 현금이 0이면 allowed_cash도 0."""
    db.add(_seed_runtime("cross_momentum", budget_pct="0.6000"))
    await db.commit()

    bm = BudgetManager()
    assert await bm.allowed_cash(db, "cross_momentum", 0) == 0
