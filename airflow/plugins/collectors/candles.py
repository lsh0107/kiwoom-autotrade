"""일봉 캐시 수집기 (pykrx 기반).

Design 011 PR 2. KOSPI/KOSDAQ 전 종목 일봉을 pykrx에서 수집하여
daily_candles 테이블에 upsert한다.

rate limit 고려해 pykrx 호출 간 1.5초 슬립. 6자리 티커 앞자리 0 유지.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

try:
    from pykrx import stock
except ImportError:
    stock = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_SLEEP_INTERVAL = 1.5


def _ensure_symbol(ticker: Any) -> str:
    """KRX 티커를 문자열 6자리로 정규화.

    Args:
        ticker: 원본 티커 값 (int 또는 str).

    Returns:
        6자리 종목 코드 문자열.
    """
    s = str(ticker).strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def collect_daily_ohlcv(
    date_str: str,
    market: str = "KOSPI",
) -> list[dict]:
    """특정 일자의 전 종목 일봉 OHLCV 수집.

    Args:
        date_str: 조회 날짜 (YYYYMMDD).
        market: 시장 구분 ("KOSPI" | "KOSDAQ").

    Returns:
        레코드 목록. 각 dict는 symbol/date/open/high/low/close/volume 포함.

    Raises:
        ImportError: pykrx 미설치 시.
    """
    if stock is None:
        raise ImportError("pykrx 패키지 미설치 — uv add --group airflow pykrx")

    try:
        df = stock.get_market_ohlcv_by_ticker(date_str, market=market)
    except (KeyError, ValueError) as exc:
        logger.warning(
            "일봉 수집 실패(KRX 데이터 미제공): %s %s — %s",
            date_str,
            market,
            exc,
        )
        return []

    time.sleep(_SLEEP_INTERVAL)

    if df is None or df.empty:
        logger.info("일봉 없음: %s %s", date_str, market)
        return []

    df = df.reset_index()
    # 컬럼명 한글 → 영문 정규화
    rename_map = {
        "티커": "symbol",
        "시가": "open",
        "고가": "high",
        "저가": "low",
        "종가": "close",
        "거래량": "volume",
    }
    df = df.rename(columns=rename_map)

    records: list[dict] = []
    for row in df.to_dict("records"):
        try:
            sym = _ensure_symbol(row.get("symbol", ""))
            if not sym:
                continue
            records.append(
                {
                    "symbol": sym,
                    "date": date_str,
                    "open": int(row.get("open", 0) or 0),
                    "high": int(row.get("high", 0) or 0),
                    "low": int(row.get("low", 0) or 0),
                    "close": int(row.get("close", 0) or 0),
                    "volume": int(row.get("volume", 0) or 0),
                }
            )
        except (ValueError, TypeError) as exc:
            logger.debug("레코드 변환 실패 스킵: %s — %s", row, exc)
            continue

    logger.info(
        "일봉 수집 완료: %s %s — %d종목",
        date_str,
        market,
        len(records),
    )
    return records


def _get_db_conn() -> Any:
    """DB 연결. storage._get_db_conn와 동일 규칙."""
    conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB")
    if not conn_uri:
        conn_uri = os.environ.get("DATABASE_URL")
    if not conn_uri:
        raise ValueError("AIRFLOW_CONN_KIWOOM_DB 또는 DATABASE_URL 미설정")

    import psycopg2

    conn_uri = conn_uri.replace("postgresql+psycopg2://", "postgresql://")
    conn_uri = conn_uri.replace("postgresql+asyncpg://", "postgresql://")
    conn_uri = conn_uri.replace("postgres+psycopg2://", "postgresql://")
    conn_uri = conn_uri.replace("postgres+asyncpg://", "postgresql://")
    conn_uri = conn_uri.replace("postgres://", "postgresql://")

    return psycopg2.connect(conn_uri)


def upsert_daily_candles(
    records: list[dict],
    source: str = "pykrx",
) -> int:
    """daily_candles에 ON CONFLICT upsert.

    Args:
        records: symbol/date(YYYYMMDD)/open/high/low/close/volume dict 목록.
        source: 수집 출처 태그 ("pykrx" | "kiwoom" | "backfill").

    Returns:
        처리된 레코드 수.

    Raises:
        RuntimeError: DB 저장 실패 시.
    """
    if not records:
        logger.info("업서트할 레코드 없음")
        return 0

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO daily_candles
                    (symbol, date, open, high, low, close, volume, source,
                     created_at, updated_at)
                    VALUES (%s, to_date(%s, 'YYYYMMDD'), %s, %s, %s, %s, %s, %s,
                            NOW(), NOW())
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        source = EXCLUDED.source,
                        updated_at = NOW()
                """
                for rec in records:
                    cur.execute(
                        sql,
                        (
                            rec["symbol"],
                            rec["date"],
                            int(rec["open"]),
                            int(rec["high"]),
                            int(rec["low"]),
                            int(rec["close"]),
                            int(rec["volume"]),
                            source,
                        ),
                    )
            conn.commit()
            logger.info(
                "daily_candles upsert 완료: %d건 (source=%s)",
                len(records),
                source,
            )
            return len(records)
        finally:
            conn.close()
    except Exception as exc:
        raise RuntimeError(
            f"daily_candles 업서트 실패: count={len(records)} source={source}"
        ) from exc
