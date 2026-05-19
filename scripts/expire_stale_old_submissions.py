"""오래된 SUBMITTED 주문 일괄 EXPIRED 정리 (HOTFIX F.10).

키움 모의/실전 미체결 주문은 장 종료 시 자동 만료 (당일 한정).
``submitted_at`` 이 N일 이전인 SUBMITTED row 는 broker side EXPIRED 가
거의 확실하므로 DB 도 EXPIRED 로 정리한다.

대상:
- ``status = 'submitted'``
- ``submitted_at < now() - INTERVAL '<days> days'``  (기본 1일)

처리:
- status = EXPIRED
- error_message = "broker 자동 만료 (submitted_at > N일 경과)"
- trade_logs row 추가 (event_type='order_expired')

사용법:
    # dry-run (기본, 7일 경과)
    uv run python scripts/expire_stale_old_submissions.py --days 1

    # 실제 적용
    uv run python scripts/expire_stale_old_submissions.py --days 1 --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

# 프로젝트 루트
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if TYPE_CHECKING:
    from src.models.order import Order

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("expire_stale_submissions")


@dataclass
class ExpireResult:
    expired: list[uuid.UUID] = field(default_factory=list)

    def summary(self) -> str:
        return f"EXPIRED: {len(self.expired)}"


async def fetch_stale_submissions(session: object, *, days: int) -> list[Order]:
    """submitted_at 이 N일 이전 SUBMITTED 주문 조회."""
    from sqlalchemy import select

    from src.models.order import Order, OrderStatus
    from src.utils.time import now_kst

    cutoff = now_kst() - timedelta(days=days)
    stmt = (
        select(Order)
        .where(
            Order.status == OrderStatus.SUBMITTED,
            Order.submitted_at < cutoff,
        )
        .order_by(Order.submitted_at)
    )
    result = await session.execute(stmt)  # type: ignore[union-attr]
    return list(result.scalars().all())


async def expire_order(order: Order, result: ExpireResult, *, session: object | None) -> None:
    """단일 주문 EXPIRED 정리."""
    from src.models.order import OrderSide, OrderStatus

    order.status = OrderStatus.EXPIRED
    order.error_message = "broker 자동 만료 (submitted_at > 1일 경과, F.10 reconcile)"
    side_str = "buy" if order.side == OrderSide.BUY else "sell"
    log.info(
        "[%s] %s %d → EXPIRED (broker_order_no=%s, submitted_at=%s)",
        order.symbol,
        side_str.upper(),
        order.quantity,
        order.broker_order_no,
        order.submitted_at,
    )
    result.expired.append(order.id)

    if session is None:
        return
    try:
        from src.trading.trade_logger import log_trade_event

        await log_trade_event(
            db=session,  # type: ignore[arg-type]
            user_id=order.user_id,
            event_type="order_expired",
            symbol=order.symbol,
            side=side_str,
            price=order.price or 0,
            quantity=order.quantity or 0,
            message="broker 자동 만료 정리 (F.10)",
            details={
                "broker_order_no": order.broker_order_no,
                "reconcile_source": "expire_stale_submissions",
                "original_reason": order.reason,
                "submitted_at": (order.submitted_at.isoformat() if order.submitted_at else None),
            },
            order_id=order.id,
            strategy_id=order.strategy_id,
            is_mock=bool(order.is_mock),
        )
    except Exception as exc:
        log.warning("[%s] trade_logs insert 실패: %s", order.symbol, exc)


async def run_expire(
    session: object,
    *,
    days: int,
    apply: bool = False,
) -> ExpireResult:
    """오래된 SUBMITTED 주문 일괄 EXPIRED 처리."""
    orders = await fetch_stale_submissions(session, days=days)
    log.info("대상 주문 %d건 (submitted_at > %d일 경과)", len(orders), days)

    result = ExpireResult()
    for order in orders:
        await expire_order(order, result, session=session)

    if apply:
        await session.commit()  # type: ignore[union-attr]
        log.info("DB commit 완료 (%d건 EXPIRED)", len(result.expired))
    else:
        await session.rollback()  # type: ignore[union-attr]
        log.info("[DRY-RUN] rollback — 실제 변경 없음 (%d건 예정)", len(result.expired))

    return result


async def _main(days: int, apply: bool) -> None:
    from src.config.database import async_session_factory

    async with async_session_factory() as session:
        result = await run_expire(session, days=days, apply=apply)

    log.info("=" * 60)
    log.info("Expire 결과: %s", result.summary())
    if result.expired:
        log.info("EXPIRED order_ids: %s", [str(x) for x in result.expired])
    log.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="오래된 SUBMITTED 주문 일괄 EXPIRED 정리 (HOTFIX F.10)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="N일 이전 SUBMITTED 대상 (기본 1).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="실제 DB 반영. 미지정 시 dry-run.",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("F.10 stale submission expire 시작 (days=%d, apply=%s)", args.days, args.apply)
    log.info("=" * 60)

    asyncio.run(_main(args.days, args.apply))


if __name__ == "__main__":
    main()
