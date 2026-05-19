"""나머지 stale SUBMITTED 주문 정합성 복구 스크립트 (HOTFIX F.9).

cross_momentum 의 fake broker_order_no ('rebalance_%') 가 아닌
실제 7자리 키움 broker_order_no 를 가진 stale SUBMITTED row 들을 정리한다.

대상 reason:
- ``momentum``: 옛 momentum 전략의 broker WebSocket 매칭 누락 row
- ``mock_qa_test`` / ``mock_qa_sell``: QA 테스트 잔재
- ``NULL`` / ``""``: 수동 발주 stale row

분기 로직:
- ``mock_qa_*``: 무조건 CANCELLED (테스트 잔재)
- BUY + broker holdings 보유 충분 → FILLED
- BUY + broker holdings 없음/부족 → FAILED
- SELL + broker holdings 0 → FILLED
- SELL + broker holdings 잔량 존재 → SKIP (수동 확인 필요)

사용법:
    # dry-run (기본)
    uv run python scripts/reconcile_remaining_stale_orders.py

    # 실제 적용
    uv run python scripts/reconcile_remaining_stale_orders.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# 프로젝트 루트를 sys.path 에 추가
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if TYPE_CHECKING:
    from src.broker.schemas import Holding
    from src.models.order import Order

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("reconcile_remaining_stale")


# F.9 대상 reason (cross_momentum 제외)
_TARGET_REASONS: tuple[str | None, ...] = (
    "momentum",
    "mock_qa_test",
    "mock_qa_sell",
    "",
    None,
)
_MOCK_QA_REASONS: tuple[str, ...] = ("mock_qa_test", "mock_qa_sell")


@dataclass
class ReconcileResult:
    """reconcile 실행 결과."""

    buy_filled: list[uuid.UUID] = field(default_factory=list)
    buy_failed: list[uuid.UUID] = field(default_factory=list)
    mock_qa_cancelled: list[uuid.UUID] = field(default_factory=list)
    sell_filled: list[uuid.UUID] = field(default_factory=list)
    sell_skipped: list[uuid.UUID] = field(default_factory=list)

    @property
    def total_changed(self) -> int:
        return (
            len(self.buy_filled)
            + len(self.buy_failed)
            + len(self.mock_qa_cancelled)
            + len(self.sell_filled)
        )

    def summary(self) -> str:
        return (
            f"BUY→FILLED: {len(self.buy_filled)}, "
            f"BUY→FAILED: {len(self.buy_failed)}, "
            f"mock_qa→CANCELLED: {len(self.mock_qa_cancelled)}, "
            f"SELL→FILLED: {len(self.sell_filled)}, "
            f"SELL 잔량존재(스킵): {len(self.sell_skipped)}"
        )


async def fetch_stale_orders(session: object) -> list[Order]:
    """F.9 대상 stale SUBMITTED 주문 조회.

    reason in (momentum, mock_qa_test, mock_qa_sell, '', NULL) +
    broker_order_no NOT LIKE 'rebalance_%' (cross_momentum F.4 대상 제외).
    """
    from sqlalchemy import or_, select

    from src.models.order import Order, OrderStatus

    stmt = (
        select(Order)
        .where(
            Order.status == OrderStatus.SUBMITTED,
            or_(
                Order.reason.in_(["momentum", "mock_qa_test", "mock_qa_sell", ""]),
                Order.reason.is_(None),
            ),
            or_(
                Order.broker_order_no.is_(None),
                ~Order.broker_order_no.like("rebalance_%"),
            ),
        )
        .order_by(Order.submitted_at)
    )
    result = await session.execute(stmt)  # type: ignore[union-attr]
    return list(result.scalars().all())


async def reconcile_order(
    order: Order,
    holdings_map: dict[str, Holding],
    result: ReconcileResult,
    *,
    session: object | None = None,
) -> None:
    """F.9 단일 주문 reconcile.

    분기:
    - mock_qa_* → CANCELLED
    - BUY + broker holdings 충분 → FILLED
    - BUY + 미보유/부족 → FAILED
    - SELL + 보유 0 → FILLED
    - SELL + 보유 → SKIP
    """
    from src.models.order import OrderSide, OrderStatus
    from src.utils.time import now_kst

    symbol = order.symbol
    holding = holdings_map.get(symbol)
    side_str = "buy" if order.side == OrderSide.BUY else "sell"

    # 1. mock_qa_* → CANCELLED (테스트 잔재)
    if order.reason in _MOCK_QA_REASONS:
        order.status = OrderStatus.CANCELLED
        order.error_message = f"{order.reason} 잔재 (F.9 reconcile 정리)"
        result.mock_qa_cancelled.append(order.id)
        log.info(
            "[%s] %s → CANCELLED (mock_qa 잔재, order_id=%s)",
            symbol,
            side_str.upper(),
            order.id,
        )
        await _emit_trade_log(
            session,
            order,
            event_type="order_cancelled",
            side=side_str,
            message="mock_qa 잔재 reconcile (F.9)",
        )
        return

    # 2. BUY
    if order.side == OrderSide.BUY:
        if holding and holding.quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = holding.avg_price or (
                holding.eval_amount // holding.quantity if holding.quantity > 0 else 0
            )
            order.filled_at = now_kst()
            result.buy_filled.append(order.id)
            log.info(
                "[%s] BUY → FILLED (qty=%d, price=%d, order_id=%s)",
                symbol,
                order.filled_quantity,
                order.filled_price,
                order.id,
            )
            await _emit_trade_log(
                session,
                order,
                event_type="order_filled",
                side=side_str,
                price=order.filled_price,
                quantity=order.filled_quantity,
                message="reconcile recovery (broker holdings 매칭, F.9)",
            )
        else:
            order.status = OrderStatus.FAILED
            order.error_message = "broker holdings 없음/부족 (F.9 reconcile)"
            result.buy_failed.append(order.id)
            log.info(
                "[%s] BUY → FAILED (holdings=%s, order_id=%s)",
                symbol,
                f"qty={holding.quantity}" if holding else "없음",
                order.id,
            )
            await _emit_trade_log(
                session,
                order,
                event_type="order_failed",
                side=side_str,
                message="reconcile: broker holdings 없음/부족",
            )
        return

    # 3. SELL
    if not holding or holding.quantity == 0:
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = 0
        order.filled_at = now_kst()
        result.sell_filled.append(order.id)
        log.info(
            "[%s] SELL → FILLED (holdings 없음/0, order_id=%s)",
            symbol,
            order.id,
        )
        await _emit_trade_log(
            session,
            order,
            event_type="order_filled",
            side=side_str,
            quantity=order.filled_quantity,
            message="reconcile recovery (broker 매도 완료 간주, F.9)",
        )
    else:
        # 잔량 존재 → 사람 확인 필요. status 유지.
        result.sell_skipped.append(order.id)
        log.warning(
            "[%s] SELL 잔량 존재 (qty=%d) — 상태 유지 (order_id=%s)",
            symbol,
            holding.quantity,
            order.id,
        )


async def _emit_trade_log(
    session: object | None,
    order: Order,
    *,
    event_type: str,
    message: str,
    price: int | None = None,
    quantity: int | None = None,
    side: str | None = None,
) -> None:
    """reconcile 결과를 trade_logs 에 기록 (F.9)."""
    if session is None:
        return
    try:
        from src.trading.trade_logger import log_trade_event

        await log_trade_event(
            db=session,  # type: ignore[arg-type]
            user_id=order.user_id,
            event_type=event_type,
            symbol=order.symbol,
            side=side or "",
            price=price if price is not None else (order.price or 0),
            quantity=quantity if quantity is not None else (order.quantity or 0),
            message=message,
            details={
                "broker_order_no": order.broker_order_no,
                "reconcile_source": "remaining_stale_reconcile",
                "original_reason": order.reason,
            },
            order_id=order.id,
            strategy_id=order.strategy_id,
            is_mock=bool(order.is_mock),
        )
    except Exception as exc:
        log.warning(
            "[%s] trade_logs insert 실패 (계속 진행): %s",
            order.symbol,
            exc,
        )


async def run_reconcile(
    session: object,
    client: object,
    *,
    apply: bool = False,
) -> ReconcileResult:
    """F.9 reconcile 메인 로직."""
    orders = await fetch_stale_orders(session)
    log.info("대상 주문 %d건 조회 완료 (F.9: momentum/mock_qa/NULL/'')", len(orders))

    if not orders:
        log.info("reconcile 대상 없음 — 종료")
        return ReconcileResult()

    balance = await client.get_balance()  # type: ignore[union-attr]
    holdings_map: dict[str, Holding] = {h.symbol: h for h in balance.holdings}
    log.info("broker holdings %d종목 조회 완료", len(holdings_map))

    result = ReconcileResult()
    for order in orders:
        await reconcile_order(order, holdings_map, result, session=session)

    if apply:
        await session.commit()  # type: ignore[union-attr]
        log.info("DB commit 완료 (변경 %d건)", result.total_changed)
    else:
        await session.rollback()  # type: ignore[union-attr]
        log.info("[DRY-RUN] rollback — 실제 변경 없음 (변경 예정 %d건)", result.total_changed)

    return result


async def _main(apply: bool) -> None:
    """CLI 엔트리포인트."""
    from src.broker.kiwoom import KiwoomClient
    from src.config.database import async_session_factory

    is_mock = os.environ.get("KIWOOM_IS_MOCK", "true").lower() not in ("false", "0", "no")
    base_url = os.environ.get(
        "KIWOOM_MOCK_BASE_URL" if is_mock else "KIWOOM_REAL_BASE_URL",
        "https://mockapi.kiwoom.com",
    )
    app_key = os.environ.get("KIWOOM_MOCK_APP_KEY" if is_mock else "KIWOOM_REAL_APP_KEY", "")
    app_secret = os.environ.get(
        "KIWOOM_MOCK_APP_SECRET" if is_mock else "KIWOOM_REAL_APP_SECRET", ""
    )

    if not app_key or not app_secret:
        log.error("KIWOOM API 키 미설정 — 종료")
        sys.exit(1)

    client = KiwoomClient(
        base_url=base_url,
        app_key=app_key,
        app_secret=app_secret,
        is_mock=is_mock,
    )

    try:
        await client.authenticate()
        log.info("키움 API 인증 완료 (is_mock=%s)", is_mock)
    except Exception as exc:
        log.error("키움 API 인증 실패: %s", exc)
        sys.exit(1)

    async with async_session_factory() as session:
        result = await run_reconcile(session, client, apply=apply)

    log.info("=" * 60)
    log.info("Reconcile 결과: %s", result.summary())
    if result.buy_filled:
        log.info("BUY→FILLED order_ids: %s", [str(x) for x in result.buy_filled])
    if result.buy_failed:
        log.info("BUY→FAILED order_ids: %s", [str(x) for x in result.buy_failed])
    if result.mock_qa_cancelled:
        log.info(
            "mock_qa→CANCELLED order_ids: %s",
            [str(x) for x in result.mock_qa_cancelled],
        )
    if result.sell_filled:
        log.info("SELL→FILLED order_ids: %s", [str(x) for x in result.sell_filled])
    if result.sell_skipped:
        log.warning(
            "SELL 잔량존재(스킵) order_ids: %s",
            [str(x) for x in result.sell_skipped],
        )
    log.info("=" * 60)


def main() -> None:
    """argparse CLI."""
    parser = argparse.ArgumentParser(
        description="나머지 stale SUBMITTED 주문 정합성 복구 (HOTFIX F.9)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="실제 DB 반영. 미지정 시 dry-run (기본).",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("F.9 remaining stale reconcile 시작 (apply=%s)", args.apply)
    log.info("=" * 60)

    asyncio.run(_main(args.apply))


if __name__ == "__main__":
    main()
