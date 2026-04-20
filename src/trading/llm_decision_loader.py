"""LLM 승인 결정 로더 — llm_decisions 테이블 → live_trader 브릿지.

설계: docs/design/design-010-llm-decision-integration.md

승인된(``status='approved'``) LLM 결정을 DB에서 읽어 live_trader가
소비할 수 있는 형태로 변환한다.

이 모듈 자체는 live_trader 동작을 변경하지 않는다(순수 조회). PR 2에서
``scripts/live_trader.py``가 이 loader를 호출하여 universe / symbol_bias /
strategy_param_hint를 반영한다.

안전 원칙:
    - DB 쿼리 timeout 2초. 실패 시 빈 결과를 반환하되 예외는 전파하지 않는다.
    - ``database_url`` 이 없으면 즉시 빈 결과를 반환한다 (no-op).
    - ``status='approved'`` 만 읽는다. pending/rejected/applied 무시.
    - ``created_at >= NOW() - since_hours`` 시간창 필터로 오래된 결정 재적용 차단.

사용 타입(design-010 §3):
    - ``universe_adjust``: 종목 제외/추가 제안
    - ``symbol_bias``: 개별 종목 매수/매도 가산/차단
    - ``strategy_param_hint``: 전략 파라미터 조정 힌트

반환 형식:
    ``dict[str, list[dict]]`` — key는 decision_type 문자열, value는 해당 타입의
    ``content`` JSON dict 리스트. 인식 불가능한 decision_type은 제외된다.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

log = logging.getLogger(__name__)


# 소비 가능한 decision_type 화이트리스트.
# 이 외의 타입은 무시하고 WARN 로그만 남긴다.
SUPPORTED_DECISION_TYPES: tuple[str, ...] = (
    "universe_adjust",
    "symbol_bias",
    "strategy_param_hint",
)

# DB 쿼리 timeout (초). 실패 시 graceful.
DB_QUERY_TIMEOUT_SEC: float = 2.0


async def load_approved_decisions(
    database_url: str | None,
    since_hours: int = 24,
    query_timeout_sec: float = DB_QUERY_TIMEOUT_SEC,
) -> dict[str, list[dict[str, Any]]]:
    """승인된 LLM 결정을 DB에서 읽어 decision_type별로 그룹화한다.

    Args:
        database_url: PostgreSQL asyncpg URL. None/빈문자열이면 빈 결과 반환.
        since_hours: 현재 시각 기준 몇 시간 이내 생성된 결정만 포함할지.
        query_timeout_sec: DB 쿼리 전체 타임아웃 (초). 초과 시 빈 결과.

    Returns:
        ``{decision_type: [content_dict, ...]}`` 형식.
        결과가 없거나 실패 시 빈 dict.

    Notes:
        - 예외는 내부에서 삼킨다 (graceful). 호출자는 결과 dict만 확인하면 된다.
        - 반환된 content dict는 DB JSON을 그대로 전달한 것이며, 소비자 측에서
          스키마를 검증해야 한다.
    """
    if not database_url:
        log.debug("llm_decision_loader: database_url 없음 — 빈 결과 반환")
        return {}

    try:
        return await asyncio.wait_for(
            _fetch_approved(database_url, since_hours),
            timeout=query_timeout_sec,
        )
    except TimeoutError:
        log.warning(
            "llm_decision_loader: DB 쿼리 %.1fs 타임아웃 — 빈 결과 반환",
            query_timeout_sec,
        )
        return {}
    except Exception:
        log.warning("llm_decision_loader: DB 조회 실패 — 빈 결과 반환", exc_info=True)
        return {}


async def _fetch_approved(
    database_url: str,
    since_hours: int,
) -> dict[str, list[dict[str, Any]]]:
    """실제 DB 조회 본체. 예외는 상위 ``load_approved_decisions``가 처리한다.

    Args:
        database_url: PostgreSQL asyncpg URL.
        since_hours: 시간창 (시간).

    Returns:
        ``{decision_type: [content, ...]}``. 인식 불가능한 decision_type은 제외.

    Raises:
        Exception: DB 연결/쿼리 실패 시. 호출자가 처리한다.
    """
    # lazy import: live_trader 외부(Airflow 등)에서 무거운 패키지 지연 로드
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_factory() as session:
            return await _query_and_group(session, since_hours)
    finally:
        await engine.dispose()


async def _query_and_group(
    session: Any,
    since_hours: int,
) -> dict[str, list[dict[str, Any]]]:
    """열린 세션에서 approved 결정을 조회하고 decision_type별로 그룹화한다.

    테스트 편의를 위해 분리되어 있다(인메모리 SQLite 세션으로 직접 검증 가능).

    Args:
        session: 열린 SQLAlchemy ``AsyncSession`` (duck-typed으로 ``execute`` 필요).
        since_hours: 시간창 (시간).

    Returns:
        ``{decision_type: [content, ...]}`` 형식. 지원되지 않는 타입은 제외.
    """
    from sqlalchemy import select

    from src.models.llm_decision import LLMDecision
    from src.utils.time import now_kst

    cutoff = now_kst() - timedelta(hours=since_hours)

    stmt = (
        select(LLMDecision)
        .where(LLMDecision.status == "approved")
        .where(LLMDecision.created_at >= cutoff)
        .order_by(LLMDecision.created_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        dtype = row.decision_type
        if dtype not in SUPPORTED_DECISION_TYPES:
            log.warning(
                "llm_decision_loader: 지원하지 않는 decision_type=%s (id=%s) — 무시",
                dtype,
                row.id,
            )
            continue
        content = row.content if isinstance(row.content, dict) else {}
        grouped.setdefault(dtype, []).append(content)

    log.info(
        "llm_decision_loader: approved 결정 %d건 로드 (타입별: %s)",
        sum(len(v) for v in grouped.values()),
        {k: len(v) for k, v in grouped.items()},
    )
    return grouped
