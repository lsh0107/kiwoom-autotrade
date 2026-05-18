"""Short Swing 포지션-주문 체결 정합성 reconciler.

HOTFIX A — P0/P1.A:
  - PENDING_ENTRY + BUY FILLED → OPEN 전이 (체결가/수량/시각 반영).
  - PENDING_ENTRY + BUY CANCELLED/REJECTED → row 삭제.
  - PENDING_ENTRY + BUY PARTIAL_FILL → 체결수량 OPEN 1 row, 잔여 PENDING_ENTRY 유지.
  - CLOSING + SELL FILLED → CLOSED 전이 + realized_pnl 계산.
  - CLOSING + SELL CANCELLED/REJECTED → OPEN 복구.

live_trader 메인 루프에 5분 주기로 등록.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order, OrderStatus
from src.models.short_swing import PositionStatus, ShortSwingPosition

if TYPE_CHECKING:
    from src.broker.base import BrokerClient

logger = structlog.get_logger("trading.short_swing_reconciler")


async def reconcile_short_swing_positions(
    db: AsyncSession,
    client: BrokerClient,  # noqa: ARG001  # 향후 broker 상태 조회 확장용
    *,
    user_id: _uuid.UUID,
) -> dict[str, int]:
    """short_swing 포지션 상태를 주문 체결 결과와 동기화한다.

    Args:
        db: 비동기 DB 세션.
        client: 브로커 클라이언트 (미사용, 향후 확장용).
        user_id: 트레이더 UUID.

    Returns:
        {"pending_to_open": int, "pending_deleted": int,
         "closing_to_closed": int, "closing_to_open": int, "errors": int}
    """
    counts = {
        "pending_to_open": 0,
        "pending_deleted": 0,
        "closing_to_closed": 0,
        "closing_to_open": 0,
        "open_qty_updated": 0,
        "errors": 0,
    }

    # ── 1) PENDING_ENTRY 포지션 reconcile ────────────────────────────────
    pending_result = await db.execute(
        select(ShortSwingPosition).where(
            ShortSwingPosition.user_id == user_id,
            ShortSwingPosition.status == PositionStatus.PENDING_ENTRY,
        )
    )
    pending_positions = list(pending_result.scalars().all())

    for pos in pending_positions:
        if pos.entry_order_id is None:
            await logger.awarning(
                "PENDING_ENTRY에 entry_order_id 없음 — 삭제",
                symbol=pos.symbol,
                position_id=str(pos.id),
            )
            await db.delete(pos)
            counts["pending_deleted"] += 1
            continue

        order_result = await db.execute(select(Order).where(Order.id == pos.entry_order_id))
        order = order_result.scalar_one_or_none()

        if order is None:
            await logger.awarning(
                "PENDING_ENTRY 주문 조회 실패 — 삭제",
                symbol=pos.symbol,
                entry_order_id=str(pos.entry_order_id),
            )
            await db.delete(pos)
            counts["pending_deleted"] += 1
            continue

        if order.status == OrderStatus.FILLED:
            # 전량 체결 → OPEN 전이
            pos.status = PositionStatus.OPEN
            pos.entry_price = order.filled_price if order.filled_price else pos.entry_price
            pos.quantity = order.filled_quantity if order.filled_quantity else pos.quantity
            pos.highest_price_since_entry = pos.entry_price
            if order.filled_at:
                pos.entry_time = order.filled_at

            await logger.ainfo(
                "PENDING_ENTRY → OPEN (체결 확인)",
                symbol=pos.symbol,
                filled_price=pos.entry_price,
                filled_quantity=pos.quantity,
            )
            counts["pending_to_open"] += 1

        elif order.status == OrderStatus.PARTIAL_FILL:
            # 부분체결 → 체결분 OPEN row 생성, 기존 PENDING_ENTRY 잔여 수량 유지
            filled_qty = order.filled_quantity or 0
            if filled_qty <= 0:
                continue

            remaining_qty = pos.quantity - filled_qty
            filled_price = order.filled_price or pos.entry_price

            # 기존 row를 OPEN 전환 (체결 수량)
            pos.status = PositionStatus.OPEN
            pos.entry_price = filled_price
            pos.quantity = filled_qty
            pos.highest_price_since_entry = filled_price
            if order.filled_at:
                pos.entry_time = order.filled_at

            await logger.ainfo(
                "PENDING_ENTRY → OPEN (부분체결)",
                symbol=pos.symbol,
                filled_quantity=filled_qty,
                remaining_quantity=remaining_qty,
            )
            counts["pending_to_open"] += 1

            # 잔여분은 로그만 기록 (30분 후 cancel 모듈이 미체결 주문 취소)
            if remaining_qty > 0:
                await logger.awarning(
                    "부분체결 잔여 수량 — cancel 모듈 대기",
                    symbol=pos.symbol,
                    remaining_quantity=remaining_qty,
                    order_id=str(pos.entry_order_id),
                )

        elif order.status in (
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
            OrderStatus.EXPIRED,
        ):
            # 취소/거절 → row 삭제 (보수적)
            await logger.ainfo(
                "PENDING_ENTRY 주문 취소/거절 — 포지션 삭제",
                symbol=pos.symbol,
                order_status=order.status.value,
            )
            await db.delete(pos)
            counts["pending_deleted"] += 1

        # SUBMITTED/ACCEPTED/CREATED → 아직 진행 중, 건너뜀

    # ── 1-b) OPEN 포지션 추가 체결 누적 (HOTFIX E — small-real 게이트 3) ──
    # 첫 PARTIAL_FILL 로 OPEN 전이된 뒤 추가 PARTIAL_FILL / FILLED 이벤트가
    # 같은 entry_order_id 로 들어오면 order.filled_quantity 가 pos.quantity
    # 보다 커진다. 그 차이만큼 누적 반영. 새 entry_price 는 가중평균(realtime
    # handler 가 이미 계산해 둠) 그대로 사용.
    open_for_accum_result = await db.execute(
        select(ShortSwingPosition).where(
            ShortSwingPosition.user_id == user_id,
            ShortSwingPosition.status == PositionStatus.OPEN,
            ShortSwingPosition.entry_order_id.is_not(None),
        )
    )
    for pos in list(open_for_accum_result.scalars().all()):
        order_result = await db.execute(select(Order).where(Order.id == pos.entry_order_id))
        order = order_result.scalar_one_or_none()
        if order is None:
            continue
        if order.status not in (OrderStatus.PARTIAL_FILL, OrderStatus.FILLED):
            continue
        order_filled_qty = int(order.filled_quantity or 0)
        if order_filled_qty <= pos.quantity:
            continue  # 추가 체결분 없음

        added_qty = order_filled_qty - pos.quantity
        # OLD 값 보존: ratio 는 entry_price 갱신 전 기준이어야 한다.
        old_entry_price = pos.entry_price
        old_stop_price = pos.stop_price
        old_take_profit_price = pos.take_profit_price

        new_entry_price = int(order.filled_price or old_entry_price)
        pos.quantity = order_filled_qty
        pos.entry_price = new_entry_price
        # 추가 체결 후 stop/take_profit 가격 재계산: 기존 비율(OLD 기준) 보존.
        # 비율은 ShortSwingPosition 에 저장 안 되므로 old_stop/old_entry_price 로 역산.
        if old_stop_price and old_entry_price:
            stop_ratio = (old_stop_price - old_entry_price) / old_entry_price
            pos.stop_price = int(new_entry_price * (1 + stop_ratio))
        if old_take_profit_price and old_entry_price:
            tp_ratio = (old_take_profit_price - old_entry_price) / old_entry_price
            pos.take_profit_price = int(new_entry_price * (1 + tp_ratio))

        await logger.ainfo(
            "OPEN 추가 체결 누적",
            symbol=pos.symbol,
            added_quantity=added_qty,
            new_total_quantity=order_filled_qty,
            new_entry_price=new_entry_price,
        )
        counts["open_qty_updated"] += 1

    # ── 2) CLOSING 포지션 reconcile ──────────────────────────────────────
    closing_result = await db.execute(
        select(ShortSwingPosition).where(
            ShortSwingPosition.user_id == user_id,
            ShortSwingPosition.status == PositionStatus.CLOSING,
        )
    )
    closing_positions = list(closing_result.scalars().all())

    for pos in closing_positions:
        if pos.exit_order_id is None:
            # exit_order_id 없으면 reconcile 불가 — 스킵
            continue

        order_result = await db.execute(select(Order).where(Order.id == pos.exit_order_id))
        order = order_result.scalar_one_or_none()

        if order is None:
            continue

        if order.status == OrderStatus.FILLED:
            # CLOSING → CLOSED 전이
            filled_price = order.filled_price or 0
            filled_qty = order.filled_quantity or pos.quantity

            filled_at = order.filled_at or datetime.now(tz=UTC)

            pos.status = PositionStatus.CLOSED
            pos.exit_price = filled_price
            pos.exit_quantity = filled_qty
            pos.exit_time = filled_at
            pos.realized_pnl = (filled_price - pos.entry_price) * filled_qty

            await logger.ainfo(
                "CLOSING → CLOSED (체결 확인)",
                symbol=pos.symbol,
                exit_price=filled_price,
                realized_pnl=pos.realized_pnl,
            )
            counts["closing_to_closed"] += 1

        elif order.status in (
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
            OrderStatus.EXPIRED,
        ):
            # SELL 취소/거절 → OPEN 복구
            pos.status = PositionStatus.OPEN
            pos.exit_order_id = None
            pos.exit_reason = None

            await logger.awarning(
                "CLOSING → OPEN 복구 (매도 취소/거절)",
                symbol=pos.symbol,
                order_status=order.status.value,
            )
            counts["closing_to_open"] += 1

        # SUBMITTED/ACCEPTED → 아직 진행 중, 건너뜀

    await db.commit()

    if any(v > 0 for v in counts.values()):
        await logger.ainfo("short_swing reconciler 결과", **counts)

    return counts
