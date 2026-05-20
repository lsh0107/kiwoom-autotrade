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
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovedDecisionEntry:
    """`load_approved_decisions_with_ids` 반환 항목.

    id 추적이 필요한 호출자(예: live_trader applied 마킹)가 사용한다.
    기존 ``load_approved_decisions`` 는 content-only dict 만 반환하므로
    id 추적이 필요 없는 호출자에게는 영향이 없다.
    """

    id: uuid.UUID
    content: dict[str, Any]


def apply_universe_decisions(
    symbols: list[str],
    decisions: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """universe_adjust / symbol_bias 승인 결정을 symbols 리스트에 적용한다.

    설계: docs/design/design-010-llm-decision-integration.md §3.

    적용 규칙 (사용자 의도 보존):
        - ``universe_adjust.exclude`` 에 포함된 종목은 symbols에서 제거된다.
        - ``symbol_bias`` 의 ``bias == 'block_buy'`` 인 종목은 symbols에서 제거된다
          (매수 자체를 차단하려는 의도이므로 유니버스에서 제외).
        - 그 외 bias (boost_buy / block_sell 등)는 PR 2에서는 반영하지 않는다
          (로그만 남기고 symbols는 그대로 유지).
        - decisions에 없는 키는 무시된다.

    Args:
        symbols: 원본 유니버스 종목 리스트 (사용자 선택/screening 결과).
        decisions: ``load_approved_decisions`` 반환 형식의 dict.

    Returns:
        필터링된 symbols 리스트. 원본 순서 유지, 중복 제거는 하지 않는다.

    Notes:
        이 함수는 feature flag가 켜진 경우에만 호출되어야 한다.
        flag off일 때는 호출자가 이 함수를 건너뛰고 원본 symbols를 사용한다.
    """
    exclude: set[str] = set()

    for content in decisions.get("universe_adjust", []):
        raw = content.get("exclude", [])
        if isinstance(raw, list):
            exclude.update(str(s) for s in raw if s)

    for content in decisions.get("symbol_bias", []):
        bias = content.get("bias")
        symbol = content.get("symbol")
        if not symbol:
            continue
        if bias == "block_buy":
            exclude.add(str(symbol))

    if not exclude:
        return list(symbols)

    filtered = [s for s in symbols if s not in exclude]
    removed = [s for s in symbols if s in exclude]
    if removed:
        log.info(
            "apply_universe_decisions: %d개 종목 제외 (approved LLM 결정 반영): %s",
            len(removed),
            removed,
        )
    return filtered


def summarize_decisions(decisions: dict[str, list[dict[str, Any]]]) -> str:
    """shadow/관찰 모드용: 승인 결정 요약 문자열 생성.

    Args:
        decisions: ``load_approved_decisions`` 반환 dict.

    Returns:
        "universe_adjust=2, symbol_bias=1, strategy_param_hint=0" 형식 문자열.
        빈 dict이면 "no approved decisions".
    """
    if not decisions:
        return "no approved decisions"
    return ", ".join(f"{k}={len(v)}" for k, v in sorted(decisions.items()))


# 소비 가능한 decision_type 화이트리스트.
# 이 외의 타입은 무시하고 WARN 로그만 남긴다.
SUPPORTED_DECISION_TYPES: tuple[str, ...] = (
    "universe_adjust",
    "symbol_bias",
    "strategy_param_hint",
)

# strategy_param_hint 에서 override 허용되는 파라미터 키 + 유효 범위.
# (min, max, is_int) — is_int=True 면 int 캐스팅 + 정수형 강제.
# 이 화이트리스트 외의 키는 무시하고 WARN 로그만 남긴다.
# 범위를 벗어나는 값은 거부(적용 안 함) + 경고 로그.
LLM_PARAM_WHITELIST: dict[str, tuple[float, float, bool]] = {
    "volume_ratio": (0.5, 2.0, False),
    "atr_stop_mult": (0.5, 3.0, False),
    "atr_tp_mult": (1.0, 5.0, False),
    "gap_risk_threshold": (-0.10, -0.01, False),
    "max_positions": (1, 10, True),
}


def extract_strategy_param_hints(
    decisions: dict[str, list[dict[str, Any]]],
) -> dict[str, float | int]:
    """approved strategy_param_hint 결정에서 whitelist 파라미터를 추출한다.

    설계: docs/design/design-010-llm-decision-integration.md §3 / PR 3.

    추출 규칙:
        - ``decisions["strategy_param_hint"]`` 리스트를 순회한다.
        - 리스트는 ``load_approved_decisions`` 가 ``created_at`` desc 로
          정렬되어 있으므로, **앞(최신) 결정의 값이 우선**한다.
        - 각 content는 ``{"strategy": "...", "params": {key: value}}`` 또는
          ``{key: value}`` 형태를 지원한다 (params 키가 없으면 content 자체가 params).
        - whitelist 에 없는 키는 무시 + WARN.
        - 숫자(int/float/str→cast) 가 아닌 값은 무시 + WARN.
        - whitelist 범위 (min, max) 밖이면 무시 + WARN.
        - is_int=True 인 키는 정수로 캐스팅 (소수점 값은 int() 변환).

    Args:
        decisions: ``load_approved_decisions`` 반환 dict.

    Returns:
        ``{"volume_ratio": 0.9, "max_positions": 3, ...}``.
        적용할 힌트가 없으면 빈 dict.

    Notes:
        이 함수는 feature flag 검사를 하지 않는다. 호출자가 flag 를 확인한 뒤
        적용 여부를 결정해야 한다.
    """
    hints: list[dict[str, Any]] = decisions.get("strategy_param_hint", [])
    if not hints:
        return {}

    result: dict[str, float | int] = {}
    for content in hints:
        if not isinstance(content, dict):
            continue
        # params 서브키 우선, 없으면 content 자체를 params 로 간주
        params = content.get("params")
        if not isinstance(params, dict):
            params = content

        for key, raw_value in params.items():
            if key not in LLM_PARAM_WHITELIST:
                # strategy/params 같은 메타 키 제외 (WARN 생략)
                if key in {"strategy", "reason", "confidence"}:
                    continue
                log.warning(
                    "extract_strategy_param_hints: 화이트리스트 외 키=%s 무시",
                    key,
                )
                continue
            # 이미 더 최신 값이 들어 있으면 건너뜀 (created_at desc 기준 최신 우선)
            if key in result:
                continue

            validated = _validate_param(key, raw_value)
            if validated is None:
                continue
            result[key] = validated

    if result:
        log.info(
            "extract_strategy_param_hints: %d개 힌트 추출 %s",
            len(result),
            result,
        )
    return result


def _validate_param(key: str, raw_value: Any) -> float | int | None:
    """whitelist 키 하나에 대해 타입/범위 검증 후 변환된 값을 반환한다.

    Args:
        key: whitelist 키.
        raw_value: content 에서 읽은 원시 값.

    Returns:
        검증 통과 시 float/int, 실패 시 None.
    """
    lo, hi, is_int = LLM_PARAM_WHITELIST[key]

    # bool 은 int 서브클래스지만 의도한 "숫자"가 아니므로 거부
    if isinstance(raw_value, bool):
        log.warning(
            "extract_strategy_param_hints: key=%s value=%r bool 타입 거부",
            key,
            raw_value,
        )
        return None

    try:
        if is_int:
            # 숫자 문자열/float 모두 수용하되 int 로 강제
            num: float = float(raw_value)
        else:
            num = float(raw_value)
    except (TypeError, ValueError):
        log.warning(
            "extract_strategy_param_hints: key=%s value=%r 숫자 변환 실패 — 무시",
            key,
            raw_value,
        )
        return None

    if num < lo or num > hi:
        log.warning(
            "extract_strategy_param_hints: key=%s value=%s 범위[%s, %s] 이탈 — 거부",
            key,
            num,
            lo,
            hi,
        )
        return None

    if is_int:
        return int(num)
    return num


def apply_llm_param_hints(
    db_config: dict[str, Any],
    llm_hints: dict[str, float | int],
) -> dict[str, Any]:
    """DB strategy_config 에 없는 키만 LLM 힌트로 채워 넣는다.

    설계: docs/design/design-010-llm-decision-integration.md §4 (사용자 우선).

    우선순위:
        1. DB(``db_config``)에 이미 있는 키 → 그대로 유지 (사용자 설정 우선)
        2. DB 에 없는 키 → ``llm_hints`` 값으로 채움
        3. 둘 다 없는 키 → 결과에도 없음 (코드 기본값 경로)

    Args:
        db_config: ``load_all_config_raw`` 결과. key → value (JSONB raw).
        llm_hints: ``extract_strategy_param_hints`` 결과.

    Returns:
        병합된 dict. ``db_config`` 는 변경되지 않는다 (shallow copy).

    Notes:
        반환 dict 는 ``build_momentum_params`` / ``build_mr_params`` 에 그대로
        전달 가능한 형식 ({key: value} 형태, JSONB ``{"value": x}`` 래핑 없음).
    """
    merged: dict[str, Any] = dict(db_config)
    applied: list[str] = []
    for key, value in llm_hints.items():
        if key in merged:
            # 사용자 DB 설정 우선 — 건너뜀
            continue
        merged[key] = value
        applied.append(key)

    if applied:
        log.info(
            "apply_llm_param_hints: DB에 없는 %d개 키에 LLM 힌트 적용: %s",
            len(applied),
            applied,
        )
    return merged


async def mark_decisions_applied(
    session: Any,
    decision_ids: list[uuid.UUID],
) -> None:
    """승인된 결정을 실제 적용 완료로 표시한다.

    approve(사용자 승인)와 applied(전략 반영 완료)를 구분하기 위한 함수.
    status='applied', applied_at=현재 시각으로 일괄 갱신한다.

    Args:
        session: 열린 SQLAlchemy ``AsyncSession``.
        decision_ids: 적용 완료할 결정 ID 목록. 빈 리스트면 no-op.
    """
    if not decision_ids:
        return

    from sqlalchemy import update

    from src.models.llm_decision import LLMDecision
    from src.utils.time import now_kst

    now = now_kst()
    stmt = (
        update(LLMDecision)
        .where(LLMDecision.id.in_(decision_ids))
        .values(status="applied", applied_at=now)
    )
    await session.execute(stmt)
    log.info(
        "mark_decisions_applied: %d건 applied 처리",
        len(decision_ids),
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


async def load_approved_decisions_with_ids(
    database_url: str | None,
    since_hours: int = 24,
    query_timeout_sec: float = DB_QUERY_TIMEOUT_SEC,
) -> dict[str, list[ApprovedDecisionEntry]]:
    """``load_approved_decisions`` + id 추적 버전.

    승인 결정을 ``ApprovedDecisionEntry`` (id + content) 리스트로 그룹화한다.
    live_trader 에서 applied 마킹 대상 id 식별에 사용한다.

    Args:
        database_url: PostgreSQL asyncpg URL. None/빈문자열이면 빈 결과.
        since_hours: 현재 시각 기준 몇 시간 이내 생성된 결정만 포함할지.
        query_timeout_sec: DB 쿼리 전체 타임아웃 (초). 초과 시 빈 결과.

    Returns:
        ``{decision_type: [ApprovedDecisionEntry, ...]}`` 형식.
        결과가 없거나 실패 시 빈 dict.

    Notes:
        예외는 내부에서 삼킨다 (graceful). ``load_approved_decisions`` 와 동일한
        안전 정책을 따른다.
    """
    if not database_url:
        log.debug("llm_decision_loader: database_url 없음 — 빈 결과 반환 (with_ids)")
        return {}

    try:
        return await asyncio.wait_for(
            _fetch_approved_with_ids(database_url, since_hours),
            timeout=query_timeout_sec,
        )
    except TimeoutError:
        log.warning(
            "llm_decision_loader: DB 쿼리 %.1fs 타임아웃 (with_ids) — 빈 결과",
            query_timeout_sec,
        )
        return {}
    except Exception:
        log.warning(
            "llm_decision_loader: DB 조회 실패 (with_ids) — 빈 결과 반환",
            exc_info=True,
        )
        return {}


async def _fetch_approved_with_ids(
    database_url: str,
    since_hours: int,
) -> dict[str, list[ApprovedDecisionEntry]]:
    """``_fetch_approved`` 의 id 추적 버전."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_factory() as session:
            return await _query_and_group_with_ids(session, since_hours)
    finally:
        await engine.dispose()


async def _query_and_group_with_ids(
    session: Any,
    since_hours: int,
) -> dict[str, list[ApprovedDecisionEntry]]:
    """``_query_and_group`` 의 id 추적 버전.

    같은 쿼리/필터를 사용하되 ``ApprovedDecisionEntry`` 로 감싼다.
    호출자는 ``[e.content for e in entries]`` 로 기존 dict 형식을 얻을 수 있다.
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

    grouped: dict[str, list[ApprovedDecisionEntry]] = {}
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
        grouped.setdefault(dtype, []).append(ApprovedDecisionEntry(id=row.id, content=content))

    log.info(
        "llm_decision_loader: approved 결정 %d건 로드 (with_ids, 타입별: %s)",
        sum(len(v) for v in grouped.values()),
        {k: len(v) for k, v in grouped.items()},
    )
    return grouped


def determine_applied_decision_ids(
    entries_by_type: dict[str, list[ApprovedDecisionEntry]],
    *,
    symbols_before: list[str],
    symbols_after: list[str],
    db_config: dict[str, Any],
) -> list[uuid.UUID]:
    """실제로 live_trader 가 소비한 결정 ID 집합을 계산한다.

    정책 (FAIL #2):
        - ``universe_adjust.exclude`` : 그 결정이 지정한 종목 중 하나라도
          ``symbols_before`` 에 있었고 ``symbols_after`` 에서 빠졌다면 applied.
        - ``symbol_bias.block_buy`` : 그 결정의 ``symbol`` 이 ``symbols_before``
          에 있었고 ``symbols_after`` 에서 빠졌다면 applied.
        - ``strategy_param_hint`` : 그 결정의 키 중 적어도 하나가
            (1) whitelist 통과
            (2) ``db_config`` 에 없음 (DB 우선이 아니라서 실제 머지됨)
            (3) 같은 키에 대해 더 최신(앞쪽) 결정이 없음 (이 결정이 source)
            (4) ``_validate_param`` 통과
          를 모두 만족하면 applied.
        - 그 외 bias (boost_buy / block_sell 등)나 빈 결정은 applied 아님.

    Args:
        entries_by_type: ``load_approved_decisions_with_ids`` 결과.
        symbols_before: apply_universe_decisions 호출 전 symbols.
        symbols_after: apply_universe_decisions 호출 후 symbols.
        db_config: DB strategy_config 원본 (LLM 머지 전). 키 존재 여부만 사용.

    Returns:
        applied 처리할 결정 ID 리스트. 중복 없음. 순서 보장 없음.
    """
    removed: set[str] = set(symbols_before) - set(symbols_after)
    applied: set[uuid.UUID] = set()

    # universe_adjust
    for entry in entries_by_type.get("universe_adjust", []):
        raw = entry.content.get("exclude", [])
        if not isinstance(raw, list):
            continue
        excluded = {str(s) for s in raw if s}
        if excluded & removed:
            applied.add(entry.id)

    # symbol_bias (block_buy만 실제 universe 변경 원인)
    for entry in entries_by_type.get("symbol_bias", []):
        if entry.content.get("bias") != "block_buy":
            continue
        symbol = entry.content.get("symbol")
        if symbol and str(symbol) in removed:
            applied.add(entry.id)

    # strategy_param_hint — 최신 우선, DB 우선 정책 그대로 재현
    seen_keys: set[str] = set()
    for entry in entries_by_type.get("strategy_param_hint", []):
        content = entry.content
        params = content.get("params") if isinstance(content.get("params"), dict) else content
        if not isinstance(params, dict):
            continue
        for key, raw_value in params.items():
            if key not in LLM_PARAM_WHITELIST:
                continue
            if key in seen_keys:
                # 더 최신(앞쪽) 결정이 이미 이 키를 차지함 — 이 entry 는 override됨
                continue
            if key in db_config:
                # DB 우선 — 머지 안 됨, applied 아님
                seen_keys.add(key)  # 더 오래된 entry 도 같은 키로는 적용 못 함
                continue
            if _validate_param(key, raw_value) is None:
                # 범위/타입 검증 실패 — 적용 안 됨
                continue
            seen_keys.add(key)
            applied.add(entry.id)

    return sorted(applied, key=lambda u: str(u))


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
