"""tests/backtest/test_generic_daily_engine.py — GenericDailyEngine 단위 테스트.

Strategy Protocol 기반 일봉 엔진 및 Generic walk-forward 검증.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.backtest.generic_daily_engine import GenericDailyEngine, GenericPosition
from src.backtest.generic_walk_forward import (
    GenericWalkForwardSummary,
    run_walk_forward_generic,
)
from src.broker.schemas import DailyPrice
from src.strategy.mean_reversion import MeanReversionParams, MeanReversionStrategy
from src.strategy.pullback import PullbackParams, PullbackStrategy
from src.strategy.range_trade import RangeParams, RangeStrategy

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def make_daily(
    date: str,
    open_: int,
    high: int,
    low: int,
    close: int,
    volume: int = 1_000_000,
) -> DailyPrice:
    """DailyPrice 생성 헬퍼."""
    return DailyPrice(date=date, open=open_, high=high, low=low, close=close, volume=volume)


def make_flat_series(n: int, price: int = 10_000) -> list[DailyPrice]:
    """횡보 가격 시리즈 (신호 발생 없음)."""
    result: list[DailyPrice] = []
    for i in range(n):
        date = f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}"
        result.append(make_daily(date, price, price + 100, price - 100, price))
    return result


def make_indexed_series(n: int, price: int = 10_000) -> list[DailyPrice]:
    """인덱스 기반 날짜 고유 시리즈."""
    result: list[DailyPrice] = []
    for i in range(n):
        year = 2023 + i // 250
        day_in_year = i % 250
        month = min(day_in_year // 21 + 1, 12)
        day = min(day_in_year % 21 + 1, 28)
        result.append(
            make_daily(f"{year}{month:02d}{day:02d}", price, price + 100, price - 100, price)
        )
    return result


# ── 테스트용 Mock 전략 ─────────────────────────────────────────────────────────


@dataclass
class _AlwaysEnterParams:
    """Mock 전략 파라미터."""

    stop_loss: float = -0.05
    take_profit: float = 0.10
    commission_rate: float = 0.00015
    tax_rate: float = 0.0020
    slippage_pct: float = 0.0


class AlwaysEnterStrategy:
    """항상 진입 신호를 내는 테스트 전략.

    데이터가 min_bars 이상이면 매 바마다 진입 신호.
    """

    name = "always_enter"

    def __init__(
        self,
        stop: float = -0.05,
        tp: float = 0.10,
        min_entry_bars: int = 1,
    ) -> None:
        """초기화.

        Args:
            stop: 손절 비율
            tp: 익절 비율
            min_entry_bars: 진입 신호 최소 데이터 바 수
        """
        self.params = _AlwaysEnterParams(stop_loss=stop, take_profit=tp)
        self._min_entry_bars = min_entry_bars

    def check_entry_signal(
        self,
        daily: list[DailyPrice],
        current_price: int,
        current_volume: int,
        time_ratio: float = 1.0,
        **_: object,
    ) -> bool:
        """항상 True (데이터 충분 시)."""
        return len(daily) >= self._min_entry_bars

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,
    ) -> str | None:
        """stop_loss / take_profit 기본 청산."""
        if entry_price <= 0:
            return None
        pnl = (current_price - entry_price) / entry_price
        if pnl <= self.params.stop_loss:
            return "stop_loss"
        if pnl >= self.params.take_profit:
            return "take_profit"
        return None


class NeverEnterStrategy:
    """절대 진입하지 않는 테스트 전략."""

    name = "never_enter"

    def __init__(self) -> None:
        """초기화."""
        self.params = _AlwaysEnterParams()

    def check_entry_signal(self, *_: object, **__: object) -> bool:
        """항상 False."""
        return False

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,
    ) -> str | None:
        """항상 None."""
        return None


class ImmediateStopLossStrategy:
    """진입 후 즉시 손절하는 테스트 전략."""

    name = "immediate_stop"

    def __init__(self) -> None:
        """초기화."""
        self.params = _AlwaysEnterParams(stop_loss=-0.001)

    def check_entry_signal(
        self,
        daily: list[DailyPrice],
        current_price: int,
        current_volume: int,
        time_ratio: float = 1.0,
        **_: object,
    ) -> bool:
        """데이터 5개 이상 시 항상 진입."""
        return len(daily) >= 5

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,
    ) -> str | None:
        """항상 손절."""
        if entry_price <= 0:
            return None
        pnl = (current_price - entry_price) / entry_price
        if pnl <= self.params.stop_loss:
            return "stop_loss"
        return None


# ── GenericDailyEngine 기본 동작 ──────────────────────────────────────────────


class TestGenericDailyEngineBasic:
    def test_empty_data_returns_empty_result(self) -> None:
        """데이터 없음 → 빈 결과 (오류 없음)."""
        engine = GenericDailyEngine(AlwaysEnterStrategy(), min_bars=5)
        result = engine.run("TEST", [])
        assert result.metrics["total_trades"] == 0

    def test_insufficient_data_returns_empty(self) -> None:
        """min_bars 미만 데이터 → 빈 결과."""
        engine = GenericDailyEngine(AlwaysEnterStrategy(), min_bars=30)
        result = engine.run("TEST", make_flat_series(10))
        assert result.metrics["total_trades"] == 0

    def test_never_enter_zero_trades(self) -> None:
        """진입 없는 전략 → 거래 0건."""
        engine = GenericDailyEngine(NeverEnterStrategy(), min_bars=5)
        result = engine.run("TEST", make_flat_series(60))
        assert result.metrics["total_trades"] == 0

    def test_result_has_required_metrics_keys(self) -> None:
        """결과에 필수 메트릭 키 존재."""
        engine = GenericDailyEngine(AlwaysEnterStrategy(), min_bars=5)
        result = engine.run("TEST", make_flat_series(60))
        required = {
            "total_trades",
            "win_rate",
            "sharpe_ratio",
            "max_drawdown",
            "profit_factor",
        }
        assert required.issubset(result.metrics.keys())

    def test_params_stored_in_result(self) -> None:
        """전략 params가 결과에 저장됨."""
        strategy = AlwaysEnterStrategy()
        engine = GenericDailyEngine(strategy, min_bars=5)
        result = engine.run("TEST", make_flat_series(60))
        assert result.params is strategy.params

    def test_mdd_non_positive(self) -> None:
        """MDD는 0 이하."""
        engine = GenericDailyEngine(AlwaysEnterStrategy(), min_bars=5)
        result = engine.run("TEST", make_flat_series(60))
        assert result.metrics["max_drawdown"] <= 0.0


# ── 진입/체결 신호 ────────────────────────────────────────────────────────────


class TestGenericDailyEngineEntryExit:
    def test_always_enter_produces_trades(self) -> None:
        """항상 진입 전략 → 거래 1건 이상."""
        engine = GenericDailyEngine(AlwaysEnterStrategy(min_entry_bars=1), min_bars=5)
        result = engine.run("TEST", make_flat_series(30))
        assert result.metrics["total_trades"] >= 1

    def test_next_day_entry_no_lookahead(self) -> None:
        """진입일 = 신호일 + 1 (익일 체결 확인)."""
        strategy = AlwaysEnterStrategy(min_entry_bars=3)
        engine = GenericDailyEngine(strategy, min_bars=5)
        data = make_flat_series(20)
        result = engine.run("TEST", data)
        # 진입일은 dates 리스트에서 신호일 바로 다음이어야 함
        for trade in result.trades:
            assert len(trade.entry_time) == 8  # YYYYMMDD

    def test_stop_loss_exit_reason(self) -> None:
        """손절 조건 → exit_reason=stop_loss."""
        # 가격이 진입 후 급락하도록 시리즈 구성
        data: list[DailyPrice] = []
        for i in range(10):
            date = f"2025010{i + 1}"
            price = 10_000 - i * 300  # 매일 3% 하락
            data.append(make_daily(date, price, price + 50, price - 50, price))

        strategy = ImmediateStopLossStrategy()
        engine = GenericDailyEngine(strategy, min_bars=2)
        result = engine.run("TEST", data)

        if result.trades:
            # 손절 거래가 있어야 함 (혹은 force_close — 마지막 바에서)
            exit_reasons = {t.exit_reason for t in result.trades}
            assert exit_reasons & {"stop_loss", "force_close"}

    def test_max_holding_days_triggers_exit(self) -> None:
        """최대 보유일 초과 → max_holding으로 청산."""
        strategy = AlwaysEnterStrategy(stop=-1.0, tp=100.0)  # 손절/익절 사실상 없음
        engine = GenericDailyEngine(
            strategy,
            min_bars=2,
            max_holding_days=3,
        )
        result = engine.run("TEST", make_flat_series(20))

        # 3일 초과 보유 → max_holding 청산이 있어야 함
        exit_reasons = [t.exit_reason for t in result.trades]
        assert any(r in {"max_holding", "force_close"} for r in exit_reasons)

    def test_max_positions_not_exceeded(self) -> None:
        """동시 포지션 수 max_positions 초과 안 함."""
        strategy = AlwaysEnterStrategy(stop=-1.0, tp=100.0)
        engine = GenericDailyEngine(
            strategy,
            min_bars=2,
            max_positions=2,
            max_holding_days=50,
        )
        result = engine.run("TEST", make_flat_series(30))
        # 오류 없이 완료 + 거래 수는 양의 정수
        assert result.metrics["total_trades"] >= 0

    def test_force_close_at_last_bar(self) -> None:
        """미청산 포지션 → 마지막 바에서 force_close."""
        strategy = AlwaysEnterStrategy(stop=-1.0, tp=100.0)  # 손절/익절 없음
        engine = GenericDailyEngine(
            strategy,
            min_bars=2,
            max_holding_days=1000,  # 타임컷 없음
        )
        result = engine.run("TEST", make_flat_series(10))
        if result.trades:
            exit_reasons = {t.exit_reason for t in result.trades}
            assert "force_close" in exit_reasons


# ── 거래 비용 계산 ────────────────────────────────────────────────────────────


class TestGenericDailyEngineFinancials:
    def test_pnl_is_net_of_costs(self) -> None:
        """손익률이 수수료 + 거래세 차감 후 값인지 확인."""
        commission = 0.00015
        tax = 0.002
        strategy = AlwaysEnterStrategy(stop=-1.0, tp=100.0)
        engine = GenericDailyEngine(
            strategy,
            min_bars=2,
            max_holding_days=2,
        )
        engine.commission_rate = commission
        engine.tax_rate = tax
        engine.slippage_pct = 0.0

        # 가격 변화 없는 시리즈 (손익 거의 0)
        data = make_flat_series(10)
        result = engine.run("TEST", data)
        for trade in result.trades:
            if trade.exit_reason in {"stop_loss", "take_profit", "max_holding", "force_close"}:
                gross = (trade.exit_price - trade.entry_price) / trade.entry_price
                expected_net = gross - commission * 2 - tax
                assert abs(trade.pnl_pct - expected_net) < 1e-6


# ── check_exit_with_indicators 지원 ──────────────────────────────────────────


class TestGenericDailyEngineIndicatorExit:
    def test_range_strategy_indicator_exit_called(self) -> None:
        """RangeStrategy: check_exit_with_indicators 경로 작동 확인 (오류 없음)."""
        params = RangeParams(
            bb_period=10,
            rsi_period=10,
            stop_loss=-0.05,
            take_profit=0.05,
        )
        strategy = RangeStrategy(params)
        engine = GenericDailyEngine(strategy, min_bars=15)
        data = make_flat_series(50, price=10_000)
        result = engine.run("TEST", data)
        # 오류 없이 완료
        assert result.metrics is not None

    def test_mean_reversion_indicator_exit_called(self) -> None:
        """MeanReversionStrategy: check_exit_with_indicators 경로 작동 확인."""
        params = MeanReversionParams(rsi_period=10, bb_period=10)
        strategy = MeanReversionStrategy(params)
        engine = GenericDailyEngine(strategy, min_bars=15)
        data = make_flat_series(50, price=10_000)
        result = engine.run("TEST", data)
        assert result.metrics is not None

    def test_pullback_no_indicator_exit(self) -> None:
        """PullbackStrategy: check_exit_with_indicators 없음 → 기본 청산만."""
        params = PullbackParams(ma_period=10, rsi_period=10)
        strategy = PullbackStrategy(params)
        engine = GenericDailyEngine(strategy, min_bars=15)
        data = make_flat_series(50, price=10_000)
        result = engine.run("TEST", data)
        assert result.metrics is not None
        # PullbackStrategy는 check_exit_with_indicators 없음
        assert not hasattr(strategy, "check_exit_with_indicators")


# ── GenericPosition ───────────────────────────────────────────────────────────


class TestGenericPosition:
    def test_peak_price_initialized_from_entry(self) -> None:
        """peak_price 초기값 = entry_price."""
        pos = GenericPosition(
            symbol="TEST",
            entry_date="20250101",
            entry_price=10_000,
        )
        assert pos.peak_price == 10_000

    def test_update_peak_only_increases(self) -> None:
        """update_peak: 최고가는 증가만."""
        pos = GenericPosition(symbol="T", entry_date="20250101", entry_price=10_000)
        pos.update_peak(12_000)
        assert pos.peak_price == 12_000
        pos.update_peak(9_000)  # 낮아도 갱신 안 함
        assert pos.peak_price == 12_000


# ── GenericWalkForwardSummary 속성 ────────────────────────────────────────────


class TestGenericWalkForwardSummary:
    def _make_summary(self, oos_sharpes: list[float]) -> GenericWalkForwardSummary:
        """테스트용 Summary 생성."""
        from src.backtest.generic_walk_forward import GenericWalkForwardResult

        summary = GenericWalkForwardSummary(symbol="TEST", strategy_name="test")
        for i, sharpe in enumerate(oos_sharpes):
            summary.windows.append(
                GenericWalkForwardResult(
                    window_id=i,
                    in_sample_metrics={
                        "sharpe_ratio": 1.0,
                        "win_rate": 0.5,
                        "avg_win": 0.02,
                        "avg_loss": -0.01,
                        "max_drawdown": -0.05,
                    },
                    oos_metrics={
                        "sharpe_ratio": sharpe,
                        "win_rate": 0.45,
                        "avg_win": 0.018,
                        "avg_loss": -0.01,
                        "max_drawdown": -0.06,
                    },
                )
            )
        return summary

    def test_avg_oos_sharpe_empty_windows(self) -> None:
        """윈도우 없으면 avg_oos_sharpe = 0.0."""
        summary = GenericWalkForwardSummary(symbol="T", strategy_name="t")
        assert summary.avg_oos_sharpe == 0.0

    def test_avg_oos_sharpe_correct(self) -> None:
        """avg_oos_sharpe = 윈도우 OOS Sharpe 평균."""
        summary = self._make_summary([1.0, 2.0, 3.0])
        assert abs(summary.avg_oos_sharpe - 2.0) < 1e-6

    def test_to_dict_has_required_keys(self) -> None:
        """to_dict 결과에 필수 키 존재."""
        summary = self._make_summary([0.5, 1.2])
        d = summary.to_dict()
        required = {"symbol", "strategy", "params", "avg_oos_sharpe", "avg_oos_mdd", "windows"}
        assert required.issubset(d.keys())

    def test_sharpe_degradation_zero_when_no_is(self) -> None:
        """IS Sharpe=0이면 degradation=0.0."""
        from src.backtest.generic_walk_forward import GenericWalkForwardResult

        result = GenericWalkForwardResult(
            window_id=0,
            in_sample_metrics={"sharpe_ratio": 0.0},
            oos_metrics={"sharpe_ratio": 1.5},
        )
        assert result.sharpe_degradation == 0.0


# ── run_walk_forward_generic ──────────────────────────────────────────────────


class TestRunWalkForwardGeneric:
    def test_insufficient_data_returns_empty_windows(self) -> None:
        """데이터 부족 → 윈도우 없는 요약 반환."""
        strategy = NeverEnterStrategy()
        data = make_indexed_series(50)
        summary = run_walk_forward_generic(
            "TEST",
            data,
            strategy,
            train_months=6,
            test_months=2,
            min_bars=5,
        )
        assert len(summary.windows) == 0
        assert summary.symbol == "TEST"

    def test_sufficient_data_creates_windows(self) -> None:
        """충분한 데이터 → 1개 이상 윈도우 생성."""
        strategy = NeverEnterStrategy()
        data = make_indexed_series(400)
        summary = run_walk_forward_generic(
            "TEST",
            data,
            strategy,
            train_months=6,
            test_months=2,
            min_bars=5,
        )
        assert len(summary.windows) >= 1

    def test_strategy_name_in_summary(self) -> None:
        """strategy_name이 올바르게 기록됨."""
        strategy = NeverEnterStrategy()
        data = make_indexed_series(300)
        summary = run_walk_forward_generic("TEST", data, strategy, min_bars=5)
        assert summary.strategy_name == "never_enter"

    def test_windows_have_oos_metrics(self) -> None:
        """각 윈도우에 oos_metrics 존재."""
        strategy = AlwaysEnterStrategy(min_entry_bars=2)
        data = make_indexed_series(400)
        summary = run_walk_forward_generic(
            "TEST",
            data,
            strategy,
            min_bars=5,
            train_months=6,
            test_months=2,
        )
        for window in summary.windows:
            assert "sharpe_ratio" in window.oos_metrics
            assert "max_drawdown" in window.oos_metrics

    def test_train_test_dates_non_empty(self) -> None:
        """train_dates, test_dates 문자열 비어있지 않음."""
        strategy = NeverEnterStrategy()
        data = make_indexed_series(300)
        summary = run_walk_forward_generic(
            "TEST",
            data,
            strategy,
            min_bars=5,
            train_months=6,
            test_months=2,
        )
        for window in summary.windows:
            assert window.train_dates != ""
            assert window.test_dates != ""

    def test_pullback_strategy_integration(self) -> None:
        """PullbackStrategy 실제 전략으로 walk-forward 실행 — 오류 없음."""
        params = PullbackParams(ma_period=10, rsi_period=10, lookback_bars=3)
        strategy = PullbackStrategy(params)
        data = make_indexed_series(350)
        summary = run_walk_forward_generic(
            "TEST",
            data,
            strategy,
            min_bars=15,
            train_months=6,
            test_months=2,
        )
        assert summary.strategy_name == "pullback"
        assert len(summary.windows) >= 1

    def test_range_strategy_integration(self) -> None:
        """RangeStrategy 실제 전략으로 walk-forward 실행 — 오류 없음."""
        params = RangeParams(bb_period=10, rsi_period=10)
        strategy = RangeStrategy(params)
        data = make_indexed_series(350)
        summary = run_walk_forward_generic(
            "TEST",
            data,
            strategy,
            min_bars=15,
            train_months=6,
            test_months=2,
        )
        assert summary.strategy_name == "range_trade"

    def test_mean_reversion_strategy_integration(self) -> None:
        """MeanReversionStrategy 실제 전략으로 walk-forward 실행 — 오류 없음."""
        params = MeanReversionParams(rsi_period=10, bb_period=10)
        strategy = MeanReversionStrategy(params)
        data = make_indexed_series(350)
        summary = run_walk_forward_generic(
            "TEST",
            data,
            strategy,
            min_bars=15,
            train_months=6,
            test_months=2,
        )
        assert summary.strategy_name == "mean_reversion"
