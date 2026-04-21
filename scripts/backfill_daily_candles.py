"""일봉 백필 스크립트.

Design 011 PR 2. daily_candles 테이블에 과거 N일치 OHLCV를
pykrx `get_market_ohlcv_by_date`로 종목별 루프 수집하여 upsert.

예시:
    uv run python scripts/backfill_daily_candles.py --days 300 --market all
    uv run python scripts/backfill_daily_candles.py --days 60 --market KOSPI --sleep 1.0
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any

# airflow/plugins 경로 주입 (collectors.candles 재사용)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
_PLUGINS = os.path.join(_ROOT, "airflow", "plugins")
for _p in (_PLUGINS,):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("backfill_daily_candles")


def _list_tickers_from_db(market: str) -> list[str]:
    """DB `stocks` 테이블에서 활성 종목 티커 목록 조회 (pykrx fallback).

    pykrx `get_market_ticker_list`가 KRX API 변경 등으로 빈 리스트를
    반환할 때의 방어적 fallback 경로. 환경변수 DATABASE_URL 사용.

    Args:
        market: "KOSPI" | "KOSDAQ".

    Returns:
        6자리 티커 문자열 목록 (is_active=True). DB 조회 실패 시 [].
    """
    try:
        from sqlalchemy import create_engine, text

        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            # src.config.settings 경유 (프로젝트 루트 import 경로 보강)
            if _ROOT not in sys.path:
                sys.path.insert(0, _ROOT)
            from src.config.settings import get_settings

            db_url = get_settings().database_url
        if not db_url:
            return []
        # async URL(asyncpg)을 sync용(psycopg2)으로 치환
        sync_url = db_url.replace("+asyncpg", "").replace("postgresql+psycopg", "postgresql")
        engine = create_engine(sync_url, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT symbol FROM stocks WHERE market = :market AND is_active = true"),
                    {"market": market},
                ).fetchall()
        finally:
            engine.dispose()
        return [str(r[0]).zfill(6) for r in rows]
    except Exception as exc:
        logger.warning("DB fallback 티커 조회 실패 market=%s: %s", market, exc)
        return []


def _list_tickers(market: str) -> list[str]:
    """시장 전 종목 티커 목록.

    Args:
        market: "KOSPI" | "KOSDAQ".

    Returns:
        6자리 티커 문자열 목록.
    """
    from pykrx import stock as pykrx_stock

    try:
        tickers = pykrx_stock.get_market_ticker_list(market=market)
    except Exception as exc:
        logger.warning("pykrx get_market_ticker_list 실패 market=%s: %s", market, exc)
        tickers = []

    if not tickers:
        logger.warning(
            "pykrx가 %s 티커 빈 리스트 반환 — DB stocks 테이블 fallback 사용",
            market,
        )
        return _list_tickers_from_db(market)
    return [str(t).zfill(6) for t in tickers]


def _fetch_single_ohlcv(
    ticker: str,
    from_date: str,
    to_date: str,
) -> list[dict]:
    """한 종목 날짜 범위 일봉 수집.

    Args:
        ticker: 6자리 종목코드.
        from_date: YYYYMMDD 시작.
        to_date: YYYYMMDD 끝.

    Returns:
        레코드 목록 (symbol/date/open/high/low/close/volume).
    """
    from pykrx import stock as pykrx_stock

    try:
        df = pykrx_stock.get_market_ohlcv_by_date(from_date, to_date, ticker)
    except (KeyError, ValueError) as exc:
        logger.warning("수집 실패 %s %s~%s: %s", ticker, from_date, to_date, exc)
        return []

    if df is None or df.empty:
        return []

    df = df.reset_index()
    rename_map = {
        "날짜": "date",
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
            d: Any = row.get("date")
            if hasattr(d, "strftime"):
                date_str = d.strftime("%Y%m%d")
            else:
                date_str = str(d).replace("-", "")[:8]
            records.append(
                {
                    "symbol": ticker,
                    "date": date_str,
                    "open": int(row.get("open", 0) or 0),
                    "high": int(row.get("high", 0) or 0),
                    "low": int(row.get("low", 0) or 0),
                    "close": int(row.get("close", 0) or 0),
                    "volume": int(row.get("volume", 0) or 0),
                }
            )
        except (ValueError, TypeError):
            continue
    return records


def backfill(
    days: int,
    markets: list[str],
    sleep_sec: float = 1.0,
    upsert_batch: int = 2000,
) -> int:
    """지정 기간·시장 일봉을 backfill 태그로 upsert.

    Args:
        days: 오늘 기준 과거 일수.
        markets: 시장 목록. 예: ["KOSPI", "KOSDAQ"].
        sleep_sec: pykrx 호출 간 슬립(초).
        upsert_batch: DB 업서트 배치 크기.

    Returns:
        총 upsert 레코드 수.
    """
    from collectors.candles import upsert_daily_candles

    today = datetime.now(tz=UTC).date()
    from_date = (today - timedelta(days=days)).strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")
    logger.info(
        "backfill 시작: %s ~ %s markets=%s sleep=%.1fs batch=%d",
        from_date,
        to_date,
        markets,
        sleep_sec,
        upsert_batch,
    )

    total = 0
    pending: list[dict] = []
    for market in markets:
        tickers = _list_tickers(market)
        logger.info("%s 종목 수: %d", market, len(tickers))
        for idx, ticker in enumerate(tickers, start=1):
            recs = _fetch_single_ohlcv(ticker, from_date, to_date)
            pending.extend(recs)
            if idx % 20 == 0:
                logger.info(
                    "%s 진행 %d/%d (누적 레코드 %d)",
                    market,
                    idx,
                    len(tickers),
                    len(pending) + total,
                )
            if len(pending) >= upsert_batch:
                total += upsert_daily_candles(pending, source="backfill")
                pending.clear()
            time.sleep(sleep_sec)
        if pending:
            total += upsert_daily_candles(pending, source="backfill")
            pending.clear()

    logger.info("backfill 완료: 총 %d 레코드", total)
    return total


def main() -> None:
    """CLI 엔트리."""
    parser = argparse.ArgumentParser(description="daily_candles backfill")
    parser.add_argument("--days", type=int, default=300, help="과거 일수 (기본 300)")
    parser.add_argument(
        "--market",
        type=str,
        default="all",
        choices=["all", "KOSPI", "KOSDAQ"],
        help="대상 시장",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="pykrx 호출 간 슬립(초)")
    parser.add_argument("--batch", type=int, default=2000, help="DB 업서트 배치 크기")
    args = parser.parse_args()

    markets = ["KOSPI", "KOSDAQ"] if args.market == "all" else [args.market]
    backfill(
        days=args.days,
        markets=markets,
        sleep_sec=args.sleep,
        upsert_batch=args.batch,
    )


if __name__ == "__main__":
    main()
