"""Walk-forward 검증 — Generic Strategy Protocol 기반.

GenericDailyEngine을 사용해 Pullback / Range / MeanReversion 전략의
In-sample / Out-of-sample 분할 검증을 수행한다.

기존 WalkForwardSummary(DailyMomentumParams 전용)와 독립 파일로 분리.
create_walk_forward_windows는 기존 walk_forward 모듈에서 재사용.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.backtest.generic_daily_engine import GenericDailyEngine
from src.backtest.walk_forward import create_walk_forward_windows
from src.broker.schemas import DailyPrice
from src.strategy.base import Strategy

logger = structlog.get_logger("backtest.generic_walk_forward")


@dataclass
class GenericWalkForwardResult:
    """Walk-forward 단일 윈도우 결과."""

    window_id: int
    in_sample_metrics: dict
    oos_metrics: dict
    train_dates: str = ""
    test_dates: str = ""

    @property
    def sharpe_degradation(self) -> float:
        """OOS Sharpe / IS Sharpe (과최적화 지표).

        값이 1.0에 가까울수록 IS→OOS 성능 저하 없음.
        IS Sharpe가 0이면 0.0 반환.
        """
        is_sharpe = float(self.in_sample_metrics.get("sharpe_ratio", 0.0))
        oos_sharpe = float(self.oos_metrics.get("sharpe_ratio", 0.0))
        if is_sharpe == 0:
            return 0.0
        return oos_sharpe / is_sharpe


@dataclass
class GenericWalkForwardSummary:
    """Walk-forward 전체 실행 요약 (Strategy 종류 무관)."""

    symbol: str
    strategy_name: str
    params_dict: dict = field(default_factory=dict)
    windows: list[GenericWalkForwardResult] = field(default_factory=list)

    @property
    def avg_oos_sharpe(self) -> float:
        """OOS 평균 Sharpe 비율."""
        vals = [w.oos_metrics.get("sharpe_ratio", 0.0) for w in self.windows]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_oos_win_rate(self) -> float:
        """OOS 평균 승률."""
        vals = [w.oos_metrics.get("win_rate", 0.0) for w in self.windows]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_oos_mdd(self) -> float:
        """OOS 평균 최대 낙폭 (MDD, 음수)."""
        vals = [w.oos_metrics.get("max_drawdown", 0.0) for w in self.windows]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_sharpe_degradation(self) -> float:
        """평균 Sharpe 저하율 (OOS/IS). 과최적화 척도."""
        vals = [w.sharpe_degradation for w in self.windows]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_oos_rr(self) -> float:
        """OOS 평균 Risk-Reward 비율 (avg_win / |avg_loss|).

        avg_loss가 0이 아닌 윈도우만 집계.
        """
        ratios: list[float] = []
        for w in self.windows:
            avg_win = float(w.oos_metrics.get("avg_win", 0.0))
            avg_loss = abs(float(w.oos_metrics.get("avg_loss", 0.0)))
            if avg_loss > 0:
                ratios.append(avg_win / avg_loss)
        return sum(ratios) / len(ratios) if ratios else 0.0

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용 딕셔너리 변환."""
        return {
            "symbol": self.symbol,
            "strategy": self.strategy_name,
            "params": self.params_dict,
            "avg_oos_sharpe": round(self.avg_oos_sharpe, 4),
            "avg_oos_win_rate": round(self.avg_oos_win_rate, 4),
            "avg_oos_mdd": round(self.avg_oos_mdd, 4),
            "avg_oos_rr": round(self.avg_oos_rr, 4),
            "avg_sharpe_degradation": round(self.avg_sharpe_degradation, 4),
            "windows": [
                {
                    "window_id": w.window_id,
                    "train_dates": w.train_dates,
                    "test_dates": w.test_dates,
                    "in_sample": w.in_sample_metrics,
                    "oos": w.oos_metrics,
                    "sharpe_degradation": round(w.sharpe_degradation, 4),
                }
                for w in self.windows
            ],
        }


def run_walk_forward_generic(
    symbol: str,
    daily_data: list[DailyPrice],
    strategy: Strategy,
    *,
    max_positions: int = 1,
    max_holding_days: int = 20,
    min_bars: int = 25,
    train_months: int = 6,
    test_months: int = 2,
) -> GenericWalkForwardSummary:
    """Generic Walk-forward 검증 실행.

    Pullback / Range / MeanReversion 등 Strategy Protocol 구현체를
    18개월 일봉 데이터로 슬라이딩 윈도우 IS/OOS 검증한다.

    Args:
        symbol: 종목코드
        daily_data: 일봉 데이터 (날짜 오름차순)
        strategy: Strategy Protocol 구현체
        max_positions: 최대 동시 포지션 수 (keyword-only)
        max_holding_days: 최대 보유일 타임컷 (keyword-only)
        min_bars: 최소 데이터 바 수 (keyword-only)
        train_months: In-sample 기간 개월 수 (keyword-only)
        test_months: OOS 기간 개월 수 (keyword-only)

    Returns:
        GenericWalkForwardSummary: walk-forward 결과 요약
    """
    # params 직렬화 (JSON 저장용)
    p = getattr(strategy, "params", None)
    params_dict: dict[str, Any] = {}
    if p is not None:
        params_dict = dict(p.__dict__)

    summary = GenericWalkForwardSummary(
        symbol=symbol,
        strategy_name=strategy.name,
        params_dict=params_dict,
    )

    windows = create_walk_forward_windows(
        len(daily_data),
        train_months=train_months,
        test_months=test_months,
    )

    if not windows:
        required = (train_months + test_months) * 21
        logger.warning(
            "Walk-forward 윈도우 생성 불가 — 데이터 부족",
            symbol=symbol,
            strategy=strategy.name,
            bars=len(daily_data),
            required=required,
        )
        return summary

    engine = GenericDailyEngine(
        strategy,
        max_positions=max_positions,
        max_holding_days=max_holding_days,
        min_bars=min_bars,
    )

    for window in windows:
        train_data = daily_data[window.train_start : window.train_end]
        test_data = daily_data[window.test_start : window.test_end]

        is_result = engine.run(symbol, train_data)
        oos_result = engine.run(symbol, test_data)

        train_dates = f"{train_data[0].date}~{train_data[-1].date}" if train_data else ""
        test_dates = f"{test_data[0].date}~{test_data[-1].date}" if test_data else ""

        wf_result = GenericWalkForwardResult(
            window_id=window.window_id,
            in_sample_metrics=is_result.metrics,
            oos_metrics=oos_result.metrics,
            train_dates=train_dates,
            test_dates=test_dates,
        )
        summary.windows.append(wf_result)

        logger.info(
            "Walk-forward 윈도우 완료",
            symbol=symbol,
            strategy=strategy.name,
            window_id=window.window_id,
            train_dates=train_dates,
            test_dates=test_dates,
            is_sharpe=round(is_result.metrics.get("sharpe_ratio", 0), 3),
            oos_sharpe=round(oos_result.metrics.get("sharpe_ratio", 0), 3),
            degradation=round(wf_result.sharpe_degradation, 3),
        )

    return summary
