#!/usr/bin/env python3
# ruff: noqa: DTZ005, T201, RUF002
"""Pullback / Range / MeanReversion 전략 일봉 어댑터 + walk-forward 확장 검증.

배경:
    ADR-019 결론: 옵션 B(Pullback/Range/MR) 1차 검증 0/20 폐기.
    원인 분석: KOSPI 대형주 유니버스 미스매치 + 과잉 보수 파라미터 + slippage 0.0 버그.
    확장 검증: 3년 기간, KOSPI 30 + KOSDAQ 30 (60종목), 완화된 파라미터 grid.

전략별 Grid:
    Pullback : ma_band_pct [0.015, 0.020, 0.025, 0.035] x rsi_max [50.0, 55.0, 60.0] = 12 조합
    Range    : rsi_max [40.0, 45.0, 50.0] x bb_std [1.5, 1.8, 2.0]                   = 9 조합
    MR       : rsi_oversold [30.0, 35.0, 40.0] x bb_std [1.8, 2.0]                   = 6 조합

판정 기준 (ADR-016 동일 보수적):
    - OOS Sharpe ≥ 1.0
    - MDD ≤ -10% (avg_oos_mdd ≥ -0.10)
    - 승률 ≥ 35%
    - RR ≥ 2.0 (avg_win / |avg_loss|)
    - OOS/IS Sharpe 비율 ≥ 0.7
    - 통과 종목 < 30% (18/60) → 폐기 권고

산출물:
    docs/backtest-results/walk_forward_extended_YYYYMMDD_HHMMSS.json

사용법:
    python scripts/run_pullback_range_wf.py
    python scripts/run_pullback_range_wf.py --symbols 005930,000660
    python scripts/run_pullback_range_wf.py --start-date 20230427 --end-date 20260427
    python scripts/run_pullback_range_wf.py --dry-run
    python scripts/run_pullback_range_wf.py --strategy pullback
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.generic_walk_forward import (
    GenericWalkForwardSummary,
    run_walk_forward_generic,
)
from src.broker.schemas import DailyPrice
from src.strategy.mean_reversion import MeanReversionParams, MeanReversionStrategy
from src.strategy.pullback import PullbackParams, PullbackStrategy
from src.strategy.range_trade import RangeParams, RangeStrategy

RESULTS_DIR = Path("docs/backtest-results")

# 확장 유니버스: KOSPI 30 + KOSDAQ 30 (총 60종목, 2026-04-27 기준)
# 재현성 보장을 위해 명시 리스트로 고정 (pykrx 시총 상위 + 섹터 분산)

# KOSPI 30: 시총 상위 20 + 중소형 10 (섹터 분산)
KOSPI_UNIVERSE: list[str] = [
    # 대형주 (기존 20)
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
    # 중소형 추가 10 (섹터 다양화)
    "066570",  # LG전자
    "012330",  # 현대모비스
    "032830",  # 삼성생명
    "316140",  # 우리금융지주
    "033780",  # KT&G
    "000810",  # 삼성화재
    "011200",  # HMM (해운)
    "010950",  # S-Oil
    "003550",  # LG
    "024110",  # 기업은행
]

# KOSDAQ 30: 2차전지/반도체/바이오/엔터 섹터 분산
KOSDAQ_UNIVERSE: list[str] = [
    # 2차전지 소재 (6)
    "247540",  # 에코프로비엠
    "086520",  # 에코프로
    "066970",  # L&F
    "091580",  # 상아프론테크
    "382800",  # 엔켐
    "178920",  # PI첨단소재
    # 반도체/소재 (6)  # noqa: ERA001
    "357780",  # 솔브레인
    "042700",  # 한미반도체
    "058470",  # 리노공업
    "036930",  # 주성엔지니어링
    "031980",  # 피에스케이
    "095340",  # ISC
    # 바이오/의료 (8)  # noqa: ERA001
    "196170",  # 알테오젠
    "145020",  # 휴젤
    "214150",  # 클래시스
    "328130",  # 루닛
    "086900",  # 메디톡스
    "084110",  # 휴온스글로벌
    "230240",  # 에스티팜
    "067630",  # 에이치엘비
    # 게임/엔터 (6)  # noqa: ERA001
    "035900",  # JYP Ent.
    "041510",  # SM엔터테인먼트
    "263750",  # 펄어비스
    "293490",  # 카카오게임즈
    "112040",  # 위메이드
    "053580",  # 웹젠
    # IT/기타 (4)  # noqa: ERA001
    "053800",  # 안랩
    "039200",  # 오스코텍
    "285540",  # 쏘카
    "060310",  # 3S
]

# 전체 유니버스 (KOSPI 30 + KOSDAQ 30 = 60종목)
LIQUID_UNIVERSE: list[str] = KOSPI_UNIVERSE + KOSDAQ_UNIVERSE

# 기본 기간: 3년 고정 (재현성)
DEFAULT_START_DATE = "20230427"
DEFAULT_END_DATE = "20260427"

# 판정 임계값 (ADR-016 동일)
PASS_SHARPE = 1.0
PASS_MDD = -0.10
PASS_WIN_RATE = 0.35
PASS_RR = 2.0
PASS_OOS_IS_RATIO = 0.7
PASS_THRESHOLD_PCT = 0.30  # 통과 비율 30% 미만 (18/60) → 폐기 권고

# 엔진 공통 설정
MAX_POSITIONS = 1
MAX_HOLDING_DAYS = 10
MIN_BARS = 25

log = logging.getLogger("pullback_range_wf")


def setup_logging() -> None:
    """로깅 설정."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def fetch_pykrx_daily(symbol: str, start: str, end: str) -> list[DailyPrice]:
    """pykrx로 종목 일봉 수집.

    Args:
        symbol: 종목코드 (6자리)
        start: 시작일 (YYYYMMDD)
        end: 종료일 (YYYYMMDD)

    Returns:
        list[DailyPrice]: 일봉 데이터 (날짜 오름차순). 오류 시 []
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


def is_pass(summary: GenericWalkForwardSummary) -> bool:
    """ADR-016 기준 통과 여부 판정.

    Args:
        summary: walk-forward 요약 결과

    Returns:
        bool: 통과 여부
    """
    if not summary.windows:
        return False
    return (
        summary.avg_oos_sharpe >= PASS_SHARPE
        and summary.avg_oos_mdd >= PASS_MDD
        and summary.avg_oos_win_rate >= PASS_WIN_RATE
        and summary.avg_oos_rr >= PASS_RR
        and summary.avg_sharpe_degradation >= PASS_OOS_IS_RATIO
    )


def build_pass_detail(summary: GenericWalkForwardSummary) -> dict[str, Any]:
    """종목별 통과/실패 상세 (기준별).

    Args:
        summary: walk-forward 요약 결과

    Returns:
        dict: 지표별 값 + 통과 여부 + 실패 사유
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


# ── 전략별 Grid 정의 ──────────────────────────────────────────────────────────


def pullback_grid() -> list[tuple[str, PullbackStrategy]]:
    """Pullback 전략 Grid (완화 확장).

    ma_band_pct [0.015, 0.020, 0.025, 0.035] × rsi_max [50.0, 55.0, 60.0] = 12 조합.

    Returns:
        list[tuple[str, PullbackStrategy]]: (label, strategy) 목록
    """
    combos = list(itertools.product([0.015, 0.020, 0.025, 0.035], [50.0, 55.0, 60.0]))
    result: list[tuple[str, PullbackStrategy]] = []
    for band, rsi_max in combos:
        label = f"band={band:.3f}_rsi_max={rsi_max:.0f}"
        params = PullbackParams(ma_band_pct=band, rsi_max=rsi_max)
        result.append((label, PullbackStrategy(params)))
    return result


def range_grid() -> list[tuple[str, RangeStrategy]]:
    """Range 전략 Grid (완화 확장).

    rsi_max [40.0, 45.0, 50.0] × bb_std [1.5, 1.8, 2.0] = 9 조합.

    Returns:
        list[tuple[str, RangeStrategy]]: (label, strategy) 목록
    """
    combos = list(itertools.product([40.0, 45.0, 50.0], [1.5, 1.8, 2.0]))
    result: list[tuple[str, RangeStrategy]] = []
    for rsi_max, bb_std in combos:
        label = f"rsi_max={rsi_max:.0f}_bb_std={bb_std:.1f}"
        params = RangeParams(rsi_max=rsi_max, bb_std=bb_std)
        result.append((label, RangeStrategy(params)))
    return result


def mr_grid() -> list[tuple[str, MeanReversionStrategy]]:
    """MeanReversion 전략 Grid (완화 확장).

    rsi_oversold [30.0, 35.0, 40.0] × bb_std [1.8, 2.0] = 6 조합.

    Returns:
        list[tuple[str, MeanReversionStrategy]]: (label, strategy) 목록
    """
    combos = list(itertools.product([30.0, 35.0, 40.0], [1.8, 2.0]))
    result: list[tuple[str, MeanReversionStrategy]] = []
    for rsi_oversold, bb_std in combos:
        label = f"rsi_oversold={rsi_oversold:.0f}_bb_std={bb_std:.1f}"
        params = MeanReversionParams(rsi_oversold=rsi_oversold, bb_std=bb_std)
        result.append((label, MeanReversionStrategy(params)))
    return result


# ── 전략 그룹 실행 ────────────────────────────────────────────────────────────


def run_strategy_group(
    strategy_name: str,
    grid: list[tuple[str, Any]],
    symbol_data: dict[str, list[DailyPrice]],
) -> dict[str, Any]:
    """단일 전략 그룹(grid x symbols) walk-forward 실행.

    Args:
        strategy_name: 전략 이름 (로그용)
        grid: [(label, strategy)] 목록
        symbol_data: 종목별 일봉 데이터

    Returns:
        dict: grid_results + best_combo + verdict
    """
    valid_symbols = list(symbol_data.keys())
    grid_results: list[dict[str, Any]] = []

    for combo_idx, (combo_label, strategy) in enumerate(grid, 1):
        log.info("")
        log.info("  [%02d/%02d] %s | Grid: %s", combo_idx, len(grid), strategy_name, combo_label)

        symbol_results: list[dict[str, Any]] = []
        pass_count = 0

        for symbol in valid_symbols:
            daily_data = symbol_data[symbol]
            wf = run_walk_forward_generic(
                symbol=symbol,
                daily_data=daily_data,
                strategy=strategy,
                max_positions=MAX_POSITIONS,
                max_holding_days=MAX_HOLDING_DAYS,
                min_bars=MIN_BARS,
            )

            detail = build_pass_detail(wf)
            if detail["passed"]:
                pass_count += 1

            symbol_results.append(
                {
                    "symbol": symbol,
                    **detail,
                    "walk_forward": wf.to_dict(),
                }
            )

            verdict = "PASS" if detail["passed"] else "FAIL"
            log.info(
                "    [%s] %s | Sharpe=%.2f MDD=%.1f%% WR=%.1f%% RR=%.2f",
                verdict,
                symbol,
                detail["sharpe"],
                detail["mdd"] * 100,
                detail["win_rate"] * 100,
                detail["rr"],
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
                "combo_label": combo_label,
                "params": getattr(strategy, "params", {}).__dict__
                if hasattr(getattr(strategy, "params", None), "__dict__")
                else {},
                "pass_count": pass_count,
                "total_symbols": len(valid_symbols),
                "pass_rate": round(pass_rate, 4),
                "verdict": verdict_combo,
                "symbol_results": symbol_results,
            }
        )

    # 최우수 조합 선택
    grid_results.sort(key=lambda r: r["pass_count"], reverse=True)
    best = grid_results[0] if grid_results else None
    best_pass_rate = best["pass_rate"] if best else 0.0
    strategy_verdict = "PASS" if best_pass_rate >= PASS_THRESHOLD_PCT else "FAIL(폐기 권고)"

    log.info("")
    log.info(
        "  [%s] %s 최우수 조합: %s → 통과 %d/%d (%.0f%%)",
        strategy_verdict,
        strategy_name,
        best["combo_label"] if best else "N/A",
        best["pass_count"] if best else 0,
        len(valid_symbols),
        best_pass_rate * 100,
    )

    return {
        "strategy": strategy_name,
        "grid_results": grid_results,
        "best_combo": {
            "combo_label": best["combo_label"] if best else None,
            "pass_count": best["pass_count"] if best else 0,
            "pass_rate": best_pass_rate,
        },
        "verdict": strategy_verdict,
    }


def main() -> None:
    """Pullback / Range / MR walk-forward 확장 검증 실행."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Pullback/Range/MR 전략 일봉 어댑터 walk-forward 확장 검증 (60종목, 3년)"
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="종목코드 (쉼표 구분, 기본: LIQUID_UNIVERSE 전체 60종목)",
    )
    parser.add_argument(
        "--start-date",
        default=DEFAULT_START_DATE,
        help=f"시작일 (YYYYMMDD, 기본: {DEFAULT_START_DATE})",
    )
    parser.add_argument(
        "--end-date",
        default=DEFAULT_END_DATE,
        help=f"종료일 (YYYYMMDD, 기본: {DEFAULT_END_DATE})",
    )
    parser.add_argument(
        "--strategy",
        default="all",
        choices=["all", "pullback", "range", "mr"],
        help="실행 전략 (기본: all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Grid 조합만 출력 후 종료")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else LIQUID_UNIVERSE
    start_date = args.start_date
    end_date = args.end_date

    log.info("=" * 70)
    log.info("Pullback / Range / MR 일봉 walk-forward 확장 검증 (ADR-019 후속)")
    log.info("=" * 70)
    log.info("종목 수  : %d개 (KOSPI 30 + KOSDAQ 30)", len(symbols))
    log.info("기간     : %s ~ %s", start_date, end_date)
    log.info("전략     : %s", args.strategy)
    log.info(
        "엔진     : max_pos=%d, max_hold=%d일, min_bars=%d, slippage=0.15%%",
        MAX_POSITIONS,
        MAX_HOLDING_DAYS,
        MIN_BARS,
    )
    log.info("=" * 70)

    # Grid 목록
    grids: dict[str, list[tuple[str, Any]]] = {}
    if args.strategy in ("all", "pullback"):
        grids["pullback"] = pullback_grid()
    if args.strategy in ("all", "range"):
        grids["range"] = range_grid()
    if args.strategy in ("all", "mr"):
        grids["mr"] = mr_grid()

    if args.dry_run:
        for strat_name, grid in grids.items():
            print(f"\n{strat_name} Grid ({len(grid)} 조합):")
            for label, _ in grid:
                print(f"  {label}")
        return

    log.info("기간 범위: %s ~ %s", start_date, end_date)

    # 종목 일봉 데이터 사전 수집
    log.info("")
    log.info("━" * 70)
    log.info("종목 일봉 데이터 수집 중 (pykrx)...")
    symbol_data: dict[str, list[DailyPrice]] = {}
    for symbol in symbols:
        daily = fetch_pykrx_daily(symbol, start_date, end_date)
        if len(daily) < 60:
            log.warning("  [SKIP] %s — 데이터 부족 (%d개)", symbol, len(daily))
        else:
            symbol_data[symbol] = daily
            log.info(
                "  [OK] %s — 일봉 %d개 (%s ~ %s)",
                symbol,
                len(daily),
                daily[0].date,
                daily[-1].date,
            )
    log.info("유효 종목: %d/%d개", len(symbol_data), len(symbols))

    if not symbol_data:
        log.error("유효 종목 없음 — 종료")
        sys.exit(1)

    # 전략 그룹 실행
    all_strategy_results: list[dict[str, Any]] = []

    for strat_name, grid in grids.items():
        log.info("")
        log.info("━" * 70)
        log.info("전략: %s (%d 조합)", strat_name.upper(), len(grid))
        log.info("━" * 70)

        strat_result = run_strategy_group(strat_name, grid, symbol_data)
        all_strategy_results.append(strat_result)

    # 최종 요약
    log.info("")
    log.info("=" * 70)
    log.info("전략별 최종 판정")
    log.info("=" * 70)

    pass_strategies: list[str] = []
    fail_strategies: list[str] = []
    strategy_pass_table: list[dict[str, Any]] = []

    for sr in all_strategy_results:
        strat = sr["strategy"]
        best = sr["best_combo"]
        verdict = sr["verdict"]
        log.info(
            "  %-12s | 최우수: %-40s | 통과 %d/%d (%.0f%%) | [%s]",
            strat.upper(),
            best["combo_label"] or "N/A",
            best["pass_count"],
            len(symbol_data),
            best["pass_rate"] * 100,
            verdict,
        )
        if "PASS" in verdict and "폐기" not in verdict:
            pass_strategies.append(strat)
        else:
            fail_strategies.append(strat)

        strategy_pass_table.append(
            {
                "strategy": strat,
                "best_combo": best["combo_label"],
                "pass_count": best["pass_count"],
                "total": len(symbol_data),
                "pass_rate": best["pass_rate"],
                "verdict": verdict,
            }
        )

    log.info("")
    if pass_strategies:
        log.info("통과 전략: %s → 모의투자 재개 후보", ", ".join(pass_strategies))
    else:
        log.info("⚠️  전 전략 폐기 권고 — 추가 파라미터 조정 또는 전략 재설계 필요")

    # 결과 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"walk_forward_extended_{timestamp}.json"

    save_data: dict[str, Any] = {
        "run_type": "pullback_range_mr_walk_forward_extended",
        "run_at": datetime.now().isoformat(),
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "universe": {
            "total": len(symbol_data),
            "kospi": [s for s in symbol_data if s in KOSPI_UNIVERSE],
            "kosdaq": [s for s in symbol_data if s in KOSDAQ_UNIVERSE],
        },
        "engine_config": {
            "max_positions": MAX_POSITIONS,
            "max_holding_days": MAX_HOLDING_DAYS,
            "min_bars": MIN_BARS,
            "slippage_pct": 0.0015,
        },
        "pass_criteria": {
            "sharpe": PASS_SHARPE,
            "mdd": PASS_MDD,
            "win_rate": PASS_WIN_RATE,
            "rr": PASS_RR,
            "oos_is_ratio": PASS_OOS_IS_RATIO,
            "min_pass_rate": PASS_THRESHOLD_PCT,
        },
        "symbols": list(symbol_data.keys()),
        "strategy_summary": strategy_pass_table,
        "strategy_results": all_strategy_results,
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

    log.info("결과 저장: %s", result_path)


if __name__ == "__main__":
    main()
