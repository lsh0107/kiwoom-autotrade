"""3단계 Kill Switch 시스템."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order, OrderStatus
from src.utils.exceptions import KillSwitchError
from src.utils.time import is_trading_hours, now_kst, today_kst

logger = structlog.get_logger(__name__)


# ── 기본 한도 ─────────────────────────────────────────

MAX_ORDER_AMOUNT = 1_000_000  # 1회 최대 주문 금액 (원)
MAX_DAILY_ORDERS = 100  # 일일 최대 주문 수
MAX_DAILY_LOSS_PCT = -3.0  # 일일 최대 손실률 (%)
PRICE_LIMIT_PCT = 30.0  # 가격제한폭 (±30%)

# ── 드로우다운 임계값 ──────────────────────────────────

DRAWDOWN_STOP_BUY_PCT = -2.0  # -2%: 신규 매수 중단
DRAWDOWN_FORCE_CLOSE_PCT = -3.0  # -3%: 전량 청산
WEEKLY_LOSS_SCALE_PCT = -4.0  # -4%/주: 투자금 축소
WEEKLY_SCALE_FACTOR = 0.5  # 축소 시 50%로


class DrawdownAction(Enum):
    """드로우다운 기반 액션."""

    NONE = "none"
    STOP_BUY = "stop_buy"  # 신규 매수 중단
    FORCE_CLOSE = "force_close"  # 전량 청산


@dataclass
class KillSwitchState:
    """사용자별 Kill Switch 상태."""

    user_id: uuid.UUID
    manual_kill: bool = False
    daily_order_count: int = 0
    daily_pnl: float = 0.0
    last_reset: datetime = field(default_factory=now_kst)

    # 드로우다운 관리
    daily_high_water_mark: int = 0  # 당일 최고 평가액
    daily_start_value: int = 0  # 당일 시작 평가액
    current_drawdown_pct: float = 0.0
    weekly_loss_pct: float = 0.0
    week_start_value: int = 0  # 주간 시작 평가액
    scale_factor: float = 1.0  # 투자금 배수 (기본 1.0, -4%/주 시 0.5)
    last_week_reset: datetime = field(default_factory=now_kst)


# 사용자별 상태 저장 (인메모리)
_user_states: dict[uuid.UUID, KillSwitchState] = {}


def get_user_state(user_id: uuid.UUID) -> KillSwitchState:
    """사용자별 킬스위치 상태 조회/생성."""
    if user_id not in _user_states:
        _user_states[user_id] = KillSwitchState(user_id=user_id)
    state = _user_states[user_id]

    today = today_kst()

    # 날짜 변경 시 일간 데이터 리셋
    if state.last_reset.date() < today.date():
        state.daily_order_count = 0
        state.daily_pnl = 0.0
        state.last_reset = today
        state.daily_start_value = 0
        state.daily_high_water_mark = 0
        state.current_drawdown_pct = 0.0

    # 주 변경 시 주간 데이터 리셋
    current_week = today.date().isocalendar()[:2]
    last_week = state.last_week_reset.date().isocalendar()[:2]
    if current_week != last_week:
        state.week_start_value = 0
        state.weekly_loss_pct = 0.0
        state.last_week_reset = today

    return state


def activate_manual_kill(user_id: uuid.UUID) -> None:
    """수동 킬스위치 활성화."""
    state = get_user_state(user_id)
    state.manual_kill = True
    logger.warning("수동 킬스위치 활성화", user_id=str(user_id))


def deactivate_manual_kill(user_id: uuid.UUID) -> None:
    """수동 킬스위치 해제."""
    state = get_user_state(user_id)
    state.manual_kill = False
    logger.info("수동 킬스위치 해제", user_id=str(user_id))


# ── 드로우다운 관리 ──────────────────────────────────


def update_drawdown(user_id: uuid.UUID, current_value: int) -> DrawdownAction:
    """평가액 기반 드로우다운 체크 및 액션 결정.

    Args:
        user_id: 사용자 ID
        current_value: 현재 총 평가액 (보유종목 평가 + 현금)

    Returns:
        DrawdownAction: NONE / STOP_BUY / FORCE_CLOSE
    """
    state = get_user_state(user_id)

    # 시작값 초기화
    if state.daily_start_value == 0:
        state.daily_start_value = current_value
        state.daily_high_water_mark = current_value
        return DrawdownAction.NONE

    # 고점 갱신
    if current_value > state.daily_high_water_mark:
        state.daily_high_water_mark = current_value

    # 드로우다운 계산 (시작 대비)
    state.current_drawdown_pct = (
        (current_value - state.daily_start_value) / state.daily_start_value * 100
    )

    # 3단계 판정
    if state.current_drawdown_pct <= DRAWDOWN_FORCE_CLOSE_PCT:
        logger.warning(
            "드로우다운 전량 청산 트리거",
            user_id=str(user_id),
            drawdown_pct=state.current_drawdown_pct,
        )
        return DrawdownAction.FORCE_CLOSE
    if state.current_drawdown_pct <= DRAWDOWN_STOP_BUY_PCT:
        logger.warning(
            "드로우다운 신규 매수 중단",
            user_id=str(user_id),
            drawdown_pct=state.current_drawdown_pct,
        )
        return DrawdownAction.STOP_BUY
    return DrawdownAction.NONE


def update_weekly_loss(user_id: uuid.UUID, current_value: int) -> float:
    """주간 손실률 추적 및 스케일 팩터 갱신.

    Args:
        user_id: 사용자 ID
        current_value: 현재 총 평가액

    Returns:
        scale_factor: 투자금 배수 (1.0 = 정상, 0.5 = 축소)
    """
    state = get_user_state(user_id)

    if state.week_start_value == 0:
        state.week_start_value = current_value
        return state.scale_factor

    state.weekly_loss_pct = (current_value - state.week_start_value) / state.week_start_value * 100

    if state.weekly_loss_pct <= WEEKLY_LOSS_SCALE_PCT:
        state.scale_factor = WEEKLY_SCALE_FACTOR
        logger.warning(
            "주간 손실 한도 초과 — 투자금 축소",
            user_id=str(user_id),
            weekly_loss_pct=state.weekly_loss_pct,
            scale_factor=state.scale_factor,
        )
    else:
        state.scale_factor = 1.0

    return state.scale_factor


def check_drawdown(user_id: uuid.UUID, side: str) -> None:
    """드로우다운 상태 기반 매수/청산 차단.

    Args:
        user_id: 사용자 ID
        side: 주문 방향 ("buy" / "sell")

    Raises:
        KillSwitchError: 드로우다운 기준 초과 시
    """
    state = get_user_state(user_id)

    if state.current_drawdown_pct <= DRAWDOWN_FORCE_CLOSE_PCT and side == "buy":
        raise KillSwitchError(
            f"드로우다운 {state.current_drawdown_pct:.1f}%: 신규 매수 금지 (전량 청산 필요)",
            level=2,
        )

    if side == "buy" and state.current_drawdown_pct <= DRAWDOWN_STOP_BUY_PCT:
        raise KillSwitchError(
            f"드로우다운 {state.current_drawdown_pct:.1f}%: 신규 매수 중단",
            level=2,
        )


# ── Level 1: 주문별 검증 ──────────────────────────────


def check_level1(
    *,
    symbol: str,  # noqa: ARG001
    side: str,  # noqa: ARG001
    price: int,
    quantity: int,
    prev_close: int | None = None,
    check_market_hours: bool = True,
) -> None:
    """Level 1 — 개별 주문 검증."""
    order_amount = price * quantity

    # 최대 주문 금액
    if order_amount > MAX_ORDER_AMOUNT:
        raise KillSwitchError(
            f"주문 금액 {order_amount:,}원이 한도 {MAX_ORDER_AMOUNT:,}원 초과",
            level=1,
        )

    # 가격 > 0, 수량 > 0
    if price <= 0 or quantity <= 0:
        raise KillSwitchError("가격과 수량은 0보다 커야 합니다", level=1)

    # 가격제한폭 (전일 종가 대비 ±30%)
    if prev_close and prev_close > 0:
        upper = int(prev_close * (1 + PRICE_LIMIT_PCT / 100))
        lower = int(prev_close * (1 - PRICE_LIMIT_PCT / 100))
        if not lower <= price <= upper:
            raise KillSwitchError(
                f"주문가 {price:,}원이 가격제한폭({lower:,}~{upper:,}) 벗어남",
                level=1,
            )

    # 장 시간 체크
    if check_market_hours and not is_trading_hours():
        raise KillSwitchError("현재 거래 가능 시간이 아닙니다", level=1)


# ── Level 2: 전략별 검증 ──────────────────────────────


def check_level2(
    *,
    order_amount: int,
    max_investment: int = MAX_ORDER_AMOUNT,
    current_invested: int = 0,
    strategy_pnl_pct: float = 0.0,
    max_loss_pct: float = MAX_DAILY_LOSS_PCT,
) -> None:
    """Level 2 — 전략별 검증."""
    # 최대 투자금 초과
    if current_invested + order_amount > max_investment:
        raise KillSwitchError(
            f"전략 투자금 한도 {max_investment:,}원 초과",
            level=2,
        )

    # 최대 손실률
    if strategy_pnl_pct < max_loss_pct:
        raise KillSwitchError(
            f"전략 손실률 {strategy_pnl_pct:.1f}%가 한도 {max_loss_pct:.1f}% 초과",
            level=2,
        )


# ── Level 3: 사용자별 검증 ────────────────────────────


async def check_level3(
    *,
    user_id: uuid.UUID,
    db: AsyncSession,
    max_daily_orders: int = MAX_DAILY_ORDERS,
) -> None:
    """Level 3 — 사용자별 검증 (일일 한도)."""
    state = get_user_state(user_id)

    # 수동 킬스위치
    if state.manual_kill:
        raise KillSwitchError("수동 킬스위치가 활성화되어 있습니다", level=3)

    # 일일 주문 수
    today = today_kst()
    result = await db.execute(
        select(func.count(Order.id)).where(
            Order.user_id == user_id,
            Order.created_at >= today,
            Order.status.notin_([OrderStatus.FAILED, OrderStatus.REJECTED]),
        )
    )
    daily_count = result.scalar() or 0
    if daily_count >= max_daily_orders:
        raise KillSwitchError(
            f"일일 주문 한도 {max_daily_orders}건 도달",
            level=3,
        )


async def run_all_checks(
    *,
    user_id: uuid.UUID,
    symbol: str,
    side: str,
    price: int,
    quantity: int,
    db: AsyncSession,
    prev_close: int | None = None,
    max_investment: int = MAX_ORDER_AMOUNT,
    current_invested: int = 0,
    strategy_pnl_pct: float = 0.0,
    max_loss_pct: float = MAX_DAILY_LOSS_PCT,
    max_daily_orders: int = MAX_DAILY_ORDERS,
    check_market_hours: bool = True,
) -> None:
    """3단계 킬스위치 전체 실행."""
    # Level 1: 주문별
    check_level1(
        symbol=symbol,
        side=side,
        price=price,
        quantity=quantity,
        prev_close=prev_close,
        check_market_hours=check_market_hours,
    )

    # Level 2: 전략별 + 드로우다운
    check_level2(
        order_amount=price * quantity,
        max_investment=max_investment,
        current_invested=current_invested,
        strategy_pnl_pct=strategy_pnl_pct,
        max_loss_pct=max_loss_pct,
    )
    check_drawdown(user_id=user_id, side=side)

    # Level 3: 사용자별
    await check_level3(
        user_id=user_id,
        db=db,
        max_daily_orders=max_daily_orders,
    )

    await logger.ainfo(
        "킬스위치 통과",
        user_id=str(user_id),
        symbol=symbol,
        side=side,
        amount=price * quantity,
    )
