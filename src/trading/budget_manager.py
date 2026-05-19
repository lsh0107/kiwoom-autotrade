"""전략별 자산(budget) 할당 관리 — design-025.

strategy_runtime.budget_pct 기반으로 전략별 가용 현금, 1회 주문 한도,
일일 주문 횟수 한도를 계산한다.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_runtime import StrategyRuntime

logger = structlog.get_logger("trading.budget_manager")


class BudgetManager:
    """전략별 예산 할당.

    strategy_runtime 테이블에서 budget_pct, max_order_amount, max_daily_orders를
    읽어 전략별 한도를 반환한다.
    """

    async def _get_runtime(self, db: AsyncSession, strategy: str) -> StrategyRuntime | None:
        """전략 런타임 행 조회.

        Args:
            db: 비동기 DB 세션.
            strategy: 전략 식별자.

        Returns:
            StrategyRuntime 또는 None.
        """
        result = await db.execute(
            select(StrategyRuntime).where(StrategyRuntime.strategy == strategy)
        )
        return result.scalar_one_or_none()

    async def allowed_cash(self, db: AsyncSession, strategy: str, available_cash: int) -> int:
        """전략에 할당된 가용 현금 계산.

        strategy_runtime.budget_pct * available_cash.
        런타임 행이 없으면 0 반환 (안전).

        Args:
            db: 비동기 DB 세션.
            strategy: 전략 식별자.
            available_cash: 계좌 전체 가용 현금 (원).

        Returns:
            전략 할당 현금 (원, 정수 내림).
        """
        rt = await self._get_runtime(db, strategy)
        if rt is None:
            await logger.awarning("strategy_runtime 미등록", strategy=strategy)
            return 0
        return int(Decimal(str(available_cash)) * rt.budget_pct)

    async def max_order_amount(self, db: AsyncSession, strategy: str) -> int:
        """전략의 1회 최대 주문 금액.

        Args:
            db: 비동기 DB 세션.
            strategy: 전략 식별자.

        Returns:
            1회 최대 주문 금액 (원). 미등록 시 0.
        """
        rt = await self._get_runtime(db, strategy)
        if rt is None:
            return 0
        return rt.max_order_amount

    async def max_daily_orders(self, db: AsyncSession, strategy: str) -> int:
        """전략의 일일 최대 주문 횟수.

        Args:
            db: 비동기 DB 세션.
            strategy: 전략 식별자.

        Returns:
            일일 최대 주문 횟수. 미등록 시 0.
        """
        rt = await self._get_runtime(db, strategy)
        if rt is None:
            return 0
        return rt.max_daily_orders
