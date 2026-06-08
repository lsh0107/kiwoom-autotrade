"""2026-06-05 mini rebalance test 주문 정합성 복구 (HOTFIX, ad-hoc).

본 스크립트는 2026-06-05 mini rebalance test 에서 발생한 25 sell 주문
(broker_order_no 0137829~0137979, reason='cross_momentum', status=SUBMITTED)
을 broker holdings 기준으로 reconcile 한다.

기존 ``scripts/reconcile_cross_momentum_orders.py`` 는
``broker_order_no LIKE 'rebalance_%'`` 만 매칭하여 이번 real broker_order_no
(01378xx ~ 01379xx) 주문에는 적용되지 않으므로 별도 스크립트 필요.

차이점:
- ``fetch_target_orders`` — broker_order_no NOT LIKE 'rebalance_%' 인 6/5
  cross_momentum SUBMITTED 주문 한정.
- 수량 정합성 검증 — broker holdings 잔량이 있는 종목은 ``EXPECTED_PRE_QTY``
  (mini test 전 holdings 수량) 맵을 사용해 ``현재 holdings + sell 수량 ==
  expected_pre_qty`` 일 때만 전량 체결(FILLED)로 판정한다. 맵에 없거나 수량이
  맞지 않으면 FILLED 처리하지 않고 ``sell_skipped_quantity_mismatch`` 로 보고.

체결가:
- ``filled_price=0`` — 기존 reconcile 관례상 허용. mock broker 측만 정확한
  체결가를 알 수 있어 복원 불가. **PnL 산출용 가격이 아님** (결과 문서 명시).

사용법:
    # dry-run (기본)
    uv run python scripts/reconcile_2026_06_05_mini_test_orders.py

    # 실제 적용
    uv run python scripts/reconcile_2026_06_05_mini_test_orders.py --apply

본 스크립트는 1 회용. 향후 weekly trigger 마다 동일 작업 발생 시 일반화
필요 (별도 HOTFIX).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

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
log = logging.getLogger("reconcile_mini_test_2026_06_05")


# 6/5 mini rebalance test 범위 (KST → UTC)
TARGET_START_UTC = datetime(2026, 6, 5, 5, 30, 0, tzinfo=UTC)  # 14:30 KST
TARGET_END_UTC = datetime(2026, 6, 5, 15, 0, 0, tzinfo=UTC)  # 다음날 00:00 KST

# mini test 전 holdings 수량 (비중↓ 4 종목 — 전량 매도가 아니라 부분 매도라
# 매도 후에도 잔량이 남는다). `현재 holdings 잔량 + sell 수량 == expected_pre_qty`
# 인 경우에만 전량 체결로 판정한다. 맵에 없는 종목이 잔량을 가지면 FILLED 금지.
EXPECTED_PRE_QTY: dict[str, int] = {
    "000720": 29,  # sell 10 → current 19
    "006800": 61,  # sell 24 → current 37
    "047040": 155,  # sell 64 → current 91
    "240810": 35,  # sell 10 → current 25
}


@dataclass
class ReconcileResult:
    sell_filled: list[uuid.UUID] = field(default_factory=list)
    sell_filled_partial_holdings: list[uuid.UUID] = field(default_factory=list)
    sell_skipped_quantity_mismatch: list[tuple[uuid.UUID, str, int, int]] = field(
        default_factory=list
    )
    # (order_id, symbol, sell_qty, current_holdings) — 추가 분석 필요

    @property
    def total_changed(self) -> int:
        return len(self.sell_filled) + len(self.sell_filled_partial_holdings)

    def summary(self) -> str:
        return (
            f"SELL→FILLED (holdings 0): {len(self.sell_filled)}, "
            f"SELL→FILLED (잔량 + sell == pre 검증 통과): "
            f"{len(self.sell_filled_partial_holdings)}, "
            f"SELL 스킵 (수량 불일치): {len(self.sell_skipped_quantity_mismatch)}"
        )


async def fetch_target_orders(session: object) -> list[Order]:
    """6/5 mini test 의 25 sell 주문 조회 (reason='cross_momentum',
    status=SUBMITTED, broker_order_no NOT LIKE 'rebalance_%', 14:30~ 범위).
    """
    from sqlalchemy import and_, not_, select

    from src.models.order import Order, OrderSide, OrderStatus

    stmt = (
        select(Order)
        .where(
            and_(
                Order.reason == "cross_momentum",
                Order.status == OrderStatus.SUBMITTED,
                Order.side == OrderSide.SELL,
                Order.submitted_at >= TARGET_START_UTC,
                Order.submitted_at < TARGET_END_UTC,
                not_(Order.broker_order_no.like("rebalance_%")),
                Order.is_mock.is_(True),
            )
        )
        .order_by(Order.submitted_at)
    )
    result = await session.execute(stmt)  # type: ignore[union-attr]
    return list(result.scalars().all())


async def reconcile_sell_order(
    order: Order,
    holdings_map: dict[str, Holding],
    result: ReconcileResult,
    *,
    session: object | None = None,
) -> None:
    """단일 sell 주문 분류 + 상태 업데이트.

    분류:
    1. holdings 에 종목 없음 (전량 매도 완료) → FILLED.
    2. holdings 에 잔량 있음 + ``EXPECTED_PRE_QTY`` 에 종목 존재 + 현재 잔량 +
       sell 수량 == expected_pre_qty (즉 부분 매도가 정확히 체결됨) → FILLED.
    3. holdings 에 잔량 있으나 위 수량 조건 불충족 (맵에 없거나 수량 불일치)
       → FILLED 금지, ``sell_skipped_quantity_mismatch`` 로 보고.

    Args:
        order: DB Order 인스턴스.
        holdings_map: {symbol: Holding} 현재 broker holdings.
        result: 결과 카운터.
        session: AsyncSession. trade_logs insert 용.
    """
    from src.models.order import OrderStatus
    from src.utils.time import now_kst

    symbol = order.symbol
    holding = holdings_map.get(symbol)

    if not holding or holding.quantity == 0:
        # 케이스 1: holdings 없음 → 전량 매도 완료
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = 0  # 체결가 복원 불가 — PnL 산출용 아님
        order.filled_at = now_kst()
        order.order_type = "market"
        result.sell_filled.append(order.id)
        log.info(
            "[%s] SELL → FILLED (holdings 0, qty=%d, broker_order_no=%s, order_id=%s)",
            symbol,
            order.quantity,
            order.broker_order_no,
            order.id,
        )
        await _emit_trade_log(
            session,
            order,
            event_type="order_filled",
            quantity=order.quantity,
            side="sell",
            message="reconcile (mini test 2026-06-05, holdings 0 → 전량 체결 간주)",
        )
        return

    # 케이스 2/3: holdings 잔량 있음 → 수량 정합성 검증 후에만 FILLED
    expected_pre = EXPECTED_PRE_QTY.get(symbol)
    if expected_pre is not None and holding.quantity + order.quantity == expected_pre:
        # 케이스 2: 부분 매도 수량 정확히 일치 → 전량 체결
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = 0  # 체결가 복원 불가 — PnL 산출용 아님
        order.filled_at = now_kst()
        order.order_type = "market"
        result.sell_filled_partial_holdings.append(order.id)
        log.info(
            "[%s] SELL → FILLED (잔량 %d + sell %d == pre %d, broker_order_no=%s, order_id=%s)",
            symbol,
            holding.quantity,
            order.quantity,
            expected_pre,
            order.broker_order_no,
            order.id,
        )
        await _emit_trade_log(
            session,
            order,
            event_type="order_filled",
            quantity=order.quantity,
            side="sell",
            message=(
                f"reconcile (mini test 2026-06-05, 잔량 {holding.quantity} + "
                f"sell {order.quantity} == pre {expected_pre} 검증 통과)"
            ),
        )
    else:
        # 케이스 3: 맵에 없거나 수량 불일치 → FILLED 금지, 스킵 + 보고
        result.sell_skipped_quantity_mismatch.append(
            (order.id, symbol, order.quantity, holding.quantity)
        )
        log.warning(
            "[%s] SELL 스킵 (수량 불일치 — FILLED 미처리): 현재 잔량 %d, sell %d, "
            "expected_pre=%s, broker_order_no=%s, order_id=%s",
            symbol,
            holding.quantity,
            order.quantity,
            expected_pre,
            order.broker_order_no,
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
    """trade_logs row 생성. session None 이면 silent skip."""
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
                "reconcile_source": "mini_test_2026_06_05",
            },
            order_id=order.id,
            strategy_id=order.strategy_id,
            is_mock=bool(order.is_mock),
        )
    except Exception as exc:
        log.warning("[%s] trade_logs insert 실패 (계속 진행): %s", order.symbol, exc)


async def run_reconcile(
    session: object,
    client: object,
    *,
    apply: bool = False,
) -> ReconcileResult:
    """reconcile 메인."""
    orders = await fetch_target_orders(session)
    log.info(
        "대상 주문 %d건 조회 완료 (6/5 mini test, broker_order_no NOT LIKE 'rebalance_%%')",
        len(orders),
    )

    if not orders:
        log.info("대상 주문 없음 — 종료")
        return ReconcileResult()

    balance = await client.get_balance()  # type: ignore[union-attr]
    holdings_map: dict[str, Holding] = {h.symbol: h for h in balance.holdings}
    log.info("broker holdings %d종목 조회 완료", len(holdings_map))

    result = ReconcileResult()
    for order in orders:
        await reconcile_sell_order(order, holdings_map, result, session=session)

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
    if result.sell_filled:
        log.info("SELL→FILLED (holdings 0) order_ids: %s", [str(x) for x in result.sell_filled])
    if result.sell_filled_partial_holdings:
        log.info(
            "SELL→FILLED (holdings 잔량 + 전량체결 가정) order_ids: %s",
            [str(x) for x in result.sell_filled_partial_holdings],
        )
    if result.sell_skipped_quantity_mismatch:
        log.info("SELL 스킵 (수량 불일치): %s", result.sell_skipped_quantity_mismatch)
    log.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="2026-06-05 mini rebalance test 주문 정합성 복구 (1회용 HOTFIX)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="실제 DB 반영. 미지정 시 dry-run (기본).",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("mini test 주문 reconcile 시작 (apply=%s)", args.apply)
    log.info("=" * 60)

    asyncio.run(_main(args.apply))


if __name__ == "__main__":
    main()
