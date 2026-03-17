"""매매 프로세스 제어 API 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.models.user import User
from src.trading.process_manager import TradingProcessManager


@pytest.fixture
def mock_pm() -> MagicMock:
    """TradingProcessManager 모킹."""
    pm = MagicMock(spec=TradingProcessManager)
    pm.get_status.return_value = {
        "status": "idle",
        "pid": None,
        "started_at": None,
        "uptime_seconds": 0,
        "stdout_tail": [],
    }
    pm.get_logs.return_value = {
        "stdout": [],
        "stderr": [],
    }
    pm.start = AsyncMock()
    pm.stop = AsyncMock()
    return pm


@pytest.fixture
def app_with_pm(app: object, mock_pm: MagicMock) -> object:
    """프로세스 매니저가 주입된 앱."""
    app.state.process_manager = mock_pm  # type: ignore[union-attr]
    return app


class TestTradingStart:
    """POST /bot/trading/start 테스트."""

    async def test_start_idle_process(
        self,
        auth_client: AsyncClient,
        test_user: User,
        app: object,
        mock_pm: MagicMock,
    ) -> None:
        """idle 상태에서 start → starting 응답."""
        app.state.process_manager = mock_pm  # type: ignore[union-attr]

        resp = await auth_client.post("/api/v1/bot/trading/start")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "starting"
        # start()는 백그라운드 태스크(asyncio.create_task)로 실행됨

    async def test_start_already_running(
        self,
        auth_client: AsyncClient,
        test_user: User,
        app: object,
        mock_pm: MagicMock,
    ) -> None:
        """running 상태에서 start → running 응답 (재시작 없음)."""
        mock_pm.get_status.return_value = {
            "status": "running",
            "pid": 12345,
            "started_at": "2026-03-14T09:00:00+00:00",
            "uptime_seconds": 3600,
            "stdout_tail": [],
        }
        app.state.process_manager = mock_pm  # type: ignore[union-attr]

        resp = await auth_client.post("/api/v1/bot/trading/start")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        mock_pm.start.assert_not_called()

    async def test_start_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 401."""
        resp = await client.post("/api/v1/bot/trading/start")
        assert resp.status_code == 401


class TestTradingStop:
    """POST /bot/trading/stop 테스트."""

    async def test_stop_running_process(
        self,
        auth_client: AsyncClient,
        test_user: User,
        app: object,
        mock_pm: MagicMock,
    ) -> None:
        """running 상태에서 stop → stopping 응답."""
        mock_pm.get_status.return_value = {
            "status": "running",
            "pid": 12345,
            "started_at": "2026-03-14T09:00:00+00:00",
            "uptime_seconds": 100,
            "stdout_tail": [],
        }
        app.state.process_manager = mock_pm  # type: ignore[union-attr]

        with patch("asyncio.create_task"):
            resp = await auth_client.post("/api/v1/bot/trading/stop")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopping"

    async def test_stop_idle_process(
        self,
        auth_client: AsyncClient,
        test_user: User,
        app: object,
        mock_pm: MagicMock,
    ) -> None:
        """idle 상태에서 stop → idle 응답 (no-op)."""
        app.state.process_manager = mock_pm  # type: ignore[union-attr]

        resp = await auth_client.post("/api/v1/bot/trading/stop")

        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"


class TestTradingStatus:
    """GET /bot/trading/status 테스트."""

    async def test_get_status_idle(
        self,
        auth_client: AsyncClient,
        test_user: User,
        app: object,
        mock_pm: MagicMock,
    ) -> None:
        """idle 상태 조회."""
        app.state.process_manager = mock_pm  # type: ignore[union-attr]

        resp = await auth_client.get("/api/v1/bot/trading/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["pid"] is None
        assert data["uptime_seconds"] == 0

    async def test_get_status_running(
        self,
        auth_client: AsyncClient,
        test_user: User,
        app: object,
        mock_pm: MagicMock,
    ) -> None:
        """running 상태 조회."""
        mock_pm.get_status.return_value = {
            "status": "running",
            "pid": 42,
            "started_at": "2026-03-14T09:00:00+00:00",
            "uptime_seconds": 7200,
            "stdout_tail": ["log line 1", "log line 2"],
        }
        app.state.process_manager = mock_pm  # type: ignore[union-attr]

        resp = await auth_client.get("/api/v1/bot/trading/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["pid"] == 42
        assert data["uptime_seconds"] == 7200
        assert "log line 1" in data["stdout_tail"]


class TestTradingLogs:
    """GET /bot/trading/logs 테스트."""

    async def test_get_logs(
        self,
        auth_client: AsyncClient,
        test_user: User,
        app: object,
        mock_pm: MagicMock,
    ) -> None:
        """로그 조회 기본."""
        mock_pm.get_logs.return_value = {
            "stdout": ["line A", "line B"],
            "stderr": ["error X"],
        }
        app.state.process_manager = mock_pm  # type: ignore[union-attr]

        resp = await auth_client.get("/api/v1/bot/trading/logs?lines=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["stdout"] == ["line A", "line B"]
        assert data["stderr"] == ["error X"]
        mock_pm.get_logs.assert_called_once_with(lines=10)
