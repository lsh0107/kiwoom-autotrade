"""Walk-forward 검증 모듈.

In-sample / Out-of-sample 분할로 과최적화를 검증한다.
6개월 in-sample → 2개월 out-of-sample 슬라이딩 윈도우 (12~18개월 커버).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from src.backtest.daily_engine import DailyBacktestEngine
from src.broker.schemas import DailyPrice
from src.strategy.momentum_daily import DailyMomentumParams

logger = structlog.get_logger("backtest.walk_forward")

# 월 기준 거래일 수
_TRADING_DAYS_PER_MONTH = 21


@dataclass
class WalkForwardWindow:
    """Walk-forward 단일 윈도우 정의."""

    window_id: int
    train_start: int  # daily_data 슬라이스 인덱스 (포함)
    train_end: int  # 슬라이스 인덱스 (미포함)
    test_start: int
    test_end: int


@dataclass
class WalkForwardResult:
    """Walk-forward 단일 윈도우 결과."""

    window_id: int
    in_sample_metrics: dict
    oos_metrics: dict
    params: DailyMomentumParams
    train_dates: str = ""  # 표시용: "YYYYMMDD~YYYYMMDD"
    test_dates: str = ""  # 표시용: "YYYYMMDD~YYYYMMDD"

    @property
    def sharpe_degradation(self) -> float:
        """Sharpe 비율 저하율 (과최적화 지표).

        OOS Sharpe / In-sample Sharpe. 1.0 근접 = 과최적화 없음.
        In-sample Sharpe가 0이면 0.0 반환.
        """
        is_sharpe = float(self.in_sample_metrics.get("sharpe_ratio", 0.0))
        oos_sharpe = float(self.oos_metrics.get("sharpe_ratio", 0.0))
        if is_sharpe == 0:
            return 0.0
        return oos_sharpe / is_sharpe


@dataclass
class WalkForwardSummary:
    """Walk-forward 전체 실행 요약."""

    symbol: str
    params: DailyMomentumParams
    windows: list[WalkForwardResult] = field(default_factory=list)

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
        """OOS 평균 MDD."""
        vals = [w.oos_metrics.get("max_drawdown", 0.0) for w in self.windows]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_sharpe_degradation(self) -> float:
        """평균 Sharpe 저하율 (OOS/IS). 과최적화 척도."""
        vals = [w.sharpe_degradation for w in self.windows]
        return sum(vals) / len(vals) if vals else 0.0

    def to_dict(self) -> dict:
        """JSON 직렬화용 딕셔너리 변환."""
        return {
            "symbol": self.symbol,
            "avg_oos_sharpe": round(self.avg_oos_sharpe, 4),
            "avg_oos_win_rate": round(self.avg_oos_win_rate, 4),
            "avg_oos_mdd": round(self.avg_oos_mdd, 4),
            "avg_sharpe_degradation": round(self.avg_sharpe_degradation, 4),
            "params": {
                "lookback": self.params.lookback,
                "vol_mult": self.params.vol_mult,
                "atr_stop_mult": self.params.atr_stop_mult,
                "atr_tp_mult": self.params.atr_tp_mult,
            },
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


def create_walk_forward_windows(
    n_bars: int,
    train_months: int = 6,
    test_months: int = 2,
) -> list[WalkForwardWindow]:
    """Walk-forward 윈도우 목록 생성.

    슬라이딩 방식: test_size 씩 전진 (겹치지 않는 OOS 구간).

    Args:
        n_bars: 전체 데이터 바 수
        train_months: In-sample 기간 (개월)
        test_months: Out-of-sample 기간 (개월)

    Returns:
        list[WalkForwardWindow]: 윈도우 목록 (최소 1개 이상)
    """
    train_size = train_months * _TRADING_DAYS_PER_MONTH
    test_size = test_months * _TRADING_DAYS_PER_MONTH

    windows: list[WalkForwardWindow] = []
    window_id = 0
    start = 0

    while start + train_size + test_size <= n_bars:
        windows.append(
            WalkForwardWindow(
                window_id=window_id,
                train_start=start,
                train_end=start + train_size,
                test_start=start + train_size,
                test_end=min(start + train_size + test_size, n_bars),
            )
        )
        start += test_size  # test_size씩 슬라이딩
        window_id += 1

    return windows


def run_walk_forward(
    symbol: str,
    daily_data: list[DailyPrice],
    params: DailyMomentumParams,
    *,
    kospi_daily: list[DailyPrice] | None = None,
    train_months: int = 6,
    test_months: int = 2,
) -> WalkForwardSummary:
    """Walk-forward 검증 실행.

    각 윈도우에서 동일 파라미터로 in-sample / OOS 백테스트를 수행하고
    Sharpe 저하율로 과최적화를 검증한다.

    Args:
        symbol: 종목코드
        daily_data: 일봉 데이터 (날짜 오름차순)
        params: 전략 파라미터
        kospi_daily: KOSPI 일봉 데이터 (keyword-only)
        train_months: In-sample 기간 개월 수 (keyword-only)
        test_months: OOS 기간 개월 수 (keyword-only)

    Returns:
        WalkForwardSummary: walk-forward 결과 요약
    """
    windows = create_walk_forward_windows(
        len(daily_data),
        train_months=train_months,
        test_months=test_months,
    )

    if not windows:
        required = (train_months + test_months) * _TRADING_DAYS_PER_MONTH
        logger.warning(
            "Walk-forward 윈도우 생성 불가 — 데이터 부족",
            symbol=symbol,
            bars=len(daily_data),
            required=required,
        )
        return WalkForwardSummary(symbol=symbol, params=params)

    engine = DailyBacktestEngine(params)
    summary = WalkForwardSummary(symbol=symbol, params=params)

    for window in windows:
        train_data = daily_data[window.train_start : window.train_end]
        test_data = daily_data[window.test_start : window.test_end]

        # KOSPI 데이터는 각 구간의 마지막 날짜까지만 사용
        kospi_train: list[DailyPrice] | None = None
        kospi_test: list[DailyPrice] | None = None
        if kospi_daily:
            if train_data:
                cutoff = train_data[-1].date
                kospi_train = [b for b in kospi_daily if b.date <= cutoff]
            if test_data:
                cutoff = test_data[-1].date
                kospi_test = [b for b in kospi_daily if b.date <= cutoff]

        is_result = engine.run(symbol, train_data, kospi_train)
        oos_result = engine.run(symbol, test_data, kospi_test)

        train_dates = f"{train_data[0].date}~{train_data[-1].date}" if train_data else ""
        test_dates = f"{test_data[0].date}~{test_data[-1].date}" if test_data else ""

        wf_result = WalkForwardResult(
            window_id=window.window_id,
            in_sample_metrics=is_result.metrics,
            oos_metrics=oos_result.metrics,
            params=params,
            train_dates=train_dates,
            test_dates=test_dates,
        )
        summary.windows.append(wf_result)

        logger.info(
            "Walk-forward 윈도우 완료",
            symbol=symbol,
            window_id=window.window_id,
            train_dates=train_dates,
            test_dates=test_dates,
            is_sharpe=round(is_result.metrics.get("sharpe_ratio", 0), 3),
            oos_sharpe=round(oos_result.metrics.get("sharpe_ratio", 0), 3),
            degradation=round(wf_result.sharpe_degradation, 3),
        )

    return summary
