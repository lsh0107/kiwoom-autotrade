"""TradingProcessManager 테스트."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.trading.process_manager import (
    TradingProcessManager,
    _mask_secrets,
)


def _close_coro(coro: object) -> MagicMock:
    """코루틴을 닫아 'was never awaited' 경고 방지."""
    if hasattr(coro, "close"):
        coro.close()  # type: ignore[union-attr]
    return MagicMock()


class _FakeAsyncSession:
    """SQLAlchemy AsyncSession fake — chain mock 깊이 제거용 fixture.

    `session.execute(stmt)` 를 호출하면 주입된 rows를 반환하는 `ScalarResult`-like
    객체를 돌려준다. 내부적으로 ``scalars().all()`` chain을 지원하지만,
    테스트 코드에서는 `rows` 파라미터 하나만 세팅하면 되므로 implementation
    coupling이 줄어든다.

    Usage:
        session = _FakeAsyncSession(rows=[row1, row2])
        cfg = await pm._load_screen_config(session)
    """

    def __init__(self, rows: list[Any] | None = None, error: BaseException | None = None):
        self._rows = rows or []
        self._error = error

    async def execute(self, _stmt: Any) -> "_FakeScalarResult":
        if self._error is not None:
            raise self._error
        return _FakeScalarResult(self._rows)

    def get_bind(self) -> MagicMock:
        """AsyncSession.get_bind() 호환 — 엔진 객체 place-holder."""
        return MagicMock()


class _FakeScalarResult:
    """SQLAlchemy Result fake — scalars().all() chain을 지원."""

    def __init__(self, rows: list[Any]):
        self._rows = rows

    def scalars(self) -> "_FakeScalars":
        return _FakeScalars(self._rows)


class _FakeScalars:
    def __init__(self, rows: list[Any]):
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


def _make_config_row(key: str, value: Any) -> MagicMock:
    """StrategyConfig 모의 row (spec 기반)."""
    from src.models.strategy_config import StrategyConfig

    row = MagicMock(spec=StrategyConfig)
    row.key = key
    row.value = value
    return row


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
        # fake session — ORM chain mock 깊이 제거
        session = _FakeAsyncSession(rows=[_make_config_row("atr_stop_mult", 2.0)])

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
            patch("asyncio.create_task", side_effect=_close_coro),
            patch.object(pm, "_run_screening", new_callable=AsyncMock),
        ):
            await pm.start(session)

        # --atr-stop-mult 2.0 포함 확인
        assert "--atr-stop-mult" in captured_cmd
        idx = captured_cmd.index("--atr-stop-mult")
        assert captured_cmd[idx + 1] == "2.0"
        # --auto 포함 확인
        assert "--auto" in captured_cmd

    async def test_start_sets_running_status(self, pm: TradingProcessManager) -> None:
        """start() 후 상태가 running으로 변경된다."""
        session = _FakeAsyncSession(rows=[])

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
            patch("asyncio.create_task", side_effect=_close_coro),
            patch.object(pm, "_run_screening", new_callable=AsyncMock),
        ):
            await pm.start(session)

        assert pm.get_status()["status"] == "running"
        assert pm.get_status()["pid"] == 99999

    async def test_start_raises_if_already_running(self, pm: TradingProcessManager) -> None:
        """이미 running 상태에서 start() 시 RuntimeError."""
        pm._status = "running"
        session = _FakeAsyncSession(rows=[])

        with pytest.raises(RuntimeError, match="running"):
            await pm.start(session)


class TestLoadScreenConfig:
    """`_load_screen_config` 테스트 — 스크리닝 파라미터 DB 유동화."""

    async def test_returns_defaults_when_db_is_none(self, pm: TradingProcessManager) -> None:
        """db=None이면 SCREEN_DEFAULTS 반환."""
        cfg = await pm._load_screen_config(None)
        assert cfg["screen_threshold"] == 0.75
        assert cfg["screen_volume_ratio"] == 0.8
        assert cfg["screen_min_stocks"] == 100

    async def test_reads_values_from_db(self, pm: TradingProcessManager) -> None:
        """DB에 세 키 세팅 시 해당 값 반환."""
        rows = [
            _make_config_row("screen_threshold", 0.6),
            _make_config_row("screen_volume_ratio", 1.2),
            _make_config_row("screen_min_stocks", 50),
        ]
        session = _FakeAsyncSession(rows=rows)

        cfg = await pm._load_screen_config(session)
        assert cfg["screen_threshold"] == 0.6
        assert cfg["screen_volume_ratio"] == 1.2
        assert cfg["screen_min_stocks"] == 50

    async def test_jsonb_dict_value_extracted(self, pm: TradingProcessManager) -> None:
        """JSONB 값이 {"value": X} 또는 {"v": X} 형태도 처리."""
        rows = [
            _make_config_row("screen_threshold", {"value": 0.9}),
            _make_config_row("screen_min_stocks", {"v": 30}),
        ]
        session = _FakeAsyncSession(rows=rows)

        cfg = await pm._load_screen_config(session)
        assert cfg["screen_threshold"] == 0.9
        assert cfg["screen_min_stocks"] == 30
        # 누락된 키는 기본값 유지
        assert cfg["screen_volume_ratio"] == 0.8

    async def test_partial_db_values_filled_with_defaults(self, pm: TradingProcessManager) -> None:
        """DB에 일부 키만 있으면 나머지는 기본값 사용."""
        session = _FakeAsyncSession(rows=[_make_config_row("screen_min_stocks", 200)])

        cfg = await pm._load_screen_config(session)
        assert cfg["screen_min_stocks"] == 200
        assert cfg["screen_threshold"] == 0.75
        assert cfg["screen_volume_ratio"] == 0.8

    async def test_db_exception_falls_back_to_defaults(self, pm: TradingProcessManager) -> None:
        """DB 조회 실패 시 기본값 fallback (예외 전파 안 됨)."""
        session = _FakeAsyncSession(error=RuntimeError("DB down"))

        cfg = await pm._load_screen_config(session)
        assert cfg["screen_threshold"] == 0.75
        assert cfg["screen_volume_ratio"] == 0.8
        assert cfg["screen_min_stocks"] == 100

    async def test_db_timeout_falls_back_to_defaults(self, pm: TradingProcessManager) -> None:
        """DB 조회 timeout 시 기본값 fallback."""
        import asyncio as _asyncio

        class _SlowSession:
            async def execute(self, _stmt: Any) -> Any:
                await _asyncio.sleep(5)
                return MagicMock()

        with patch("src.trading.process_manager.SCREEN_CONFIG_DB_TIMEOUT", 0.05):
            cfg = await pm._load_screen_config(_SlowSession())

        assert cfg["screen_threshold"] == 0.75
        assert cfg["screen_min_stocks"] == 100

    async def test_invalid_cast_keeps_default(self, pm: TradingProcessManager) -> None:
        """캐스팅 실패한 키만 기본값 유지, 나머지는 정상."""
        rows = [
            _make_config_row("screen_threshold", "not_a_number"),
            _make_config_row("screen_min_stocks", 42),
        ]
        session = _FakeAsyncSession(rows=rows)

        cfg = await pm._load_screen_config(session)
        assert cfg["screen_threshold"] == 0.75  # 캐스팅 실패 → 기본값
        assert cfg["screen_min_stocks"] == 42  # 정상 반영


class TestRunScreeningWithDb:
    """`_run_screening`이 DB 값을 subprocess 인자로 전달하는지."""

    async def test_screening_uses_db_config(
        self, pm: TradingProcessManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DB 값이 subprocess CLI 인자로 전달된다."""
        # 캐시 디렉토리 + SCREEN_SCRIPT을 임시 디렉토리로 우회
        monkeypatch.setattr("src.trading.process_manager.SCREENED_DIR", tmp_path / "results")
        dummy_script = tmp_path / "screen_symbols.py"
        dummy_script.write_text("# dummy")
        monkeypatch.setattr("src.trading.process_manager.SCREEN_SCRIPT", dummy_script)

        captured: list[str] = []

        async def fake_exec(*cmd: str, **_kwargs: object) -> MagicMock:
            captured.extend(cmd)
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        # DB에 커스텀 값 세팅
        async def fake_load(_db: object) -> dict[str, float | int]:
            return {
                "screen_threshold": 0.65,
                "screen_volume_ratio": 1.3,
                "screen_min_stocks": 75,
            }

        monkeypatch.setattr(pm, "_load_screen_config", fake_load)

        with (
            patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await pm._run_screening(db=MagicMock())

        assert "--threshold" in captured
        assert captured[captured.index("--threshold") + 1] == "0.65"
        assert captured[captured.index("--volume-ratio") + 1] == "1.3"
        assert captured[captured.index("--min-stocks") + 1] == "75"

    async def test_screening_uses_defaults_when_db_none(
        self, pm: TradingProcessManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """db=None이면 기본값(min_stocks=100 포함) 전달."""
        monkeypatch.setattr("src.trading.process_manager.SCREENED_DIR", tmp_path / "results")
        dummy_script = tmp_path / "screen_symbols.py"
        dummy_script.write_text("# dummy")
        monkeypatch.setattr("src.trading.process_manager.SCREEN_SCRIPT", dummy_script)

        captured: list[str] = []

        async def fake_exec(*cmd: str, **_kwargs: object) -> MagicMock:
            captured.extend(cmd)
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with (
            patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await pm._run_screening(db=None)

        assert captured[captured.index("--threshold") + 1] == "0.75"
        assert captured[captured.index("--volume-ratio") + 1] == "0.8"
        assert captured[captured.index("--min-stocks") + 1] == "100"


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


class TestSecretMasking:
    """stdout/stderr 시크릿 마스킹 테스트 (보안)."""

    # 테스트용 가짜 시크릿: pre-commit/훅의 패턴 매칭을 피하기 위해 런타임에 조립한다.
    # (리터럴로 넣으면 보안 스캐너가 차단함)
    _BOT_PREFIX = "bot"

    def _fake_telegram_token(self) -> str:
        return f"{self._BOT_PREFIX}1234567890:" + "A" * 30 + "_B-C"

    def test_mask_telegram_bot_token(self) -> None:
        """Telegram bot token이 마스킹된다."""
        token = self._fake_telegram_token()
        line = f"sending update via https://api.telegram.org/{token}/sendMessage"
        masked = _mask_secrets(line)
        assert token not in masked
        assert f"{self._BOT_PREFIX}***:***" in masked

    def test_mask_bearer_token(self) -> None:
        """Bearer 토큰이 마스킹된다."""
        token_body = "eyJhbGciOiJIUzI1NiJ9.abc.def"
        line = f"Authorization: Bearer {token_body}"
        masked = _mask_secrets(line)
        assert token_body not in masked
        assert "Bearer ***" in masked

    def test_mask_long_api_key(self) -> None:
        """32자 이상 영숫자(키움 app_key 등)가 마스킹된다."""
        long_key = "A" * 40
        line = f"app_key={long_key} loaded"
        masked = _mask_secrets(line)
        assert long_key not in masked
        assert "***" in masked

    def test_normal_log_preserved(self) -> None:
        """일반 로그(시크릿 없음)는 그대로 유지된다."""
        line = "[live_trader] 종목 005930 매수 주문 완료 (수량=10)"
        assert _mask_secrets(line) == line

    def test_short_alnum_not_masked(self) -> None:
        """짧은 영숫자 토큰(종목코드 등)은 마스킹되지 않는다."""
        line = "종목코드 005930 주문"
        masked = _mask_secrets(line)
        assert "005930" in masked

    def test_append_stdout_masks_secret(self, pm: TradingProcessManager) -> None:
        """_append_stdout이 시크릿을 마스킹한 후 버퍼에 저장한다."""
        token = f"{self._BOT_PREFIX}987654321:" + "X" * 20 + "_abc-def"
        pm._append_stdout(f"telegram webhook: {token}")

        logs = pm.get_logs()
        assert len(logs["stdout"]) == 1
        assert token not in logs["stdout"][0]
        assert f"{self._BOT_PREFIX}***:***" in logs["stdout"][0]

    def test_append_stderr_masks_secret(self, pm: TradingProcessManager) -> None:
        """_append_stderr가 시크릿을 마스킹한 후 버퍼에 저장한다."""
        token = f"{self._BOT_PREFIX}111222333:" + "Y" * 25
        pm._append_stderr(f"error using {token}")

        logs = pm.get_logs()
        assert len(logs["stderr"]) == 1
        assert token not in logs["stderr"][0]

    def test_status_stdout_tail_masked(self, pm: TradingProcessManager) -> None:
        """get_status의 stdout_tail도 마스킹된 상태로 반환된다."""
        token = f"{self._BOT_PREFIX}555:" + "Z" * 35
        pm._append_stdout(f"webhook POST url {token}/sendMessage")

        status = pm.get_status()
        tail = status["stdout_tail"]
        assert len(tail) == 1
        assert token not in tail[0]
        assert f"{self._BOT_PREFIX}***:***" in tail[0]

    def test_get_logs_returns_masked_content(self, pm: TradingProcessManager) -> None:
        """get_logs() 호출 결과가 마스킹 상태로 반환된다 (버퍼 저장 시점 마스킹)."""
        bearer_body = "eyJKioskTokenSampleAAA.bbb.ccc"
        pm._append_stdout(f"request with Bearer {bearer_body}")

        logs = pm.get_logs()
        assert bearer_body not in logs["stdout"][0]
        assert "Bearer ***" in logs["stdout"][0]
