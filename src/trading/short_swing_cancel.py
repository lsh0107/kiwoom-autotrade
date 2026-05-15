"""Short Swing 미체결 주문 취소 모듈.

설계 문서 8절 — 15:20 또는 제출 후 30분 경과한 미체결 매수 주문을 취소한다.
reason == "short_swing" + side == BUY + status == SUBMITTED + 30분 경과 시 cancel.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order, OrderSide, OrderStatus
from src.trading.order_service import cancel_order
from src.trading.trade_logger import log_trade_event

if TYPE_CHECKING:
    from src.broker.base import BrokerClient

logger = structlog.get_logger("trading.short_swing_cancel")

_DEFAULT_THRESHOLD_MINUTES = 30


async def cancel_stale_buy_orders(
    db: AsyncSession,
    client: BrokerClient,
    *,
    user_id: object,
    now: datetime | None = None,
    threshold_minutes: int = _DEFAULT_THRESHOLD_MINUTES,
) -> dict[str, int]:
    """미체결 short_swing 매수 주문 취소.

    조건:
        - reason LIKE 'short_swing%' (short_swing 태깅 주문)
        - side == BUY
        - status == SUBMITTED
        - submitted_at + threshold_minutes <= now

    Args:
        db: 비동기 DB 세션.
        client: 브로커 클라이언트 (cancel API 호출용).
        user_id: 트레이더 UUID.
        now: 현재 시각 주입 (테스트용). None이면 실제 KST.
        threshold_minutes: 미체결 허용 시간 (분).

    Returns:
        {"cancelled": int, "skipped": int, "errors": int}
    """
    if now is None:
        from src.utils.time import now_kst

        now = now_kst()

    uid = _uuid.UUID(str(user_id))
    cutoff = now - timedelta(minutes=threshold_minutes)

    # 미체결 short_swing 매수 주문 조회 (user_id 스코핑)
    stmt = select(Order).where(
        Order.user_id == uid,
        Order.reason.like("short_swing%"),
        Order.side == OrderSide.BUY,
        Order.status == OrderStatus.SUBMITTED,
        Order.submitted_at <= cutoff,
    )
    result = await db.execute(stmt)
    stale_orders = list(result.scalars().all())

    counts = {"cancelled": 0, "skipped": 0, "errors": 0}

    if not stale_orders:
        await logger.ainfo(
            "미체결 취소 대상 없음",
            threshold_minutes=threshold_minutes,
            cutoff=cutoff.isoformat(),
        )
        return counts

    await logger.ainfo(
        "미체결 취소 대상 발견",
        count=len(stale_orders),
        threshold_minutes=threshold_minutes,
    )

    for order in stale_orders:
        try:
            # 브로커 취소 API 호출
            if order.broker_order_no:
                try:
                    await client.cancel_order(order.broker_order_no)
                except Exception as broker_exc:
                    await logger.awarning(
                        "브로커 취소 API 실패 (DB 상태만 갱신)",
                        order_id=str(order.id),
                        symbol=order.symbol,
                        error=str(broker_exc),
                    )

            # DB 상태 취소
            await cancel_order(db=db, order_id=order.id, user_id=uid)

            await logger.ainfo(
                "미체결 주문 취소 완료",
                order_id=str(order.id),
                symbol=order.symbol,
                price=order.price,
                quantity=order.quantity,
                submitted_at=order.submitted_at.isoformat() if order.submitted_at else None,
                elapsed_minutes=int((now - order.submitted_at).total_seconds() / 60)
                if order.submitted_at
                else None,
            )
            counts["cancelled"] += 1

        except Exception as exc:
            await logger.aerror(
                "미체결 주문 취소 실패",
                order_id=str(order.id),
                symbol=order.symbol,
                error=str(exc),
            )
            await log_trade_event(
                db=db,
                user_id=uid,
                event_type="order_cancel_failed",
                symbol=order.symbol,
                side="buy",
                price=order.price,
                quantity=order.quantity,
                message=f"short_swing 미체결 취소 실패: {exc}",
                order_id=order.id,
                is_mock=order.is_mock,
            )
            counts["errors"] += 1

    await db.commit()
    return counts
