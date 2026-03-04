"""AI 자동매매 봇 API 테스트."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.strategy import Strategy
from src.models.user import User


async def _create_strategy(db: AsyncSession, user: User) -> Strategy:
    """테스트용 전략을 DB에 생성한다."""
    strategy = Strategy(
        user_id=user.id,
        name="테스트전략",
        description="테스트용 전략입니다",
        symbols=["005930", "000660"],
        max_investment=5_000_000,
        max_loss_pct=-3.0,
        max_position_pct=30.0,
    )
    db.add(strategy)
    await db.flush()
    await db.refresh(strategy)
    return strategy


class TestCreateStrategy:
    """전략 생성 테스트."""

    async def test_create_strategy(self, auth_client: AsyncClient, test_user: User) -> None:
        """전략 생성 → 200, 응답 데이터 확인."""
        resp = await auth_client.post(
            "/api/v1/bot/strategies",
            json={
                "name": "새전략",
                "description": "설명",
                "symbols": ["005930"],
                "max_investment": 2_000_000,
                "max_loss_pct": -2.0,
                "max_position_pct": 25.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "새전략"
        assert data["description"] == "설명"
        assert data["symbols"] == ["005930"]
        assert data["status"] == "stopped"
        assert data["is_auto_trading"] is False
        assert data["max_investment"] == 2_000_000


class TestListStrategies:
    """전략 목록 테스트."""

    async def test_list_strategies_empty(self, auth_client: AsyncClient, test_user: User) -> None:
        """전략이 없으면 빈 목록."""
        resp = await auth_client.get("/api/v1/bot/strategies")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_strategies(
        self, auth_client: AsyncClient, test_user: User, db: AsyncSession
    ) -> None:
        """전략 생성 후 목록에 포함."""
        await _create_strategy(db, test_user)
        resp = await auth_client.get("/api/v1/bot/strategies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "테스트전략"


class TestGetStrategy:
    """전략 상세 조회 테스트."""

    async def test_get_strategy(
        self, auth_client: AsyncClient, test_user: User, db: AsyncSession
    ) -> None:
        """전략 상세 조회 → 200."""
        strategy = await _create_strategy(db, test_user)
        resp = await auth_client.get(f"/api/v1/bot/strategies/{strategy.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "테스트전략"
        assert data["symbols"] == ["005930", "000660"]

    async def test_get_nonexistent_strategy(
        self, auth_client: AsyncClient, test_user: User
    ) -> None:
        """존재하지 않는 전략 → 404."""
        fake_id = uuid.uuid4()
        resp = await auth_client.get(f"/api/v1/bot/strategies/{fake_id}")
        assert resp.status_code == 404


class TestUpdateStrategy:
    """전략 수정 테스트."""

    async def test_update_strategy(
        self, auth_client: AsyncClient, test_user: User, db: AsyncSession
    ) -> None:
        """전략 수정 → 200, 변경된 값 확인."""
        strategy = await _create_strategy(db, test_user)
        resp = await auth_client.put(
            f"/api/v1/bot/strategies/{strategy.id}",
            json={
                "name": "수정된전략",
                "max_investment": 10_000_000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "수정된전략"
        assert data["max_investment"] == 10_000_000


class TestStartStopStrategy:
    """전략 시작/중지 테스트."""

    async def test_start_strategy(
        self, auth_client: AsyncClient, test_user: User, db: AsyncSession
    ) -> None:
        """전략 시작 → active, is_auto_trading=True."""
        strategy = await _create_strategy(db, test_user)
        resp = await auth_client.post(f"/api/v1/bot/strategies/{strategy.id}/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["is_auto_trading"] is True

    async def test_stop_strategy(
        self, auth_client: AsyncClient, test_user: User, db: AsyncSession
    ) -> None:
        """전략 중지 → stopped, is_auto_trading=False."""
        strategy = await _create_strategy(db, test_user)
        # 먼저 시작
        await auth_client.post(f"/api/v1/bot/strategies/{strategy.id}/start")
        # 중지
        resp = await auth_client.post(f"/api/v1/bot/strategies/{strategy.id}/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["is_auto_trading"] is False


class TestKillSwitch:
    """킬스위치 테스트."""

    async def test_kill_switch_activate(self, auth_client: AsyncClient, test_user: User) -> None:
        """킬스위치 활성화 → ok."""
        resp = await auth_client.post(
            "/api/v1/bot/kill-switch",
            json={"active": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["kill_switch_active"] is True

    async def test_kill_switch_deactivate(self, auth_client: AsyncClient, test_user: User) -> None:
        """킬스위치 비활성화 → ok."""
        resp = await auth_client.post(
            "/api/v1/bot/kill-switch",
            json={"active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["kill_switch_active"] is False


class TestGetSignals:
    """시그널 목록 테스트."""

    async def test_get_signals_empty(self, auth_client: AsyncClient, test_user: User) -> None:
        """시그널이 없으면 빈 목록."""
        resp = await auth_client.get("/api/v1/bot/signals")
        assert resp.status_code == 200
        assert resp.json() == []


class TestBotUnauthenticated:
    """미인증 봇 API 테스트."""

    async def test_unauthenticated_strategies(self, client: AsyncClient) -> None:
        """미인증 시 전략 목록 → 401."""
        resp = await client.get("/api/v1/bot/strategies")
        assert resp.status_code == 401

    async def test_unauthenticated_kill_switch(self, client: AsyncClient) -> None:
        """미인증 시 킬스위치 → 401."""
        resp = await client.post(
            "/api/v1/bot/kill-switch",
            json={"active": True},
        )
        assert resp.status_code == 401

    async def test_unauthenticated_signals(self, client: AsyncClient) -> None:
        """미인증 시 시그널 조회 → 401."""
        resp = await client.get("/api/v1/bot/signals")
        assert resp.status_code == 401
