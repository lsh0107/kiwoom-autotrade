"""사전 스크리닝 수집기 (Design 012 PR 3).

일봉 캐시(daily_candles)에서 종목별 시계열을 읽어 스크리닝 엔진으로 통과/미통과를
계산하고, daily_screening_cache 테이블에 upsert한다.

실행 환경:
    Airflow worker — psycopg2 동기 접근.
    의존: daily_candle_collection DAG 완료 이후(Asset trigger).

rate limit/네트워크 없음 — 계산만 수행.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_DAYS = 260  # 52주(약 250거래일) + 여유분


def _get_db_conn() -> Any:
    """DB 연결. collectors.candles와 동일 규칙."""
    conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB") or os.environ.get("DATABASE_URL")
    if not conn_uri:
        raise ValueError("AIRFLOW_CONN_KIWOOM_DB 또는 DATABASE_URL 미설정")

    import psycopg2

    for prefix in (
        "postgresql+psycopg2://",
        "postgresql+asyncpg://",
        "postgres+psycopg2://",
        "postgres+asyncpg://",
        "postgres://",
    ):
        conn_uri = conn_uri.replace(prefix, "postgresql://")
    return psycopg2.connect(conn_uri)


def load_screening_params(
    profile: str = "momentum_breakout",
) -> dict[str, Any]:
    """스크리닝 파라미터 로드.

    Phase 2 이상에서는 `strategy_configs` 테이블에서 프로파일별 값을 가져오지만
    이 PR에서는 환경변수 기반 기본값을 사용한다.
    """
    return {
        "profile": profile,
        "threshold": float(os.environ.get("SCREEN_THRESHOLD", "0.75")),
        "volume_ratio": float(os.environ.get("SCREEN_VOLUME_RATIO", "0.8")),
        "min_stocks": int(os.environ.get("SCREEN_MIN_STOCKS", "10")),
    }


def _fetch_daily_series(
    conn: Any,
    symbol: str,
    lookback_days: int,
    on_date: _dt.date,
) -> list[dict[str, Any]]:
    """단일 종목의 daily_candles 시계열(시간 오름차순)을 읽는다."""
    start = on_date - _dt.timedelta(days=lookback_days)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM daily_candles
            WHERE symbol = %s AND date BETWEEN %s AND %s
            ORDER BY date ASC
            """,
            (symbol, start, on_date),
        )
        rows = cur.fetchall()
    return [
        {
            "date": r[0].strftime("%Y%m%d") if hasattr(r[0], "strftime") else str(r[0]),
            "open": int(r[1] or 0),
            "high": int(r[2] or 0),
            "low": int(r[3] or 0),
            "close": int(r[4] or 0),
            "volume": int(r[5] or 0),
        }
        for r in rows
    ]


def _rows_to_daily_price(rows: list[dict[str, Any]]) -> list[Any]:
    """dict 시계열을 DailyPrice 객체 리스트로 변환 (엔진 입력 타입)."""
    from src.broker.schemas import DailyPrice

    return [
        DailyPrice(
            date=r["date"],
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            volume=r["volume"],
        )
        for r in rows
    ]


def compute_screening(
    params: dict[str, Any],
    on_date: _dt.date,
    universe: Iterable[tuple[str, str]],
    *,
    get_sector: Any,
    get_hint: Any,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """유니버스 전체 스크리닝 수행 → upsert 대상 dict 리스트 반환.

    Args:
        params: `load_screening_params()` 결과.
        on_date: 평가 기준일 (장 마감일).
        universe: (symbol, name) 이터러블.
        get_sector: symbol → 섹터명 매핑 함수.
        get_hint: symbol → 전략 힌트 함수.
        lookback_days: 일봉 조회 lookback 일수.
        run_id: Airflow run_id (감사/추적).

    Returns:
        `DailyScreeningCacheStore.upsert_many` 에 바로 전달 가능한 행 리스트.
    """
    from src.screening.cache_store import result_to_row
    from src.screening.engine import check_screen_condition, rank_and_fill

    threshold = float(params["threshold"])
    volume_ratio = float(params["volume_ratio"])
    min_stocks = int(params["min_stocks"])
    profile = str(params.get("profile", "momentum_breakout"))

    candidates: list[dict[str, Any]] = []
    conn = _get_db_conn()
    try:
        for symbol, name in universe:
            try:
                series = _fetch_daily_series(conn, symbol, lookback_days, on_date)
            except Exception as exc:
                logger.warning("일봉 조회 실패: %s — %s", symbol, exc)
                continue

            daily = _rows_to_daily_price(series)
            result = check_screen_condition(daily, threshold, volume_ratio)
            if result is None:
                logger.debug("데이터 부족 스킵: %s (bars=%d)", symbol, len(daily))
                continue
            candidates.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "sector": get_sector(symbol),
                    "hint": get_hint(symbol),
                    **result,
                }
            )
    finally:
        conn.close()

    # 통과 + 보충된 상위 rank를 산출 (rank 부여)
    ranked = rank_and_fill(candidates, min_stocks=min_stocks)
    ranked_by_symbol = {c["symbol"]: c for c in ranked}

    rows: list[dict[str, Any]] = []
    for c in candidates:
        ranked_entry = ranked_by_symbol.get(c["symbol"])
        # 통과/보충된 항목은 rank_and_fill 결과의 rank를 반영
        merged = {**c, **(ranked_entry or {})}
        rows.append(
            result_to_row(
                merged,
                on_date=on_date,
                profile=profile,
                symbol=c["symbol"],
                name=c["name"],
                sector=c["sector"],
                hint=c["hint"],
                threshold=threshold,
                volume_ratio_param=volume_ratio,
                min_stocks_param=min_stocks,
                run_id=run_id,
            )
        )

    logger.info(
        "스크리닝 완료: 후보 %d / 통과+보충 %d (profile=%s, on_date=%s)",
        len(candidates),
        len(ranked),
        profile,
        on_date,
    )
    return rows


def upsert_screening_rows(rows: list[dict[str, Any]]) -> int:
    """daily_screening_cache ON CONFLICT upsert (psycopg2 동기).

    Airflow worker에서 SQLAlchemy async 엔진을 피하고 psycopg2로 직접 실행.
    """
    if not rows:
        logger.info("업서트할 스크리닝 행 없음")
        return 0

    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO daily_screening_cache
                (date, profile, symbol, name, sector, hint, rank, passed,
                 price_ratio, vol_ratio, bonus_score, close, high_52w, volume,
                 avg_volume, threshold, volume_ratio_param, min_stocks_param,
                 run_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, NOW(), NOW())
                ON CONFLICT (date, profile, symbol) DO UPDATE SET
                    name = EXCLUDED.name,
                    sector = EXCLUDED.sector,
                    hint = EXCLUDED.hint,
                    rank = EXCLUDED.rank,
                    passed = EXCLUDED.passed,
                    price_ratio = EXCLUDED.price_ratio,
                    vol_ratio = EXCLUDED.vol_ratio,
                    bonus_score = EXCLUDED.bonus_score,
                    close = EXCLUDED.close,
                    high_52w = EXCLUDED.high_52w,
                    volume = EXCLUDED.volume,
                    avg_volume = EXCLUDED.avg_volume,
                    threshold = EXCLUDED.threshold,
                    volume_ratio_param = EXCLUDED.volume_ratio_param,
                    min_stocks_param = EXCLUDED.min_stocks_param,
                    run_id = EXCLUDED.run_id,
                    updated_at = NOW()
            """
            for r in rows:
                cur.execute(
                    sql,
                    (
                        r["date"],
                        r["profile"],
                        r["symbol"],
                        r["name"],
                        r["sector"],
                        r["hint"],
                        int(r["rank"]),
                        bool(r["passed"]),
                        float(r["price_ratio"]),
                        float(r["vol_ratio"]),
                        int(r["bonus_score"]),
                        int(r["close"]),
                        int(r["high_52w"]),
                        int(r["volume"]),
                        int(r["avg_volume"]),
                        float(r["threshold"]),
                        float(r["volume_ratio_param"]),
                        int(r["min_stocks_param"]),
                        r.get("run_id"),
                    ),
                )
        conn.commit()
        logger.info("daily_screening_cache upsert 완료: %d건", len(rows))
        return len(rows)
    finally:
        conn.close()
