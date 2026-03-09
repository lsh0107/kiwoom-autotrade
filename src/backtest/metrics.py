"""백테스트 성과 지표 계산."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.backtest.result import TradeRecord


def calc_metrics(trades: list[TradeRecord]) -> dict:
    """거래 기록으로부터 성과 지표를 계산한다.

    Args:
        trades: 거래 기록 리스트

    Returns:
        dict: 성과 지표
            - total_trades: 총 거래 수
            - win_count: 승리 거래 수
            - loss_count: 패배 거래 수
            - win_rate: 승률 (%)
            - avg_pnl: 평균 손익률 (%)
            - avg_win: 평균 수익률 (%)
            - avg_loss: 평균 손실률 (%)
            - max_drawdown: 최대 낙폭 (%)
            - sharpe_ratio: 샤프비율 (연환산)
            - monthly_avg_return: 월평균 수익률 (%)
            - profit_factor: 프로핏 팩터
    """
    if not trades:
        return _empty_metrics()

    pnl_list = [t.pnl_pct for t in trades]
    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]

    total_trades = len(trades)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0

    avg_pnl = (sum(pnl_list) / total_trades) * 100 if total_trades > 0 else 0.0
    avg_win = (sum(wins) / win_count) * 100 if win_count > 0 else 0.0
    avg_loss = (sum(losses) / loss_count) * 100 if loss_count > 0 else 0.0

    # 최대 낙폭 (MDD)
    max_drawdown = _calc_max_drawdown(pnl_list)

    # 샤프비율 (연환산, 일일 거래 기준)
    sharpe_ratio = _calc_sharpe_ratio(pnl_list)

    # 월평균 수익률 (거래일 기준 약 22일)
    monthly_avg_return = _calc_monthly_return(trades, pnl_list)

    # 프로핏 팩터
    total_wins = sum(wins) if wins else 0.0
    total_losses = abs(sum(losses)) if losses else 0.0
    profit_factor = (
        total_wins / total_losses if total_losses > 0 else float("inf") if total_wins > 0 else 0.0
    )

    return {
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
        "avg_pnl": round(avg_pnl, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "max_drawdown": round(max_drawdown, 4),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "monthly_avg_return": round(monthly_avg_return, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else float("inf"),
    }


def _empty_metrics() -> dict:
    """거래 없을 때 빈 지표 반환."""
    return {
        "total_trades": 0,
        "win_count": 0,
        "loss_count": 0,
        "win_rate": 0.0,
        "avg_pnl": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "max_drawdown": 0.0,
        "sharpe_ratio": 0.0,
        "monthly_avg_return": 0.0,
        "profit_factor": 0.0,
    }


def _calc_max_drawdown(pnl_list: list[float]) -> float:
    """누적 수익 기반 최대 낙폭 (MDD) 계산.

    Args:
        pnl_list: 거래별 손익률 리스트

    Returns:
        float: 최대 낙폭 (%, 음수)
    """
    if not pnl_list:
        return 0.0

    # 누적 자산 곡선 (1.0 기준)
    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0

    for pnl in pnl_list:
        cumulative *= 1.0 + pnl
        if cumulative > peak:
            peak = cumulative
        drawdown = (cumulative - peak) / peak
        if drawdown < max_dd:
            max_dd = drawdown

    return max_dd * 100  # % 단위


def _calc_sharpe_ratio(pnl_list: list[float]) -> float:
    """샤프비율 계산 (연환산).

    거래별 수익률의 평균과 표준편차로 계산.
    연환산: sqrt(252) 적용 (일일 거래 가정).

    Args:
        pnl_list: 거래별 손익률 리스트

    Returns:
        float: 샤프비율
    """
    if len(pnl_list) < 2:
        return 0.0

    mean_return = sum(pnl_list) / len(pnl_list)

    variance = sum((r - mean_return) ** 2 for r in pnl_list) / (len(pnl_list) - 1)
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return 0.0

    # 연환산 (일일 거래 가정)
    return (mean_return / std_dev) * math.sqrt(252)


def _calc_monthly_return(trades: list[TradeRecord], pnl_list: list[float]) -> float:
    """월평균 수익률 계산.

    전체 기간의 누적 수익률을 월 수로 나눠 산출.

    Args:
        trades: 거래 기록 리스트
        pnl_list: 거래별 손익률 리스트

    Returns:
        float: 월평균 수익률 (%)
    """
    if not trades or not pnl_list:
        return 0.0

    # 누적 수익률
    cumulative = 1.0
    for pnl in pnl_list:
        cumulative *= 1.0 + pnl
    total_return = (cumulative - 1.0) * 100

    # 기간 추정 (첫 거래 ~ 마지막 거래)
    first_date = trades[0].entry_time[:8]
    last_date = trades[-1].exit_time[:8]

    if first_date == last_date:
        return total_return

    # 거래일 기반 월 수 추정 (22거래일 = 1개월)
    unique_dates = {t.entry_time[:8] for t in trades} | {t.exit_time[:8] for t in trades}
    trading_days = len(unique_dates)
    months = max(trading_days / 22.0, 1.0)

    return total_return / months
