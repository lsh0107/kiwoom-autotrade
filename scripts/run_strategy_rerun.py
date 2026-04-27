#!/usr/bin/env python3
# ruff: noqa: DTZ005, T201, RUF001, RUF002, RUF003
"""ADR-016 후속 — atr_tp_mult 상향 + tp_pct 완화 grid × walk-forward 재검증.

배경:
    ADR-016 결과: 20종목 walk-forward 0/20 통과. RR ≥ 2.0이 유일한 차단 요인.
    원인: ATR 익절이 +5% 고정 상한에 막혀 avg_win이 제한됨.

Grid:
    atr_tp_mult: {4.0, 5.0, 6.0, 7.0, 8.0}
    tp_pct: {0.05, 0.07, 0.10, None(상한 없음)}
    기타: lookback=20, vol_mult=1.5, atr_stop_mult=1.5 (ADR-016 우수값 고정)

판정 기준 (ADR-016 동일):
    - OOS Sharpe ≥ 1.0
    - MDD ≤ -10% (avg_oos_mdd >= -0.10)
    - 승률 ≥ 35%
    - RR ≥ 2.0
    - OOS/IS Sharpe 비율 ≥ 0.7 (과최적화 방지)
    - 통과 종목 < 30% (6/20) → 폐기 권고

사용법:
    python scripts/run_strategy_rerun.py
    python scripts/run_strategy_rerun.py --symbols 005930,000660 --months 18
    python scripts/run_strategy_rerun.py --dry-run  # 파라미터 조합만 출력
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

from src.backtest.walk_forward import WalkForwardSummary, run_walk_forward
from src.broker.schemas import DailyPrice
from src.strategy.momentum_daily import DailyMomentumParams

RESULTS_DIR = Path("docs/backtest-results")

# ADR-016 고정 파라미터 (우수값)
FIXED_LOOKBACK = 20
FIXED_VOL_MULT = 1.5
FIXED_ATR_STOP = 1.5

# Grid 탐색 공간
ATR_TP_MULT_GRID: list[float] = [4.0, 5.0, 6.0, 7.0, 8.0]
TP_PCT_GRID: list[float | None] = [0.05, 0.07, 0.10, None]

# KOSPI 유동성 상위 20종목
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

# 판정 임계값
PASS_SHARPE = 1.0
PASS_MDD = -0.10  # avg_oos_mdd >= -0.10 (절댓값 10% 이내)
PASS_WIN_RATE = 0.35
PASS_RR = 2.0
PASS_OOS_IS_RATIO = 0.7
PASS_THRESHOLD_PCT = 0.30  # 통과 비율 30% 미만 → 폐기 권고

log = logging.getLogger("strategy_rerun")


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


def is_pass(summary: WalkForwardSummary) -> bool:
    """ADR-016 기준으로 종목 통과 여부 판정.

    Args:
        summary: walk-forward 요약 결과

    Returns:
        bool: 통과 여부 (전체 기준 충족 시 True)
    """
    if not summary.windows:
        return False
    sharpe = summary.avg_oos_sharpe
    mdd = summary.avg_oos_mdd
    win_rate = summary.avg_oos_win_rate
    rr = summary.avg_oos_rr
    oos_is = summary.avg_sharpe_degradation

    return (
        sharpe >= PASS_SHARPE
        and mdd >= PASS_MDD
        and win_rate >= PASS_WIN_RATE
        and rr >= PASS_RR
        and oos_is >= PASS_OOS_IS_RATIO
    )


def build_pass_detail(summary: WalkForwardSummary) -> dict[str, Any]:
    """종목별 통과/실패 상세 (기준별).

    Args:
        summary: walk-forward 요약 결과

    Returns:
        dict: 지표별 값 + 통과 여부
    """
    if not summary.windows:
        return {
            "sharpe": 0.0,
            "mdd": 0.0,
            "win_rate": 0.0,
            "rr": 0.0,
            "oos_is_ratio": 0.0,
            "passed": False,
            "fail_reasons": ["no_windows"],
        }

    sharpe = summary.avg_oos_sharpe
    mdd = summary.avg_oos_mdd
    win_rate = summary.avg_oos_win_rate
    rr = summary.avg_oos_rr
    oos_is = summary.avg_sharpe_degradation

    fail_reasons: list[str] = []
    if sharpe < PASS_SHARPE:
        fail_reasons.append(f"sharpe={sharpe:.2f}<{PASS_SHARPE}")
    if mdd < PASS_MDD:
        fail_reasons.append(f"mdd={mdd * 100:.1f}%<{PASS_MDD * 100:.0f}%")
    if win_rate < PASS_WIN_RATE:
        fail_reasons.append(f"win_rate={win_rate * 100:.1f}%<{PASS_WIN_RATE * 100:.0f}%")
    if rr < PASS_RR:
        fail_reasons.append(f"rr={rr:.2f}<{PASS_RR}")
    if oos_is < PASS_OOS_IS_RATIO:
        fail_reasons.append(f"oos_is={oos_is:.2f}<{PASS_OOS_IS_RATIO}")

    return {
        "sharpe": round(sharpe, 4),
        "mdd": round(mdd, 4),
        "win_rate": round(win_rate, 4),
        "rr": round(rr, 4),
        "oos_is_ratio": round(oos_is, 4),
        "passed": not fail_reasons,
        "fail_reasons": fail_reasons,
    }


def make_params(atr_tp_mult: float, tp_pct: float | None) -> DailyMomentumParams:
    """Grid 파라미터 조합으로 DailyMomentumParams 생성.

    Args:
        atr_tp_mult: ATR 익절 배수
        tp_pct: 고정 익절 상한 (None이면 상한 없음)

    Returns:
        DailyMomentumParams: 전략 파라미터
    """
    return DailyMomentumParams(
        lookback=FIXED_LOOKBACK,
        vol_mult=FIXED_VOL_MULT,
        atr_stop_mult=FIXED_ATR_STOP,
        atr_tp_mult=atr_tp_mult,
        tp_pct=tp_pct,
    )


def format_tp_pct(tp_pct: float | None) -> str:
    """tp_pct 표시 문자열 변환.

    Args:
        tp_pct: 고정 익절 상한

    Returns:
        str: 표시 문자열
    """
    return "None" if tp_pct is None else f"{tp_pct * 100:.0f}%"


def main() -> None:
    """Grid × walk-forward 재검증 실행."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="ADR-016 후속 atr_tp_mult 상향 grid walk-forward 재검증"
    )
    parser.add_argument(
        "--symbols", default=None, help="종목코드 (쉼표 구분, 기본: LIQUID_UNIVERSE 전체)"
    )
    parser.add_argument("--months", type=int, default=18, help="백테스트 기간 (개월, 기본 18)")
    parser.add_argument("--dry-run", action="store_true", help="파라미터 조합만 출력하고 종료")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else LIQUID_UNIVERSE
    grid = list(itertools.product(ATR_TP_MULT_GRID, TP_PCT_GRID))

    log.info("=" * 70)
    log.info("ADR-016 후속 — atr_tp_mult 상향 grid × walk-forward 재검증")
    log.info("=" * 70)
    log.info("종목 수  : %d개", len(symbols))
    log.info(
        "Grid     : atr_tp_mult %s × tp_pct %s = %d 조합",
        ATR_TP_MULT_GRID,
        [format_tp_pct(t) for t in TP_PCT_GRID],
        len(grid),
    )
    log.info(
        "고정값   : lookback=%d, vol_mult=%.1f, atr_stop=%.1f",
        FIXED_LOOKBACK,
        FIXED_VOL_MULT,
        FIXED_ATR_STOP,
    )
    log.info("기간     : %d개월", args.months)
    log.info("=" * 70)

    if args.dry_run:
        print("\nGrid 파라미터 조합 목록:")
        for i, (atr_tp, tp_pct) in enumerate(grid, 1):
            print(f"  [{i:02d}] atr_tp_mult={atr_tp:.1f}, tp_pct={format_tp_pct(tp_pct)}")
        return

    start_date, end_date = get_date_range(args.months)

    log.info("KOSPI 지수 데이터 수집 중...")
    kospi_daily = fetch_pykrx_kospi(start_date, end_date)
    log.info("KOSPI 일봉 %d개 수집 완료", len(kospi_daily))

    # 종목별 일봉 데이터 사전 수집 (grid마다 재수집하지 않도록)
    log.info("")
    log.info("━" * 70)
    log.info("종목 일봉 데이터 사전 수집 중...")
    symbol_data: dict[str, list[DailyPrice]] = {}
    for symbol in symbols:
        daily = fetch_pykrx_daily(symbol, start_date, end_date)
        if len(daily) < 60:
            log.warning("  [SKIP] %s — 데이터 부족 (%d개)", symbol, len(daily))
        else:
            symbol_data[symbol] = daily
            log.info(
                "  [OK] %s — 일봉 %d개 (%s~%s)", symbol, len(daily), daily[0].date, daily[-1].date
            )

    valid_symbols = list(symbol_data.keys())
    log.info("유효 종목: %d/%d개", len(valid_symbols), len(symbols))

    # Grid × Walk-forward 실행
    grid_results: list[dict[str, Any]] = []

    for combo_idx, (atr_tp, tp_pct) in enumerate(grid, 1):
        params = make_params(atr_tp, tp_pct)
        combo_label = f"atr_tp={atr_tp:.1f} tp_pct={format_tp_pct(tp_pct)}"

        log.info("")
        log.info("━" * 70)
        log.info("[%02d/%02d] Grid: %s", combo_idx, len(grid), combo_label)
        log.info("━" * 70)

        symbol_results: list[dict[str, Any]] = []
        pass_count = 0

        for symbol in valid_symbols:
            daily_data = symbol_data[symbol]
            wf = run_walk_forward(
                symbol=symbol,
                daily_data=daily_data,
                params=params,
                kospi_daily=kospi_daily if kospi_daily else None,
            )

            detail = build_pass_detail(wf)
            passed = detail["passed"]
            if passed:
                pass_count += 1

            symbol_results.append(
                {
                    "symbol": symbol,
                    **detail,
                    "walk_forward": wf.to_dict(),
                }
            )

            verdict = "PASS" if passed else "FAIL"
            rr = detail["rr"]
            sharpe = detail["sharpe"]
            mdd = detail["mdd"] * 100
            wr = detail["win_rate"] * 100
            log.info(
                "  [%s] %s | Sharpe=%.2f MDD=%.1f%% WR=%.1f%% RR=%.2f",
                verdict,
                symbol,
                sharpe,
                mdd,
                wr,
                rr,
            )

        pass_rate = pass_count / len(valid_symbols) if valid_symbols else 0.0
        verdict_combo = "PASS" if pass_rate >= PASS_THRESHOLD_PCT else "FAIL(폐기 권고)"
        log.info(
            "  → 통과: %d/%d (%.0f%%) [%s]",
            pass_count,
            len(valid_symbols),
            pass_rate * 100,
            verdict_combo,
        )

        grid_results.append(
            {
                "combo_id": combo_idx,
                "params": {
                    "atr_tp_mult": atr_tp,
                    "tp_pct": tp_pct,
                    "lookback": FIXED_LOOKBACK,
                    "vol_mult": FIXED_VOL_MULT,
                    "atr_stop_mult": FIXED_ATR_STOP,
                },
                "pass_count": pass_count,
                "total_symbols": len(valid_symbols),
                "pass_rate": round(pass_rate, 4),
                "verdict": verdict_combo,
                "symbol_results": symbol_results,
            }
        )

    # 결과 정렬 (통과 종목 수 내림차순)
    grid_results.sort(key=lambda r: r["pass_count"], reverse=True)

    # 요약 출력
    log.info("")
    log.info("=" * 70)
    log.info("Grid Walk-Forward 재검증 결과 요약")
    log.info("=" * 70)
    best = grid_results[0] if grid_results else None
    for r in grid_results:
        p = r["params"]
        label = f"atr_tp={p['atr_tp_mult']:.1f} tp_pct={format_tp_pct(p['tp_pct'])}"
        log.info(
            "  %s | 통과 %d/%d (%.0f%%) [%s]",
            label,
            r["pass_count"],
            r["total_symbols"],
            r["pass_rate"] * 100,
            r["verdict"],
        )

    if best:
        bp = best["params"]
        log.info("")
        log.info(
            "최적 조합: atr_tp_mult=%.1f, tp_pct=%s → 통과 %d/%d (%.0f%%)",
            bp["atr_tp_mult"],
            format_tp_pct(bp["tp_pct"]),
            best["pass_count"],
            best["total_symbols"],
            best["pass_rate"] * 100,
        )
        if best["pass_rate"] < PASS_THRESHOLD_PCT:
            log.warning(
                "⚠️  최우수 조합도 통과율 %.0f%% < 30%% → 전략 폐기 권고", best["pass_rate"] * 100
            )

    # 이전 결과 비교 (ADR-016: 0/20)
    prev_pass = 0
    prev_total = len(LIQUID_UNIVERSE)

    # 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"walk_forward_rerun_{timestamp}.json"

    save_data: dict[str, Any] = {
        "run_type": "adr016_rerun_tp_grid",
        "run_at": datetime.now().isoformat(),
        "period": {
            "start": start_date,
            "end": end_date,
            "months": args.months,
        },
        "fixed_params": {
            "lookback": FIXED_LOOKBACK,
            "vol_mult": FIXED_VOL_MULT,
            "atr_stop_mult": FIXED_ATR_STOP,
        },
        "grid": {
            "atr_tp_mult": ATR_TP_MULT_GRID,
            "tp_pct": TP_PCT_GRID,
        },
        "pass_criteria": {
            "sharpe": PASS_SHARPE,
            "mdd": PASS_MDD,
            "win_rate": PASS_WIN_RATE,
            "rr": PASS_RR,
            "oos_is_ratio": PASS_OOS_IS_RATIO,
            "min_pass_rate": PASS_THRESHOLD_PCT,
        },
        "comparison": {
            "prev_adr016": {"pass_count": prev_pass, "total": prev_total, "pass_rate": 0.0},
        },
        "symbols": valid_symbols,
        "grid_results": grid_results,
        "best_combo": {
            "atr_tp_mult": best["params"]["atr_tp_mult"] if best else None,
            "tp_pct": best["params"]["tp_pct"] if best else None,
            "pass_count": best["pass_count"] if best else 0,
            "pass_rate": best["pass_rate"] if best else 0.0,
        },
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

    log.info("")
    log.info("결과 저장: %s", result_path)


if __name__ == "__main__":
    main()
