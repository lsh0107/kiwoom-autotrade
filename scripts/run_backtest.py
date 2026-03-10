#!/usr/bin/env python3
# ruff: noqa: T201, DTZ005
"""모멘텀 돌파 전략 백테스트 실행.

키움 모의투자 API에서 과거 데이터를 수집하고 백테스트를 실행한다.

사용법:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --symbols 005930
    python scripts/run_backtest.py --days 3 --symbols 005930
    python scripts/run_backtest.py --auto          # 최근 스크리닝 결과 자동 로드
    python scripts/run_backtest.py --auto --days 5  # 스크리닝 종목 + 5일 백테스트

필수 환경변수:
    KIWOOM_MOCK_APP_KEY: 모의투자 앱 키
    KIWOOM_MOCK_APP_SECRET: 모의투자 앱 시크릿

Rate Limit:
    모의투자 초당 5건. 요청 간 최소 1초 대기.
"""

import argparse
import asyncio
import glob as glob_mod
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine
from src.backtest.strategy import MomentumParams
from src.broker.constants import MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import DailyPrice, MinutePrice

# ── 설정 ───────────────────────────────────────────────

DEFAULT_SYMBOLS = ["005930"]  # 삼성전자 (종목 1개씩 안전하게)
RESULTS_DIR = Path("docs/backtest-results")
MAX_RETRIES = 3  # API 에러 시 최대 재시도 횟수

log = logging.getLogger("backtest")


# ── 유틸 ───────────────────────────────────────────────


def setup_logging(log_to_file: bool = False) -> None:
    """로깅 설정. --auto 모드에서는 파일 출력도 활성화."""
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_to_file:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = RESULTS_DIR / f"backtest_{datetime.now().strftime('%Y%m%d')}.log"
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
        print(f"로그 파일: {log_path}")

    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        log.error("환경변수 %s가 없습니다.", key)
        sys.exit(1)
    return value


def get_trading_dates(days: int) -> list[str]:
    """최근 N 거래일 날짜 리스트 반환 (주말 제외)."""
    dates: list[str] = []
    current = datetime.now()
    while len(dates) < days:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
    dates.reverse()
    return dates


def format_pct(value: float) -> str:
    """퍼센트 포맷팅."""
    return f"{value * 100:+.2f}%"


def _safe_int(v: str | int) -> int:
    """부호 접두사 포함 가격/수량 안전 변환."""
    if isinstance(v, int):
        return abs(v)
    s = str(v).lstrip("+-")
    return int(s) if s else 0


def parse_daily_raw(raw_items: list[dict]) -> list[DailyPrice]:
    """ka10086 원본 응답을 DailyPrice 리스트로 변환."""
    results: list[DailyPrice] = []
    for item in raw_items:
        try:
            results.append(
                DailyPrice(
                    date=item.get("date", ""),
                    open=_safe_int(item.get("open_pric", 0)),
                    high=_safe_int(item.get("high_pric", 0)),
                    low=_safe_int(item.get("low_pric", 0)),
                    close=_safe_int(item.get("close_pric", item.get("cur_prc", 0))),
                    volume=_safe_int(item.get("trde_qty", 0)),
                )
            )
        except (ValueError, TypeError):
            continue
    return results


def load_screened_symbols() -> list[str]:
    """최근 스크리닝 결과에서 종목코드 로드.

    docs/backtest-results/screened_*.json 중 가장 최근 파일을 읽는다.
    """
    pattern = str(RESULTS_DIR / "screened_*.json")
    files = sorted(glob_mod.glob(pattern))
    if not files:
        log.error("스크리닝 결과 파일 없음: %s", pattern)
        log.error("먼저 python scripts/screen_symbols.py 실행 필요")
        sys.exit(1)

    latest = files[-1]
    log.info("스크리닝 결과 로드: %s", latest)

    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    symbols = data.get("symbols", [])
    if not symbols:
        log.warning("스크리닝 통과 종목 없음 — DEFAULT_SYMBOLS 사용")
        return DEFAULT_SYMBOLS

    log.info("스크리닝 종목 %d개: %s", len(symbols), ", ".join(symbols))
    return symbols


def print_result(symbol: str, result: "BacktestResult") -> None:  # noqa: F821
    """백테스트 결과 출력."""
    m = result.metrics
    log.info("─" * 50)
    log.info("  종목: %s", symbol)
    log.info("─" * 50)
    log.info("  총 거래 수    : %d", m.get("total_trades", 0))
    log.info("  승률          : %.1f%%", m.get("win_rate", 0) * 100)
    log.info("  총 수익률     : %s", format_pct(m.get("total_return", 0)))
    log.info("  월평균 수익률 : %s", format_pct(m.get("avg_monthly_return", 0)))
    log.info("  최대 낙폭(MDD): %s", format_pct(m.get("max_drawdown", 0)))
    log.info("  샤프비율      : %.2f", m.get("sharpe_ratio", 0))
    log.info("  프로핏팩터    : %.2f", m.get("profit_factor", 0))

    if result.trades:
        log.info("  거래 내역:")
        for t in result.trades:
            log.info(
                "    %s -> %s | 진입 %s원 -> 청산 %s원 | %s | %s",
                t.entry_time,
                t.exit_time,
                f"{t.entry_price:,}",
                f"{t.exit_price:,}",
                format_pct(t.pnl_pct),
                t.exit_reason,
            )


# ── 데이터 수집 (재시도 포함) ─────────────────────────


async def _request_with_retry(client: KiwoomClient, endpoint: str, api_id: str, body: dict) -> dict:
    """API 요청 + 지수 백오프 재시도."""
    for attempt in range(MAX_RETRIES):
        try:
            return await client._request(endpoint, api_id, json_body=body)
        except Exception as e:
            wait = (attempt + 1) * 3  # 3초, 6초, 9초
            if attempt < MAX_RETRIES - 1:
                log.warning(
                    "API 에러 (시도 %d/%d): %s → %d초 대기", attempt + 1, MAX_RETRIES, e, wait
                )
                await asyncio.sleep(wait)
            else:
                log.error("API 최종 실패 (시도 %d/%d): %s", attempt + 1, MAX_RETRIES, e)
                raise
    return {}  # unreachable


async def collect_daily(client: KiwoomClient, symbol: str) -> list[DailyPrice]:
    """일봉 데이터 수집 (ka10086). 연속 조회로 250거래일 수집."""
    from src.broker.constants import API_IDS, DEFAULT_EXCHANGE, ENDPOINTS
    from src.broker.schemas import to_kiwoom_symbol

    log.info("  일봉 조회 (ka10086)...")
    all_raw: list[dict] = []
    qry_dt = datetime.now().strftime("%Y%m%d")

    for page in range(13):
        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)
        data = await _request_with_retry(
            client,
            ENDPOINTS["market"],
            API_IDS["daily_price"],
            {"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
        )

        items = data.get("daly_stkpc", [])
        if not items:
            break
        all_raw.extend(items)
        first_dt, last_dt = items[0].get("date", ""), items[-1].get("date", "")
        log.info("    페이지 %d: %d개 (%s~%s)", page + 1, len(items), last_dt, first_dt)
        last_date = items[-1].get("date", "")
        if not last_date:
            break
        qry_dt = last_date
        await asyncio.sleep(0.8)

    daily = parse_daily_raw(all_raw)
    daily.sort(key=lambda x: x.date)
    if daily:
        log.info("  일봉 %d개 (기간: %s~%s)", len(daily), daily[0].date, daily[-1].date)
    else:
        log.info("  일봉 0개")
    return daily


async def collect_minute(client: KiwoomClient, symbol: str, date: str) -> list[MinutePrice]:
    """분봉 데이터 수집 + 날짜 prefix 부착."""
    raw = await client.get_minute_price(symbol, 5, base_dt=date)

    processed: list[MinutePrice] = []
    for bar in raw:
        dt = bar.datetime
        if len(dt) >= 14:
            processed.append(bar)
        elif len(dt) == 6:
            processed.append(
                MinutePrice(
                    datetime=date + dt,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
            )
        else:
            processed.append(bar)

    filtered = [
        m for m in processed if m.datetime.startswith(date) and "0900" <= m.datetime[8:12] <= "1530"
    ]
    filtered.sort(key=lambda x: x.datetime)
    return filtered


# ── 백테스트 실행 ──────────────────────────────────────


async def run_backtest_for_symbol(
    client: KiwoomClient,
    symbol: str,
    trading_dates: list[str],
    params: MomentumParams,
) -> dict:
    """단일 종목 백테스트 실행."""
    log.info("[%s] 데이터 수집 중...", symbol)

    daily_data = await collect_daily(client, symbol)
    await asyncio.sleep(5)  # 일봉 연속조회 후 쿨다운

    all_minute: list[MinutePrice] = []
    for date in trading_dates:
        day_data = await collect_minute(client, symbol, date)
        all_minute.extend(day_data)
        log.info("  분봉 %s: %d개", date, len(day_data))
        await asyncio.sleep(1.5)
    all_minute.sort(key=lambda x: x.datetime)
    log.info("  총 분봉: %d개, 총 일봉: %d개", len(all_minute), len(daily_data))

    if not all_minute:
        log.warning("  [SKIP] %s 분봉 데이터 없음", symbol)
        return {"symbol": symbol, "skipped": True}

    engine = BacktestEngine(params)
    result = engine.run_with_symbol(symbol, all_minute, daily_data)

    print_result(symbol, result)

    return {
        "symbol": symbol,
        "skipped": False,
        "metrics": result.metrics,
        "params": {
            "volume_ratio": params.volume_ratio,
            "stop_loss": params.stop_loss,
            "take_profit": params.take_profit,
            "high_52w_threshold": params.high_52w_threshold,
            "max_positions": params.max_positions,
        },
        "trades": [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_pct": t.pnl_pct,
                "exit_reason": t.exit_reason,
            }
            for t in result.trades
        ],
        "data_info": {
            "daily_bars": len(daily_data),
            "minute_bars": len(all_minute),
            "trading_dates": trading_dates,
        },
    }


async def main() -> None:
    """백테스트 실행."""
    parser = argparse.ArgumentParser(description="모멘텀 돌파 전략 백테스트")
    parser.add_argument("--symbols", default=None, help="종목코드 (쉼표 구분)")
    parser.add_argument("--days", type=int, default=3, help="백테스트 기간 (거래일 수)")
    parser.add_argument("--volume-ratio", type=float, default=1.5, help="거래량 배수")
    parser.add_argument("--stop-loss", type=float, default=-0.005, help="손절 비율")
    parser.add_argument("--take-profit", type=float, default=0.010, help="익절 비율")
    parser.add_argument("--auto", action="store_true", help="최근 스크리닝 결과에서 종목 자동 로드")
    args = parser.parse_args()

    # --auto 모드: 로그 파일 활성화 + 스크리닝 결과 로드
    setup_logging(log_to_file=args.auto)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    if args.auto:
        symbols = load_screened_symbols()
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        symbols = DEFAULT_SYMBOLS

    trading_dates = get_trading_dates(args.days)

    params = MomentumParams(
        volume_ratio=args.volume_ratio,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
    )

    log.info("=" * 60)
    log.info("모멘텀 돌파 전략 백테스트")
    log.info("실행: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 60)
    log.info("모드     : %s", "AUTO (스크리닝)" if args.auto else "MANUAL")
    log.info("종목     : %s", ", ".join(symbols))
    log.info("기간     : %s ~ %s (%d일)", trading_dates[0], trading_dates[-1], len(trading_dates))
    log.info(
        "파라미터 : volume_ratio=%s, stop_loss=%s, take_profit=%s",
        params.volume_ratio,
        params.stop_loss,
        params.take_profit,
    )
    log.info("=" * 60)

    app_key = get_env_or_exit("KIWOOM_MOCK_APP_KEY")
    app_secret = get_env_or_exit("KIWOOM_MOCK_APP_SECRET")

    client = KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key=app_key,
        app_secret=app_secret,
        is_mock=True,
    )

    all_results: list[dict] = []

    try:
        await client.authenticate()
        log.info("[OK] 토큰 발급 성공")

        for symbol in symbols:
            try:
                result = await run_backtest_for_symbol(client, symbol, trading_dates, params)
                all_results.append(result)
            except Exception as e:
                log.error("[ERROR] %s: %s", symbol, e)
                log.debug(traceback.format_exc())
                all_results.append({"symbol": symbol, "error": str(e)})
    finally:
        await client.close()

    # 결과 요약
    log.info("=" * 60)
    log.info("전체 결과 요약")
    log.info("=" * 60)
    for r in all_results:
        if r.get("skipped"):
            log.info("  %s: SKIP (데이터 없음)", r["symbol"])
        elif r.get("error"):
            log.info("  %s: ERROR — %s", r["symbol"], r["error"])
        else:
            m = r.get("metrics", {})
            log.info(
                "  %s: 거래 %d건, 승률 %.1f%%, 월수익 %s",
                r["symbol"],
                m.get("total_trades", 0),
                m.get("win_rate", 0) * 100,
                format_pct(m.get("avg_monthly_return", 0)),
            )

    # 결과 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"backtest_{timestamp}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_at": datetime.now().isoformat(),
                "mode": "auto" if args.auto else "manual",
                "params": {
                    "volume_ratio": params.volume_ratio,
                    "stop_loss": params.stop_loss,
                    "take_profit": params.take_profit,
                    "high_52w_threshold": params.high_52w_threshold,
                    "max_positions": params.max_positions,
                },
                "trading_dates": trading_dates,
                "symbols": symbols,
                "results": all_results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    log.info("결과 저장: %s", result_path)


if __name__ == "__main__":
    asyncio.run(main())
