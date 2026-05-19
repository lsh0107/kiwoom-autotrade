"""StrategyRegistry 단위 테스트.

design-025: strategy_runtime 테이블 기반 활성 전략 TTL 캐시 조회.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_runtime import StrategyRuntime
from src.trading.strategy_registry import StrategyRegistry

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _make_runtime(
    strategy: str = "cross_momentum",
    enabled: bool = True,
    budget_pct: str = "0.6000",
) -> StrategyRuntime:
    """테스트용 StrategyRuntime 생성."""
    return StrategyRuntime(
        strategy=strategy,
        enabled=enabled,
        budget_pct=Decimal(budget_pct),
        max_order_amount=5_000_000,
        max_daily_orders=100,
    )


# ── 테스트 ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_enabled_returns_only_enabled(db: AsyncSession) -> None:
    """enabled=true 만 반환하는지 확인."""
    db.add(_make_runtime("cross_momentum", enabled=True))
    db.add(_make_runtime("short_swing", enabled=False))
    db.add(_make_runtime("multi_regime", enabled=True))
    await db.commit()

    registry = StrategyRegistry(ttl_seconds=1.0)
    result = await registry.load_enabled(db)

    names = {r.strategy for r in result}
    assert names == {"cross_momentum", "multi_regime"}
    assert len(result) == 2


@pytest.mark.asyncio
async def test_load_enabled_empty_table(db: AsyncSession) -> None:
    """테이블이 비어있으면 빈 리스트 반환."""
    registry = StrategyRegistry()
    result = await registry.load_enabled(db)
    assert result == []


@pytest.mark.asyncio
async def test_ttl_cache_hit(db: AsyncSession) -> None:
    """TTL 이내 재호출 시 캐시 반환 (DB 재조회 안 함)."""
    db.add(_make_runtime("cross_momentum", enabled=True))
    await db.commit()

    registry = StrategyRegistry(ttl_seconds=60.0)  # 긴 TTL

    result1 = await registry.load_enabled(db)
    assert len(result1) == 1

    # DB에서 행 추가 — 캐시 때문에 반영 안 됨
    db.add(_make_runtime("short_swing", enabled=True))
    await db.commit()

    result2 = await registry.load_enabled(db)
    assert len(result2) == 1  # 캐시 — 여전히 1개


@pytest.mark.asyncio
async def test_ttl_cache_expired(db: AsyncSession) -> None:
    """TTL 만료 후 DB 재조회."""
    db.add(_make_runtime("cross_momentum", enabled=True))
    await db.commit()

    registry = StrategyRegistry(ttl_seconds=0.0)  # 즉시 만료

    result1 = await registry.load_enabled(db)
    assert len(result1) == 1

    db.add(_make_runtime("short_swing", enabled=True))
    await db.commit()

    result2 = await registry.load_enabled(db)
    assert len(result2) == 2  # TTL 만료 → 재조회


@pytest.mark.asyncio
async def test_is_enabled(db: AsyncSession) -> None:
    """is_enabled 편의 메서드."""
    db.add(_make_runtime("cross_momentum", enabled=True))
    db.add(_make_runtime("short_swing", enabled=False))
    await db.commit()

    registry = StrategyRegistry(ttl_seconds=1.0)

    assert await registry.is_enabled(db, "cross_momentum") is True
    assert await registry.is_enabled(db, "short_swing") is False
    assert await registry.is_enabled(db, "nonexistent") is False


@pytest.mark.asyncio
async def test_invalidate_clears_cache(db: AsyncSession) -> None:
    """invalidate() 호출 후 DB 재조회."""
    db.add(_make_runtime("cross_momentum", enabled=True))
    await db.commit()

    registry = StrategyRegistry(ttl_seconds=60.0)
    result1 = await registry.load_enabled(db)
    assert len(result1) == 1

    db.add(_make_runtime("short_swing", enabled=True))
    await db.commit()

    # 캐시 유효 → 여전히 1개
    assert len(await registry.load_enabled(db)) == 1

    # invalidate → 재조회
    registry.invalidate()
    result2 = await registry.load_enabled(db)
    assert len(result2) == 2
