"""파라미터 그리드 서치 모듈.

전략 파라미터 조합별 백테스트를 실행하고 결과를 비교한다.
데이터는 한 번만 수집하고 전 조합에 재사용한다.

종목 변동성에 따라 단타/스윙 전략을 자동 선택한다.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum

import structlog

from src.backtest.engine import BacktestEngine
from src.backtest.result import BacktestResult
from src.backtest.strategy import MomentumParams
from src.broker.schemas import DailyPrice, MinutePrice
from src.strategy.indicators import VolatilityClass, classify_volatility

logger = structlog.get_logger("backtest.grid_search")


class StrategyMode(Enum):
    """전략 모드."""

    DAY_TRADE = "day_trade"  # 변동성 높은 종목: 당일 청산
    SWING = "swing"  # 안정적 종목: 며칠 보유


def classify_volatility_to_mode(daily_data: list[DailyPrice]) -> StrategyMode:
    """변동성 분류 결과를 StrategyMode로 매핑.

    indicators.classify_volatility → VolatilityClass를 기존 StrategyMode로 변환.

    Args:
        daily_data: 최근 일봉 데이터

    Returns:
        StrategyMode: DAY_TRADE (MOMENTUM) or SWING (MEAN_REVERSION/CONSERVATIVE)
    """

    vol_class = classify_volatility(daily_data)
    if vol_class == VolatilityClass.MOMENTUM:
        return StrategyMode.DAY_TRADE
    return StrategyMode.SWING


@dataclass
class GridSearchConfig:
    """그리드 서치 설정."""

    stop_loss: list[float] = field(default_factory=list)
    take_profit: list[float] = field(default_factory=list)
    volume_ratio: list[float] = field(default_factory=list)
    price_change_min: list[float] = field(default_factory=list)
    trailing_stop_pct: list[float | None] = field(default_factory=list)
    require_bullish_bar: list[bool] = field(default_factory=list)
    high_52w_threshold: list[float] = field(default_factory=lambda: [0.0])
    rsi_min: list[float | None] = field(default_factory=lambda: [None])
    atr_stop_multiplier: list[float | None] = field(default_factory=lambda: [None])

    # 고정 파라미터
    max_positions: int = 3
    force_close_time: str = "15:15"
    entry_start_time: str = "09:05"
    entry_end_time: str = "13:00"

    def __post_init__(self) -> None:
        """빈 리스트면 단타 기본값 적용."""
        if not self.stop_loss:
            self.stop_loss = [-0.003, -0.005, -0.007, -0.01]
        if not self.take_profit:
            self.take_profit = [0.01, 0.015, 0.02, 0.03]
        if not self.volume_ratio:
            self.volume_ratio = [0.3, 0.5, 0.7]
        if not self.price_change_min:
            self.price_change_min = [0.0, 0.003, 0.005]
        if not self.trailing_stop_pct:
            self.trailing_stop_pct = [None, -0.003, -0.005]
        if not self.require_bullish_bar:
            self.require_bullish_bar = [True, False]


def make_day_trade_config() -> GridSearchConfig:
    """단타 전략 그리드 설정."""
    return GridSearchConfig(
        stop_loss=[-0.003, -0.005, -0.007, -0.01],
        take_profit=[0.01, 0.015, 0.02, 0.03],
        volume_ratio=[0.3, 0.5, 0.7],
        price_change_min=[0.0, 0.003, 0.005],
        trailing_stop_pct=[None, -0.003, -0.005],
        require_bullish_bar=[True, False],
        max_positions=3,
        force_close_time="15:15",
        entry_start_time="09:05",
        entry_end_time="13:00",
    )


def make_swing_config() -> GridSearchConfig:
    """스윙 전략 그리드 설정."""
    return GridSearchConfig(
        stop_loss=[-0.02, -0.03, -0.05],
        take_profit=[0.03, 0.05, 0.08],
        volume_ratio=[0.3, 0.5],
        price_change_min=[0.0, 0.003],
        trailing_stop_pct=[None, -0.01, -0.015],
        require_bullish_bar=[False],
        max_positions=2,
        force_close_time="15:15",  # 동시호가 5분 전 청산
        entry_start_time="09:05",
        entry_end_time="14:30",  # 오후까지 진입 가능
    )


@dataclass
class GridSearchResult:
    """그리드 서치 단일 조합 결과."""

    params: MomentumParams
    backtest_result: BacktestResult
    rank: int = 0


def generate_param_combinations(config: GridSearchConfig) -> list[MomentumParams]:
    """설정에서 모든 파라미터 조합을 생성한다."""
    combos = list(
        itertools.product(
            config.stop_loss,
            config.take_profit,
            config.volume_ratio,
            config.price_change_min,
            config.trailing_stop_pct,
            config.require_bullish_bar,
            config.high_52w_threshold,
            config.rsi_min,
            config.atr_stop_multiplier,
        )
    )

    params_list = []
    for sl, tp, vr, pcm, tsp, bullish, h52, rsi, atr in combos:
        params_list.append(
            MomentumParams(
                stop_loss=sl,
                take_profit=tp,
                volume_ratio=vr,
                price_change_min=pcm,
                trailing_stop_pct=tsp,
                require_bullish_bar=bullish,
                high_52w_threshold=h52,
                rsi_min=rsi,
                atr_stop_multiplier=atr,
                max_positions=config.max_positions,
                force_close_time=config.force_close_time,
                entry_start_time=config.entry_start_time,
                entry_end_time=config.entry_end_time,
            )
        )
    return params_list


def run_grid_search(
    symbol: str,
    minute_data: list[MinutePrice],
    daily_data: list[DailyPrice],
    config: GridSearchConfig | None = None,
    *,
    sort_by: str = "profit_factor",
    min_trades: int = 5,
) -> list[GridSearchResult]:
    """파라미터 그리드 서치 실행.

    데이터를 한 번만 받아 모든 조합에 재사용한다.

    Args:
        symbol: 종목코드
        minute_data: 분봉 데이터 (시간 오름차순)
        daily_data: 일봉 데이터 (날짜 오름차순)
        config: 그리드 설정 (None이면 기본값)
        sort_by: 정렬 기준 메트릭
        min_trades: 최소 거래 수 (미만이면 결과에서 하위로)

    Returns:
        정렬된 결과 리스트
    """
    config = config or GridSearchConfig()
    params_list = generate_param_combinations(config)

    logger.info("그리드 서치 시작", symbol=symbol, total_combinations=len(params_list))

    results: list[GridSearchResult] = []

    for i, params in enumerate(params_list):
        engine = BacktestEngine(params)
        bt_result = engine.run_with_symbol(symbol, minute_data, daily_data)
        results.append(GridSearchResult(params=params, backtest_result=bt_result))

        if (i + 1) % 100 == 0:
            logger.info("진행", completed=i + 1, total=len(params_list))

    # 정렬: 최소 거래 수 미달은 하위, 나머지는 sort_by 내림차순
    def sort_key(r: GridSearchResult) -> tuple[int, float]:
        trades = r.backtest_result.metrics.get("total_trades", 0)
        has_enough = 1 if trades >= min_trades else 0
        val = r.backtest_result.metrics.get(sort_by, 0.0)
        if val == float("inf"):
            val = 9999.0
        return (has_enough, float(val))

    results.sort(key=sort_key, reverse=True)

    for rank, r in enumerate(results, 1):
        r.rank = rank

    logger.info("그리드 서치 완료", total=len(results))
    return results


def format_results_table(results: list[GridSearchResult], top_n: int = 20) -> str:
    """결과를 텍스트 테이블로 포맷."""
    lines = []
    header = (
        f"{'#':>3} | {'SL':>6} | {'TP':>6} | {'Vol':>5} | {'PcM':>5} | "
        f"{'Trail':>6} | {'Bull':>4} | {'Trades':>6} | {'WinR':>6} | "
        f"{'AvgPnL':>8} | {'PF':>8} | {'MDD':>8} | {'Sharpe':>7}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for r in results[:top_n]:
        p = r.params
        m = r.backtest_result.metrics
        pf = m.get("profit_factor", 0.0)
        pf_str = "inf" if pf == float("inf") else f"{pf:.2f}"
        trail_str = f"{p.trailing_stop_pct * 100:.1f}%" if p.trailing_stop_pct else "-"

        lines.append(
            f"{r.rank:>3} | {p.stop_loss:>6.3f} | {p.take_profit:>6.3f} | "
            f"{p.volume_ratio:>5.1f} | {p.price_change_min * 100:>4.1f}% | "
            f"{trail_str:>6} | {'Y' if p.require_bullish_bar else 'N':>4} | "
            f"{m.get('total_trades', 0):>6} | {m.get('win_rate', 0) * 100:>5.1f}% | "
            f"{m.get('avg_pnl', 0) * 100:>+7.3f}% | {pf_str:>8} | "
            f"{m.get('max_drawdown', 0) * 100:>+7.2f}% | {m.get('sharpe_ratio', 0):>7.2f}"
        )

    return "\n".join(lines)
