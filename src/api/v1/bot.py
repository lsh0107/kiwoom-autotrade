"""AI 자동매매 봇 API 라우터."""

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.ai import AISignal
from src.models.strategy import Strategy, StrategyStatus
from src.models.trade_log import TradeLog
from src.models.user import User
from src.trading.kill_switch import activate_manual_kill, deactivate_manual_kill
from src.utils.exceptions import NotFoundError

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/bot", tags=["자동매매"])


# ── 스키마 ────────────────────────────────────────────


class CreateStrategyRequest(BaseModel):
    """전략 생성 요청."""

    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    symbols: list[str] = Field(default_factory=list)
    max_investment: int = Field(default=1_000_000, gt=0)
    max_loss_pct: float = Field(default=-3.0, le=0)
    max_position_pct: float = Field(default=30.0, gt=0, le=100)


class UpdateStrategyRequest(BaseModel):
    """전략 수정 요청."""

    name: str | None = None
    description: str | None = None
    symbols: list[str] | None = None
    max_investment: int | None = None
    max_loss_pct: float | None = None
    max_position_pct: float | None = None


class StrategyResponse(BaseModel):
    """전략 응답."""

    id: uuid.UUID
    name: str
    description: str
    symbols: list[str]
    status: StrategyStatus
    is_auto_trading: bool
    max_investment: int
    max_loss_pct: float
    max_position_pct: float
    kill_switch_active: bool
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_strategy(cls, s: Strategy) -> "StrategyResponse":
        """Strategy 모델 → 응답."""
        return cls(
            id=s.id,
            name=s.name,
            description=s.description,
            symbols=s.symbols or [],
            status=s.status,
            is_auto_trading=s.is_auto_trading,
            max_investment=s.max_investment,
            max_loss_pct=s.max_loss_pct,
            max_position_pct=s.max_position_pct,
            kill_switch_active=s.kill_switch_active,
            created_at=s.created_at.isoformat() if s.created_at else "",
        )


class SignalResponse(BaseModel):
    """시그널 응답."""

    id: uuid.UUID
    symbol: str
    action: str
    confidence: float
    target_price: int | None
    reasoning: str
    risk_level: str
    is_executed: bool
    rejection_reason: str | None
    created_at: str

    model_config = {"from_attributes": True}


class KillSwitchRequest(BaseModel):
    """킬스위치 요청."""

    active: bool


class TradingProcessResponse(BaseModel):
    """매매 프로세스 제어 응답."""

    status: str
    message: str


class ProcessStatusResponse(BaseModel):
    """프로세스 상태 응답."""

    status: str
    pid: int | None
    started_at: str | None
    uptime_seconds: int
    stdout_tail: list[str]


class ProcessLogsResponse(BaseModel):
    """프로세스 로그 응답."""

    stdout: list[str]
    stderr: list[str]


class TradeHistoryResponse(BaseModel):
    """매매 이력 응답."""

    id: uuid.UUID
    symbol: str
    side: str
    price: int
    quantity: int
    event_type: str
    message: str
    is_mock: bool
    created_at: str

    model_config = {"from_attributes": True}


# ── 엔드포인트 ────────────────────────────────────────


@router.post("/strategies", response_model=StrategyResponse)
async def create_strategy(
    req: CreateStrategyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StrategyResponse:
    """전략 생성."""
    strategy = Strategy(
        user_id=user.id,
        name=req.name,
        description=req.description,
        symbols=req.symbols,
        max_investment=req.max_investment,
        max_loss_pct=req.max_loss_pct,
        max_position_pct=req.max_position_pct,
    )
    db.add(strategy)
    await db.flush()
    return StrategyResponse.from_strategy(strategy)


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[StrategyResponse]:
    """전략 목록."""
    result = await db.execute(
        select(Strategy).where(Strategy.user_id == user.id).order_by(Strategy.created_at.desc())
    )
    return [StrategyResponse.from_strategy(s) for s in result.scalars().all()]


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StrategyResponse:
    """전략 상세."""
    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.user_id != user.id:
        raise NotFoundError("전략")
    return StrategyResponse.from_strategy(strategy)


@router.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    req: UpdateStrategyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StrategyResponse:
    """전략 수정."""
    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.user_id != user.id:
        raise NotFoundError("전략")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(strategy, field, value)

    return StrategyResponse.from_strategy(strategy)


@router.post("/strategies/{strategy_id}/start", response_model=StrategyResponse)
async def start_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StrategyResponse:
    """전략 시작 (자동매매 활성화)."""
    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.user_id != user.id:
        raise NotFoundError("전략")

    strategy.status = StrategyStatus.ACTIVE
    strategy.is_auto_trading = True
    return StrategyResponse.from_strategy(strategy)


@router.post("/strategies/{strategy_id}/stop", response_model=StrategyResponse)
async def stop_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StrategyResponse:
    """전략 중지."""
    strategy = await db.get(Strategy, strategy_id)
    if not strategy or strategy.user_id != user.id:
        raise NotFoundError("전략")

    strategy.status = StrategyStatus.STOPPED
    strategy.is_auto_trading = False
    return StrategyResponse.from_strategy(strategy)


@router.post("/kill-switch")
async def toggle_kill_switch(
    req: KillSwitchRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str | bool]:
    """사용자 수준 킬스위치 토글."""
    if req.active:
        activate_manual_kill(user.id)
    else:
        deactivate_manual_kill(user.id)

    return {"status": "ok", "kill_switch_active": req.active}


@router.get("/signals", response_model=list[SignalResponse])
async def list_signals(
    strategy_id: uuid.UUID | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SignalResponse]:
    """시그널 이력 조회."""
    query = (
        select(AISignal)
        .where(AISignal.user_id == user.id)
        .order_by(AISignal.created_at.desc())
        .limit(limit)
    )
    if strategy_id:
        query = query.where(AISignal.strategy_id == strategy_id)

    result = await db.execute(query)
    signals = result.scalars().all()

    return [
        SignalResponse(
            id=s.id,
            symbol=s.symbol,
            action=s.action,
            confidence=s.confidence,
            target_price=s.target_price,
            reasoning=s.reasoning,
            risk_level=s.risk_level,
            is_executed=s.is_executed,
            rejection_reason=s.rejection_reason,
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in signals
    ]


# ── 프로세스 제어 API ─────────────────────────────────


@router.post("/trading/start", response_model=TradingProcessResponse)
async def start_trading(
    request: Request,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TradingProcessResponse:
    """매매 프로세스를 시작한다."""
    from src.trading.process_manager import TradingProcessManager

    pm: TradingProcessManager = request.app.state.process_manager

    current = pm.get_status()["status"]
    if current in ("starting", "running", "waiting_next"):
        return TradingProcessResponse(
            status=current,
            message="매매 프로세스가 이미 실행 중입니다",
        )

    # 백그라운드에서 시작 (스크리닝 포함이라 시간 소요)
    import asyncio

    async def _start_bg() -> None:
        try:
            await pm.start(db)
        except Exception as e:
            logger.error("프로세스 시작 실패", error=str(e))

    request.app.state._start_task = asyncio.create_task(_start_bg())

    return TradingProcessResponse(
        status="starting",
        message="매매 프로세스를 시작합니다 (스크리닝 중...)",
    )


@router.post("/trading/stop", response_model=TradingProcessResponse)
async def stop_trading(
    request: Request,
    _user: User = Depends(get_current_user),
) -> TradingProcessResponse:
    """매매 프로세스를 중지한다."""
    from src.trading.process_manager import TradingProcessManager

    pm: TradingProcessManager = request.app.state.process_manager

    if pm.get_status()["status"] == "idle":
        return TradingProcessResponse(
            status="idle",
            message="실행 중인 매매 프로세스가 없습니다",
        )

    # 비동기로 중지 시작 (응답 먼저 반환)
    _stop_task = asyncio.create_task(pm.stop())  # noqa: RUF006

    return TradingProcessResponse(
        status="stopping",
        message="매매 프로세스를 중지합니다",
    )


@router.get("/trading/status", response_model=ProcessStatusResponse)
async def get_trading_status(
    request: Request,
    _user: User = Depends(get_current_user),
) -> ProcessStatusResponse:
    """프로세스 상태를 조회한다."""
    from src.trading.process_manager import TradingProcessManager

    pm: TradingProcessManager = request.app.state.process_manager
    data = pm.get_status()

    return ProcessStatusResponse(
        status=data["status"],
        pid=data["pid"],
        started_at=data["started_at"],
        uptime_seconds=data["uptime_seconds"],
        stdout_tail=data["stdout_tail"],
    )


@router.get("/trading/logs", response_model=ProcessLogsResponse)
async def get_trading_logs(
    request: Request,
    _user: User = Depends(get_current_user),
    lines: int = Query(default=50, ge=1, le=500, description="반환할 최대 줄 수"),
) -> ProcessLogsResponse:
    """프로세스 로그를 조회한다."""
    from src.trading.process_manager import TradingProcessManager

    pm: TradingProcessManager = request.app.state.process_manager
    data = pm.get_logs(lines=lines)

    return ProcessLogsResponse(
        stdout=data["stdout"],
        stderr=data["stderr"],
    )


# ── 매매 이력 API ─────────────────────────────────────


@router.get("/trade-history", response_model=list[TradeHistoryResponse])
async def get_trade_history(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=500, description="조회 건수 (최대 500)"),
) -> list[TradeHistoryResponse]:
    """당일 매매 이력을 조회한다.

    created_at 기준 오늘(UTC) 필터링.
    """
    today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(TradeLog)
        .where(TradeLog.user_id == _user.id, TradeLog.created_at >= today_start)
        .order_by(TradeLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        TradeHistoryResponse(
            id=log.id,
            symbol=log.symbol,
            side=log.side,
            price=log.price,
            quantity=log.quantity,
            event_type=log.event_type,
            message=log.message,
            is_mock=log.is_mock,
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in logs
    ]
