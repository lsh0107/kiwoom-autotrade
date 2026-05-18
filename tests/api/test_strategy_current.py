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


# ── _compute_next_rebalance_kst 단위 테스트 (HOTFIX F.3) ─────────────────────


class TestComputeNextRebalanceKst:
    """_compute_next_rebalance_kst: monthly/weekly 분기 검증."""

    def test_monthly_this_month(self) -> None:
        """monthly + 이번 달 마지막 영업일 미도래 → 이번 달."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        # 2026-05-14 (수), 5월 마지막 영업일 = 2026-05-29 (금)
        result = _compute_next_rebalance_kst(date(2026, 5, 14), freq="monthly")
        assert result == "2026-05-29T14:55:00+09:00"

    def test_monthly_after_last_bd(self) -> None:
        """monthly + 이번 달 마지막 영업일 지남 → 다음 달."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        # 2026-05-30 → 5월 마지막 영업일(29) 지남 → 6월 마지막 영업일
        result = _compute_next_rebalance_kst(date(2026, 5, 30), freq="monthly")
        assert "2026-06" in result
        assert "T14:55:00+09:00" in result

    def test_monthly_on_last_bd_returns_same_day(self) -> None:
        """monthly + 오늘이 마지막 영업일 → 오늘."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        # 2026-12-31 = 목요일 (마지막 영업일)
        result = _compute_next_rebalance_kst(date(2026, 12, 31), freq="monthly")
        assert result == "2026-12-31T14:55:00+09:00"

    def test_weekly_wednesday_returns_this_friday(self) -> None:
        """weekly + 수요일 → 이번 주 금요일."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        # 2026-05-20 = 수요일, 이번 주 금요일 = 2026-05-22
        with patch("src.api.v1.strategy.is_business_day", return_value=True):
            result = _compute_next_rebalance_kst(date(2026, 5, 20), freq="weekly")
        assert result == "2026-05-22T14:55:00+09:00"

    def test_weekly_saturday_returns_next_friday(self) -> None:
        """weekly + 토요일 → 다음 주 금요일."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        # 2026-05-23 = 토요일, 다음 금요일 = 2026-05-29
        with patch("src.api.v1.strategy.is_business_day", return_value=True):
            result = _compute_next_rebalance_kst(date(2026, 5, 23), freq="weekly")
        assert result == "2026-05-29T14:55:00+09:00"

    def test_weekly_friday_returns_today(self) -> None:
        """weekly + 오늘이 금요일 영업일 → 오늘."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        # 2026-05-22 = 금요일
        with patch("src.api.v1.strategy.is_business_day", return_value=True):
            result = _compute_next_rebalance_kst(date(2026, 5, 22), freq="weekly")
        assert result == "2026-05-22T14:55:00+09:00"

    def test_weekly_friday_holiday_fallback_to_thursday(self) -> None:
        """weekly + 금요일 휴장 → 목요일 영업일."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        # 2026-05-20 = 수요일
        # 이번 주 금요일(22) 휴장, 목요일(21) 영업일
        def mock_is_bd(d: date) -> bool:
            return d != date(2026, 5, 22)

        with patch("src.api.v1.strategy.is_business_day", side_effect=mock_is_bd):
            result = _compute_next_rebalance_kst(date(2026, 5, 20), freq="weekly")
        assert result == "2026-05-21T14:55:00+09:00"

    def test_default_freq_is_monthly(self) -> None:
        """freq 미지정 시 monthly 동작."""
        from src.api.v1.strategy import _compute_next_rebalance_kst

        result = _compute_next_rebalance_kst(date(2026, 5, 14))
        assert result == "2026-05-29T14:55:00+09:00"


class TestBuildCrossMomentumDetailWeekly:
    """_build_cross_momentum_detail: weekly freq 시 next_rebalance_kst 검증."""

    def test_weekly_next_rebalance_is_friday(self) -> None:
        """params.rebalance_freq='weekly' → next_rebalance_kst 금요일."""
        from src.api.v1.strategy import _build_cross_momentum_detail
        from src.trading.cross_momentum_rebalance import RebalanceParams

        params = RebalanceParams(rebalance_freq="weekly")
        # 2026-05-20 = 수요일, 이번 주 금요일 = 2026-05-22
        with patch("src.api.v1.strategy.is_business_day", return_value=True):
            detail = _build_cross_momentum_detail(params, 10_000_000, 100, date(2026, 5, 20))

        assert detail.next_rebalance_kst == "2026-05-22T14:55:00+09:00"
