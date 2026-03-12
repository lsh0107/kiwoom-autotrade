"""그리드 서치 모듈 테스트."""

from src.backtest.grid_search import (
    GridSearchConfig,
    format_results_table,
    generate_param_combinations,
    run_grid_search,
)
from src.backtest.strategy import MomentumParams
from src.broker.schemas import DailyPrice, MinutePrice


def _daily(date: str, close: int = 10000, high: int = 11000, volume: int = 100000) -> DailyPrice:
    return DailyPrice(date=date, open=close, high=high, low=close - 100, close=close, volume=volume)


def _minute(dt: str, close: int = 10000, volume: int = 50000) -> MinutePrice:
    return MinutePrice(
        datetime=dt, open=close, high=close + 50, low=close - 50, close=close, volume=volume
    )


class TestGenerateParamCombinations:
    """파라미터 조합 생성 테스트."""

    def test_default_config_count(self) -> None:
        """기본 설정에서 4*4*3*3*3*2*1*1*1 = 864개 조합."""
        config = GridSearchConfig()
        combos = generate_param_combinations(config)
        assert len(combos) == 4 * 4 * 3 * 3 * 3 * 2 * 1 * 1 * 1

    def test_custom_config_count(self) -> None:
        """커스텀 설정에서 정확한 조합 수."""
        config = GridSearchConfig(
            stop_loss=[-0.01, -0.02],
            take_profit=[0.03],
            volume_ratio=[1.5],
            price_change_min=[0.0],
            trailing_stop_pct=[None],
            require_bullish_bar=[False],
            high_52w_threshold=[0.90],
            rsi_min=[None],
            atr_stop_multiplier=[None],
        )
        combos = generate_param_combinations(config)
        assert len(combos) == 2

    def test_params_type(self) -> None:
        """생성된 조합이 MomentumParams 타입."""
        config = GridSearchConfig(
            stop_loss=[-0.02],
            take_profit=[0.03],
            volume_ratio=[2.0],
            price_change_min=[0.0],
            trailing_stop_pct=[None],
            require_bullish_bar=[True],
            high_52w_threshold=[0.90],
            rsi_min=[50.0],
            atr_stop_multiplier=[None],
        )
        combos = generate_param_combinations(config)
        assert len(combos) == 1
        assert isinstance(combos[0], MomentumParams)
        assert combos[0].stop_loss == -0.02
        assert combos[0].rsi_min == 50.0
        assert combos[0].atr_stop_multiplier is None


class TestRunGridSearch:
    """그리드 서치 실행 테스트."""

    def test_empty_data(self) -> None:
        """빈 데이터로 실행하면 거래 0건."""
        config = GridSearchConfig(
            stop_loss=[-0.02],
            take_profit=[0.03],
            volume_ratio=[1.5],
            price_change_min=[0.0],
            trailing_stop_pct=[None],
            require_bullish_bar=[False],
            high_52w_threshold=[0.90],
            rsi_min=[None],
            atr_stop_multiplier=[None],
        )
        results = run_grid_search("005930", [], [], config)
        assert len(results) == 1
        assert results[0].backtest_result.metrics["total_trades"] == 0

    def test_results_sorted(self) -> None:
        """결과가 정렬되어 반환."""
        daily = [_daily(f"202503{i:02d}") for i in range(1, 22)]
        minute = [
            _minute(f"20250310{h:02d}{m:02d}00", close=10500, volume=200000)
            for h in range(9, 15)
            for m in range(0, 60, 5)
        ]
        config = GridSearchConfig(
            stop_loss=[-0.01, -0.03],
            take_profit=[0.02, 0.05],
            volume_ratio=[1.5],
            price_change_min=[0.0],
            trailing_stop_pct=[None],
            require_bullish_bar=[False],
            high_52w_threshold=[0.90],
            rsi_min=[None],
            atr_stop_multiplier=[None],
        )
        results = run_grid_search("005930", minute, daily, config, sort_by="win_rate")
        assert len(results) == 4
        # 순위가 부여됨
        assert results[0].rank == 1
        assert results[-1].rank == 4

    def test_min_trades_filter(self) -> None:
        """최소 거래 수 미달 결과가 하위로."""
        config = GridSearchConfig(
            stop_loss=[-0.02],
            take_profit=[0.03],
            volume_ratio=[1.5],
            price_change_min=[0.0],
            trailing_stop_pct=[None],
            require_bullish_bar=[False],
            high_52w_threshold=[0.90],
            rsi_min=[None],
            atr_stop_multiplier=[None],
        )
        results = run_grid_search("005930", [], [], config, min_trades=5)
        assert results[0].backtest_result.metrics["total_trades"] == 0


class TestFormatResultsTable:
    """테이블 포맷팅 테스트."""

    def test_header_present(self) -> None:
        """헤더가 포함됨."""
        table = format_results_table([], top_n=5)
        assert "SL" in table
        assert "WinR" in table
        assert "PF" in table

    def test_top_n_limit(self) -> None:
        """top_n 제한 동작."""
        daily = [_daily(f"202503{i:02d}") for i in range(1, 22)]
        minute = [
            _minute(f"20250310{h:02d}{m:02d}00", close=10500, volume=200000)
            for h in range(9, 15)
            for m in range(0, 60, 5)
        ]
        config = GridSearchConfig(
            stop_loss=[-0.01, -0.02, -0.03],
            take_profit=[0.03],
            volume_ratio=[1.5],
            price_change_min=[0.0],
            trailing_stop_pct=[None],
            require_bullish_bar=[False],
            high_52w_threshold=[0.90],
            rsi_min=[None],
            atr_stop_multiplier=[None],
        )
        results = run_grid_search("005930", minute, daily, config)
        table = format_results_table(results, top_n=2)
        lines = table.strip().split("\n")
        # 헤더 + 구분선 + 2개 결과 = 4줄
        assert len(lines) == 4
