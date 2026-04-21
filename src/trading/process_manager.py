"""live_trader.py 프로세스 관리 — 싱글턴.

연속 모드: 시작 1회 → 매일 장 시작 전 자동 재시작 → 취소 시 루프 탈출.
"""

import asyncio
import signal
import sys
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import BASE_DIR
from src.models.strategy_config import StrategyConfig
from src.utils.secret_masking import mask_secrets as _mask_secrets

logger = structlog.get_logger(__name__)

# 하위 호환: 기존 import 경로 유지 (`from src.trading.process_manager import _mask_secrets`)
__all__ = ["TradingProcessManager", "_mask_secrets"]


# 파일 경로 상수 (프로젝트 루트 기준 절대 경로)
KILL_SWITCH_FILE = BASE_DIR / "data" / ".kill_switch"
PID_FILE = BASE_DIR / "data" / ".trader.pid"
LIVE_TRADER_SCRIPT = BASE_DIR / "scripts" / "live_trader.py"
SCREEN_SCRIPT = BASE_DIR / "scripts" / "screen_symbols.py"
SCREENED_DIR = BASE_DIR / "docs" / "backtest-results"

# 최근 스크리닝 결과 재사용 유효시간 (분). 이 시간 이내면 재스크리닝 스킵
SCREEN_CACHE_MINUTES = 60

# KST 타임존
KST = timezone(timedelta(hours=9))

# 장 시작 전 실행 시각 (HH:MM)
MARKET_PRE_OPEN_HOUR = 8
MARKET_PRE_OPEN_MINUTE = 40

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

# 스크리닝 CLI 인자 기본값 (DB `strategy_config`에 키가 없을 때 fallback).
# admin은 `PUT /api/v1/settings/strategy`로 값 조정 가능.
SCREEN_DEFAULTS: dict[str, float | int] = {
    "screen_threshold": 0.75,
    "screen_volume_ratio": 0.8,
    "screen_min_stocks": 100,
}

# 스크리닝 설정 DB 조회 timeout (초). 초과 시 기본값 fallback.
SCREEN_CONFIG_DB_TIMEOUT = 2.0


class TradingProcessManager:
    """live_trader.py 프로세스를 관리하는 싱글턴.

    연속 모드: 한 번 시작하면 매일 장 시작 전 자동 재시작.
    취소하면 루프 탈출 + 현재 프로세스 종료.
    """

    def __init__(self) -> None:
        """초기화."""
        self._process: asyncio.subprocess.Process | None = None
        self._status: Literal[
            "idle", "starting", "running", "stopping", "crashed", "waiting_next"
        ] = "idle"
        self._started_at: datetime | None = None
        self._stdout_buffer: deque[str] = deque(maxlen=200)
        self._stderr_buffer: deque[str] = deque(maxlen=200)
        self._monitor_task: asyncio.Task[None] | None = None
        self._continuous = False  # 연속 모드 플래그
        self._stop_requested = False  # 취소 요청 플래그
        self._db_factory: object | None = None  # DB 세션 팩토리 (연속 모드용)

    def _append_stdout(self, line: str) -> None:
        """stdout 버퍼에 시크릿 마스킹 후 append."""
        self._stdout_buffer.append(_mask_secrets(line))

    def _append_stderr(self, line: str) -> None:
        """stderr 버퍼에 시크릿 마스킹 후 append."""
        self._stderr_buffer.append(_mask_secrets(line))

    async def start(self, db: AsyncSession) -> None:
        """매매 프로세스를 시작한다 (연속 모드).

        한 번 호출하면 매일 장 시작 전 자동 재시작.

        Args:
            db: DB 세션 (strategy_config 읽기용)
        """
        if self._status in ("starting", "running", "stopping", "waiting_next"):
            raise RuntimeError(f"프로세스가 이미 {self._status} 상태입니다")

        self._continuous = True
        self._stop_requested = False

        # DB 세션 팩토리 저장 (재시작 시 새 세션 필요)
        self._db_factory = db.get_bind()

        await self._launch_process(db)

    async def _launch_process(self, db: AsyncSession) -> None:
        """실제 프로세스 실행."""
        self._status = "starting"
        self._stdout_buffer.clear()
        self._stderr_buffer.clear()

        try:
            # 스크리닝 먼저 실행 (DB에서 screen_* 파라미터 로드)
            await self._run_screening(db)

            # strategy_config에서 인자 빌드
            args = await self._build_args_from_db(db)
            cmd = [sys.executable, str(LIVE_TRADER_SCRIPT), *args]

            logger.info("매매 프로세스 시작", cmd=" ".join(cmd))

            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(BASE_DIR),
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

    async def _load_screen_config(self, db: AsyncSession | None) -> dict[str, float | int]:
        """DB `strategy_config`에서 스크리닝 파라미터를 읽어 반환한다.

        DB 없거나 조회 실패/timeout 시 ``SCREEN_DEFAULTS``를 반환한다 (예외 전파 금지).

        Args:
            db: DB 세션. None이면 기본값 반환.

        Returns:
            3개 키(screen_threshold, screen_volume_ratio, screen_min_stocks)에
            대한 값 딕셔너리. 누락된 키는 기본값으로 채워진다.
        """
        cfg: dict[str, float | int] = dict(SCREEN_DEFAULTS)
        if db is None:
            return cfg

        try:
            result = await asyncio.wait_for(
                db.execute(
                    select(StrategyConfig).where(
                        StrategyConfig.key.in_(list(SCREEN_DEFAULTS.keys()))
                    )
                ),
                timeout=SCREEN_CONFIG_DB_TIMEOUT,
            )
            rows = result.scalars().all()
        except TimeoutError:
            logger.warning(
                "스크리닝 설정 DB 조회 timeout — 기본값 사용",
                timeout=SCREEN_CONFIG_DB_TIMEOUT,
            )
            return cfg
        except Exception:
            logger.warning("스크리닝 설정 DB 조회 실패 — 기본값 사용", exc_info=True)
            return cfg

        for row in rows:
            raw = row.value
            # JSONB 값이 dict로 감싸진 경우 ({"value": X} 또는 {"v": X}) 추출
            if isinstance(raw, dict):
                if "value" in raw:
                    raw = raw["value"]
                elif "v" in raw:
                    raw = raw["v"]
                else:
                    logger.warning(
                        "스크리닝 설정 JSONB 포맷 이상 — 기본값 유지",
                        key=row.key,
                    )
                    continue
            try:
                if row.key == "screen_min_stocks":
                    cfg[row.key] = int(raw)
                else:
                    cfg[row.key] = float(raw)
            except (TypeError, ValueError):
                logger.warning(
                    "스크리닝 설정 캐스팅 실패 — 기본값 유지",
                    key=row.key,
                    raw=repr(raw),
                )

        return cfg

    async def _try_prescreen_cache_bridge(self) -> bool:
        """USE_PRESCREEN_CACHE 플래그 경로 — 캐시 적중 시 True.

        DB에 당일 결과가 있으면 `docs/backtest-results/screened_*.json` 을
        생성해 기존 live_trader 소비 경로와 호환되게 만든다.
        I/O는 blocking 이므로 스레드 offload.

        Returns:
            True: 캐시 적중 → 서브프로세스 스크리닝 스킵.
            False: flag off / 캐시 miss → 기존 경로 수행.
        """
        from src.trading.prescreen_cache import (
            is_prescreen_cache_enabled,
            write_screened_json_from_db,
        )

        if not is_prescreen_cache_enabled():
            return False

        today_kst = datetime.now(tz=KST).date()

        def _bridge() -> str | None:
            path = write_screened_json_from_db(today_kst, SCREENED_DIR)
            return str(path) if path else None

        try:
            out_path = await asyncio.to_thread(_bridge)
        except Exception as exc:
            logger.warning(
                "prescreen_cache 브리지 실패 — subprocess 폴백",
                error=str(exc),
            )
            self._append_stdout(f"[스크리닝] prescreen_cache 브리지 실패 — 폴백: {exc}")
            return False

        if not out_path:
            self._append_stdout(
                "[스크리닝] prescreen_cache 미스(당일 데이터 없음) — 서브프로세스 폴백"
            )
            logger.info("prescreen_cache miss — fallback to subprocess")
            return False

        self._append_stdout(f"[스크리닝] prescreen_cache 적중 → 브리지 파일: {out_path}")
        logger.info("prescreen_cache 적중", bridge_path=out_path)
        return True

    async def _run_screening(self, db: AsyncSession | None = None) -> None:
        """종목 스크리닝 실행 (live_trader 시작 전).

        우선순위:
            1. `USE_PRESCREEN_CACHE=true` 시 DB의 daily_screening_cache 조회 후
               `screened_*.json` 파일로 브리지. 캐시 적중 시 subprocess 스킵.
            2. 최근 SCREEN_CACHE_MINUTES 분 이내에 생성된 스크리닝 JSON이 있으면 재사용.
            3. 그 외에는 `scripts/screen_symbols.py` 서브프로세스 실행.

        CLI 인자(threshold, volume_ratio, min_stocks)는 DB `strategy_config`의
        `screen_*` 키에서 읽는다. DB 미제공/조회 실패 시 ``SCREEN_DEFAULTS``.

        Args:
            db: DB 세션. None이면 기본값으로 스크리닝.
        """
        if not SCREEN_SCRIPT.exists():
            logger.warning("스크리닝 스크립트 없음, 건너뜀: %s", SCREEN_SCRIPT)
            return

        # 1) USE_PRESCREEN_CACHE flag: DB 캐시 → JSON 브리지
        if await self._try_prescreen_cache_bridge():
            return

        # 2) 최근 스크리닝 결과 캐시 확인
        if SCREENED_DIR.exists():
            latest = None
            for f in SCREENED_DIR.glob("screened_*.json"):
                if latest is None or f.stat().st_mtime > latest.stat().st_mtime:
                    latest = f
            if latest is not None:
                age_seconds = datetime.now(tz=UTC).timestamp() - latest.stat().st_mtime
                if age_seconds < SCREEN_CACHE_MINUTES * 60:
                    age_min = int(age_seconds // 60)
                    msg = (
                        f"[스크리닝] 최근 결과 재사용: {latest.name} "
                        f"({age_min}분 전, 재스크리닝 스킵)"
                    )
                    self._append_stdout(msg)
                    logger.info(
                        "스크리닝 캐시 재사용",
                        file=latest.name,
                        age_minutes=age_min,
                    )
                    return

        self._append_stdout("[스크리닝] 종목 스크리닝 시작...")
        logger.info("종목 스크리닝 실행")

        cfg = await self._load_screen_config(db)
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(SCREEN_SCRIPT),
            "--threshold",
            str(cfg["screen_threshold"]),
            "--volume-ratio",
            str(cfg["screen_volume_ratio"]),
            "--min-stocks",
            str(int(cfg["screen_min_stocks"])),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(BASE_DIR),
        )
        stdout, stderr = await proc.communicate()

        if stdout:
            for line in stdout.decode(errors="replace").strip().split("\n"):
                self._append_stdout(f"[스크리닝] {line}")

        if proc.returncode != 0:
            err = stderr.decode(errors="replace") if stderr else "unknown"
            self._append_stdout(f"[스크리닝] 실패 (rc={proc.returncode}): {err}")
            logger.warning("스크리닝 실패", returncode=proc.returncode, stderr=err)
        else:
            self._append_stdout("[스크리닝] 완료")
            logger.info("스크리닝 완료")

        # 스크리닝 후 쿨다운 (레이트 리밋)
        await asyncio.sleep(5)

    async def stop(self) -> None:
        """프로세스 중지 + 연속 모드 해제."""
        self._stop_requested = True
        self._continuous = False

        if self._process is None or self._status == "idle":
            self._status = "idle"
            return

        if self._status == "waiting_next":
            # 다음 장 대기 중이면 바로 idle로
            self._status = "idle"
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
            return

        if self._status == "stopping":
            return

        self._status = "stopping"

        try:
            # 1. kill_switch 파일 생성
            KILL_SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
            KILL_SWITCH_FILE.touch()
            logger.info("kill_switch 파일 생성, 10초 대기")

            # 2. 정상 종료 대기
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
                logger.info("프로세스 정상 종료 (kill_switch)")
                return
            except TimeoutError:
                pass

            # 3. SIGTERM
            if self._process.returncode is None:
                logger.info("SIGTERM 전송")
                self._process.send_signal(signal.SIGTERM)
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=20)
                    return
                except TimeoutError:
                    pass

            # 4. SIGKILL
            if self._process.returncode is None:
                logger.warning("SIGKILL 전송")
                self._process.kill()
                await self._process.wait()

        finally:
            if KILL_SWITCH_FILE.exists():
                KILL_SWITCH_FILE.unlink()
            if PID_FILE.exists():
                PID_FILE.unlink()

            self._status = "idle"
            self._process = None
            self._started_at = None

            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()

    def get_status(self) -> dict:
        """현재 프로세스 상태를 반환한다."""
        uptime_seconds = 0
        if self._started_at is not None:
            delta = datetime.now(tz=UTC) - self._started_at
            uptime_seconds = int(delta.total_seconds())

        return {
            "status": self._status,
            "continuous": self._continuous,
            "pid": self._process.pid
            if self._process and self._process.returncode is None
            else None,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": uptime_seconds,
            "stdout_tail": list(self._stdout_buffer)[-10:],
        }

    def get_logs(self, lines: int = 50) -> dict:
        """stdout/stderr 버퍼를 반환한다."""
        return {
            "stdout": list(self._stdout_buffer)[-lines:],
            "stderr": list(self._stderr_buffer)[-lines:],
        }

    async def _monitor_process(self) -> None:
        """프로세스 모니터링 + 연속 모드 시 자동 재시작."""
        if self._process is None:
            return

        async def _read_stream(stream: asyncio.StreamReader, append: Callable[[str], None]) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                append(line.decode(errors="replace").rstrip())

        tasks = []
        if self._process.stdout:
            tasks.append(
                asyncio.create_task(_read_stream(self._process.stdout, self._append_stdout))
            )
        if self._process.stderr:
            tasks.append(
                asyncio.create_task(_read_stream(self._process.stderr, self._append_stderr))
            )

        # 프로세스 종료 대기
        returncode = await self._process.wait()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # PID 파일 정리
        if PID_FILE.exists():
            PID_FILE.unlink()

        self._process = None

        # 취소 요청이면 루프 탈출
        if self._stop_requested:
            self._status = "idle"
            return

        # 비정상 종료 (crash)
        if returncode != 0:
            logger.error("매매 프로세스 비정상 종료", returncode=returncode)
            self._status = "crashed"
            self._continuous = False
            return

        # 정상 종료 (15:35 자동 종료)
        logger.info("매매 프로세스 정상 종료 (장 마감)", returncode=returncode)
        self._append_stdout(f"[시스템] 장 마감 종료 (returncode={returncode})")

        # 연속 모드: 다음 장 시작까지 대기 후 재시작
        if self._continuous and not self._stop_requested:
            await self._wait_and_restart()

    async def _wait_and_restart(self) -> None:
        """다음 거래일 장 시작 전까지 대기 후 자동 재시작."""
        next_start = self._calc_next_market_open()
        wait_seconds = (next_start - datetime.now(tz=KST)).total_seconds()

        if wait_seconds < 0:
            wait_seconds = 0

        self._status = "waiting_next"
        logger.info(
            "다음 장 시작 대기",
            next_start=next_start.isoformat(),
            wait_seconds=int(wait_seconds),
        )
        self._append_stdout(
            f"[시스템] 다음 장 시작 대기: {next_start.strftime('%m/%d %H:%M')} "
            f"({int(wait_seconds // 3600)}시간 {int((wait_seconds % 3600) // 60)}분 후)"
        )

        # 대기 (1분 단위로 체크 — 취소 요청 감지)
        elapsed = 0.0
        while elapsed < wait_seconds:
            if self._stop_requested:
                self._status = "idle"
                logger.info("대기 중 취소 요청 — 연속 모드 해제")
                return
            await asyncio.sleep(min(60, wait_seconds - elapsed))
            elapsed += 60

        # 다시 시작
        if self._stop_requested:
            self._status = "idle"
            return

        logger.info("연속 모드: 자동 재시작")
        self._append_stdout("[시스템] 연속 모드: 자동 재시작")

        # 새 DB 세션으로 파라미터 다시 읽기
        from src.config.database import async_session_factory

        async with async_session_factory() as db:
            await self._launch_process(db)

    def _calc_next_market_open(self) -> datetime:
        """다음 거래일 장 시작 전 시각을 계산한다 (공휴일/주말 스킵)."""
        from scripts.korean_holidays import is_market_closed

        now = datetime.now(tz=KST)
        target = now.replace(
            hour=MARKET_PRE_OPEN_HOUR,
            minute=MARKET_PRE_OPEN_MINUTE,
            second=0,
            microsecond=0,
        )

        # 오늘 장 시작 시간이 이미 지났으면 내일부터
        if target <= now:
            target += timedelta(days=1)

        # 주말/공휴일 스킵
        for _ in range(10):  # 최대 10일 탐색
            closed, _reason = is_market_closed(target.date())
            if not closed:
                return target
            target += timedelta(days=1)

        return target

    async def _build_args_from_db(self, db: AsyncSession) -> list[str]:
        """strategy_config에서 파라미터를 읽어 CLI 인자를 구성한다."""
        result = await db.execute(
            select(StrategyConfig).where(StrategyConfig.key.in_(list(_CONFIG_KEY_TO_ARG.keys())))
        )
        configs = {row.key: row.value for row in result.scalars().all()}

        args: list[str] = ["--auto"]

        for key, arg_flag in _CONFIG_KEY_TO_ARG.items():
            if key in configs:
                value = configs[key]
                if isinstance(value, dict) and "v" in value:
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
