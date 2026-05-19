"""Cross-momentum handler — orchestrator 용 래퍼.

기존 check_monthly_rebalance 를 orchestrator HandlerFn 시그니처로 wrap.
ACTIVE_STRATEGY env 가드를 orchestrator 가 대체하므로, 호출 시 env 를
일시적으로 설정하여 기존 함수의 내부 가드를 통과시킨다.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.base import BrokerClient
from src.broker.schemas import Holding

log = logging.getLogger("trading.handlers.cross_momentum")


async def handle(
    *,
    db: AsyncSession,
    client: BrokerClient,
    holdings_map: dict[str, Holding],
    available_cash: int,  # noqa: ARG001
    allowed_budget: int,
    max_order_amount: int,  # noqa: ARG001
    today: date,
    current_hhmm: str,
) -> dict[str, Any]:
    """Orchestrator 가 호출하는 cross_momentum handler.

    기존 check_monthly_rebalance 를 호출하되, budget 을 allowed_budget 으로 제한한다.
    ACTIVE_STRATEGY env 를 일시 설정하여 내부 가드를 통과시킨다.

    Args:
        db: 비동기 DB 세션.
        client: 브로커 클라이언트.
        holdings_map: 보유종목 {종목코드: Holding}.
        available_cash: 계좌 전체 가용 현금.
        allowed_budget: 이 전략에 할당된 현금.
        max_order_amount: 1회 최대 주문 금액.
        today: 오늘 날짜.
        current_hhmm: 현재 시각 HHMM.

    Returns:
        {"executed": bool, "error": str | None}
    """
    from src.trading.cross_momentum_rebalance import (
        CrossMomentumRebalanceAdapter,
        check_monthly_rebalance,
        load_rebalance_params,
    )

    # ACTIVE_STRATEGY env 일시 설정 (기존 _is_cross_momentum_enabled 가드 통과)
    prev = os.environ.get("ACTIVE_STRATEGY")
    os.environ["ACTIVE_STRATEGY"] = "cross_momentum"
    try:
        params = await load_rebalance_params(db)
        adapter = CrossMomentumRebalanceAdapter(params=params)

        current_holdings = {sym: h.quantity for sym, h in holdings_map.items()}

        executed = await check_monthly_rebalance(
            adapter,
            current_hhmm,
            today,
            client,
            current_holdings,
            allowed_budget,  # budget-bounded cash
        )

        return {"executed": executed, "error": None}
    except Exception as exc:
        log.exception("cross_momentum handler 실패")
        return {"executed": False, "error": str(exc)}
    finally:
        # env 복원
        if prev is None:
            os.environ.pop("ACTIVE_STRATEGY", None)
        else:
            os.environ["ACTIVE_STRATEGY"] = prev
