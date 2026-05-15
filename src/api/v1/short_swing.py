"""Short Swing 전략 전용 API 라우터.

설계 문서 9절 — 후보 조회, 스크리닝 실행, 포지션 조회, 진입/청산 체크.
"""

from __future__ import annotations

from datetime import date, datetime

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import ActiveBrokerCredential, CurrentUser, DBSession
from src.config.active_strategy import ActiveStrategy, get_active_strategy
from src.models.order import Order, OrderSide, OrderStatus
from src.models.short_swing import PositionStatus, ShortSwingCandidate, ShortSwingPosition
from src.trading.kill_switch import KillSwitchStatus
from src.trading.kill_switch import kill_switch as ks
from src.trading.short_swing import load_short_swing_params
from src.utils.time import KST

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/short-swing", tags=["Short Swing"])


# ── 응답 스키마 ──────────────────────────────────────────


class ShortSwingStatusResponse(BaseModel):
    """Short Swing 전략 현황."""

    active_strategy: str
    enabled: bool
    next_candidate_screen_at: str
    entry_window: str
    exit_window: str
    open_positions: int
    max_positions: int
    today_new_positions: int
    max_daily_new_positions: int
    kill_switch_active: bool


class CandidateItem(BaseModel):
    """Short Swing 후보 종목 응답 항목."""

    id: str
    trade_date: str
    symbol: str
    name: str
    close: int
    ma20: float
    ma60: float
    high_60d: int
    drawdown_from_high: float
    trading_value: int
    avg_trading_value_20d: int
    return_5d: float
    score: float
    reason_json: dict | None = None


class CandidatesResponse(BaseModel):
    """후보 목록 응답."""

    date: str
    count: int
    candidates: list[CandidateItem]


class ScreenResponse(BaseModel):
    """스크리닝 실행 결과."""

    date: str
    created: int
    sample: list[CandidateItem]


class PositionItem(BaseModel):
    """Short Swing 포지션 응답 항목."""

    id: str
    symbol: str
    name: str
    entry_date: str
    entry_price: int
    quantity: int
    highest_price_since_entry: int
    stop_price: int
    take_profit_price: int
    trailing_armed: bool
    max_holding_until: str
    status: str
    exit_reason: str | None = None
    exit_price: int | None = None
    exit_quantity: int | None = None
    realized_pnl: int | None = None


class PositionsResponse(BaseModel):
    """포지션 목록 응답."""

    count: int
    positions: list[PositionItem]


class EntryCheckResponse(BaseModel):
    """진입 체크 결과."""

    checked: int
    ordered: int
    skipped: list[dict]
    errors: list[dict]
    would_order: list[dict] = []


class ExitCheckResponse(BaseModel):
    """청산 체크 결과."""

    checked: int
    closed: int
    skipped: list[dict]
    actions: list[dict]
    errors: list[dict]
    would_exit: list[dict] = []


# ── 헬퍼 ────────────────────────────────────────────────


def _candidate_to_item(c: ShortSwingCandidate) -> CandidateItem:
    """ShortSwingCandidate ORM → CandidateItem 응답 변환."""
    return CandidateItem(
        id=str(c.id),
        trade_date=c.trade_date.isoformat(),
        symbol=c.symbol,
        name=c.name,
        close=c.close,
        ma20=c.ma20,
        ma60=c.ma60,
        high_60d=c.high_60d,
        drawdown_from_high=c.drawdown_from_high,
        trading_value=c.trading_value,
        avg_trading_value_20d=c.avg_trading_value_20d,
        return_5d=c.return_5d,
        score=c.score,
        reason_json=c.reason_json,
    )


def _position_to_item(p: ShortSwingPosition) -> PositionItem:
    """ShortSwingPosition ORM → PositionItem 응답 변환."""
    return PositionItem(
        id=str(p.id),
        symbol=p.symbol,
        name=p.name,
        entry_date=p.entry_date.isoformat(),
        entry_price=p.entry_price,
        quantity=p.quantity,
        highest_price_since_entry=p.highest_price_since_entry,
        stop_price=p.stop_price,
        take_profit_price=p.take_profit_price,
        trailing_armed=p.trailing_armed,
        max_holding_until=p.max_holding_until.isoformat(),
        status=p.status.value if isinstance(p.status, PositionStatus) else str(p.status),
        exit_reason=p.exit_reason,
        exit_price=p.exit_price,
        exit_quantity=p.exit_quantity,
        realized_pnl=p.realized_pnl,
    )


async def _count_open_positions(db: AsyncSession, user_id: object) -> int:
    """open + pending_entry 상태 포지션 수 조회 (user 스코핑)."""
    result = await db.execute(
        select(func.count(ShortSwingPosition.id)).where(
            ShortSwingPosition.user_id == user_id,
            ShortSwingPosition.status.in_([PositionStatus.OPEN, PositionStatus.PENDING_ENTRY]),
        )
    )
    return result.scalar() or 0


async def _count_today_new_positions(db: AsyncSession, user_id: object) -> int:
    """오늘 short_swing 신규 매수 주문 수."""
    from src.utils.time import now_kst

    today = now_kst().date()
    today_start = datetime(today.year, today.month, today.day, tzinfo=KST)
    result = await db.execute(
        select(func.count(Order.id)).where(
            Order.user_id == user_id,
            Order.side == OrderSide.BUY,
            Order.reason == "short_swing",
            Order.created_at >= today_start,
            Order.status.notin_([OrderStatus.FAILED, OrderStatus.REJECTED, OrderStatus.CANCELLED]),
        )
    )
    return result.scalar() or 0


# ── 엔드포인트 ──────────────────────────────────────────


@router.get("/status", response_model=ShortSwingStatusResponse)
async def get_short_swing_status(
    current_user: CurrentUser,
    db: DBSession,
) -> ShortSwingStatusResponse:
    """Short Swing 전략 현황 조회.

    활성 전략 여부, 파라미터, 포지션 수, kill_switch 상태를 반환한다.
    """
    # TODO: 향후 role=admin 도입 시 권한 강화
    strategy = get_active_strategy()
    is_short_swing = strategy == ActiveStrategy.SHORT_SWING

    if not is_short_swing:
        return ShortSwingStatusResponse(
            active_strategy=strategy.value,
            enabled=False,
            next_candidate_screen_at="15:50",
            entry_window="09:20-13:00",
            exit_window="09:20-15:10",
            open_positions=0,
            max_positions=5,
            today_new_positions=0,
            max_daily_new_positions=2,
            kill_switch_active=False,
        )

    params = await load_short_swing_params(db)
    open_count = await _count_open_positions(db, current_user.id)
    today_new = await _count_today_new_positions(db, current_user.id)
    ks_status = ks.get_status(current_user.id)

    return ShortSwingStatusResponse(
        active_strategy=strategy.value,
        enabled=params.short_swing_enabled,
        next_candidate_screen_at="15:50",
        entry_window=f"{params.entry_start_time}-{params.entry_end_time}",
        exit_window="09:20-15:10",
        open_positions=open_count,
        max_positions=params.max_positions,
        today_new_positions=today_new,
        max_daily_new_positions=params.max_daily_new_positions,
        kill_switch_active=ks_status != KillSwitchStatus.NORMAL,
    )


@router.get("/candidates", response_model=CandidatesResponse)
async def get_short_swing_candidates(
    _current_user: CurrentUser,
    db: DBSession,
    date_param: date | None = Query(None, alias="date", description="조회 기준일 (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100),
) -> CandidatesResponse:
    """Short Swing 후보 종목 조회.

    date 미지정 시 가장 최근 trade_date 기준으로 반환한다.
    """
    # TODO: 향후 role=admin 도입 시 권한 강화
    if date_param is None:
        latest = await db.execute(select(func.max(ShortSwingCandidate.trade_date)))
        date_param = latest.scalar()
        if date_param is None:
            return CandidatesResponse(date="", count=0, candidates=[])

    result = await db.execute(
        select(ShortSwingCandidate)
        .where(ShortSwingCandidate.trade_date == date_param)
        .order_by(ShortSwingCandidate.score.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    return CandidatesResponse(
        date=date_param.isoformat(),
        count=len(rows),
        candidates=[_candidate_to_item(c) for c in rows],
    )


@router.post("/screen", response_model=ScreenResponse)
async def run_screen(
    _current_user: CurrentUser,
    db: DBSession,
    date_param: date | None = Query(None, alias="date", description="스크리닝 기준일 (YYYY-MM-DD)"),
) -> ScreenResponse:
    """Short Swing 스크리닝 동기 실행.

    후보를 생성하고 결과를 반환한다.
    """
    # TODO: 향후 role=admin 도입 시 권한 강화
    from src.screening.short_swing_screener import run_short_swing_screening

    if date_param is None:
        from src.utils.time import now_kst

        date_param = now_kst().date()

    candidates = await run_short_swing_screening(db, date_param)

    sample = [_candidate_to_item(c) for c in candidates[:5]]
    return ScreenResponse(
        date=date_param.isoformat(),
        created=len(candidates),
        sample=sample,
    )


@router.get("/positions", response_model=PositionsResponse)
async def get_short_swing_positions(
    current_user: CurrentUser,
    db: DBSession,
    status: str | None = Query(None, description="필터: pending_entry, open, closing, closed"),
    limit: int = Query(50, ge=1, le=200),
) -> PositionsResponse:
    """Short Swing 포지션 조회.

    status 필터로 상태별 조회 가능. user_id 스코핑 적용.
    """
    stmt = select(ShortSwingPosition).where(
        ShortSwingPosition.user_id == current_user.id,
    )

    if status is not None:
        try:
            status_enum = PositionStatus(status)
        except ValueError:
            # 잘못된 status 값 → 빈 결과
            return PositionsResponse(count=0, positions=[])
        stmt = stmt.where(ShortSwingPosition.status == status_enum)

    stmt = stmt.order_by(ShortSwingPosition.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return PositionsResponse(
        count=len(rows),
        positions=[_position_to_item(p) for p in rows],
    )


@router.post("/run-entry-check", response_model=EntryCheckResponse)
async def run_entry_check_endpoint(
    current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
    dry_run: bool = Query(True, description="true면 주문 생성 없이 시뮬레이션만"),
) -> EntryCheckResponse:
    """Short Swing 진입 체크 동기 실행.

    dry_run=true면 후보 평가 + 신호 계산은 정상 수행, 주문 생성/브로커 호출만 skip.
    """
    # TODO: 향후 role=admin 도입 시 권한 강화
    from src.trading.short_swing import run_entry_check

    result = await run_entry_check(
        db,
        _build_broker_client(credential, db),
        user_id=current_user.id,
        dry_run=dry_run,
    )

    return EntryCheckResponse(
        checked=result.checked,
        ordered=result.ordered,
        skipped=result.skipped,
        errors=result.errors,
        would_order=result.would_order,
    )


@router.post("/run-exit-check", response_model=ExitCheckResponse)
async def run_exit_check_endpoint(
    current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
    dry_run: bool = Query(True, description="true면 주문 생성 없이 시뮬레이션만"),
) -> ExitCheckResponse:
    """Short Swing 청산 체크 동기 실행.

    dry_run=true면 청산 조건 평가는 정상 수행, SELL 주문만 skip.
    """
    # TODO: 향후 role=admin 도입 시 권한 강화
    from src.trading.short_swing_exit import run_exit_check

    result = await run_exit_check(
        db,
        _build_broker_client(credential, db),
        user_id=current_user.id,
        dry_run=dry_run,
    )

    return ExitCheckResponse(
        checked=result.checked,
        closed=result.closed,
        skipped=result.skipped,
        actions=[
            {"symbol": a.symbol, "reason": a.reason, "success": a.success, "message": a.message}
            for a in result.actions
        ],
        errors=result.errors,
        would_exit=result.would_exit,
    )


# ── 내부 브로커 클라이언트 빌더 ──────────────────────────


def _build_broker_client(
    credential: object,
    db: AsyncSession,
) -> object:
    """BrokerCredential에서 KiwoomClient를 생성한다."""
    from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
    from src.broker.kiwoom import KiwoomClient
    from src.utils.crypto import decrypt

    return KiwoomClient(
        base_url=MOCK_BASE_URL if credential.is_mock else REAL_BASE_URL,
        app_key=decrypt(credential.encrypted_app_key),
        app_secret=decrypt(credential.encrypted_app_secret),
        is_mock=credential.is_mock,
        db=db,
        credential_id=credential.id,
    )
