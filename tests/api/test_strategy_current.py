"""GET /api/v1/strategy/current 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.active_strategy import ActiveStrategy
from src.models.broker import BrokerCredential
from src.models.strategy_config import StrategyConfig
from src.models.user import User
from src.utils.crypto import encrypt

ENDPOINT = "/api/v1/strategy/current"


# ── fixtures ────────────────────────────────────────────


@pytest.fixture
async def _seed_cross_momentum_config(db: AsyncSession) -> None:
    """cross_momentum.* strategy_config 8개 키를 seed한다."""
    seeds = [
        ("cross_momentum.rebalance_freq", "monthly"),
        ("cross_momentum.n_positions", 5),
        ("cross_momentum.top_pct", 0.20),
        ("cross_momentum.use_vol_filter", False),
        ("cross_momentum.use_trend_filter", False),
        ("cross_momentum.min_order_amount", 500_000),
        ("cross_momentum.max_order_amount_pct", 0.20),
        ("cross_momentum.cash_buffer_pct", 0.10),
    ]
    for key, value in seeds:
        db.add(StrategyConfig(key=key, value=value, description="", updated_by="seed"))
    await db.flush()


@pytest.fixture
async def credential_for_auth(db: AsyncSession, test_user: User) -> BrokerCredential:
    """테스트용 브로커 자격증명 (strategy 엔드포인트용)."""
    cred = BrokerCredential(
        user_id=test_user.id,
        broker_name="kiwoom",
        encrypted_app_key=encrypt("test_app_key"),
        encrypted_app_secret=encrypt("test_app_secret"),
        account_no="1234567890",
        is_mock=True,
        is_active=True,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


def _cm_patches(available_cash: int = 10_000_000, today: date | None = None):
    """cross_momentum 테스트용 공통 patch context manager 목록."""
    patches = [
        patch(
            "src.api.v1.strategy.get_active_strategy",
            return_value=ActiveStrategy.CROSS_MOMENTUM,
        ),
        patch(
            "src.api.v1.strategy._fetch_available_cash",
            new_callable=AsyncMock,
            return_value=available_cash,
        ),
    ]
    if today is not None:
        patches.append(
            patch("src.api.v1.strategy._today", return_value=today),
        )
    return patches


# ── 테스트 ──────────────────────────────────────────────


class TestStrategyCurrentAuth:
    """인증 테스트."""

    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """미인증 → 401."""
        resp = await client.get(ENDPOINT)
        assert resp.status_code in (401, 403)


class TestStrategyNone:
    """ACTIVE_STRATEGY=none 일 때."""

    async def test_none_strategy(
        self,
        auth_client: AsyncClient,
        credential_for_auth: BrokerCredential,
    ) -> None:
        """active_strategy=none → cross_momentum=null."""
        with patch(
            "src.api.v1.strategy.get_active_strategy",
            return_value=ActiveStrategy.NONE,
        ):
            resp = await auth_client.get(ENDPOINT)

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_strategy"] == "none"
        assert data["cross_momentum"] is None
        assert data["multi_regime"] is None


class TestCrossMomentumDetail:
    """ACTIVE_STRATEGY=cross_momentum 일 때."""

    async def test_all_fields_populated(
        self,
        auth_client: AsyncClient,
        credential_for_auth: BrokerCredential,
        _seed_cross_momentum_config: None,
    ) -> None:
        """cross_momentum 활성 시 모든 필드 채워짐."""
        patches = _cm_patches()
        with patches[0], patches[1]:
            resp = await auth_client.get(ENDPOINT)

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_strategy"] == "cross_momentum"

        cm = data["cross_momentum"]
        assert cm is not None
        assert cm["rebalance_freq"] == "monthly"
        assert cm["n_positions"] == 5
        assert cm["top_pct"] == 0.20
        assert cm["use_vol_filter"] is False
        assert cm["use_trend_filter"] is False
        assert cm["min_order_amount"] == 500_000
        assert cm["cash_buffer_pct"] == 0.10
        assert cm["universe_size"] > 0
        assert cm["formula"] == "12-1mo momentum"
        assert cm["target_preview"] == []
        assert cm["expected_orders"] is None

    async def test_max_order_amount_dynamic(
        self,
        auth_client: AsyncClient,
        credential_for_auth: BrokerCredential,
        _seed_cross_momentum_config: None,
    ) -> None:
        """max_order_amount = available_cash x max_order_amount_pct."""
        patches = _cm_patches(available_cash=10_000_000)
        with patches[0], patches[1]:
            resp = await auth_client.get(ENDPOINT)

        assert resp.status_code == 200
        cm = resp.json()["cross_momentum"]
        # 10_000_000 x 0.20 = 2_000_000
        assert cm["max_order_amount"] == 2_000_000

    async def test_next_rebalance_kst_may_2026(
        self,
        auth_client: AsyncClient,
        credential_for_auth: BrokerCredential,
        _seed_cross_momentum_config: None,
    ) -> None:
        """today=2026-05-14 → 다음 리밸런싱 = 2026-05-29 (KRX 기준 5월 마지막 영업일)."""
        fixed_today = date(2026, 5, 14)
        patches = _cm_patches(today=fixed_today)
        with patches[0], patches[1], patches[2]:
            resp = await auth_client.get(ENDPOINT)

        assert resp.status_code == 200
        cm = resp.json()["cross_momentum"]
        assert cm["next_rebalance_kst"] == "2026-05-29T14:55:00+09:00"

    async def test_universe_size_positive(
        self,
        auth_client: AsyncClient,
        credential_for_auth: BrokerCredential,
        _seed_cross_momentum_config: None,
    ) -> None:
        """universe_size > 0."""
        patches = _cm_patches(available_cash=5_000_000)
        with patches[0], patches[1]:
            resp = await auth_client.get(ENDPOINT)

        assert resp.status_code == 200
        assert resp.json()["cross_momentum"]["universe_size"] > 0

    async def test_balance_failure_fallback(
        self,
        auth_client: AsyncClient,
        credential_for_auth: BrokerCredential,
        _seed_cross_momentum_config: None,
    ) -> None:
        """잔고 조회 실패 → max_order_amount=0, 여전히 200."""
        patches = _cm_patches(available_cash=0)
        with patches[0], patches[1]:
            resp = await auth_client.get(ENDPOINT)

        assert resp.status_code == 200
        cm = resp.json()["cross_momentum"]
        assert cm["max_order_amount"] == 0
