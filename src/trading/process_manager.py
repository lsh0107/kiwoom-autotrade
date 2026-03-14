"""live_trader.py 프로세스 관리 — 싱글턴."""

import asyncio
import signal
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_config import StrategyConfig

logger = structlog.get_logger(__name__)

# 파일 경로 상수
KILL_SWITCH_FILE = Path("data/.kill_switch")
PID_FILE = Path("data/.trader.pid")
LIVE_TRADER_SCRIPT = Path("scripts/live_trader.py")

# argparse 인자로 연결되는 strategy_config 키 매핑
_CONFIG_KEY_TO_ARG: dict[str, str] = {
    "atr_stop_mult": "--atr-stop-mult",
    "atr_tp_mult": "--atr-tp-mult",
    "min_atr_pct": "--min-atr-pct",
    "min_stop_pct": "--min-stop-pct",
    "force_close_time": "--force-close-time",
    "market_close_time": "--market-close-time",
    "entry_start_time": "--entry-start-time",
    "entry_end_time": "--entry-end-time",
    "max_holding_days": "--max-holding-days",
    "gap_risk_threshold": "--gap-risk-threshold",
    "max_positions": "--max-positions",
}


class TradingProcessManager:
    """live_trader.py 프로세스를 관리하는 싱글턴.

    싱글 인스턴스만 실행 허용. zombie 방지, crash 감지.
    """

    def __init__(self) -> None:
        """초기화."""
        self._process: asyncio.subprocess.Process | None = None
        self._status: Literal["idle", "starting", "running", "stopping", "crashed"] = "idle"
        self._started_at: datetime | None = None
        self._stdout_buffer: deque[str] = deque(maxlen=100)
        self._stderr_buffer: deque[str] = deque(maxlen=100)
        self._monitor_task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def start(self, db: AsyncSession) -> None:
        """live_trader.py 프로세스를 시작한다.

        Args:
            db: DB 세션 (strategy_config 읽기용)

        Raises:
            RuntimeError: 이미 실행 중이거나 starting/stopping 상태
        """
        if self._status in ("starting", "running", "stopping"):
            raise RuntimeError(f"프로세스가 이미 {self._status} 상태입니다")

        self._status = "starting"
        self._stdout_buffer.clear()
        self._stderr_buffer.clear()

        try:
            args = await self._build_args_from_db(db)
            cmd = [sys.executable, str(LIVE_TRADER_SCRIPT), *args]

            logger.info("매매 프로세스 시작", cmd=" ".join(cmd))

            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            self._started_at = datetime.now(tz=UTC)
            self._status = "running"

            # PID 기록
            PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(self._process.pid))

            # 백그라운드 모니터링 시작
            self._monitor_task = asyncio.create_task(self._monitor_process())

            logger.info("매매 프로세스 시작 완료", pid=self._process.pid)

        except Exception:
            self._status = "idle"
            raise

    async def stop(self) -> None:
        """live_trader.py 프로세스를 중지한다.

        순서: kill_switch 파일 생성 → 10초 대기 → SIGTERM → 20초 대기 → SIGKILL
        """
        if self._process is None or self._status == "idle":
            return

        if self._status == "stopping":
            return

        self._status = "stopping"

        try:
            # 1. kill_switch 파일 생성 (정중한 요청)
            KILL_SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
            KILL_SWITCH_FILE.touch()
            logger.info("kill_switch 파일 생성, 10초 대기")

            # 2. 10초 대기 (정상 종료 기회)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
                logger.info("프로세스 정상 종료 (kill_switch 신호)")
                return
            except TimeoutError:
                pass

            # 3. SIGTERM
            if self._process.returncode is None:
                logger.info("SIGTERM 전송")
                self._process.send_signal(signal.SIGTERM)

                try:
                    await asyncio.wait_for(self._process.wait(), timeout=20)
                    logger.info("프로세스 SIGTERM 후 종료")
                    return
                except TimeoutError:
                    pass

            # 4. SIGKILL (최후 수단)
            if self._process.returncode is None:
                logger.warning("SIGKILL 전송 (강제 종료)")
                self._process.kill()
                await self._process.wait()

        finally:
            # kill_switch 파일 삭제
            if KILL_SWITCH_FILE.exists():
                KILL_SWITCH_FILE.unlink()

            # PID 파일 삭제
            if PID_FILE.exists():
                PID_FILE.unlink()

            self._status = "idle"
            self._process = None
            self._started_at = None

            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()

    def get_status(self) -> dict:
        """현재 프로세스 상태를 반환한다.

        Returns:
            status, pid, started_at, uptime_seconds, stdout_tail 포함 딕셔너리
        """
        uptime_seconds = 0
        if self._started_at is not None:
            delta = datetime.now(tz=UTC) - self._started_at
            uptime_seconds = int(delta.total_seconds())

        return {
            "status": self._status,
            "pid": self._process.pid
            if self._process and self._process.returncode is None
            else None,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": uptime_seconds,
            "stdout_tail": list(self._stdout_buffer)[-10:],
        }

    def get_logs(self, lines: int = 50) -> dict:
        """stdout/stderr 버퍼를 반환한다.

        Args:
            lines: 반환할 최대 줄 수

        Returns:
            stdout, stderr 리스트 딕셔너리
        """
        return {
            "stdout": list(self._stdout_buffer)[-lines:],
            "stderr": list(self._stderr_buffer)[-lines:],
        }

    async def _monitor_process(self) -> None:
        """stdout/stderr 읽기 + 프로세스 종료 감지 (백그라운드 태스크)."""
        if self._process is None:
            return

        async def _read_stream(stream: asyncio.StreamReader, buf: deque[str]) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                buf.append(line.decode(errors="replace").rstrip())

        tasks = []
        if self._process.stdout:
            tasks.append(
                asyncio.create_task(_read_stream(self._process.stdout, self._stdout_buffer))
            )
        if self._process.stderr:
            tasks.append(
                asyncio.create_task(_read_stream(self._process.stderr, self._stderr_buffer))
            )

        # 프로세스 종료 대기
        returncode = await self._process.wait()

        # 스트림 읽기 완료 대기
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 비정상 종료 감지
        if self._status == "running":
            logger.error(
                "매매 프로세스 비정상 종료",
                returncode=returncode,
                last_stderr=list(self._stderr_buffer)[-5:],
            )
            self._status = "crashed"
            self._process = None

            # PID 파일 정리
            if PID_FILE.exists():
                PID_FILE.unlink()

    async def _build_args_from_db(self, db: AsyncSession) -> list[str]:
        """strategy_config 테이블에서 파라미터를 읽어 CLI 인자를 구성한다.

        Args:
            db: DB 세션

        Returns:
            argparse 인자 리스트
        """
        result = await db.execute(
            select(StrategyConfig).where(StrategyConfig.key.in_(list(_CONFIG_KEY_TO_ARG.keys())))
        )
        configs = {row.key: row.value for row in result.scalars().all()}

        args: list[str] = ["--auto"]

        for key, arg_flag in _CONFIG_KEY_TO_ARG.items():
            if key in configs:
                value = configs[key]
                # JSON value는 숫자/문자열 — 그대로 str 변환
                if isinstance(value, dict) and "v" in value:
                    # {"v": actual_value} 래핑 형식 지원
                    args.extend([arg_flag, str(value["v"])])
                else:
                    args.extend([arg_flag, str(value)])

        return args

    async def cleanup(self) -> None:
        """앱 종료 시 프로세스 정리."""
        if self._status not in ("idle",):
            logger.info("앱 종료 — 매매 프로세스 cleanup")
            await self.stop()


# 싱글턴 인스턴스
_process_manager: TradingProcessManager | None = None


def get_process_manager() -> TradingProcessManager:
    """프로세스 매니저 싱글턴을 반환한다."""
    global _process_manager
    if _process_manager is None:
        _process_manager = TradingProcessManager()
    return _process_manager
