"""매매 제어 API (KillSwitch) 테스트."""

from httpx import AsyncClient

from src.trading.kill_switch import KillSwitchStatus, _kill_switch_states


class TestSoftStop:
    """POST /api/v1/trading/soft-stop 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        # 전역 상태를 비운다
        _kill_switch_states.clear()

    async def test_soft_stop(self, auth_client: AsyncClient) -> None:
        """soft-stop → SOFT_STOPPED."""
        resp = await auth_client.post("/api/v1/trading/soft-stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == KillSwitchStatus.SOFT_STOPPED

    async def test_soft_stop_requires_auth(self, client: AsyncClient) -> None:
        """미인증 → 거부."""
        resp = await client.post("/api/v1/trading/soft-stop")
        assert resp.status_code in (401, 403)


class TestHardStop:
    """POST /api/v1/trading/hard-stop 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        _kill_switch_states.clear()

    async def test_hard_stop_with_confirm(self, auth_client: AsyncClient) -> None:
        """confirm=True → HARD_STOPPED."""
        resp = await auth_client.post(
            "/api/v1/trading/hard-stop",
            json={"confirm": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == KillSwitchStatus.HARD_STOPPED

    async def test_hard_stop_without_confirm(self, auth_client: AsyncClient) -> None:
        """confirm=False → 400."""
        resp = await auth_client.post(
            "/api/v1/trading/hard-stop",
            json={"confirm": False},
        )
        assert resp.status_code == 400

    async def test_hard_stop_default_confirm_false(self, auth_client: AsyncClient) -> None:
        """confirm 미전달 (기본값 False) → 400."""
        resp = await auth_client.post(
            "/api/v1/trading/hard-stop",
            json={},
        )
        assert resp.status_code == 400

    async def test_hard_stop_requires_auth(self, client: AsyncClient) -> None:
        """미인증 → 거부."""
        resp = await client.post("/api/v1/trading/hard-stop", json={"confirm": True})
        assert resp.status_code in (401, 403)


class TestGetKillSwitchStatus:
    """GET /api/v1/trading/kill-switch-status 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        _kill_switch_states.clear()

    async def test_initial_status_normal(self, auth_client: AsyncClient) -> None:
        """초기 상태는 NORMAL."""
        resp = await auth_client.get("/api/v1/trading/kill-switch-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == KillSwitchStatus.NORMAL

    async def test_status_after_soft_stop(self, auth_client: AsyncClient) -> None:
        """soft-stop 후 상태 조회."""
        await auth_client.post("/api/v1/trading/soft-stop")
        resp = await auth_client.get("/api/v1/trading/kill-switch-status")
        assert resp.status_code == 200
        assert resp.json()["status"] == KillSwitchStatus.SOFT_STOPPED

    async def test_status_requires_auth(self, client: AsyncClient) -> None:
        """미인증 → 거부."""
        resp = await client.get("/api/v1/trading/kill-switch-status")
        assert resp.status_code in (401, 403)


class TestResume:
    """POST /api/v1/trading/resume 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        _kill_switch_states.clear()

    async def test_resume_from_soft_stopped(self, auth_client: AsyncClient) -> None:
        """SOFT_STOPPED → resume → NORMAL."""
        await auth_client.post("/api/v1/trading/soft-stop")
        resp = await auth_client.post("/api/v1/trading/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == KillSwitchStatus.NORMAL

    async def test_resume_from_hard_stopped(self, auth_client: AsyncClient) -> None:
        """HARD_STOPPED → resume → NORMAL."""
        await auth_client.post("/api/v1/trading/hard-stop", json={"confirm": True})
        resp = await auth_client.post("/api/v1/trading/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == KillSwitchStatus.NORMAL

    async def test_resume_from_normal(self, auth_client: AsyncClient) -> None:
        """NORMAL → resume → NORMAL (멱등)."""
        resp = await auth_client.post("/api/v1/trading/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == KillSwitchStatus.NORMAL

    async def test_full_lifecycle(self, auth_client: AsyncClient) -> None:
        """전체 순환: soft-stop → hard-stop → resume."""
        r1 = await auth_client.post("/api/v1/trading/soft-stop")
        assert r1.json()["status"] == KillSwitchStatus.SOFT_STOPPED

        r2 = await auth_client.post("/api/v1/trading/hard-stop", json={"confirm": True})
        assert r2.json()["status"] == KillSwitchStatus.HARD_STOPPED

        r3 = await auth_client.post("/api/v1/trading/resume")
        assert r3.json()["status"] == KillSwitchStatus.NORMAL

    async def test_resume_requires_auth(self, client: AsyncClient) -> None:
        """미인증 → 거부."""
        resp = await client.post("/api/v1/trading/resume")
        assert resp.status_code in (401, 403)
