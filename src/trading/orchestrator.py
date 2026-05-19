"""멀티 전략 오케스트레이터 — design-025.

매 tick 마다 활성 전략을 조회하고, 브로커 잔고를 1회 조회한 뒤
각 전략 handler 에 budget-bounded 파라미터를 전달하여 실행한다.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.base import BrokerClient
from src.trading.budget_manager import BudgetManager
from src.trading.strategy_registry import StrategyRegistry

log = logging.getLogger("trading.orchestrator")

# handler 함수 시그니처 통일
HandlerFn = Callable[..., Awaitable[dict[str, Any]]]


class Orchestrator:
    """멀티 전략 오케스트레이터.

    매 tick:
    1. registry.load_enabled() → 활성 전략 목록
    2. client.get_balance() 1회 → holdings + available_cash
    3. 전략별 handler 호출 (budget-bounded)

    Args:
        registry: StrategyRegistry 인스턴스.
        budget_manager: BudgetManager 인스턴스.
        handlers: {전략 식별자: handler 함수} 매핑.
    """

    def __init__(
        self,
        registry: StrategyRegistry,
        budget_manager: BudgetManager,
        handlers: dict[str, HandlerFn],
    ) -> None:
        self._registry = registry
        self._budget = budget_manager
        self._handlers = handlers

    async def tick(
        self,
        db: AsyncSession,
        client: BrokerClient,
        current_hhmm: str,
        today: date,
    ) -> dict[str, Any]:
        """메인 루프에서 매 tick 호출.

        Args:
            db: 비동기 DB 세션.
            client: 브로커 클라이언트.
            current_hhmm: 현재 시각 HHMM.
            today: 오늘 날짜 (KST).

        Returns:
            {전략 식별자: handler 반환값} 매핑.
        """
        enabled = await self._registry.load_enabled(db)
        if not enabled:
            log.info("활성 전략 없음 — idle")
            return {}

        # 브로커 잔고 1회 조회 (전략 간 공유)
        balance = await client.get_balance()
        holdings_map = {h.symbol: h for h in balance.holdings}
        available_cash = balance.available_cash

        results: dict[str, Any] = {}
        for runtime in enabled:
            strategy_name = runtime.strategy
            handler = self._handlers.get(strategy_name)
            if handler is None:
                log.warning("handler 미등록: %s (skip)", strategy_name)
                continue

            allowed_budget = await self._budget.allowed_cash(db, strategy_name, available_cash)
            max_order = await self._budget.max_order_amount(db, strategy_name)

            log.info(
                "전략 실행: %s (budget=%s, max_order=%s)",
                strategy_name,
                f"{allowed_budget:,}",
                f"{max_order:,}",
            )

            try:
                result = await handler(
                    db=db,
                    client=client,
                    holdings_map=holdings_map,
                    available_cash=available_cash,
                    allowed_budget=allowed_budget,
                    max_order_amount=max_order,
                    today=today,
                    current_hhmm=current_hhmm,
                )
                results[strategy_name] = result
            except Exception:
                log.exception("전략 handler 실패: %s", strategy_name)
                results[strategy_name] = {"error": True}

        return results
