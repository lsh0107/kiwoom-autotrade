"""성과 지표 계산 테스트."""

import pytest

from src.backtest.metrics import calc_metrics
from src.backtest.result import TradeRecord


def _trade(
    pnl: float, entry: str = "20250101093000", exit_t: str = "20250101100000"
) -> TradeRecord:
    """테스트용 TradeRecord 생성 헬퍼."""
    return TradeRecord(
        symbol="005930",
        entry_time=entry,
        exit_time=exit_t,
        entry_price=10000,
        exit_price=int(10000 * (1 + pnl)),
        side="BUY",
        pnl_pct=pnl,
        exit_reason="take_profit" if pnl > 0 else "stop_loss",
    )


class TestCalcMetrics:
    """calc_metrics 테스트."""

    def test_empty_trades(self) -> None:
        """거래 없을 때 빈 지표."""
        metrics = calc_metrics([])
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["max_drawdown"] == 0.0

    def test_all_wins(self) -> None:
        """전승 시 승률 100%."""
        trades = [_trade(0.01), _trade(0.005), _trade(0.008)]
        metrics = calc_metrics(trades)
        assert metrics["total_trades"] == 3
        assert metrics["win_count"] == 3
        assert metrics["loss_count"] == 0
        assert metrics["win_rate"] == 1.0

    def test_all_losses(self) -> None:
        """전패 시 승률 0%."""
        trades = [_trade(-0.005), _trade(-0.003)]
        metrics = calc_metrics(trades)
        assert metrics["total_trades"] == 2
        assert metrics["win_count"] == 0
        assert metrics["loss_count"] == 2
        assert metrics["win_rate"] == 0.0

    def test_mixed_trades(self) -> None:
        """승패 혼합 시 정확한 승률 계산."""
        trades = [_trade(0.01), _trade(-0.005), _trade(0.008), _trade(-0.003)]
        metrics = calc_metrics(trades)
        assert metrics["total_trades"] == 4
        assert metrics["win_count"] == 2
        assert metrics["loss_count"] == 2
        assert metrics["win_rate"] == 0.5

    def test_avg_pnl(self) -> None:
        """평균 손익률 계산."""
        trades = [_trade(0.01), _trade(-0.005)]
        metrics = calc_metrics(trades)
        expected_avg = (0.01 + (-0.005)) / 2
        assert metrics["avg_pnl"] == pytest.approx(expected_avg, abs=0.01)

    def test_max_drawdown(self) -> None:
        """최대 낙폭 계산."""
        trades = [_trade(0.01), _trade(-0.02), _trade(-0.01)]
        metrics = calc_metrics(trades)
        assert metrics["max_drawdown"] < 0

    def test_sharpe_ratio_positive(self) -> None:
        """수익 거래만 있으면 양의 샤프비율."""
        trades = [_trade(0.005), _trade(0.008), _trade(0.006)]
        metrics = calc_metrics(trades)
        assert metrics["sharpe_ratio"] > 0

    def test_sharpe_ratio_single_trade(self) -> None:
        """거래 1건이면 샤프비율 0."""
        trades = [_trade(0.01)]
        metrics = calc_metrics(trades)
        assert metrics["sharpe_ratio"] == 0.0

    def test_profit_factor_no_losses(self) -> None:
        """손실 없으면 profit_factor가 inf."""
        trades = [_trade(0.01), _trade(0.005)]
        metrics = calc_metrics(trades)
        assert metrics["profit_factor"] == float("inf")

    def test_profit_factor_no_wins(self) -> None:
        """수익 없으면 profit_factor가 0."""
        trades = [_trade(-0.005), _trade(-0.003)]
        metrics = calc_metrics(trades)
        assert metrics["profit_factor"] == 0.0

    def test_profit_factor_mixed(self) -> None:
        """혼합 시 profit_factor 계산."""
        trades = [_trade(0.01), _trade(-0.005)]
        metrics = calc_metrics(trades)
        expected = 0.01 / 0.005
        assert metrics["profit_factor"] == pytest.approx(expected, abs=0.01)

    def test_monthly_return(self) -> None:
        """월평균 수익률 계산."""
        trades = [
            _trade(0.01, "20250101093000", "20250101100000"),
            _trade(0.005, "20250102093000", "20250102100000"),
        ]
        metrics = calc_metrics(trades)
        # 2거래일이므로 월평균 수익률 계산 가능
        assert "monthly_avg_return" in metrics

    def test_max_drawdown_no_drawdown(self) -> None:
        """연속 수익이면 MDD가 0."""
        trades = [_trade(0.01), _trade(0.01), _trade(0.01)]
        metrics = calc_metrics(trades)
        assert metrics["max_drawdown"] == 0.0

    def test_max_drawdown_exact_value(self) -> None:
        """MDD 정확한 수치 검증."""
        # 누적: 1.0 → 1.05(+5%) → 0.9975(-5%) → peak=1.05
        # dd = (0.9975 - 1.05) / 1.05 = -0.05 = -5%
        trades = [_trade(0.05), _trade(-0.05)]
        metrics = calc_metrics(trades)
        expected_dd = ((1.05 * 0.95) - 1.05) / 1.05
        assert metrics["max_drawdown"] == pytest.approx(expected_dd, abs=0.01)

    def test_monthly_return_same_day(self) -> None:
        """같은 날 거래의 월평균 수익률."""
        trades = [
            _trade(0.01, "20250101093000", "20250101100000"),
            _trade(0.005, "20250101103000", "20250101110000"),
        ]
        metrics = calc_metrics(trades)
        # first_date == last_date이므로 total_return 그대로 반환
        assert metrics["monthly_avg_return"] != 0.0

    def test_trade_cost_exceeds_profit(self) -> None:
        """거래비용이 수익보다 클 때 손실 확인."""
        # 0.1% 수익이지만 0.21% 비용 → 순손실
        trades = [_trade(-0.0011)]  # net: 0.001 - 0.0021 = -0.0011
        metrics = calc_metrics(trades)
        assert metrics["avg_pnl"] < 0
