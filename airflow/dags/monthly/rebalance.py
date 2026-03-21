"""월봉 리밸런싱 DAG.

매월 마지막 거래일에 Pool A 전 종목의 월봉 12이평 신호를 생성하고
텔레그램으로 매수/매도 신호를 전송한다.

스케줄: 매월 28~31일 중 UTC 06:00 (KST 15:00) 실행.
태스크 내부에서 마지막 거래일 여부를 확인해 조기 종료한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task

from callbacks.telegram import on_failure_telegram


@dag(
    dag_id="monthly_rebalance",
    schedule="0 6 28-31 * *",  # 매월 28~31일 KST 15:00 (UTC 06:00) 실행
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["monthly", "rebalance", "tier1"],
)
def monthly_rebalance() -> None:
    """월봉 리밸런싱 파이프라인."""

    @task.short_circuit()
    def check_last_trading_day() -> bool:
        """오늘이 해당 월의 마지막 거래일인지 확인.

        다음 달 첫 거래일 전날이 마지막 거래일이다.
        pykrx로 다음 달 첫 거래일을 조회해 판별한다.
        """
        import datetime as dt

        from pykrx import stock

        today = dt.datetime.now(tz=dt.UTC) + dt.timedelta(hours=9)
        today_date = today.date()

        # 이번 달 마지막 날 계산
        if today_date.month == 12:
            next_month_first = today_date.replace(year=today_date.year + 1, month=1, day=1)
        else:
            next_month_first = today_date.replace(month=today_date.month + 1, day=1)

        # 다음 달 첫 거래일 조회 (최대 7일 내)
        for delta in range(7):
            candidate = next_month_first + dt.timedelta(days=delta)
            date_str = candidate.strftime("%Y%m%d")
            trading_dates = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSPI")
            if trading_dates is not None and not trading_dates.empty:
                # 다음 달 첫 거래일 직전 영업일이 이번 달 마지막 거래일
                last_trading_day = candidate - dt.timedelta(days=1)
                while last_trading_day.weekday() >= 5:  # 토/일 건너뜀
                    last_trading_day -= dt.timedelta(days=1)
                is_last = today_date == last_trading_day
                import logging

                logging.getLogger(__name__).info(
                    "마지막 거래일 확인: 오늘=%s, 마지막 거래일=%s, 해당=%s",
                    today_date,
                    last_trading_day,
                    is_last,
                )
                return is_last

        return False

    @task()
    def load_universe() -> list[dict]:
        """Pool A 종목 목록 로드.

        DB의 stock_universe 테이블에서 pool='A' 종목을 조회한다.
        DB 미연결 시 빈 목록 반환.
        """
        import logging
        import os

        logger = logging.getLogger(__name__)

        conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB") or os.environ.get("DATABASE_URL")
        if not conn_uri:
            logger.warning("DB 연결 정보 미설정 — 빈 유니버스 반환")
            return []

        import psycopg2

        conn_uri = conn_uri.replace("postgresql+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgres+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgres://", "postgresql://")

        try:
            conn = psycopg2.connect(conn_uri)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT symbol, name FROM stock_universe"
                        " WHERE pool = 'pool_a' AND is_active = TRUE"
                        " ORDER BY symbol"
                    )
                    rows = cur.fetchall()
                    symbols = [{"symbol": row[0], "name": row[1]} for row in rows]
                    logger.info("Pool A 종목 로드 완료: %d종목", len(symbols))
                    return symbols
            finally:
                conn.close()
        except Exception as exc:
            logger.error("종목 목록 로드 실패: %s", exc)
            return []

    @task()
    def fetch_monthly_data(symbols: list[dict]) -> list[dict]:
        """pykrx로 월봉 데이터 수집.

        각 종목의 최근 24개월 월봉 OHLCV를 수집한다.
        ADX 계산에 최소 15개월, MA12 계산에 13개월 필요.

        Args:
            symbols: Pool A 종목 목록. 각 항목은 symbol, name 키 포함.

        Returns:
            종목별 월봉 데이터 목록.
        """
        import datetime as dt
        import logging
        import time

        from pykrx import stock

        logger = logging.getLogger(__name__)

        today = dt.datetime.now(tz=dt.UTC) + dt.timedelta(hours=9)
        end_date = today.strftime("%Y%m%d")
        start_date = (today - dt.timedelta(days=730)).strftime("%Y%m%d")  # 약 24개월

        result: list[dict] = []
        for item in symbols:
            symbol = item["symbol"]
            try:
                df = stock.get_market_ohlcv(start_date, end_date, symbol, freq="m")
                time.sleep(0.5)  # pykrx rate limit

                if df is None or df.empty:
                    logger.warning("월봉 데이터 없음: %s", symbol)
                    continue

                df = df.reset_index()
                df.columns = [str(c).lower() for c in df.columns]

                # 컬럼 정규화 (한글 컬럼 처리)
                col_map = {
                    "날짜": "date",
                    "시가": "open",
                    "고가": "high",
                    "저가": "low",
                    "종가": "close",
                    "거래량": "volume",
                }
                df = df.rename(columns=col_map)

                records = df.to_dict("records")
                result.append(
                    {
                        "symbol": symbol,
                        "name": item.get("name", symbol),
                        "monthly_data": records,
                    }
                )
                logger.debug("월봉 수집: %s (%d개월)", symbol, len(records))

            except Exception as exc:
                logger.warning("월봉 수집 실패 — %s: %s", symbol, exc)
                continue

        logger.info("월봉 데이터 수집 완료: %d/%d 종목", len(result), len(symbols))
        return result

    @task()
    def generate_signals(data: list[dict]) -> list[dict]:
        """월봉 12이평 신호 생성.

        Args:
            data: fetch_monthly_data 결과.

        Returns:
            MonthlySignal 딕셔너리 목록. signal이 "buy" 또는 "sell"인 것만 포함.
        """
        import logging
        from dataclasses import asdict

        from analysis.monthly_trend import check_monthly_ma12

        logger = logging.getLogger(__name__)

        signals: list[dict] = []
        for item in data:
            symbol = item["symbol"]
            name = item.get("name", symbol)
            monthly_data = item.get("monthly_data", [])

            signal = check_monthly_ma12(symbol, monthly_data, name=name)
            if signal.signal in ("buy", "sell"):
                signals.append(asdict(signal))
                logger.info("신호 생성: %s(%s) → %s", symbol, name, signal.signal)

        logger.info(
            "신호 생성 완료: 매수 %d, 매도 %d",
            sum(1 for s in signals if s["signal"] == "buy"),
            sum(1 for s in signals if s["signal"] == "sell"),
        )
        return signals

    @task()
    def store_signals(signals: list[dict]) -> None:
        """DB monthly_signals 테이블에 신호 저장.

        Args:
            signals: generate_signals 결과.
        """
        import logging
        import os

        logger = logging.getLogger(__name__)

        if not signals:
            logger.info("저장할 신호 없음")
            return

        conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB") or os.environ.get("DATABASE_URL")
        if not conn_uri:
            logger.warning("DB 연결 정보 미설정 — 신호 저장 스킵")
            return

        import psycopg2

        conn_uri = conn_uri.replace("postgresql+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgres+psycopg2://", "postgresql://")
        conn_uri = conn_uri.replace("postgres://", "postgresql://")

        try:
            conn = psycopg2.connect(conn_uri)
            try:
                with conn.cursor() as cur:
                    for s in signals:
                        cur.execute(
                            """
                            INSERT INTO monthly_signals
                                (symbol, name, signal, close, ma12, adx,
                                 volume_ratio, reason, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (symbol, created_at::date)
                            DO UPDATE SET
                                signal = EXCLUDED.signal,
                                close = EXCLUDED.close,
                                ma12 = EXCLUDED.ma12,
                                adx = EXCLUDED.adx,
                                volume_ratio = EXCLUDED.volume_ratio,
                                reason = EXCLUDED.reason
                            """,
                            (
                                s["symbol"],
                                s["name"],
                                s["signal"],
                                s["close"],
                                s["ma12"],
                                s["adx"],
                                s["volume_ratio"],
                                s["reason"],
                            ),
                        )
                conn.commit()
                logger.info("월봉 신호 %d건 DB 저장 완료", len(signals))
            finally:
                conn.close()
        except Exception as exc:
            logger.error("신호 DB 저장 실패: %s", exc)

    @task()
    def notify_telegram(signals: list[dict]) -> None:
        """텔레그램으로 매수/매도 신호 전송.

        Args:
            signals: generate_signals 결과.
        """
        import logging
        import os

        logger = logging.getLogger(__name__)

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if not bot_token or not chat_id:
            logger.warning("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정 — 전송 스킵")
            return

        if not signals:
            logger.info("전송할 신호 없음")
            return

        buy_signals = [s for s in signals if s["signal"] == "buy"]
        sell_signals = [s for s in signals if s["signal"] == "sell"]

        lines: list[str] = ["[월봉 리밸런싱 신호]"]

        if buy_signals:
            lines.append("\n매수 신호:")
            for s in buy_signals:
                lines.append(
                    f"• {s['name']}({s['symbol']}) "
                    f"종가 {s['close']:,.0f} MA12 {s['ma12']:,.0f} "
                    f"ADX {s['adx']:.1f} 거래량 {s['volume_ratio']:.1f}x"
                )

        if sell_signals:
            lines.append("\n매도 신호:")
            for s in sell_signals:
                lines.append(
                    f"• {s['name']}({s['symbol']}) 종가 {s['close']:,.0f} MA12 {s['ma12']:,.0f}"
                )

        message = "\n".join(lines)

        import requests

        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(
                    "텔레그램 신호 전송 완료 (매수 %d, 매도 %d)",
                    len(buy_signals),
                    len(sell_signals),
                )
            else:
                logger.warning("텔레그램 전송 실패: %s %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.warning("텔레그램 전송 에러: %s", exc)

    # DAG 흐름: 마지막 거래일 확인 → 종목 로드 → 월봉 수집 → 신호 생성 → 저장 + 알림
    is_last_day = check_last_trading_day()
    universe = load_universe()
    monthly_data = fetch_monthly_data(universe)
    signals = generate_signals(monthly_data)
    store_signals(signals)
    notify_telegram(signals)

    # short_circuit: False 시 후속 태스크 전부 skip
    is_last_day >> universe


monthly_rebalance()
