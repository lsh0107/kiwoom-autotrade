"""전략 런타임 레지스트리 — strategy_runtime 테이블 기반 활성 전략 조회.

design-025: 매 tick 마다 enabled=true 전략을 조회하고 TTL 캐시로 DB 부하를 줄인다.
"""

from __future__ import annotations

import time as _time

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_runtime import StrategyRuntime

logger = structlog.get_logger("trading.strategy_registry")


class StrategyRegistry:
    """strategy_runtime 테이블에서 활성 전략을 TTL 캐시로 관리.

    Args:
        ttl_seconds: 캐시 유효 시간 (초). 기본 5초.
    """

    def __init__(self, ttl_seconds: float = 5.0) -> None:
        self._cache: list[StrategyRuntime] | None = None
        self._cached_at: float = 0.0
        self._ttl = ttl_seconds

    def invalidate(self) -> None:
        """캐시 강제 무효화."""
        self._cache = None
        self._cached_at = 0.0

    async def load_enabled(self, db: AsyncSession) -> list[StrategyRuntime]:
        """enabled=true 전략 조회 (TTL 캐시).

        TTL 이내이면 캐시 반환, 초과 시 DB 재조회.

        Args:
            db: 비동기 DB 세션.

        Returns:
            활성 전략 StrategyRuntime 리스트.
        """
        now = _time.monotonic()
        if self._cache is not None and (now - self._cached_at) < self._ttl:
            return self._cache

        result = await db.execute(select(StrategyRuntime).where(StrategyRuntime.enabled.is_(True)))
        rows = list(result.scalars().all())

        self._cache = rows
        self._cached_at = now
        await logger.adebug("strategy_registry 캐시 갱신", count=len(rows))
        return rows

    async def is_enabled(self, db: AsyncSession, strategy: str) -> bool:
        """특정 전략이 활성화되어 있는지 확인.

        Args:
            db: 비동기 DB 세션.
            strategy: 전략 식별자 (cross_momentum / short_swing / multi_regime).

        Returns:
            활성 여부.
        """
        enabled = await self.load_enabled(db)
        return any(rt.strategy == strategy for rt in enabled)
