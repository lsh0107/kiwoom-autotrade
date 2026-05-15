"""Short Swing API 엔드포인트 테스트."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.active_strategy import ActiveStrategy
from src.models.broker import BrokerCredential
from src.models.short_swing import PositionStatus, ShortSwingCandidate, ShortSwingPosition
from src.models.user import User
from src.utils.crypto import encrypt

KST = timezone(timedelta(hours=9))

# ── fixtures ────────────────────────────────────────────


@pytest.fixture
async def credential_for_ss(db: AsyncSession, test_user: User) -> BrokerCredential:
    """Short Swing 테스트용 브로커 자격증명."""
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


@pytest.fixture
async def _seed_candidates(db: AsyncSession) -> list[ShortSwingCandidate]:
    """테스트용 후보 종목 seed."""
    today = date(2026, 5, 14)
    yesterday = date(2026, 5, 13)
    candidates = [
        ShortSwingCandidate(
            trade_date=today,
            symbol="005930",
            name="삼성전자",
            close=70000,
            ma20=68000.0,
            ma60=65000.0,
            high_60d=75000,
            drawdown_from_high=-0.067,
            trading_value=500_000_000_000,
            avg_trading_value_20d=400_000_000_000,
            return_5d=0.03,
            score=85.5,
            reason_json={"pullback": True},
        ),
        ShortSwingCandidate(
            trade_date=today,
            symbol="000660",
            name="SK하이닉스",
            close=120000,
            ma20=115000.0,
            ma60=110000.0,
            high_60d=130000,
            drawdown_from_high=-0.077,
            trading_value=300_000_000_000,
            avg_trading_value_20d=250_000_000_000,
            return_5d=0.02,
            score=78.2,
            reason_json=None,
        ),
        ShortSwingCandidate(
            trade_date=yesterday,
            symbol="035420",
            name="NAVER",
            close=200000,
            ma20=195000.0,
            ma60=190000.0,
            high_60d=220000,
            drawdown_from_high=-0.091,
            trading_value=100_000_000_000,
            avg_trading_value_20d=90_000_000_000,
            return_5d=0.01,
            score=72.0,
            reason_json=None,
        ),
    ]
    db.add_all(candidates)
    await db.commit()
    for c in candidates:
        await db.refresh(c)
    return candidates


@pytest.fixture
async def _seed_positions(db: AsyncSession) -> list[ShortSwingPosition]:
    """테스트용 포지션 seed."""
    now = datetime(2026, 5, 14, 10, 0, tzinfo=KST)
    positions = [
        ShortSwingPosition(
            symbol="005930",
            name="삼성전자",
            entry_date=date(2026, 5, 12),
            entry_time=now - timedelta(days=2),
            entry_price=69000,
            quantity=10,
            highest_price_since_entry=71000,
            stop_price=67620,
            take_profit_price=71760,
            trailing_armed=False,
            max_holding_until=date(2026, 5, 19),
            status=PositionStatus.OPEN,
        ),
        ShortSwingPosition(
            symbol="000660",
            name="SK하이닉스",
            entry_date=date(2026, 5, 10),
            entry_time=now - timedelta(days=4),
            entry_price=118000,
            quantity=5,
            highest_price_since_entry=122000,
            stop_price=115640,
            take_profit_price=122720,
            trailing_armed=True,
            max_holding_until=date(2026, 5, 17),
            status=PositionStatus.CLOSED,
            exit_reason="take_profit",
        ),
    ]
    db.add_all(positions)
    await db.commit()
    for p in positions:
        await db.refresh(p)
    return positions


def _patch_strategy(strategy: ActiveStrategy):
    """활성 전략 패치."""
    return patch(
        "src.api.v1.short_swing.get_active_strategy",
        return_value=strategy,
    )


# ── 인증 테스트 ────────────────────────────────────────────


class TestShortSwingAuth:
    """미인증 시 401 반환."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/short-swing/status"),
            ("GET", "/api/v1/short-swing/candidates"),
            ("POST", "/api/v1/short-swing/screen"),
            ("GET", "/api/v1/short-swing/positions"),
            ("POST", "/api/v1/short-swing/run-entry-check"),
            ("POST", "/api/v1/short-swing/run-exit-check"),
        ],
    )
    async def test_unauthenticated_returns_401(
        self, client: AsyncClient, method: str, path: str
    ) -> None:
        """미인증 → 401."""
        resp = await client.request(method, path)
        assert resp.status_code in (401, 403)


# ── /status 테스트 ──────────────────────────────────────


class TestShortSwingStatus:
    """GET /api/v1/short-swing/status."""

    async def test_none_strategy_defaults(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """active_strategy=none → enabled=false, open_positions=0."""
        with _patch_strategy(ActiveStrategy.NONE):
            resp = await auth_client.get("/api/v1/short-swing/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_strategy"] == "none"
        assert data["enabled"] is False
        assert data["open_positions"] == 0
        assert data["today_new_positions"] == 0
        assert data["kill_switch_active"] is False
        assert data["entry_window"] == "09:20-13:00"
        assert data["exit_window"] == "09:20-15:10"

    async def test_short_swing_active_with_positions(
        self,
        auth_client: AsyncClient,
        _seed_positions: list[ShortSwingPosition],
    ) -> None:
        """active_strategy=short_swing + DB 포지션 → 값 채움."""
        with _patch_strategy(ActiveStrategy.SHORT_SWING):
            resp = await auth_client.get("/api/v1/short-swing/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_strategy"] == "short_swing"
        assert data["enabled"] is True
        assert data["open_positions"] == 1  # 1 open, 1 closed
        assert data["max_positions"] == 5
        assert data["max_daily_new_positions"] == 2


# ── /candidates 테스트 ──────────────────────────────────


class TestShortSwingCandidates:
    """GET /api/v1/short-swing/candidates."""

    async def test_no_date_returns_latest(
        self,
        auth_client: AsyncClient,
        _seed_candidates: list[ShortSwingCandidate],
    ) -> None:
        """date 미지정 → 가장 최근 trade_date (2026-05-14)."""
        resp = await auth_client.get("/api/v1/short-swing/candidates")

        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-05-14"
        assert data["count"] == 2
        # score 내림차순
        assert data["candidates"][0]["symbol"] == "005930"
        assert data["candidates"][1]["symbol"] == "000660"

    async def test_specific_date(
        self,
        auth_client: AsyncClient,
        _seed_candidates: list[ShortSwingCandidate],
    ) -> None:
        """date=2026-05-13 → 해당 날짜만."""
        resp = await auth_client.get("/api/v1/short-swing/candidates?date=2026-05-13")

        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-05-13"
        assert data["count"] == 1
        assert data["candidates"][0]["symbol"] == "035420"

    async def test_empty_when_no_data(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """데이터 없으면 빈 목록."""
        resp = await auth_client.get("/api/v1/short-swing/candidates")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["candidates"] == []


# ── /positions 테스트 ───────────────────────────────────


class TestShortSwingPositions:
    """GET /api/v1/short-swing/positions."""

    async def test_filter_open(
        self,
        auth_client: AsyncClient,
        _seed_positions: list[ShortSwingPosition],
    ) -> None:
        """status=open → open 포지션만."""
        resp = await auth_client.get("/api/v1/short-swing/positions?status=open")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["positions"][0]["symbol"] == "005930"
        assert data["positions"][0]["status"] == "open"

    async def test_filter_closed(
        self,
        auth_client: AsyncClient,
        _seed_positions: list[ShortSwingPosition],
    ) -> None:
        """status=closed → closed 포지션만."""
        resp = await auth_client.get("/api/v1/short-swing/positions?status=closed")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["positions"][0]["symbol"] == "000660"
        assert data["positions"][0]["exit_reason"] == "take_profit"

    async def test_all_positions(
        self,
        auth_client: AsyncClient,
        _seed_positions: list[ShortSwingPosition],
    ) -> None:
        """status 미지정 → 전체."""
        resp = await auth_client.get("/api/v1/short-swing/positions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2


# ── /screen 테스트 ──────────────────────────────────────


class TestShortSwingScreen:
    """POST /api/v1/short-swing/screen."""

    async def test_screen_creates_candidates(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """스크리닝 실행 → 후보 생성 확인."""
        mock_candidates = [
            ShortSwingCandidate(
                trade_date=date(2026, 5, 15),
                symbol="005930",
                name="삼성전자",
                close=70000,
                ma20=68000.0,
                ma60=65000.0,
                high_60d=75000,
                drawdown_from_high=-0.067,
                trading_value=500_000_000_000,
                avg_trading_value_20d=400_000_000_000,
                return_5d=0.03,
                score=85.5,
                reason_json=None,
            ),
        ]
        with patch(
            "src.screening.short_swing_screener.run_short_swing_screening",
            new_callable=AsyncMock,
            return_value=mock_candidates,
        ):
            resp = await auth_client.post("/api/v1/short-swing/screen?date=2026-05-15")

        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-05-15"
        assert data["created"] == 1
        assert len(data["sample"]) == 1
        assert data["sample"][0]["symbol"] == "005930"


# ── /run-entry-check 테스트 ─────────────────────────────


class TestRunEntryCheck:
    """POST /api/v1/short-swing/run-entry-check."""

    async def test_dry_run_no_orders(
        self,
        auth_client: AsyncClient,
        credential_for_ss: BrokerCredential,
    ) -> None:
        """dry_run=true → active_strategy=none 강제 → 주문 0, mismatch skip."""
        from src.trading.short_swing import EntryResult

        mock_result = EntryResult(
            checked=0,
            ordered=0,
            skipped=[{"reason": "active_strategy_mismatch"}],
            errors=[],
        )
        with patch(
            "src.trading.short_swing.run_entry_check",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await auth_client.post("/api/v1/short-swing/run-entry-check?dry_run=true")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ordered"] == 0
        assert any(s.get("reason") == "active_strategy_mismatch" for s in data["skipped"])


# ── /run-exit-check 테스트 ──────────────────────────────


class TestRunExitCheck:
    """POST /api/v1/short-swing/run-exit-check."""

    async def test_dry_run_no_closes(
        self,
        auth_client: AsyncClient,
        credential_for_ss: BrokerCredential,
    ) -> None:
        """dry_run=true → 청산 0."""
        from src.trading.short_swing_exit import ExitResult

        mock_result = ExitResult(
            checked=0,
            closed=0,
            skipped=[{"reason": "active_strategy_mismatch"}],
            actions=[],
            errors=[],
        )
        with patch(
            "src.trading.short_swing_exit.run_exit_check",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await auth_client.post("/api/v1/short-swing/run-exit-check?dry_run=true")

        assert resp.status_code == 200
        data = resp.json()
        assert data["closed"] == 0


# ── /strategy/current + short_swing 테스트 ──────────────


class TestStrategyCurrentShortSwing:
    """GET /api/v1/strategy/current — short_swing 분기."""

    async def test_short_swing_detail_populated(
        self,
        auth_client: AsyncClient,
        credential_for_ss: BrokerCredential,
        _seed_positions: list[ShortSwingPosition],
    ) -> None:
        """active_strategy=short_swing 시 short_swing 필드 채워짐."""
        with patch(
            "src.api.v1.strategy.get_active_strategy",
            return_value=ActiveStrategy.SHORT_SWING,
        ):
            resp = await auth_client.get("/api/v1/strategy/current")

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_strategy"] == "short_swing"
        assert data["cross_momentum"] is None

        ss = data["short_swing"]
        assert ss is not None
        assert ss["enabled"] is True
        assert ss["max_positions"] == 5
        assert ss["entry_window"] == "09:20-13:00"
        assert ss["exit_window"] == "09:20-15:10"
        assert ss["stop_loss"] == -0.02
        assert ss["take_profit"] == 0.04
        assert ss["trailing_armed_pct"] == 0.03
        assert ss["trailing_stop_pct"] == -0.015
        assert ss["max_holding_days"] == 7
        assert ss["min_order_amount"] == 500_000
        assert ss["cash_buffer_pct"] == 0.15
        assert ss["open_positions"] == 1  # 1 open
        assert ss["today_new_positions"] == 0
