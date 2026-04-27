#!/usr/bin/env python3
# ruff: noqa: DTZ005
"""52주 신고가 일봉 모멘텀 전략 백테스트.

pykrx로 역사적 일봉 데이터를 수집하고 백테스트 / 그리드 서치 / walk-forward를 실행한다.
키움 API 불필요 (pykrx 사용).

사용법:
    python scripts/run_daily_backtest.py
    python scripts/run_daily_backtest.py --symbols 005930,000660
    python scripts/run_daily_backtest.py --months 18 --grid
    python scripts/run_daily_backtest.py --months 18 --no-walk-forward
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.daily_engine import DailyBacktestEngine
from src.backtest.walk_forward import run_walk_forward
from src.broker.schemas import DailyPrice
from src.strategy.momentum_daily import DailyMomentumParams

RESULTS_DIR = Path("docs/backtest-results")
log = logging.getLogger("daily_backtest")

# KOSPI 유동성 상위 20종목 (시가총액 기준, 2026년 기준)
LIQUID_UNIVERSE: list[str] = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "005380",  # 현대차
    "035420",  # NAVER
    "051910",  # LG화학
    "068270",  # 셀트리온
    "000270",  # 기아
    "207940",  # 삼성바이오로직스
    "006400",  # 삼성SDI
    "028260",  # 삼성물산
    "105560",  # KB금융
    "055550",  # 신한지주
    "086790",  # 하나금융지주
    "017670",  # SK텔레콤
    "030200",  # KT
    "015760",  # 한국전력
    "373220",  # LG에너지솔루션
    "003670",  # 포스코퓨처엠
    "096770",  # SK이노베이션
    "034730",  # SK
]


def setup_logging() -> None:
    """로깅 설정."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_date_range(months: int) -> tuple[str, str]:
    """N개월 날짜 범위 반환 (YYYYMMDD).

    Args:
        months: 개월 수

    Returns:
        tuple[str, str]: (start_date, end_date)
    """
    end = datetime.now(tz=None).date()
    start = end - timedelta(days=months * 31)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_pykrx_daily(symbol: str, start: str, end: str) -> list[DailyPrice]:
    """pykrx로 종목 일봉 수집.

    Args:
        symbol: 종목코드 (6자리)
        start: 시작일 (YYYYMMDD)
        end: 종료일 (YYYYMMDD)

    Returns:
        list[DailyPrice]: 일봉 데이터 (날짜 오름차순)
    """
    from pykrx import stock as pykrx_stock  # lazy import

    df = pykrx_stock.get_market_ohlcv_by_date(start, end, symbol)
    if df is None or df.empty:
        return []

    result: list[DailyPrice] = []
    for idx, row in df.iterrows():
        date_str = str(idx).replace("-", "")[:8]
        result.append(
            DailyPrice(
                date=date_str,
                open=int(row.get("시가", row.get("Open", 0))),
                high=int(row.get("고가", row.get("High", 0))),
                low=int(row.get("저가", row.get("Low", 0))),
                close=int(row.get("종가", row.get("Close", 0))),
                volume=int(row.get("거래량", row.get("Volume", 0))),
            )
        )
    result.sort(key=lambda x: x.date)
    return result


def fetch_pykrx_kospi(start: str, end: str) -> list[DailyPrice]:
    """pykrx로 KOSPI 지수 일봉 수집 (코드 1001).

    pykrx 버전에 따라 내부 API 응답 형식이 달라질 수 있으므로
    예외 발생 시 빈 리스트 반환 (KOSPI 필터 미적용으로 폴백).

    Args:
        start: 시작일 (YYYYMMDD)
        end: 종료일 (YYYYMMDD)

    Returns:
        list[DailyPrice]: KOSPI 일봉 데이터 (날짜 오름차순). 오류 시 []
    """
    from pykrx import stock as pykrx_stock  # lazy import

    try:
        df = pykrx_stock.get_index_ohlcv_by_date(start, end, "1001")
    except Exception as exc:
        log.warning("KOSPI 지수 데이터 수집 실패 — KOSPI 필터 미적용으로 폴백: %s", exc)
        return []
    if df is None or df.empty:
        return []

    result: list[DailyPrice] = []
    for idx, row in df.iterrows():
        date_str = str(idx).replace("-", "")[:8]
        close_val = int(row.get("종가", row.get("Close", 0)))
        result.append(
            DailyPrice(
                date=date_str,
                open=int(row.get("시가", row.get("Open", close_val))),
                high=int(row.get("고가", row.get("High", close_val))),
                low=int(row.get("저가", row.get("Low", close_val))),
                close=close_val,
                volume=0,
            )
        )
    result.sort(key=lambda x: x.date)
    return result


def run_grid_search_daily(
    symbol: str,
    daily_data: list[DailyPrice],
    kospi_daily: list[DailyPrice],
) -> list[dict[str, Any]]:
    """일봉 전략 파라미터 그리드 서치.

    파라미터 공간:
    - lookback: 10, 20, 30
    - vol_mult: 1.2, 1.5, 2.0
    - atr_stop_mult: 1.0, 1.5, 2.0
    - atr_tp_mult: 3, 4, 6
    총 81 조합

    Args:
        symbol: 종목코드
        daily_data: 일봉 데이터
        kospi_daily: KOSPI 일봉 데이터

    Returns:
        list[dict]: 파라미터 조합별 결과 (profit_factor 내림차순)
    """
    param_grid = list(
        itertools.product(
            [10, 20, 30],  # lookback
            [1.2, 1.5, 2.0],  # vol_mult
            [1.0, 1.5, 2.0],  # atr_stop_mult
            [3.0, 4.0, 6.0],  # atr_tp_mult
        )
    )

    log.info("  그리드 서치 시작 — %d 조합", len(param_grid))
    results: list[dict[str, Any]] = []

    for lookback, vol_mult, atr_stop, atr_tp in param_grid:
        params = DailyMomentumParams(
            lookback=int(lookback),
            vol_mult=vol_mult,
            atr_stop_mult=atr_stop,
            atr_tp_mult=atr_tp,
        )
        engine = DailyBacktestEngine(params)
        bt = engine.run(symbol, daily_data, kospi_daily if kospi_daily else None)
        results.append(
            {
                "lookback": lookback,
                "vol_mult": vol_mult,
                "atr_stop_mult": atr_stop,
                "atr_tp_mult": atr_tp,
                "metrics": bt.metrics,
            }
        )

    def sort_key(r: dict[str, Any]) -> tuple[int, float]:
        trades = r["metrics"].get("total_trades", 0)
        pf = r["metrics"].get("profit_factor", 0.0)
        if pf == float("inf"):
            pf = 9999.0
        return (1 if trades >= 3 else 0, pf)

    results.sort(key=sort_key, reverse=True)
    return results


def format_metrics_row(label: str, m: dict[str, Any]) -> str:
    """메트릭 한 줄 포맷."""
    pf = m.get("profit_factor", 0.0)
    pf_str = "inf" if pf == float("inf") else f"{pf:.2f}"
    return (
        f"  {label:20s} | "
        f"거래:{m.get('total_trades', 0):4d} | "
        f"승률:{m.get('win_rate', 0) * 100:5.1f}% | "
        f"Sharpe:{m.get('sharpe_ratio', 0):6.2f} | "
        f"MDD:{m.get('max_drawdown', 0) * 100:+6.2f}% | "
        f"PF:{pf_str}"
    )


def main() -> None:
    """백테스트 실행."""
    setup_logging()

    parser = argparse.ArgumentParser(description="52주 신고가 일봉 모멘텀 백테스트 (pykrx)")
    parser.add_argument(
        "--symbols",
        default=None,
        help="종목코드 (쉼표 구분, 기본: LIQUID_UNIVERSE 상위 5종목)",
    )
    parser.add_argument("--months", type=int, default=18, help="백테스트 기간 (개월, 기본 18)")
    parser.add_argument("--lookback", type=int, default=20, help="신고가 lookback (기본 20)")
    parser.add_argument("--vol-mult", type=float, default=1.5, help="거래량 배수 (기본 1.5)")
    parser.add_argument("--atr-stop", type=float, default=1.5, help="ATR 손절 배수 (기본 1.5)")
    parser.add_argument("--atr-tp", type=float, default=4.0, help="ATR 익절 배수 (기본 4.0)")
    parser.add_argument("--grid", action="store_true", help="파라미터 그리드 서치 실행")
    parser.add_argument("--no-walk-forward", action="store_true", help="Walk-forward 스킵")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else LIQUID_UNIVERSE[:5]
    start_date, end_date = get_date_range(args.months)

    log.info("=" * 70)
    log.info("52주 신고가 일봉 모멘텀 백테스트")
    log.info("=" * 70)
    log.info("종목    : %s", ", ".join(symbols))
    log.info("기간    : %s ~ %s (%d개월)", start_date, end_date, args.months)
    log.info("모드    : %s", "그리드 서치" if args.grid else "단일 파라미터")
    log.info("=" * 70)

    # KOSPI 지수 수집
    log.info("KOSPI 지수 데이터 수집 중...")
    kospi_daily = fetch_pykrx_kospi(start_date, end_date)
    log.info("KOSPI 일봉 %d개 수집 완료", len(kospi_daily))

    default_params = DailyMomentumParams(
        lookback=args.lookback,
        vol_mult=args.vol_mult,
        atr_stop_mult=args.atr_stop,
        atr_tp_mult=args.atr_tp,
    )

    all_results: list[dict[str, Any]] = []

    for symbol in symbols:
        log.info("")
        log.info("━" * 70)
        log.info("[%s] 데이터 수집 중...", symbol)

        daily_data = fetch_pykrx_daily(symbol, start_date, end_date)
        if len(daily_data) < 60:
            log.warning("  [SKIP] 데이터 부족: %d개", len(daily_data))
            all_results.append({"symbol": symbol, "skipped": True})
            continue

        log.info(
            "  일봉 %d개 (기간: %s~%s)", len(daily_data), daily_data[0].date, daily_data[-1].date
        )

        symbol_result: dict[str, Any] = {"symbol": symbol}

        if args.grid:
            grid_results = run_grid_search_daily(symbol, daily_data, kospi_daily)
            symbol_result["grid_search"] = grid_results[:20]

            log.info("  ─── 그리드 서치 TOP 5 ───")
            for r in grid_results[:5]:
                m = r["metrics"]
                log.info(
                    "    lookback=%d vol=%.1f stop=%.1f tp=%.1f | "
                    "거래:%d 승률:%.1f%% Sharpe:%.2f MDD:%.1f%%",
                    r["lookback"],
                    r["vol_mult"],
                    r["atr_stop_mult"],
                    r["atr_tp_mult"],
                    m.get("total_trades", 0),
                    m.get("win_rate", 0) * 100,
                    m.get("sharpe_ratio", 0),
                    m.get("max_drawdown", 0) * 100,
                )

            # 최적 파라미터로 walk-forward
            if not args.no_walk_forward and grid_results:
                best = grid_results[0]
                best_params = DailyMomentumParams(
                    lookback=best["lookback"],
                    vol_mult=best["vol_mult"],
                    atr_stop_mult=best["atr_stop_mult"],
                    atr_tp_mult=best["atr_tp_mult"],
                )
                wf = run_walk_forward(
                    symbol=symbol,
                    daily_data=daily_data,
                    params=best_params,
                    kospi_daily=kospi_daily if kospi_daily else None,
                )
                symbol_result["walk_forward"] = wf.to_dict()
                log.info(
                    "  WF: avg_oos_sharpe=%.2f avg_oos_wr=%.1f%% degradation=%.2f",
                    wf.avg_oos_sharpe,
                    wf.avg_oos_win_rate * 100,
                    wf.avg_sharpe_degradation,
                )
        else:
            engine = DailyBacktestEngine(default_params)
            bt = engine.run(symbol, daily_data, kospi_daily if kospi_daily else None)

            symbol_result["metrics"] = bt.metrics
            symbol_result["params"] = {
                "lookback": default_params.lookback,
                "vol_mult": default_params.vol_mult,
                "atr_stop_mult": default_params.atr_stop_mult,
                "atr_tp_mult": default_params.atr_tp_mult,
            }
            symbol_result["trades"] = [
                {
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": t.pnl_pct,
                    "exit_reason": t.exit_reason,
                }
                for t in bt.trades
            ]
            log.info(format_metrics_row(symbol, bt.metrics))

            if not args.no_walk_forward:
                wf = run_walk_forward(
                    symbol=symbol,
                    daily_data=daily_data,
                    params=default_params,
                    kospi_daily=kospi_daily if kospi_daily else None,
                )
                symbol_result["walk_forward"] = wf.to_dict()
                log.info(
                    "  WF: avg_oos_sharpe=%.2f avg_oos_wr=%.1f%% degradation=%.2f",
                    wf.avg_oos_sharpe,
                    wf.avg_oos_win_rate * 100,
                    wf.avg_sharpe_degradation,
                )

        all_results.append(symbol_result)

    # ── 결과 저장 ─────────────────────────────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"daily_backtest_{timestamp}.json"

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "strategy": "momentum_daily",
                "run_at": datetime.now().isoformat(),
                "period": {
                    "start": start_date,
                    "end": end_date,
                    "months": args.months,
                },
                "params": {
                    "lookback": default_params.lookback,
                    "vol_mult": default_params.vol_mult,
                    "atr_stop_mult": default_params.atr_stop_mult,
                    "atr_tp_mult": default_params.atr_tp_mult,
                },
                "symbols": symbols,
                "results": all_results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    log.info("")
    log.info("결과 저장: %s", result_path)


if __name__ == "__main__":
    main()
