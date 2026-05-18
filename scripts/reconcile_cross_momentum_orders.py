"""cross_momentum 주문 정합성 복구 스크립트 (HOTFIX F.4).

운영 환경에 이미 broker 계좌에 보유가 존재하지만 DB orders 가
SUBMITTED + filled_quantity=0 + fake broker_order_no (rebalance_...) 로
갇혀 있어 realtime.py 가 체결 이벤트를 매칭하지 못하는 상태를 복구한다.

사용법:
    # dry-run (기본, 출력만)
    uv run python scripts/reconcile_cross_momentum_orders.py

    # 실제 적용
    uv run python scripts/reconcile_cross_momentum_orders.py --apply
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
log = logging.getLogger("reconcile_cross_momentum")


# ── 결과 데이터 클래스 ──────────────────────────────────────────────────────


@dataclass
class ReconcileResult:
    """reconcile 실행 결과."""

    buy_filled: list[uuid.UUID] = field(default_factory=list)
    buy_failed: list[uuid.UUID] = field(default_factory=list)
    buy_cancelled: list[uuid.UUID] = field(default_factory=list)
    sell_filled: list[uuid.UUID] = field(default_factory=list)
    sell_skipped: list[uuid.UUID] = field(default_factory=list)

    @property
    def total_changed(self) -> int:
        return (
            len(self.buy_filled)
            + len(self.buy_failed)
            + len(self.buy_cancelled)
            + len(self.sell_filled)
        )

    def summary(self) -> str:
        return (
            f"BUY→FILLED: {len(self.buy_filled)}, "
            f"BUY→FAILED: {len(self.buy_failed)}, "
            f"BUY→CANCELLED (quantity=0): {len(self.buy_cancelled)}, "
            f"SELL→FILLED: {len(self.sell_filled)}, "
            f"SELL 잔량존재(스킵): {len(self.sell_skipped)}"
        )


# ── 핵심 로직 (테스트 가능하도록 분리) ──────────────────────────────────────


async def fetch_stale_orders(session: object) -> list[Order]:
    """DB에서 fake broker_order_no 를 가진 cross_momentum SUBMITTED 주문 조회.

    Args:
        session: AsyncSession 인스턴스.

    Returns:
        Order 리스트.
    """
    from sqlalchemy import select

    from src.models.order import Order, OrderStatus

    stmt = (
        select(Order)
        .where(
            Order.reason == "cross_momentum",
            Order.status == OrderStatus.SUBMITTED,
            Order.broker_order_no.like("rebalance_%"),
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
    """단일 주문에 대해 holdings 와 비교하여 상태 업데이트 + trade_logs row 생성.

    order 객체를 in-place 수정한다. commit 은 호출자 책임.

    Args:
        order: DB Order 인스턴스 (dirty state 가능).
        holdings_map: {symbol: Holding} 브로커 잔고 매핑.
        result: 결과 카운터 (in-place 수정).
        session: AsyncSession. 제공 시 trade_logs row 도 insert (F.7).
    """
    from src.models.order import OrderSide, OrderStatus
    from src.utils.time import now_kst

    symbol = order.symbol
    holding = holdings_map.get(symbol)
    side_str = "buy" if order.side == OrderSide.BUY else "sell"

    if order.side == OrderSide.BUY:
        # quantity=0 fake row 는 실 체결이 없는 _persist_rebalance 잔재 (F.4 발견 결함).
        # FILLED 마킹 시 거래내역 왜곡되므로 CANCELLED 로 정리.
        if order.quantity == 0:
            order.status = OrderStatus.CANCELLED
            order.error_message = "quantity=0 fake row (실 체결 없음, F.6 reconcile 정리)"
            result.buy_cancelled.append(order.id)
            log.info(
                "[%s] BUY → CANCELLED (quantity=0 fake row, order_id=%s)",
                symbol,
                order.id,
            )
            await _emit_trade_log(
                session,
                order,
                event_type="order_cancelled",
                message="quantity=0 fake row reconcile (F.6)",
            )
            return
        if holding and holding.quantity >= order.quantity:
            # BUY + holdings 존재 + 수량 충분 → FILLED
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = holding.avg_price or (
                holding.eval_amount // holding.quantity if holding.quantity > 0 else 0
            )
            order.filled_at = now_kst()
            # cross_momentum 는 시장가 주문이라 order_type='market' 보정 (F.7).
            order.order_type = "market"
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
                price=order.filled_price,
                quantity=order.filled_quantity,
                side=side_str,
                message="reconcile recovery (broker holdings 매칭)",
            )
        else:
            # BUY + holdings 없음 또는 수량 부족 → FAILED
            order.status = OrderStatus.FAILED
            order.error_message = "broker holdings 없음 (수동 reconcile)"
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
                message="reconcile: broker holdings 없음",
            )

    elif order.side == OrderSide.SELL:
        if not holding or holding.quantity == 0:
            # SELL + holdings 없음/수량 0 → FILLED (매도 완료로 간주)
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = 0
            order.filled_at = now_kst()
            order.order_type = "market"
            result.sell_filled.append(order.id)
            log.info(
                "[%s] SELL → FILLED (holdings 없음, order_id=%s)",
                symbol,
                order.id,
            )
            await _emit_trade_log(
                session,
                order,
                event_type="order_filled",
                quantity=order.filled_quantity,
                side=side_str,
                message="reconcile recovery (broker 매도 완료 간주)",
            )
        else:
            # SELL + holdings 잔량 존재 → 스킵
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
    """reconcile 결과를 trade_logs 에 기록 (F.7).

    session=None 이거나 trade_log 모듈 import 실패 시 silent skip.
    Order 의 user_id / strategy_id / is_mock / symbol 을 그대로 전달.
    """
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
                "reconcile_source": "cross_momentum_reconcile",
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


async def fix_existing_filled_orders(session: object) -> int:
    """이미 FILLED 된 cross_momentum rebalance_% row 에 대해 사후 보정 (F.7).

    F.4/F.6 머지 시점에 처리된 row 들은 order_type='limit' 으로 남아 있고
    trade_logs row 도 없다. 본 함수가 한 번 더 돌려도 idempotent.

    수행:
    - order_type 이 'market' 이 아니면 'market' 보정.
    - 해당 order_id 의 trade_logs row 가 하나도 없으면 'order_filled' insert.

    Returns:
        보정한 row 수 (order_type 보정 + trade_logs insert 중 한 가지라도 발생).
    """
    from sqlalchemy import select

    from src.models.order import Order, OrderStatus
    from src.models.trade_log import TradeLog

    stmt = select(Order).where(
        Order.reason == "cross_momentum",
        Order.status == OrderStatus.FILLED,
        Order.broker_order_no.like("rebalance_%"),
    )
    result_obj = await session.execute(stmt)  # type: ignore[union-attr]
    rows = list(result_obj.scalars().all())

    fixed = 0
    for order in rows:
        changed = False
        if order.order_type != "market":
            order.order_type = "market"
            changed = True

        log_stmt = select(TradeLog.id).where(TradeLog.order_id == order.id)
        log_existing = (await session.execute(log_stmt)).first()  # type: ignore[union-attr]
        if log_existing is None:
            await _emit_trade_log(
                session,
                order,
                event_type="order_filled",
                side="buy" if order.side.value == "buy" else "sell",
                price=order.filled_price or 0,
                quantity=order.filled_quantity or order.quantity,
                message="reconcile recovery (사후 보강, F.7)",
            )
            changed = True

        if changed:
            fixed += 1
            log.info(
                "[%s] 사후 보강 (order_type=market + trade_logs insert, order_id=%s)",
                order.symbol,
                order.id,
            )

    return fixed


async def run_reconcile(
    session: object,
    client: object,
    *,
    apply: bool = False,
) -> ReconcileResult:
    """reconcile 메인 로직.

    Args:
        session: AsyncSession 인스턴스.
        client: KiwoomClient 인스턴스 (get_balance 호출용).
        apply: True 면 DB commit. False (dry-run) 면 rollback.

    Returns:
        ReconcileResult: 각 케이스 카운트 + order_id 리스트.
    """
    # 1. stale 주문 조회
    orders = await fetch_stale_orders(session)
    log.info(
        "대상 주문 %d건 조회 완료 (strategy=cross_momentum, status=SUBMITTED, fake order_no)",
        len(orders),
    )

    # 2. broker holdings 조회 (stale 없어도 사후 보강 위해 항상 수행)
    balance = await client.get_balance()  # type: ignore[union-attr]
    holdings_map: dict[str, Holding] = {h.symbol: h for h in balance.holdings}
    log.info("broker holdings %d종목 조회 완료", len(holdings_map))

    # 3. 주문별 reconcile (stale 가 있을 때만)
    result = ReconcileResult()
    for order in orders:
        await reconcile_order(order, holdings_map, result, session=session)

    # 4. 이미 FILLED 된 cross_momentum row 사후 보강 (idempotent, F.7)
    fixed = await fix_existing_filled_orders(session)
    if fixed > 0:
        log.info("이미 FILLED 된 cross_momentum row %d건 사후 보강", fixed)

    # 5. commit / rollback
    if apply:
        await session.commit()  # type: ignore[union-attr]
        log.info("DB commit 완료 (변경 %d건 + 사후 보강 %d건)", result.total_changed, fixed)
    else:
        await session.rollback()  # type: ignore[union-attr]
        log.info(
            "[DRY-RUN] rollback — 실제 변경 없음 (변경 예정 %d건 + 사후 보강 %d건)",
            result.total_changed,
            fixed,
        )

    return result


# ── CLI ──────────────────────────────────────────────────────────────────────


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
    if result.buy_cancelled:
        log.info(
            "BUY→CANCELLED (quantity=0) order_ids: %s",
            [str(x) for x in result.buy_cancelled],
        )
    if result.sell_filled:
        log.info("SELL→FILLED order_ids: %s", [str(x) for x in result.sell_filled])
    if result.sell_skipped:
        log.info("SELL 스킵 order_ids: %s", [str(x) for x in result.sell_skipped])
    log.info("=" * 60)


def main() -> None:
    """argparse CLI."""
    parser = argparse.ArgumentParser(
        description="cross_momentum 주문 정합성 복구 (HOTFIX F.4)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="실제 DB 반영. 미지정 시 dry-run (기본).",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("cross_momentum 주문 reconcile 시작 (apply=%s)", args.apply)
    log.info("=" * 60)

    asyncio.run(_main(args.apply))


if __name__ == "__main__":
    main()
