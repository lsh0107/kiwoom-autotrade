"""활성 전략 관리 모듈.

ADR-024 (env ACTIVE_STRATEGY 단일 토글) → design-025 (DB strategy_runtime 다중 토글) 전환.

design-025 5/N: env 의존 가드를 DB 기반으로 교체.
``get_active_strategy()`` 는 호환용으로 유지 (UI status 표시 등).
신규 코드는 ``is_strategy_enabled_db()`` 사용 권장.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ActiveStrategy(StrEnum):
    """활성 전략 enum (호환용).

    design-025 후속에서 점진적으로 제거 예정. 신규 코드는 strategy_runtime 사용.
    """

    CROSS_MOMENTUM = "cross_momentum"
    MULTI_REGIME = "multi_regime"
    SHORT_SWING = "short_swing"
    NONE = "none"


def get_active_strategy() -> ActiveStrategy:
    """환경변수 ACTIVE_STRATEGY 읽기 (deprecated, UI status 호환용).

    Returns:
        ActiveStrategy 인스턴스. 잘못된 값이면 NONE.
    """
    raw = os.environ.get("ACTIVE_STRATEGY", "none").strip().lower()
    try:
        return ActiveStrategy(raw)
    except ValueError:
        return ActiveStrategy.NONE


async def is_strategy_enabled_db(db: AsyncSession, strategy: str) -> bool:
    """strategy_runtime DB 에서 전략 활성 여부 조회 (design-025).

    DB 우선. row 가 없거나 조회 실패 시 env ``ACTIVE_STRATEGY`` 로 fallback.

    Args:
        db: AsyncSession.
        strategy: 전략 식별자 (cross_momentum / short_swing / multi_regime).

    Returns:
        True 면 enabled.
    """
    import logging

    log = logging.getLogger("config.active_strategy")
    try:
        from sqlalchemy import select

        from src.models.strategy_runtime import StrategyRuntime

        result = await db.execute(
            select(StrategyRuntime).where(StrategyRuntime.strategy == strategy)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return bool(row.enabled)
    except Exception as exc:
        log.warning("strategy_runtime DB 조회 실패, env fallback: %s", exc)

    return get_active_strategy().value == strategy
