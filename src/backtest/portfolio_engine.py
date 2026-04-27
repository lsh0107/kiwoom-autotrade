"""크로스-섹션 모멘텀 포트폴리오 백테스트 엔진.

cross-sectional momentum 전략의 monthly rebalance 포트폴리오를 시뮬레이션한다.

설계 원칙:
  - look-ahead 방지: 각 리밸런싱 T0에서 T0 이전 데이터만 신호 계산에 사용
  - 거래비용: slippage + commission (매수/매도) + tax (매도만), 실제 회전율 기반
  - 성과 지표: Sharpe (월간 연환산), MDD, IR vs 벤치마크
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.broker.schemas import DailyPrice
from src.strategy.cross_momentum import (
    CrossMomentumParams,
    apply_trend_filter,
    apply_vol_filter,
    compute_momentum_score,
    select_portfolio,
)

logger = structlog.get_logger("backtest.portfolio_engine")


@dataclass
class PortfolioBacktestResult:
    """포트폴리오 백테스트 결과."""

    monthly_returns: list[float] = field(default_factory=list)
    benchmark_monthly_returns: list[float] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    rebalance_dates: list[str] = field(default_factory=list)
    portfolios: list[list[str]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용 딕셔너리 변환.

        Returns:
            dict: 직렬화 가능한 결과 딕셔너리
        """
        return {
            "metrics": self.metrics,
            "monthly_returns": [round(r, 6) for r in self.monthly_returns],
            "benchmark_monthly_returns": [round(r, 6) for r in self.benchmark_monthly_returns],
            "equity_curve": [round(v, 6) for v in self.equity_curve],
            "rebalance_dates": self.rebalance_dates,
            "portfolios": self.portfolios,
        }


class CrossMomentumPortfolioEngine:
    """크로스-섹션 모멘텀 포트폴리오 백테스트 엔진.

    monthly rebalance:
      - 신호: 각 월말 T0 종가 기준 (T0 이전 데이터만 사용)
      - 집행: T0 종가 기준 (슬리피지 포함)
      - 청산: 익월말 T1 종가 기준

    look-ahead 방지: 신호 계산 시 T0 이전 데이터만 접근.
    """

    def run(
        self,
        universe_data: dict[str, list[DailyPrice]],
        benchmark_data: list[DailyPrice],
        params: CrossMomentumParams,
        start_date: str,
        end_date: str,
    ) -> PortfolioBacktestResult:
        """포트폴리오 백테스트 실행.

        Args:
            universe_data: 종목별 전체 일봉 데이터 (look-ahead용 이력 포함)
            benchmark_data: 벤치마크 일봉 데이터 (KOSPI 지수)
            params: 전략 파라미터
            start_date: 첫 리밸런싱 포함 기간 시작 (YYYYMMDD)
            end_date: 기간 종료 (YYYYMMDD)

        Returns:
            PortfolioBacktestResult: 백테스트 결과
        """
        # 기간 내 유니버스 날짜 수집 → 월말 기준일 목록
        all_dates = sorted(
            {
                d.date
                for daily_list in universe_data.values()
                for d in daily_list
                if start_date <= d.date <= end_date
            }
        )

        month_ends = _find_month_ends(all_dates)

        if len(month_ends) < 2:
            logger.warning(
                "월말 기준일 부족 — 최소 2개 필요",
                start_date=start_date,
                end_date=end_date,
                found=len(month_ends),
            )
            return PortfolioBacktestResult(metrics=_empty_portfolio_metrics())

        monthly_returns: list[float] = []
        benchmark_monthly_returns: list[float] = []
        equity = 1.0
        equity_curve: list[float] = [1.0]
        rebalance_dates: list[str] = []
        portfolios: list[list[str]] = []
        prev_portfolio: list[str] = []

        for i in range(len(month_ends) - 1):
            t0 = month_ends[i]
            t1 = month_ends[i + 1]

            # look-ahead 방지: T0까지의 데이터만 신호 계산에 사용
            universe_up_to_t0: dict[str, list[DailyPrice]] = {
                s: [d for d in daily if d.date <= t0] for s, daily in universe_data.items()
            }

            # 모멘텀 점수 계산
            scores: dict[str, float] = {}
            for symbol, daily_t0 in universe_up_to_t0.items():
                score = compute_momentum_score(daily_t0, params)
                if score is not None:
                    scores[symbol] = score

            if not scores:
                logger.debug("점수 계산 가능 종목 없음", t0=t0)
                continue

            # 필터 적용
            candidates = list(scores.keys())

            if params.use_vol_filter:
                vol_pass = apply_vol_filter(universe_up_to_t0, params)
                candidates = [s for s in candidates if s in vol_pass]

            if params.use_trend_filter:
                trend_pass = apply_trend_filter(universe_up_to_t0, params)
                candidates = [s for s in candidates if s in trend_pass]

            if not candidates:
                logger.debug("필터 통과 종목 없음", t0=t0)
                continue

            # 상위 데실 선택
            new_portfolio = select_portfolio(candidates, scores, params)
            if not new_portfolio:
                continue

            # 거래비용 계산 (실제 회전율 기반)
            prev_set = set(prev_portfolio)
            new_set = set(new_portfolio)
            sold = prev_set - new_set
            bought = new_set - prev_set

            n_prev = max(len(prev_portfolio), 1)
            n_new = len(new_portfolio)

            # 매도 비용: 매도 비중 x (슬리피지 + 수수료 + 거래세)
            sell_cost = (
                len(sold)
                / n_prev
                * (params.slippage_pct + params.commission_rate + params.tax_rate)
                if prev_portfolio
                else 0.0
            )
            # 매수 비용: 매수 비중 x (슬리피지 + 수수료)
            buy_cost = len(bought) / n_new * (params.slippage_pct + params.commission_rate)
            total_cost = sell_cost + buy_cost

            # 기간 equal-weight 수익률 (T0 → T1)
            period_return = _compute_portfolio_period_return(new_portfolio, universe_data, t0, t1)
            if period_return is None:
                continue

            net_return = period_return - total_cost
            equity *= 1.0 + net_return
            equity_curve.append(equity)
            monthly_returns.append(net_return)

            # 벤치마크 수익률
            bm_return = _compute_period_return_single(benchmark_data, t0, t1)
            benchmark_monthly_returns.append(bm_return if bm_return is not None else 0.0)

            rebalance_dates.append(t0)
            portfolios.append(list(new_portfolio))
            prev_portfolio = new_portfolio

            logger.debug(
                "리밸런싱 완료",
                t0=t0,
                t1=t1,
                n_portfolio=len(new_portfolio),
                net_return=round(net_return, 4),
                equity=round(equity, 4),
            )

        metrics = _portfolio_metrics(monthly_returns, benchmark_monthly_returns, equity_curve)

        logger.info(
            "포트폴리오 백테스트 완료",
            start_date=start_date,
            end_date=end_date,
            n_periods=len(monthly_returns),
            sharpe=metrics.get("sharpe_ratio"),
            mdd=metrics.get("max_drawdown"),
            ir=metrics.get("ir_vs_benchmark"),
        )

        return PortfolioBacktestResult(
            monthly_returns=monthly_returns,
            benchmark_monthly_returns=benchmark_monthly_returns,
            equity_curve=equity_curve,
            rebalance_dates=rebalance_dates,
            portfolios=portfolios,
            metrics=metrics,
        )


# ── 내부 헬퍼 함수 ──────────────────────────────────────────────────────────────


def _find_month_ends(dates: list[str]) -> list[str]:
    """날짜 리스트에서 월말 거래일 목록 반환.

    각 YYYYMM 그룹에서 최대(최신) 날짜를 월말 거래일로 취급한다.

    Args:
        dates: 정렬된 YYYYMMDD 날짜 문자열 리스트

    Returns:
        list[str]: 각 월의 마지막 거래일 목록 (오름차순)
    """
    month_max: dict[str, str] = {}
    for date in dates:
        ym = date[:6]
        if ym not in month_max or date > month_max[ym]:
            month_max[ym] = date
    return sorted(month_max.values())


def _get_price_at_or_before(daily: list[DailyPrice], target_date: str) -> int | None:
    """target_date 이전 또는 당일 가장 가까운 종가 반환.

    Args:
        daily: 일봉 데이터 (날짜 오름차순)
        target_date: 기준 날짜 (YYYYMMDD)

    Returns:
        int | None: 종가 또는 None (해당 날짜 이전 데이터 없음)
    """
    for d in reversed(daily):
        if d.date <= target_date:
            return d.close
    return None


def _compute_portfolio_period_return(
    portfolio: list[str],
    universe_data: dict[str, list[DailyPrice]],
    t0: str,
    t1: str,
) -> float | None:
    """포트폴리오 기간 equal-weight 수익률 계산 (T0 → T1).

    Args:
        portfolio: 포트폴리오 종목 리스트
        universe_data: 전체 유니버스 일봉 데이터
        t0: 시작일 (YYYYMMDD)
        t1: 종료일 (YYYYMMDD)

    Returns:
        float | None: equal-weight 평균 수익률. 계산 가능 종목 없으면 None.
    """
    returns: list[float] = []
    for symbol in portfolio:
        daily = universe_data.get(symbol, [])
        p0 = _get_price_at_or_before(daily, t0)
        p1 = _get_price_at_or_before(daily, t1)
        if p0 is None or p1 is None or p0 <= 0:
            continue
        returns.append((p1 - p0) / p0)

    if not returns:
        return None
    return sum(returns) / len(returns)


def _compute_period_return_single(
    daily: list[DailyPrice],
    t0: str,
    t1: str,
) -> float | None:
    """단일 시계열 기간 수익률 계산 (벤치마크용).

    Args:
        daily: 일봉 데이터
        t0: 시작일 (YYYYMMDD)
        t1: 종료일 (YYYYMMDD)

    Returns:
        float | None: 수익률 또는 None
    """
    p0 = _get_price_at_or_before(daily, t0)
    p1 = _get_price_at_or_before(daily, t1)
    if p0 is None or p1 is None or p0 <= 0:
        return None
    return (p1 - p0) / p0


def _portfolio_metrics(
    monthly_returns: list[float],
    benchmark_monthly_returns: list[float],
    equity_curve: list[float],
) -> dict[str, Any]:
    """포트폴리오 성과 지표 계산.

    Args:
        monthly_returns: 월별 순수익률 리스트
        benchmark_monthly_returns: 벤치마크 월별 수익률 리스트
        equity_curve: 누적 자산 곡선 (1.0 기준)

    Returns:
        dict: sharpe_ratio, max_drawdown, ir_vs_benchmark, total_return, 등
    """
    if not monthly_returns:
        return _empty_portfolio_metrics()

    sharpe = _monthly_sharpe(monthly_returns)
    mdd = _calc_mdd(equity_curve)
    total_return = (equity_curve[-1] - 1.0) if len(equity_curve) >= 2 else 0.0
    avg_monthly = sum(monthly_returns) / len(monthly_returns)

    ir = 0.0
    if len(benchmark_monthly_returns) == len(monthly_returns):
        ir = _information_ratio(monthly_returns, benchmark_monthly_returns)

    return {
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(mdd, 4),
        "ir_vs_benchmark": round(ir, 4),
        "total_return": round(total_return, 4),
        "avg_monthly_return": round(avg_monthly, 4),
        "n_periods": len(monthly_returns),
    }


def _empty_portfolio_metrics() -> dict[str, Any]:
    """빈 포트폴리오 지표 반환."""
    return {
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
        "ir_vs_benchmark": 0.0,
        "total_return": 0.0,
        "avg_monthly_return": 0.0,
        "n_periods": 0,
    }


def _monthly_sharpe(returns: list[float]) -> float:
    """월간 수익률로 연환산 Sharpe 비율 계산.

    연환산: sqrt(12) 적용 (월간 → 연간).

    Args:
        returns: 월별 수익률 리스트

    Returns:
        float: 연환산 Sharpe 비율
    """
    n = len(returns)
    if n < 2:
        return 0.0
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std_r = math.sqrt(variance)
    if std_r == 0.0:
        return 0.0
    return (mean_r / std_r) * math.sqrt(12)


def _information_ratio(
    port_returns: list[float],
    bm_returns: list[float],
) -> float:
    """포트폴리오 대 벤치마크 연환산 Information Ratio.

    초과 수익률의 평균 / 표준편차 x sqrt(12).

    Args:
        port_returns: 포트폴리오 월별 수익률
        bm_returns: 벤치마크 월별 수익률

    Returns:
        float: 연환산 IR
    """
    excess = [p - b for p, b in zip(port_returns, bm_returns, strict=False)]
    n = len(excess)
    if n < 2:
        return 0.0
    mean_e = sum(excess) / n
    variance = sum((e - mean_e) ** 2 for e in excess) / (n - 1)
    std_e = math.sqrt(variance)
    if std_e == 0.0:
        return 0.0
    return (mean_e / std_e) * math.sqrt(12)


def _calc_mdd(equity_curve: list[float]) -> float:
    """자산 곡선 기반 최대 낙폭 계산.

    Args:
        equity_curve: 바별 자산 가치 리스트 (1.0 기준)

    Returns:
        float: 최대 낙폭 (음수, 예: -0.25 = -25%)
    """
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    mdd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak
            if dd < mdd:
                mdd = dd
    return mdd
