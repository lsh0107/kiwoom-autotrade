"""종목 마스터 동기화 DAG.

매월 1일 pykrx로 KOSPI/KOSDAQ 전 종목 정보를 갱신하고
종목 간 가격 상관관계를 계산하여 stock_relations에 저장한다.

스케줄: 매월 1일 UTC 01:00 (KST 10:00) 실행.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task

from callbacks.telegram import on_failure_telegram


@dag(
    dag_id="stock_master_sync",
    schedule="0 1 1 * *",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=60),
    },
    tags=["monthly", "master", "stocks"],
)
def stock_master_sync() -> None:
    """종목 마스터 동기화 파이프라인."""

    @task()
    def sync_stock_master() -> int:
        """pykrx로 KOSPI/KOSDAQ 종목 목록을 stocks 테이블에 upsert.

        Returns:
            upsert된 종목 수.
        """
        import datetime as dt
        import logging
        import os
        import time

        from pykrx import stock as krx_stock

        logger = logging.getLogger(__name__)

        conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB") or os.environ.get("DATABASE_URL")
        if not conn_uri:
            logger.warning("DB 연결 정보 미설정 — 동기화 스킵")
            return 0

        import psycopg2

        # SQLAlchemy 드라이버 접두사 제거
        conn_uri = conn_uri.replace("postgresql+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgresql+asyncpg://", "postgresql://")
        conn_uri = conn_uri.replace("postgres+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgres+asyncpg://", "postgresql://")
        conn_uri = conn_uri.replace("postgres://", "postgresql://")

        # 오늘 날짜 (pykrx 형식)
        today = (dt.datetime.now(tz=dt.UTC) + dt.timedelta(hours=9)).strftime("%Y%m%d")

        all_stocks: list[tuple[str, str, str]] = []  # (symbol, name, market)

        for market in ("KOSPI", "KOSDAQ"):
            tickers = krx_stock.get_market_ticker_list(today, market=market)
            time.sleep(0.5)
            for ticker in tickers:
                name = krx_stock.get_market_ticker_name(ticker)
                all_stocks.append((ticker, name, market))
            logger.info("%s 종목 수집: %d종목", market, len(tickers))
            time.sleep(1)

        logger.info("총 종목 수집 완료: %d종목", len(all_stocks))

        if not all_stocks:
            return 0

        try:
            conn = psycopg2.connect(conn_uri)
            try:
                with conn.cursor() as cur:
                    for symbol, name, market in all_stocks:
                        cur.execute(
                            """
                            INSERT INTO stocks
                                (id, symbol, name, market,
                                 is_active, created_at, updated_at)
                            VALUES (gen_random_uuid(), %s, %s, %s, true, NOW(), NOW())
                            ON CONFLICT (symbol) DO UPDATE
                            SET name = EXCLUDED.name,
                                market = EXCLUDED.market,
                                updated_at = NOW()
                            """,
                            (symbol, name, market),
                        )
                conn.commit()
                logger.info("stocks upsert 완료: %d건", len(all_stocks))
                return len(all_stocks)
            finally:
                conn.close()
        except Exception as exc:
            logger.error("stocks upsert 실패: %s", exc)
            raise

    @task()
    def calculate_price_correlation(stock_count: int) -> int:
        """최근 60일 가격 상관관계 계산 후 stock_relations에 저장.

        상관계수 0.7 이상인 종목 쌍만 저장한다.

        Args:
            stock_count: sync_stock_master 결과 (0이면 스킵).

        Returns:
            저장된 관계 수.
        """
        import datetime as dt
        import logging
        import os
        import time

        logger = logging.getLogger(__name__)

        if stock_count == 0:
            logger.info("종목 동기화 없음 — 상관관계 계산 스킵")
            return 0

        conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB") or os.environ.get("DATABASE_URL")
        if not conn_uri:
            logger.warning("DB 연결 정보 미설정 — 상관관계 계산 스킵")
            return 0

        import psycopg2

        conn_uri = conn_uri.replace("postgresql+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgresql+asyncpg://", "postgresql://")
        conn_uri = conn_uri.replace("postgres+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgres+asyncpg://", "postgresql://")
        conn_uri = conn_uri.replace("postgres://", "postgresql://")

        from pykrx import stock as krx_stock

        today = dt.datetime.now(tz=dt.UTC) + dt.timedelta(hours=9)
        end_date = today.strftime("%Y%m%d")
        start_date = (today - dt.timedelta(days=90)).strftime("%Y%m%d")  # 60 거래일 확보용 90일

        # DB에서 is_active 종목 조회
        try:
            conn = psycopg2.connect(conn_uri)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, symbol FROM stocks"
                        " WHERE is_active = TRUE ORDER BY symbol LIMIT 200"
                    )
                    rows = cur.fetchall()
                    stocks = [(str(row[0]), row[1]) for row in rows]  # [(uuid, symbol)]
            finally:
                conn.close()
        except Exception as exc:
            logger.error("종목 목록 조회 실패: %s", exc)
            return 0

        logger.info("상관관계 계산 대상: %d종목", len(stocks))

        # 일봉 수집
        import pandas as pd

        prices: dict[str, pd.Series] = {}
        for _uuid, symbol in stocks:
            try:
                df = krx_stock.get_market_ohlcv(start_date, end_date, symbol)
                time.sleep(0.3)
                if df is not None and not df.empty:
                    df.columns = [str(c).lower() for c in df.columns]
                    close_col = next((c for c in df.columns if "종가" in c or c == "close"), None)
                    if close_col:
                        prices[symbol] = df[close_col]
            except Exception as exc:
                logger.debug("일봉 수집 실패 — %s: %s", symbol, exc)
                continue

        if len(prices) < 2:
            logger.warning("가격 데이터 부족 — 상관관계 계산 불가")
            return 0

        # 상관관계 계산
        price_df = pd.DataFrame(prices).dropna(axis=0, how="all").dropna(axis=1, how="all")
        if price_df.shape[0] < 20:
            logger.warning("데이터 행 부족 (%d행)", price_df.shape[0])
            return 0

        corr_matrix = price_df.corr()
        symbol_to_id = {symbol: uuid for uuid, symbol in stocks}

        # 상관계수 0.7 이상 쌍 추출
        pairs: list[tuple[str, str, float]] = []
        symbols = list(corr_matrix.columns)
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1 :]:
                c = corr_matrix.loc[sym1, sym2]
                if c >= 0.7 and sym1 in symbol_to_id and sym2 in symbol_to_id:
                    pairs.append((symbol_to_id[sym1], symbol_to_id[sym2], float(c)))

        logger.info("상관관계 쌍 추출 완료: %d쌍 (r≥0.7)", len(pairs))

        if not pairs:
            return 0

        # stock_relations upsert
        saved = 0
        try:
            conn = psycopg2.connect(conn_uri)
            try:
                with conn.cursor() as cur:
                    for from_id, to_id, score in pairs:
                        # 양방향 저장
                        for fid, tid in [(from_id, to_id), (to_id, from_id)]:
                            cur.execute(
                                """
                                INSERT INTO stock_relations
                                    (id, from_stock_id, to_stock_id,
                                     relation_type, score, period_days,
                                     source, valid_from)
                                VALUES (gen_random_uuid(), %s, %s,
                                        'price_correlation', %s, 60,
                                        'pykrx_correlation', CURRENT_DATE)
                                ON CONFLICT (from_stock_id, to_stock_id, relation_type)
                                DO UPDATE SET score=%s, period_days=60,
                                             valid_from=CURRENT_DATE
                                """,
                                (fid, tid, score, score),
                            )
                        saved += 1
                conn.commit()
                logger.info("상관관계 저장 완료: %d쌍", saved)
                return saved
            finally:
                conn.close()
        except Exception as exc:
            logger.error("상관관계 저장 실패: %s", exc)
            raise

    # DAG 흐름
    count = sync_stock_master()
    calculate_price_correlation(count)


stock_master_sync()
