"""strategy_runtime API 테스트 (design-025 3/N)."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_runtime import StrategyRuntime


@pytest.fixture
async def seed_runtime(db: AsyncSession) -> None:
    """기본 시드 3건 (cross_momentum enabled, short_swing/multi_regime disabled)."""
    # 마이그레이션 021 이 시드해두지만 테스트 DB 는 비어있을 수 있으므로 보장.
    from sqlalchemy import select

    existing = await db.execute(select(StrategyRuntime))
    if existing.scalars().first() is not None:
        return

    db.add_all(
        [
            StrategyRuntime(
                strategy="cross_momentum",
                enabled=True,
                budget_pct=Decimal("0.60"),
                max_order_amount=50_000_000,
                max_daily_orders=200,
                updated_by="seed",
            ),
            StrategyRuntime(
                strategy="short_swing",
                enabled=False,
                budget_pct=Decimal("0.30"),
                max_order_amount=5_000_000,
                max_daily_orders=100,
                updated_by="seed",
            ),
            StrategyRuntime(
                strategy="multi_regime",
                enabled=False,
                budget_pct=Decimal("0.00"),
                max_order_amount=1_000_000,
                max_daily_orders=50,
                updated_by="seed",
            ),
        ]
    )
    await db.commit()


class TestListStrategyRuntime:
    async def test_admin_can_list(self, admin_client: AsyncClient, seed_runtime: None) -> None:
        resp = await admin_client.get("/api/v1/strategy/runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        names = {row["strategy"] for row in data}
        assert {"cross_momentum", "short_swing", "multi_regime"}.issubset(names)

    async def test_user_forbidden(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.get("/api/v1/strategy/runtime")
        assert resp.status_code == 403

    async def test_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/strategy/runtime")
        assert resp.status_code == 401


class TestPatchStrategyRuntime:
    async def test_toggle_enabled(self, admin_client: AsyncClient, seed_runtime: None) -> None:
        # short_swing 활성화 — 0.6 + 0.3 = 0.9 OK
        resp = await admin_client.patch(
            "/api/v1/strategy/runtime/short_swing",
            json={"enabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    async def test_budget_overflow_rejected(
        self, admin_client: AsyncClient, seed_runtime: None
    ) -> None:
        # cross_momentum 0.6 + short_swing 0.3 + multi_regime 활성 0.2 → 1.1 초과
        await admin_client.patch(
            "/api/v1/strategy/runtime/short_swing",
            json={"enabled": True},
        )
        resp = await admin_client.patch(
            "/api/v1/strategy/runtime/multi_regime",
            json={"enabled": True, "budget_pct": 0.2},
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        detail = body.get("detail") or body.get("message") or str(body)
        assert "1.0 초과" in detail

    async def test_update_max_order_amount(
        self, admin_client: AsyncClient, seed_runtime: None
    ) -> None:
        resp = await admin_client.patch(
            "/api/v1/strategy/runtime/cross_momentum",
            json={"max_order_amount": 100_000_000},
        )
        assert resp.status_code == 200
        assert resp.json()["max_order_amount"] == 100_000_000

    async def test_unknown_strategy_404(
        self, admin_client: AsyncClient, seed_runtime: None
    ) -> None:
        resp = await admin_client.patch(
            "/api/v1/strategy/runtime/unknown_strategy",
            json={"enabled": True},
        )
        assert resp.status_code == 404

    async def test_budget_pct_range_validation(
        self, admin_client: AsyncClient, seed_runtime: None
    ) -> None:
        resp = await admin_client.patch(
            "/api/v1/strategy/runtime/cross_momentum",
            json={"budget_pct": 1.5},
        )
        assert resp.status_code == 422  # pydantic validation

    async def test_user_forbidden_patch(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.patch(
            "/api/v1/strategy/runtime/cross_momentum",
            json={"enabled": False},
        )
        assert resp.status_code == 403
