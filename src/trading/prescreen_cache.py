"""사전 스크리닝 캐시 조회 모듈 (Design 012 PR 4).

Airflow DAG가 장 마감 후 `daily_screening_cache` 에 저장한 결과를
`live_trader` / `process_manager` 가 DB 단일 쿼리로 재사용한다.

Feature flag: `USE_PRESCREEN_CACHE` (기본 false).
Flag off 이거나 당일 데이터 부재 시 호출자는 기존 subprocess 경로로 폴백한다.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.models.daily_screening_cache import DailyScreeningCache

log = logging.getLogger(__name__)

_DEFAULT_PROFILE = "momentum_breakout"


def is_prescreen_cache_enabled() -> bool:
    """USE_PRESCREEN_CACHE 환경변수 활성 여부."""
    raw = os.environ.get("USE_PRESCREEN_CACHE", "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _sync_database_url(database_url: str | None) -> str | None:
    """async 드라이버 URL을 동기용으로 변환."""
    if not database_url:
        return None
    # 공용 async → sync 치환
    for src, dst in (
        ("+asyncpg", "+psycopg2"),
        ("+aiosqlite", ""),
    ):
        database_url = database_url.replace(src, dst)
    return database_url


def load_screened_rows(
    on_date: dt.date,
    profile: str = _DEFAULT_PROFILE,
    database_url: str | None = None,
) -> list[DailyScreeningCache]:
    """DB에서 당일 통과 종목 조회 (rank 오름차순).

    Args:
        on_date: 기준일 (장 마감일).
        profile: 스크리닝 프로파일명.
        database_url: 동기 DB URL. None이면 환경변수 DATABASE_URL.

    Returns:
        통과 종목 리스트. 캐시 부재 / DB 미설정 시 빈 리스트.
    """
    url = _sync_database_url(database_url or os.environ.get("DATABASE_URL"))
    if not url:
        log.warning("prescreen_cache: DATABASE_URL 미설정 — 캐시 미조회")
        return []
    try:
        engine = create_engine(url, future=True)
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory() as session:
            return list(
                session.execute(
                    select(DailyScreeningCache)
                    .where(
                        DailyScreeningCache.date == on_date,
                        DailyScreeningCache.profile == profile,
                        DailyScreeningCache.passed.is_(True),
                    )
                    .order_by(DailyScreeningCache.rank.asc())
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        log.warning("prescreen_cache 조회 실패 — 폴백: %s", exc)
        return []


def load_screened_symbols_from_db(
    on_date: dt.date | None = None,
    profile: str = _DEFAULT_PROFILE,
    database_url: str | None = None,
) -> list[str]:
    """DB에서 당일 통과 종목 코드 리스트 로드.

    Args:
        on_date: 조회 기준일. None이면 오늘(UTC 로컬 날짜). Airflow/KST 맥락에서는
            호출자가 today_kst()를 넘기는 것을 권장.

    Returns:
        종목 코드 리스트. 조회 실패/캐시 없음 시 빈 리스트.
    """
    target = on_date or dt.datetime.now(tz=dt.UTC).date()
    rows = load_screened_rows(target, profile=profile, database_url=database_url)
    return [r.symbol for r in rows]


def write_screened_json_from_db(
    on_date: dt.date,
    out_dir: Path,
    *,
    profile: str = _DEFAULT_PROFILE,
    database_url: str | None = None,
) -> Path | None:
    """당일 캐시 → `screened_{YYYYMMDD_HHMMSS}.json` 파일 생성.

    `scripts/screen_symbols.py` 가 만드는 JSON과 동일한 키 구조를 사용해
    `live_trader.load_screened_symbols()` 의 downstream 호환성을 유지한다.

    Returns:
        생성된 파일 경로. 캐시 비어 있으면 None.
    """
    rows = load_screened_rows(on_date, profile=profile, database_url=database_url)
    if not rows:
        log.info("prescreen_cache: %s(%s) 통과 종목 없음", on_date, profile)
        return None

    now = dt.datetime.now(tz=dt.UTC).astimezone()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"screened_{timestamp}.json"

    details: list[dict[str, Any]] = []
    for r in rows:
        details.append(
            {
                "symbol": r.symbol,
                "name": r.name,
                "sector": r.sector,
                "hint": r.hint,
                "rank": r.rank,
                "price_ratio": r.price_ratio,
                "vol_ratio": r.vol_ratio,
                "bonus_score": r.bonus_score,
                "close": r.close,
                "high_52w": r.high_52w,
                "volume": r.volume,
                "avg_volume": r.avg_volume,
                "date": r.date.strftime("%Y%m%d"),
            }
        )

    payload = {
        "run_at": now.isoformat(),
        "source": "prescreen_cache",
        "profile": profile,
        "threshold": rows[0].threshold,
        "volume_ratio": rows[0].volume_ratio_param,
        "min_stocks": rows[0].min_stocks_param,
        "passed_count": len(rows),
        "symbols": [r.symbol for r in rows],
        "details": details,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info(
        "prescreen_cache → JSON 브리지 생성: %s (%d종목)",
        out_path,
        len(rows),
    )
    return out_path
