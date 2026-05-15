"""Short Swing 장중 청산 엔진.

설계 문서 7절 — 09:20~15:10 보유 포지션 감시, 청산 조건 충족 시 지정가 매도.
우선순위: kill_switch > ma20_pending > stop_loss > take_profit > trailing_stop > max_holding_days.
ma20_breakdown 마킹 후 다음 거래일 첫 사이클에서 우선 청산.
"""

from __future__ import annotations

import math
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import OrderRequest, OrderSideEnum, Quote
from src.config.active_strategy import ActiveStrategy, get_active_strategy
from src.models.order import OrderSide
from src.models.short_swing import ExitReason, PositionStatus, ShortSwingPosition
from src.trading.kill_switch import KillSwitchStatus
from src.trading.kill_switch import kill_switch as ks
from src.trading.order_service import CreateOrderParams, create_order, submit_order
from src.trading.short_swing import load_short_swing_params
from src.trading.trade_logger import log_trade_event

if TYPE_CHECKING:
    from src.broker.base import BrokerClient

logger = structlog.get_logger("trading.short_swing_exit")

# ── 청산 시간 범위 ───────────────────────────────────────────────────────────

_EXIT_START = time(9, 20)
_EXIT_END = time(15, 10)


# ── 결과 ─────────────────────────────────────────────────────────────────────


@dataclass
class ExitAction:
    """개별 포지션 청산 결과."""

    symbol: str
    reason: str
    success: bool
    message: str = ""


@dataclass
class ExitResult:
    """한 번의 run_exit_check 실행 결과."""

    checked: int = 0
    closed: int = 0
    skipped: list[dict[str, str]] = field(default_factory=list)
    actions: list[ExitAction] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    would_exit: list[dict[str, object]] = field(default_factory=list)


# ── MA20 이탈 체크 ──────────────────────────────────────────────────────────

_MA20_PERIOD = 20


async def _check_ma20_breakdown(db: AsyncSession, symbol: str) -> bool:
    """직전 영업일 종가가 MA20 미만인지 확인한다.

    daily_candles 테이블에서 최근 20일 종가를 조회하여 MA20 계산.
    종가 < MA20 이면 True (ma20_breakdown 후보).

    Args:
        db: 비동기 DB 세션.
        symbol: 종목 코드.

    Returns:
        True이면 MA20 이탈 상태.
    """
    from src.models.daily_candle import DailyCandle

    stmt = (
        select(DailyCandle.close)
        .where(DailyCandle.symbol == symbol)
        .order_by(DailyCandle.date.desc())
        .limit(_MA20_PERIOD)
    )
    result = await db.execute(stmt)
    closes = list(result.scalars().all())

    if len(closes) < _MA20_PERIOD:
        await logger.adebug(
            "MA20 체크 스킵: 캔들 부족",
            symbol=symbol,
            available=len(closes),
            required=_MA20_PERIOD,
        )
        return False

    latest_close = closes[0]
    ma20 = sum(closes) / _MA20_PERIOD

    breakdown = latest_close < ma20
    if breakdown:
        await logger.ainfo(
            "MA20 이탈 감지",
            symbol=symbol,
            close=latest_close,
            ma20=round(ma20, 2),
        )

    return breakdown


# ── 메인 진입점 ──────────────────────────────────────────────────────────────


async def run_exit_check(
    db: AsyncSession,
    client: BrokerClient,
    *,
    user_id: object,
    now: datetime | None = None,
    dry_run: bool = False,
) -> ExitResult:
    """Short swing 장중 청산 체크 — open 포지션 순회 → 청산 조건 판정 → 지정가 매도.

    Args:
        db: 비동기 DB 세션.
        client: 브로커 클라이언트.
        user_id: 트레이더 UUID.
        now: 현재 시각 주입 (테스트용). None이면 실제 KST.
        dry_run: True이면 SELL 주문 skip, would_exit 반환.

    Returns:
        ExitResult: 체크/청산/스킵/에러 요약.
    """
    result = ExitResult()

    if now is None:
        from src.utils.time import now_kst

        now = now_kst()

    # ── 글로벌 가드 ──────────────────────────────────────────────────────

    # 1) ACTIVE_STRATEGY
    if get_active_strategy() != ActiveStrategy.SHORT_SWING:
        await logger.ainfo("EXIT SKIP: ACTIVE_STRATEGY != short_swing")
        result.skipped.append({"reason": "active_strategy_mismatch"})
        return result

    # 2) 시간 가드
    current_time = now.time()
    if not (_EXIT_START <= current_time <= _EXIT_END):
        await logger.ainfo(
            "EXIT SKIP: 청산 시간 외",
            current=current_time.isoformat(),
            window=f"{_EXIT_START.isoformat()}~{_EXIT_END.isoformat()}",
        )
        result.skipped.append({"reason": "outside_exit_window"})
        return result

    # 3) 파라미터 로드
    params = await load_short_swing_params(db)

    uid = _uuid.UUID(str(user_id))

    # 4) open 포지션 조회 (user_id 스코핑)
    positions_query = select(ShortSwingPosition).where(
        ShortSwingPosition.status == PositionStatus.OPEN,
        ShortSwingPosition.user_id == uid,
    )
    positions_result = await db.execute(positions_query)
    positions = list(positions_result.scalars().all())

    if not positions:
        await logger.ainfo("EXIT SKIP: open 포지션 없음")
        result.skipped.append({"reason": "no_open_positions"})
        return result

    # 5) kill switch 확인 (전체 적용)
    ks_status = ks.get_status(uid)
    kill_switch_active = ks_status != KillSwitchStatus.NORMAL

    today = now.date()

    # ── 포지션별 청산 판정 ────────────────────────────────────────────────

    for pos in positions:
        result.checked += 1

        # 시세 조회
        try:
            quote: Quote = await client.get_quote(pos.symbol)
        except Exception as exc:
            await logger.awarning("시세 조회 실패", symbol=pos.symbol, error=str(exc))
            result.errors.append({"symbol": pos.symbol, "error": str(exc)})
            continue

        current_price = quote.price

        # highest_price_since_entry 갱신
        if current_price > pos.highest_price_since_entry:
            pos.highest_price_since_entry = current_price
            await logger.adebug(
                "최고가 갱신",
                symbol=pos.symbol,
                highest=current_price,
            )

        # trailing_armed 갱신
        trailing_armed_price = math.floor(pos.entry_price * (1 + params.trailing_armed_pct))
        if not pos.trailing_armed and current_price >= trailing_armed_price:
            pos.trailing_armed = True
            await logger.ainfo(
                "트레일링 활성화",
                symbol=pos.symbol,
                current_price=current_price,
                armed_price=trailing_armed_price,
            )

        # ── 청산 조건 평가 (우선순위 위→아래) ────────────────────────────

        exit_reason: str | None = None

        # 1) kill_switch
        if kill_switch_active:
            exit_reason = ExitReason.KILL_SWITCH

        # 2) MA20 이탈 우선 청산 (전일 마킹 → 다음 거래일 즉시 청산)
        if exit_reason is None and pos.exit_reason == ExitReason.MA20_BREAKDOWN:
            exit_reason = ExitReason.MA20_BREAKDOWN
            await logger.ainfo(
                "MA20 이탈 우선 청산 발동 (전일 마킹)",
                symbol=pos.symbol,
                current_price=current_price,
                entry_price=pos.entry_price,
            )

        # 3) stop_loss (stop_loss는 음수, 예: -0.02)
        if exit_reason is None:
            stop_price_calc = math.floor(pos.entry_price * (1 + params.stop_loss))
            if current_price <= stop_price_calc:
                exit_reason = ExitReason.STOP_LOSS

        # 4) take_profit
        if exit_reason is None:
            take_profit_price_calc = math.floor(pos.entry_price * (1 + params.take_profit))
            if current_price >= take_profit_price_calc:
                exit_reason = ExitReason.TAKE_PROFIT

        # 5) trailing_stop (trailing_stop_pct는 음수, 예: -0.015)
        if exit_reason is None and pos.trailing_armed:
            trailing_stop_price = math.floor(
                pos.highest_price_since_entry * (1 + params.trailing_stop_pct)
            )
            if current_price <= trailing_stop_price:
                exit_reason = ExitReason.TRAILING_STOP

        # 6) max_holding_days
        if exit_reason is None and today >= pos.max_holding_until:
            exit_reason = ExitReason.MAX_HOLDING_DAYS

        # 7) ma20_breakdown — 종가 < MA20 시 후보 마킹 (실매도는 다음 거래일)
        if exit_reason is None:
            ma20_breakdown = await _check_ma20_breakdown(db, pos.symbol)
            if ma20_breakdown:
                pos.exit_reason = ExitReason.MA20_BREAKDOWN
                await logger.ainfo(
                    "MA20 이탈 후보 마킹 (다음 거래일 우선 청산)",
                    symbol=pos.symbol,
                    current_price=current_price,
                    entry_price=pos.entry_price,
                )
                result.skipped.append({"symbol": pos.symbol, "reason": "ma20_breakdown_pending"})
                continue

        if exit_reason is None:
            await logger.adebug(
                "EXIT SKIP(종목): 청산 조건 미충족",
                symbol=pos.symbol,
                current_price=current_price,
                entry_price=pos.entry_price,
                trailing_armed=pos.trailing_armed,
            )
            result.skipped.append({"symbol": pos.symbol, "reason": "no_exit_condition"})
            # DB 갱신 (highest_price, trailing_armed)은 flush
            continue

        # ── dry_run: 주문 없이 결과만 수집 ─────────────────────────────
        if dry_run:
            result.would_exit.append(
                {
                    "symbol": pos.symbol,
                    "reason": exit_reason,
                    "current_price": current_price,
                    "entry_price": pos.entry_price,
                    "quantity": pos.quantity,
                }
            )
            continue

        # ── 청산 실행: holdings 검증 후 지정가 전량 매도 ────────────────

        await logger.ainfo(
            "청산 조건 발동",
            symbol=pos.symbol,
            reason=exit_reason,
            current_price=current_price,
            entry_price=pos.entry_price,
        )

        # P1.D: 청산 직전 broker holdings 실보유 검증
        sell_quantity = pos.quantity
        try:
            broker_holdings = await client.get_holdings()
            held = next((h for h in broker_holdings if h.symbol == pos.symbol), None)
            real_qty = held.quantity if held else 0

            if real_qty == 0:
                await logger.aerror(
                    "broker 보유수량 0 — SELL 금지, RECONCILIATION_ERROR 마킹",
                    symbol=pos.symbol,
                    db_quantity=pos.quantity,
                )
                pos.status = PositionStatus.RECONCILIATION_ERROR
                await db.commit()
                result.errors.append(
                    {
                        "symbol": pos.symbol,
                        "error": "broker_holdings_zero",
                    }
                )
                result.actions.append(
                    ExitAction(
                        symbol=pos.symbol,
                        reason=exit_reason,
                        success=False,
                        message="broker holdings=0, RECONCILIATION_ERROR",
                    )
                )
                continue
            if real_qty < pos.quantity:
                await logger.awarning(
                    "broker 보유수량 < DB — 실제 수량으로 SELL",
                    symbol=pos.symbol,
                    db_quantity=pos.quantity,
                    real_quantity=real_qty,
                )
                sell_quantity = real_qty
        except Exception as exc:
            # fail-closed: broker 조회 실패는 위험. SELL skip + 다음 사이클 재시도.
            # DB 수량 기준 SELL 은 "실제 보유 0 인데 매도 시도" 위험을 키움.
            await logger.aerror(
                "broker holdings 조회 실패 — SELL skip, 다음 사이클 재시도",
                symbol=pos.symbol,
                error=str(exc),
            )
            result.errors.append(
                {
                    "symbol": pos.symbol,
                    "error": f"holdings_fetch_failed: {exc}",
                }
            )
            result.actions.append(
                ExitAction(
                    symbol=pos.symbol,
                    reason=exit_reason,
                    success=False,
                    message=f"broker holdings 조회 실패: {exc}",
                )
            )
            continue

        try:
            order_params = CreateOrderParams(
                user_id=uid,
                symbol=pos.symbol,
                symbol_name=pos.name,
                side=OrderSide.SELL,
                price=current_price,
                quantity=sell_quantity,
                reason=f"short_swing_exit:{exit_reason}",
                is_mock=client._is_mock if hasattr(client, "_is_mock") else True,
                prev_close=quote.prev_close,
                check_market_hours=False,
            )
            order = await create_order(db=db, params=order_params)
        except Exception as exc:
            await logger.aerror(
                "청산 주문 생성 실패",
                symbol=pos.symbol,
                error=str(exc),
            )
            result.errors.append({"symbol": pos.symbol, "error": f"create_order: {exc}"})
            result.actions.append(
                ExitAction(symbol=pos.symbol, reason=exit_reason, success=False, message=str(exc))
            )
            continue

        # 브로커 주문 제출
        try:
            broker_req = OrderRequest(
                symbol=pos.symbol,
                side=OrderSideEnum.SELL,
                price=current_price,
                quantity=sell_quantity,
            )
            broker_resp = await client.place_order(broker_req)
            await submit_order(db=db, order=order, broker_response=broker_resp)
        except Exception as exc:
            await logger.aerror(
                "청산 브로커 주문 제출 실패",
                symbol=pos.symbol,
                error=str(exc),
            )
            # order_failed 이벤트 기록
            await log_trade_event(
                db=db,
                user_id=uid,
                event_type="order_failed",
                symbol=pos.symbol,
                side="sell",
                price=current_price,
                quantity=sell_quantity,
                message=f"short_swing 청산 브로커 실패: {exc}",
                order_id=order.id,
                is_mock=order.is_mock,
            )
            result.errors.append({"symbol": pos.symbol, "error": f"submit_order: {exc}"})
            result.actions.append(
                ExitAction(symbol=pos.symbol, reason=exit_reason, success=False, message=str(exc))
            )
            # status 유지 (open) — 다음 사이클에서 재시도
            continue

        # 브로커 응답 확인
        if broker_resp.status == "submitted":
            # closing → 체결 reconciler 가 CLOSED 전이
            pos.status = PositionStatus.CLOSING
            pos.exit_reason = exit_reason
            pos.exit_order_id = order.id

            await db.commit()

            await logger.ainfo(
                "short_swing 청산 주문 성공",
                symbol=pos.symbol,
                reason=exit_reason,
                price=current_price,
                quantity=pos.quantity,
                order_id=str(order.id),
            )

            result.closed += 1
            result.actions.append(ExitAction(symbol=pos.symbol, reason=exit_reason, success=True))
        else:
            # 브로커가 즉시 거부
            await log_trade_event(
                db=db,
                user_id=uid,
                event_type="order_failed",
                symbol=pos.symbol,
                side="sell",
                price=current_price,
                quantity=pos.quantity,
                message=f"short_swing 청산 브로커 거부: {broker_resp.message}",
                order_id=order.id,
                is_mock=order.is_mock,
            )
            result.errors.append(
                {
                    "symbol": pos.symbol,
                    "error": f"broker_rejected: {broker_resp.message}",
                }
            )
            result.actions.append(
                ExitAction(
                    symbol=pos.symbol,
                    reason=exit_reason,
                    success=False,
                    message=broker_resp.message,
                )
            )

    # 모든 포지션 highest_price/trailing_armed 갱신 flush
    await db.commit()

    return result
