#!/usr/bin/env python3
# ruff: noqa: T201, DTZ005
"""모멘텀 돌파 전략 파라미터 그리드 서치.

데이터를 한 번 수집한 후 모든 파라미터 조합에 대해 백테스트를 실행한다.

사용법:
    python scripts/run_grid_search.py --symbols 005930
    python scripts/run_grid_search.py --symbols 005930 --days 5 --top 30
    python scripts/run_grid_search.py --symbols 005930 --sort-by win_rate
    python scripts/run_grid_search.py --auto  # 최근 스크리닝 결과 자동 로드

필수 환경변수:
    KIWOOM_MOCK_APP_KEY: 모의투자 앱 키
    KIWOOM_MOCK_APP_SECRET: 모의투자 앱 시크릿
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_backtest import (
    RESULTS_DIR,
    collect_daily,
    collect_minute,
    get_env_or_exit,
    get_trading_dates,
    load_screened_symbols,
    setup_logging,
)
from src.backtest.grid_search import (
    StrategyMode,
    classify_volatility_to_mode,
    format_results_table,
    make_day_trade_config,
    make_swing_config,
    run_grid_search,
)
from src.broker.constants import MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import MinutePrice

DEFAULT_SYMBOLS = ["005930"]

log = logging.getLogger("grid_search")


async def main() -> None:
    """그리드 서치 실행."""
    parser = argparse.ArgumentParser(description="모멘텀 전략 파라미터 그리드 서치")
    parser.add_argument("--symbols", default=None, help="종목코드 (쉼표 구분)")
    parser.add_argument("--days", type=int, default=3, help="백테스트 기간 (거래일 수)")
    parser.add_argument("--top", type=int, default=20, help="상위 N개 결과 표시")
    parser.add_argument("--sort-by", default="profit_factor", help="정렬 기준 메트릭")
    parser.add_argument("--min-trades", type=int, default=5, help="최소 거래 수")
    parser.add_argument("--auto", action="store_true", help="최근 스크리닝 결과 자동 로드")
    args = parser.parse_args()

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

    log.info("=" * 70)
    log.info("모멘텀 전략 파라미터 그리드 서치 (자동 단타/스윙 분류)")
    log.info("=" * 70)
    log.info("종목     : %s", ", ".join(symbols))
    log.info("기간     : %s ~ %s (%d일)", trading_dates[0], trading_dates[-1], len(trading_dates))
    log.info("정렬기준 : %s", args.sort_by)
    log.info("=" * 70)

    app_key = get_env_or_exit("KIWOOM_MOCK_APP_KEY")
    app_secret = get_env_or_exit("KIWOOM_MOCK_APP_SECRET")

    client = KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key=app_key,
        app_secret=app_secret,
        is_mock=True,
    )

    all_symbol_results = {}

    try:
        await client.authenticate()
        log.info("[OK] 토큰 발급 성공")

        for symbol in symbols:
            log.info("")
            log.info("━" * 70)
            log.info("[%s] 데이터 수집 중...", symbol)
            log.info("━" * 70)

            # 데이터 한 번만 수집
            daily_data = await collect_daily(client, symbol)
            await asyncio.sleep(5)

            all_minute: list[MinutePrice] = []
            for date in trading_dates:
                day_data = await collect_minute(client, symbol, date)
                all_minute.extend(day_data)
                log.info("  분봉 %s: %d개", date, len(day_data))
                await asyncio.sleep(1.5)
            all_minute.sort(key=lambda x: x.datetime)

            if not all_minute:
                log.warning("  [SKIP] %s 분봉 데이터 없음", symbol)
                continue

            # 변동성 기반 자동 전략 분류
            mode = classify_volatility_to_mode(daily_data)
            if mode == StrategyMode.DAY_TRADE:
                config = make_day_trade_config()
                mode_label = "단타"
            else:
                config = make_swing_config()
                mode_label = "스윙"

            log.info(
                "  일봉 %d개, 분봉 %d개 — [%s] 그리드 서치 시작...",
                len(daily_data),
                len(all_minute),
                mode_label,
            )

            # 그리드 서치 실행 (sync — 데이터 재사용)
            results = run_grid_search(
                symbol=symbol,
                minute_data=all_minute,
                daily_data=daily_data,
                config=config,
                sort_by=args.sort_by,
                min_trades=args.min_trades,
            )

            all_symbol_results[symbol] = results

            # 결과 출력
            print(f"\n{'━' * 70}")
            label = f"[{symbol}] [{mode_label}] 그리드 서치 결과"
            print(f"{label} — 상위 {args.top}개 (정렬: {args.sort_by})")
            print(f"{'━' * 70}")
            print(format_results_table(results, top_n=args.top))

            # 최고 조합 상세
            if results and results[0].backtest_result.metrics.get("total_trades", 0) > 0:
                best = results[0]
                m = best.backtest_result.metrics
                p = best.params
                print(f"\n{'─' * 40}")
                print(f"최적 파라미터 ({symbol}):")
                print(f"  stop_loss: {p.stop_loss}")
                print(f"  take_profit: {p.take_profit}")
                print(f"  volume_ratio: {p.volume_ratio}")
                print(f"  high_52w_threshold: {p.high_52w_threshold}")
                print(f"  rsi_min: {p.rsi_min}")
                print(f"  atr_stop_multiplier: {p.atr_stop_multiplier}")
                wr = m["win_rate"] * 100
                pf = m["profit_factor"]
                print(f"  → 거래 {m['total_trades']}건, 승률 {wr:.1f}%, PF {pf:.2f}")

    finally:
        await client.close()

    # JSON 결과 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"grid_search_{timestamp}.json"

    save_data = {
        "run_at": datetime.now().isoformat(),
        "trading_dates": trading_dates,
        "sort_by": args.sort_by,
        "symbols": symbols,
        "results": {},
    }

    for symbol, results in all_symbol_results.items():
        save_data["results"][symbol] = [
            {
                "rank": r.rank,
                "params": {
                    "stop_loss": r.params.stop_loss,
                    "take_profit": r.params.take_profit,
                    "volume_ratio": r.params.volume_ratio,
                    "high_52w_threshold": r.params.high_52w_threshold,
                    "price_change_min": r.params.price_change_min,
                    "rsi_min": r.params.rsi_min,
                    "atr_stop_multiplier": r.params.atr_stop_multiplier,
                },
                "metrics": r.backtest_result.metrics,
            }
            for r in results[:50]  # 상위 50개만 저장
        ]

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    log.info("결과 저장: %s", result_path)


if __name__ == "__main__":
    asyncio.run(main())
