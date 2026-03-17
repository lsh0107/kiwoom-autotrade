"""TradingProcessManager 테스트."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.trading.process_manager import (
    TradingProcessManager,
)


@pytest.fixture
def pm() -> TradingProcessManager:
    """TradingProcessManager 인스턴스."""
    return TradingProcessManager()


@pytest.fixture(autouse=True)
def cleanup_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트 후 kill_switch/PID 파일 정리."""
    monkeypatch.setattr(
        "src.trading.process_manager.KILL_SWITCH_FILE",
        tmp_path / ".kill_switch",
    )
    monkeypatch.setattr(
        "src.trading.process_manager.PID_FILE",
        tmp_path / ".trader.pid",
    )


class TestProcessManagerStatus:
    """상태 조회 테스트."""

    def test_initial_status_is_idle(self, pm: TradingProcessManager) -> None:
        """초기 상태는 idle."""
        status = pm.get_status()
        assert status["status"] == "idle"
        assert status["pid"] is None
        assert status["started_at"] is None
        assert status["uptime_seconds"] == 0

    def test_logs_empty_initially(self, pm: TradingProcessManager) -> None:
        """초기 로그는 비어있다."""
        logs = pm.get_logs()
        assert logs["stdout"] == []
        assert logs["stderr"] == []

    def test_get_logs_respects_lines_limit(self, pm: TradingProcessManager) -> None:
        """lines 파라미터가 로그 제한을 적용한다."""
        for i in range(20):
            pm._stdout_buffer.append(f"line {i}")

        logs = pm.get_logs(lines=5)
        assert len(logs["stdout"]) == 5
        assert logs["stdout"][-1] == "line 19"


class TestProcessManagerStart:
    """프로세스 시작 테스트."""

    async def test_start_builds_correct_args(
        self, pm: TradingProcessManager, tmp_path: Path
    ) -> None:
        """start()가 DB 파라미터를 CLI 인자로 올바르게 전달한다."""

        # DB mock: atr_stop_mult=2.0 반환 (실제 모델 spec 기반)
        from src.models.strategy_config import StrategyConfig

        mock_db = AsyncMock()
        mock_row1 = MagicMock(spec=StrategyConfig)
        mock_row1.key = "atr_stop_mult"
        mock_row1.value = 2.0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row1]
        mock_db.execute = AsyncMock(return_value=mock_result)

        captured_cmd: list[str] = []

        async def fake_exec(*cmd: str, **_kwargs: object) -> MagicMock:
            captured_cmd.extend(cmd)
            proc = MagicMock()
            proc.pid = 12345
            proc.returncode = None
            proc.stdout = AsyncMock()
            proc.stdout.readline = AsyncMock(return_value=b"")
            proc.stderr = AsyncMock()
            proc.stderr.readline = AsyncMock(return_value=b"")
            proc.wait = AsyncMock(return_value=0)
            return proc

        with (
            patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
            patch("asyncio.create_task"),
            patch.object(pm, "_run_screening", new_callable=AsyncMock),
        ):
            await pm.start(mock_db)

        # --atr-stop-mult 2.0 포함 확인
        assert "--atr-stop-mult" in captured_cmd
        idx = captured_cmd.index("--atr-stop-mult")
        assert captured_cmd[idx + 1] == "2.0"
        # --auto 포함 확인
        assert "--auto" in captured_cmd

    async def test_start_sets_running_status(self, pm: TradingProcessManager) -> None:
        """start() 후 상태가 running으로 변경된다."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        proc = MagicMock()
        proc.pid = 99999
        proc.returncode = None
        proc.stdout = AsyncMock()
        proc.stdout.readline = AsyncMock(return_value=b"")
        proc.stderr = AsyncMock()
        proc.stderr.readline = AsyncMock(return_value=b"")
        proc.wait = AsyncMock(return_value=0)

        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("asyncio.create_task"),
            patch.object(pm, "_run_screening", new_callable=AsyncMock),
        ):
            await pm.start(mock_db)

        assert pm.get_status()["status"] == "running"
        assert pm.get_status()["pid"] == 99999

    async def test_start_raises_if_already_running(self, pm: TradingProcessManager) -> None:
        """이미 running 상태에서 start() 시 RuntimeError."""
        pm._status = "running"

        mock_db = AsyncMock()
        with pytest.raises(RuntimeError, match="running"):
            await pm.start(mock_db)


class TestProcessManagerStop:
    """프로세스 중지 테스트."""

    async def test_stop_creates_kill_switch_file(
        self, pm: TradingProcessManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """stop() 시 kill_switch 파일이 생성된다."""
        ks_file = tmp_path / ".kill_switch"
        monkeypatch.setattr("src.trading.process_manager.KILL_SWITCH_FILE", ks_file)
        monkeypatch.setattr("src.trading.process_manager.PID_FILE", tmp_path / ".trader.pid")

        proc = MagicMock()
        proc.returncode = None
        # wait() 를 호출하면 즉시 0 반환 (정상 종료 시뮬레이션)
        proc.wait = AsyncMock(return_value=0)
        proc.send_signal = MagicMock()
        proc.kill = MagicMock()

        pm._process = proc
        pm._status = "running"

        kill_switch_created = False

        original_touch = Path.touch

        def mock_touch(self: Path, *args: object, **kwargs: object) -> None:
            nonlocal kill_switch_created
            if self == ks_file:
                kill_switch_created = True
            original_touch(self, *args, **kwargs)

        with (
            patch.object(Path, "touch", mock_touch),
            patch("asyncio.wait_for", return_value=0),
        ):
            await pm.stop()

        assert kill_switch_created

    async def test_stop_idle_noop(self, pm: TradingProcessManager) -> None:
        """idle 상태에서 stop() 호출해도 오류 없다."""
        await pm.stop()
        assert pm.get_status()["status"] == "idle"

    async def test_stop_sets_idle_after_completion(
        self, pm: TradingProcessManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """stop() 완료 후 상태가 idle로 변경된다."""
        monkeypatch.setattr("src.trading.process_manager.KILL_SWITCH_FILE", tmp_path / ".ks")
        monkeypatch.setattr("src.trading.process_manager.PID_FILE", tmp_path / ".pid")

        proc = MagicMock()
        proc.returncode = None
        proc.wait = AsyncMock(return_value=0)
        proc.send_signal = MagicMock()
        proc.kill = MagicMock()

        pm._process = proc
        pm._status = "running"

        with patch("asyncio.wait_for", return_value=0):
            await pm.stop()

        assert pm.get_status()["status"] == "idle"
        assert pm.get_status()["pid"] is None


class TestProcessManagerCrash:
    """크래시 감지 테스트."""

    async def test_monitor_detects_crash(self, pm: TradingProcessManager) -> None:
        """비정상 종료(returncode != 0) 시 상태가 crashed로 변경된다."""
        proc = MagicMock()
        proc.returncode = None
        proc.stdout = None
        proc.stderr = None
        # 비정상 종료 코드 반환
        proc.wait = AsyncMock(return_value=1)

        pm._process = proc
        pm._status = "running"

        await pm._monitor_process()

        assert pm._status == "crashed"
        assert pm._process is None
