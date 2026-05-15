"""활성 전략 현황 조회 라우터."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import ActiveBrokerCredential, CurrentUser, DBSession
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.config.active_strategy import ActiveStrategy, get_active_strategy
from src.models.broker import BrokerCredential as BrokerCredentialModel
from src.trading.cross_momentum_rebalance import RebalanceParams, load_rebalance_params
from src.utils.crypto import decrypt
from src.utils.krx_calendar import is_business_day

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/strategy", tags=["전략 현황"])


# ── 응답 스키마 ──────────────────────────────────────────


class ExpectedOrdersPreview(BaseModel):
    """예상 주문 프리뷰 (dry-run 결과)."""

    sells: list[str]
    buys: list[str]
    target_symbols: list[str]
    cash_per_position: int
    total_notional: int


class CrossMomentumDetail(BaseModel):
    """Cross-momentum 전략 상세 정보."""

    rebalance_freq: str
    n_positions: int
    top_pct: float | None
    use_vol_filter: bool
    use_trend_filter: bool
    min_order_amount: int
    max_order_amount: int
    cash_buffer_pct: float
    universe_size: int
    next_rebalance_kst: str | None
    formula: str
    target_preview: list[str]
    expected_orders: ExpectedOrdersPreview | None


class ShortSwingDetail(BaseModel):
    """Short Swing 전략 상세 정보."""

    enabled: bool
    entry_window: str
    exit_window: str
    next_candidate_screen_at: str
    max_positions: int
    max_daily_new_positions: int
    stop_loss: float
    take_profit: float
    trailing_armed_pct: float
    trailing_stop_pct: float
    max_holding_days: int
    min_order_amount: int
    cash_buffer_pct: float
    universe_size: int
    open_positions: int
    today_new_positions: int


class StrategyCurrentResponse(BaseModel):
    """활성 전략 현황 응답."""

    active_strategy: str
    cross_momentum: CrossMomentumDetail | None = None
    short_swing: ShortSwingDetail | None = None
    multi_regime: dict | None = None


# ── 헬퍼 ────────────────────────────────────────────────


def _today() -> date:
    """오늘 KST 날짜 반환 (테스트에서 monkeypatch 가능)."""
    from src.utils.time import now_kst

    return now_kst().date()


def _find_last_business_day_of_month(year: int, month: int) -> date:
    """주어진 연월의 마지막 영업일을 반환한다."""
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def _compute_next_rebalance_kst(today: date) -> str:
    """다음 리밸런싱 예정일을 ISO 8601 문자열로 반환한다.

    이번 달 마지막 영업일이 오늘 이후이면 그 날, 아니면 다음 달 마지막 영업일.
    시각은 14:55 KST.
    """
    last_bd = _find_last_business_day_of_month(today.year, today.month)
    if last_bd >= today:
        return f"{last_bd.isoformat()}T14:55:00+09:00"
    # 다음 달
    if today.month == 12:
        next_year, next_month = today.year + 1, 1
    else:
        next_year, next_month = today.year, today.month + 1
    next_last_bd = _find_last_business_day_of_month(next_year, next_month)
    return f"{next_last_bd.isoformat()}T14:55:00+09:00"


async def _fetch_available_cash(
    credential: BrokerCredentialModel,
    db: AsyncSession,
) -> int:
    """브로커에서 주문가능금액을 조회한다. 실패 시 0 반환."""
    client = KiwoomClient(
        base_url=MOCK_BASE_URL if credential.is_mock else REAL_BASE_URL,
        app_key=decrypt(credential.encrypted_app_key),
        app_secret=decrypt(credential.encrypted_app_secret),
        is_mock=credential.is_mock,
        db=db,
        credential_id=credential.id,
    )
    try:
        balance = await client.get_balance()
        return balance.available_cash
    except Exception:
        logger.warning("잔고 조회 실패, available_cash=0 fallback", exc_info=True)
        return 0
    finally:
        await client.close()


def _build_cross_momentum_detail(
    params: RebalanceParams,
    available_cash: int,
    universe_size: int,
    today: date,
) -> CrossMomentumDetail:
    """RebalanceParams + 런타임 데이터로 CrossMomentumDetail을 조립한다."""
    max_order_amount = int(available_cash * params.max_order_amount_pct)
    next_rebalance = _compute_next_rebalance_kst(today)
    formula = f"{params.formation_months}-{params.skip_months}mo momentum"

    return CrossMomentumDetail(
        rebalance_freq=params.rebalance_freq,
        n_positions=params.n_positions,
        top_pct=params.top_pct,
        use_vol_filter=params.use_vol_filter,
        use_trend_filter=params.use_trend_filter,
        min_order_amount=params.min_order_amount,
        max_order_amount=max_order_amount,
        cash_buffer_pct=params.cash_buffer_pct,
        universe_size=universe_size,
        next_rebalance_kst=next_rebalance,
        formula=formula,
        target_preview=[],
        expected_orders=None,
    )


async def _build_short_swing_detail(
    db: AsyncSession,
    user: object,
) -> ShortSwingDetail:
    """DB에서 Short Swing 파라미터 + 런타임 데이터를 읽어 ShortSwingDetail을 조립한다."""
    from datetime import datetime

    from sqlalchemy import func, select

    from src.models.order import Order, OrderSide, OrderStatus
    from src.models.short_swing import PositionStatus, ShortSwingPosition
    from src.trading.short_swing import load_short_swing_params
    from src.utils.time import KST

    params = await load_short_swing_params(db)

    open_result = await db.execute(
        select(func.count(ShortSwingPosition.id)).where(
            ShortSwingPosition.status == PositionStatus.OPEN,
        )
    )
    open_positions = open_result.scalar() or 0

    today = _today()
    today_start = datetime(today.year, today.month, today.day, tzinfo=KST)
    new_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.user_id == user.id,
            Order.side == OrderSide.BUY,
            Order.reason == "short_swing",
            Order.created_at >= today_start,
            Order.status.notin_([OrderStatus.FAILED, OrderStatus.REJECTED, OrderStatus.CANCELLED]),
        )
    )
    today_new = new_result.scalar() or 0

    return ShortSwingDetail(
        enabled=params.short_swing_enabled,
        entry_window=f"{params.entry_start_time}-{params.entry_end_time}",
        exit_window="09:20-15:10",
        next_candidate_screen_at="15:50",
        max_positions=params.max_positions,
        max_daily_new_positions=params.max_daily_new_positions,
        stop_loss=params.stop_loss,
        take_profit=params.take_profit,
        trailing_armed_pct=params.trailing_armed_pct,
        trailing_stop_pct=params.trailing_stop_pct,
        max_holding_days=params.max_holding_days,
        min_order_amount=params.min_order_amount,
        cash_buffer_pct=params.cash_buffer_pct,
        universe_size=params.candidate_limit,
        open_positions=open_positions,
        today_new_positions=today_new,
    )


# ── 엔드포인트 ──────────────────────────────────────────


@router.get("/current", response_model=StrategyCurrentResponse)
async def get_strategy_current(
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
) -> StrategyCurrentResponse:
    """활성 전략 현황과 cross_momentum 상세를 반환한다.

    balance 조회 실패해도 200 응답 (best effort).
    """
    from src.strategy.cross_momentum_universe import FROZEN_UNIVERSE

    strategy = get_active_strategy()

    if strategy == ActiveStrategy.CROSS_MOMENTUM:
        params = await load_rebalance_params(db)
        available_cash = await _fetch_available_cash(credential, db)
        universe_size = len(FROZEN_UNIVERSE)
        today = _today()

        detail = _build_cross_momentum_detail(params, available_cash, universe_size, today)
        return StrategyCurrentResponse(
            active_strategy=strategy.value,
            cross_momentum=detail,
        )

    if strategy == ActiveStrategy.SHORT_SWING:
        ss_detail = await _build_short_swing_detail(db, _current_user)
        return StrategyCurrentResponse(
            active_strategy=strategy.value,
            short_swing=ss_detail,
        )

    return StrategyCurrentResponse(active_strategy=strategy.value)
