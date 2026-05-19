"""Short-swing handler — orchestrator 용 래퍼.

기존 run_entry_check, run_exit_check, cancel_stale_buy_orders,
reconcile_short_swing_positions 를 orchestrator HandlerFn 시그니처로 통합.

시간대별 실행:
  - entry: 09:20~13:00
  - exit: 09:20~15:10
  - cancel: 매 cycle (30분 경과 or 15:20 일괄)
  - reconcile: 매 cycle
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.base import BrokerClient
from src.broker.schemas import Holding

log = logging.getLogger("trading.handlers.short_swing")

# 시간대 상수 (live_trader.py 와 동일)
_ENTRY_START = "0920"
_ENTRY_END = "1300"
_EXIT_START = "0920"
_EXIT_END = "1510"
_CANCEL_HHMM = "1520"


async def handle(
    *,
    db: AsyncSession,
    client: BrokerClient,
    holdings_map: dict[str, Holding],  # noqa: ARG001
    available_cash: int,  # noqa: ARG001
    allowed_budget: int,  # noqa: ARG001
    max_order_amount: int,  # noqa: ARG001
    today: date,  # noqa: ARG001
    current_hhmm: str,
) -> dict[str, Any]:
    """Orchestrator 가 호출하는 short_swing handler.

    기존 4개 함수를 시간대에 따라 호출한다.
    design-025 5/N: ACTIVE_STRATEGY env 의존 제거. 내부 가드가 DB 기반.

    Args:
        db: 비동기 DB 세션.
        client: 브로커 클라이언트.
        holdings_map: 보유종목 (미사용, 기존 함수가 직접 조회).
        available_cash: 계좌 전체 가용 현금 (미사용).
        allowed_budget: 이 전략에 할당된 현금 (미사용, 기존 함수가 params로 제어).
        max_order_amount: 1회 최대 주문 금액 (미사용).
        today: 오늘 날짜 (미사용).
        current_hhmm: 현재 시각 HHMM.

    Returns:
        {"reconcile": dict, "entry": dict | None, "exit": dict | None, "cancel": dict | None}
    """
    from src.trading.live_order_persist import resolve_live_trader_user_id

    user_id = await resolve_live_trader_user_id(db)

    result: dict[str, Any] = {}

    # reconcile — 매 cycle
    result["reconcile"] = await _run_reconcile(db, client, user_id)

    # entry — 09:20~13:00
    if _ENTRY_START <= current_hhmm <= _ENTRY_END:
        result["entry"] = await _run_entry(db, client, user_id)
    else:
        result["entry"] = None

    # exit — 09:20~15:10
    if _EXIT_START <= current_hhmm <= _EXIT_END:
        result["exit"] = await _run_exit(db, client, user_id)
    else:
        result["exit"] = None

    # cancel — 매 cycle (30분 경과 or 15:20 일괄)
    result["cancel"] = await _run_cancel(db, client, user_id, current_hhmm)

    return result


async def _run_reconcile(db: AsyncSession, client: BrokerClient, user_id: object) -> dict[str, Any]:
    """포지션-주문 체결 정합성 reconcile."""
    try:
        from src.trading.short_swing_reconciler import reconcile_short_swing_positions

        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)
        total = sum(counts.values())
        if total > 0:
            log.info(
                "reconcile: open=%d, deleted=%d, closed=%d, reverted=%d, errors=%d",
                counts["pending_to_open"],
                counts["pending_deleted"],
                counts["closing_to_closed"],
                counts["closing_to_open"],
                counts["errors"],
            )
        return counts
    except Exception as exc:
        log.exception("reconcile 실패")
        return {"error": str(exc)}


async def _run_entry(db: AsyncSession, client: BrokerClient, user_id: object) -> dict[str, Any]:
    """진입 체크."""
    try:
        from src.trading.short_swing import run_entry_check

        r = await run_entry_check(db, client, user_id=user_id)
        log.info(
            "entry: checked=%d, ordered=%d, skipped=%d, errors=%d",
            r.checked,
            r.ordered,
            len(r.skipped),
            len(r.errors),
        )
        return {
            "checked": r.checked,
            "ordered": r.ordered,
            "skipped": len(r.skipped),
            "errors": len(r.errors),
        }
    except Exception as exc:
        log.exception("entry 실패")
        return {"error": str(exc)}


async def _run_exit(db: AsyncSession, client: BrokerClient, user_id: object) -> dict[str, Any]:
    """청산 체크."""
    try:
        from src.trading.short_swing_exit import run_exit_check

        r = await run_exit_check(db, client, user_id=user_id)
        log.info(
            "exit: checked=%d, closed=%d, skipped=%d, errors=%d",
            r.checked,
            r.closed,
            len(r.skipped),
            len(r.errors),
        )
        return {
            "checked": r.checked,
            "closed": r.closed,
            "skipped": len(r.skipped),
            "errors": len(r.errors),
        }
    except Exception as exc:
        log.exception("exit 실패")
        return {"error": str(exc)}


async def _run_cancel(
    db: AsyncSession,
    client: BrokerClient,
    user_id: object,
    current_hhmm: str,
) -> dict[str, Any]:
    """미체결 매수 주문 취소."""
    threshold = 0 if current_hhmm >= _CANCEL_HHMM else 30

    try:
        from src.trading.short_swing_cancel import cancel_stale_buy_orders

        counts = await cancel_stale_buy_orders(
            db, client, user_id=user_id, threshold_minutes=threshold
        )
        if counts["cancelled"] > 0:
            log.info(
                "cancel: cancelled=%d, errors=%d",
                counts["cancelled"],
                counts["errors"],
            )
        return counts
    except Exception as exc:
        log.exception("cancel 실패")
        return {"error": str(exc)}
