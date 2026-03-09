#!/usr/bin/env python3
# ruff: noqa: T201, DTZ005
"""모멘텀 돌파 전략 백테스트 실행.

키움 모의투자 API에서 과거 데이터를 수집하고 백테스트를 실행한다.

사용법:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --symbols 005930
    python scripts/run_backtest.py --days 3 --symbols 005930

필수 환경변수:
    KIWOOM_MOCK_APP_KEY: 모의투자 앱 키
    KIWOOM_MOCK_APP_SECRET: 모의투자 앱 시크릿

Rate Limit:
    모의투자 초당 5건. 요청 간 최소 1초 대기.
"""

import argparse
import asyncio
import json
import os
import sys
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

# KiwoomClient 내장 AsyncLimiter가 rate limit 처리 (초당 5건)
# 별도 sleep 불필요


# ── 유틸 ───────────────────────────────────────────────


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        print(f"[ERROR] 환경변수 {key}가 없습니다.")
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


def print_result(symbol: str, result: "BacktestResult") -> None:  # noqa: F821
    """백테스트 결과 출력."""
    m = result.metrics
    print(f"\n{'─' * 50}")
    print(f"  종목: {symbol}")
    print(f"{'─' * 50}")
    print(f"  총 거래 수    : {m.get('total_trades', 0)}")
    print(f"  승률          : {m.get('win_rate', 0) * 100:.1f}%")
    print(f"  총 수익률     : {format_pct(m.get('total_return', 0))}")
    print(f"  월평균 수익률 : {format_pct(m.get('avg_monthly_return', 0))}")
    print(f"  최대 낙폭(MDD): {format_pct(m.get('max_drawdown', 0))}")
    print(f"  샤프비율      : {m.get('sharpe_ratio', 0):.2f}")
    print(f"  프로핏팩터    : {m.get('profit_factor', 0):.2f}")

    if result.trades:
        print("\n  거래 내역:")
        for t in result.trades:
            print(
                f"    {t.entry_time} → {t.exit_time} | "
                f"진입 {t.entry_price:,}원 → 청산 {t.exit_price:,}원 | "
                f"{format_pct(t.pnl_pct)} | {t.exit_reason}"
            )


# ── 데이터 수집 ────────────────────────────────────────


async def collect_daily(client: KiwoomClient, symbol: str) -> list[DailyPrice]:
    """일봉 데이터 수집 (ka10086). 연속 조회로 250거래일 수집."""
    from datetime import datetime as dt

    from src.broker.constants import API_IDS, DEFAULT_EXCHANGE, ENDPOINTS
    from src.broker.schemas import to_kiwoom_symbol

    print("  일봉 조회 (ka10086)...")
    all_raw: list[dict] = []
    qry_dt = dt.now().strftime("%Y%m%d")

    # 최대 13회 조회 (20개/회 x 13 = 260거래일, 약 52주)
    # 키움 모의투자 연속조회 페널티 방지: 요청 간 0.5초 대기
    for page in range(13):
        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)
        try:
            data = await client._request(
                ENDPOINTS["market"],
                API_IDS["daily_price"],
                json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
            )
        except Exception:
            # 429 등 에러 시 3초 대기 후 재시도
            print(f"    일봉 {page}페이지 429 → 3초 대기 후 재시도")
            await asyncio.sleep(3)
            data = await client._request(
                ENDPOINTS["market"],
                API_IDS["daily_price"],
                json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
            )
        items = data.get("daly_stkpc", [])
        if not items:
            break
        all_raw.extend(items)
        first_dt, last_dt = items[0].get("date", ""), items[-1].get("date", "")
        print(f"    페이지 {page + 1}: {len(items)}개 ({last_dt}~{first_dt})")
        last_date = items[-1].get("date", "")
        if not last_date:
            break
        qry_dt = last_date
        await asyncio.sleep(0.5)  # 연속조회 페널티 방지
    raw = all_raw
    daily = parse_daily_raw(raw)
    daily.sort(key=lambda x: x.date)
    print(
        f"  일봉 {len(daily)}개 (기간: {daily[0].date}~{daily[-1].date})" if daily else "  일봉 0개"
    )
    return daily


async def collect_minute(client: KiwoomClient, symbol: str, date: str) -> list[MinutePrice]:
    """분봉 데이터 수집 + 날짜 prefix 부착."""
    raw = await client.get_minute_price(symbol, 5, base_dt=date)

    # cntr_tm이 HHMMSS만 올 수 있으므로 날짜 prefix 추가
    processed: list[MinutePrice] = []
    for bar in raw:
        dt = bar.datetime
        # 이미 14자리(YYYYMMDDHHMMSS)면 그대로
        if len(dt) >= 14:
            processed.append(bar)
        elif len(dt) == 6:
            # HHMMSS → date + HHMMSS
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

    # 해당 날짜만 필터 + 장중 시간만 (09:00 ~ 15:30)
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
    print(f"\n[{symbol}] 데이터 수집 중...")

    # 1. 일봉 데이터 (ka10086 — 모의투자 지원)
    daily_data = await collect_daily(client, symbol)

    # 일봉 연속조회 후 쿨다운 (버킷 보충)
    await asyncio.sleep(3)

    # 2. 분봉 데이터 (각 날짜별)
    all_minute: list[MinutePrice] = []
    for date in trading_dates:
        day_data = await collect_minute(client, symbol, date)
        all_minute.extend(day_data)
        print(f"  분봉 {date}: {len(day_data)}개")
        await asyncio.sleep(0.5)  # 분봉 연속조회 딜레이
    all_minute.sort(key=lambda x: x.datetime)
    print(f"  총 분봉: {len(all_minute)}개, 총 일봉: {len(daily_data)}개")

    if not all_minute:
        print("  [SKIP] 분봉 데이터 없음")
        return {"symbol": symbol, "skipped": True}

    # 3. 백테스트 실행
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
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="종목코드 (쉼표 구분)")
    parser.add_argument("--days", type=int, default=3, help="백테스트 기간 (거래일 수)")
    parser.add_argument("--volume-ratio", type=float, default=1.5, help="거래량 배수")
    parser.add_argument("--stop-loss", type=float, default=-0.005, help="손절 비율")
    parser.add_argument("--take-profit", type=float, default=0.010, help="익절 비율")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    trading_dates = get_trading_dates(args.days)

    params = MomentumParams(
        volume_ratio=args.volume_ratio,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
    )

    print("=" * 60)
    print("모멘텀 돌파 전략 백테스트")
    print(f"실행: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"종목     : {', '.join(symbols)}")
    print(f"기간     : {trading_dates[0]} ~ {trading_dates[-1]} ({len(trading_dates)}일)")
    print(
        f"파라미터 : volume_ratio={params.volume_ratio}, "
        f"stop_loss={params.stop_loss}, take_profit={params.take_profit}"
    )
    print("=" * 60)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

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
        print("\n[OK] 토큰 발급 성공")

        for symbol in symbols:
            try:
                result = await run_backtest_for_symbol(client, symbol, trading_dates, params)
                all_results.append(result)
            except Exception as e:
                print(f"\n[ERROR] {symbol}: {e}")
                import traceback

                traceback.print_exc()
                all_results.append({"symbol": symbol, "error": str(e)})

    finally:
        await client.close()

    # 결과 요약
    print(f"\n{'=' * 60}")
    print("전체 결과 요약")
    print(f"{'=' * 60}")
    for r in all_results:
        if r.get("skipped"):
            print(f"  {r['symbol']}: SKIP (데이터 없음)")
        elif r.get("error"):
            print(f"  {r['symbol']}: ERROR — {r['error']}")
        else:
            m = r.get("metrics", {})
            print(
                f"  {r['symbol']}: "
                f"거래 {m.get('total_trades', 0)}건, "
                f"승률 {m.get('win_rate', 0) * 100:.1f}%, "
                f"월수익 {format_pct(m.get('avg_monthly_return', 0))}"
            )

    # 결과 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"backtest_{timestamp}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_at": datetime.now().isoformat(),
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
    print(f"\n결과 저장: {result_path}")


if __name__ == "__main__":
    asyncio.run(main())
