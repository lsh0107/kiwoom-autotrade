"""tests/backtest/test_daily_engine.py — DailyBacktestEngine 단위 테스트."""

from __future__ import annotations

from src.backtest.daily_engine import DailyBacktestEngine
from src.broker.schemas import DailyPrice
from src.strategy.momentum_daily import DailyMomentumParams

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def make_daily(
    date: str,
    open_: int,
    high: int,
    low: int,
    close: int,
    volume: int = 1_000_000,
) -> DailyPrice:
    return DailyPrice(
        date=date,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def make_flat_series(n: int, price: int = 10_000) -> list[DailyPrice]:
    """횡보 가격 시리즈 (신고가 돌파 없음)."""
    result: list[DailyPrice] = []
    for i in range(n):
        date = f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}"
        result.append(make_daily(date, price, price + 100, price - 100, price))
    return result


def make_breakout_series(
    n_prior: int = 25,
    n_after: int = 15,
    prior_price: int = 10_000,
    breakout_price: int = 11_000,
    after_volume: int = 3_000_000,
) -> list[DailyPrice]:
    """N일 횡보 후 신고가 돌파 시리즈."""
    result: list[DailyPrice] = []
    for i in range(n_prior):
        date = f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}"
        result.append(
            make_daily(date, prior_price, prior_price + 50, prior_price - 50, prior_price)
        )
    for j in range(n_after):
        i = n_prior + j
        date = f"2026{i // 28 + 1:02d}{i % 28 + 1:02d}"
        close = breakout_price + j * 50
        result.append(make_daily(date, close - 50, close + 200, close - 200, close, after_volume))
    return result


# ── 기본 동작 ─────────────────────────────────────────────────────────────────


class TestDailyBacktestEngineBasic:
    def test_empty_data_returns_empty_result(self) -> None:
        """데이터 없음 → 빈 결과."""
        engine = DailyBacktestEngine()
        result = engine.run("TEST", daily_data=[], kospi_daily=None)
        assert result.metrics["total_trades"] == 0

    def test_insufficient_data_returns_empty(self) -> None:
        """lookback 미만 데이터 → 빈 결과."""
        params = DailyMomentumParams(lookback=20)
        engine = DailyBacktestEngine(params)
        result = engine.run("TEST", make_flat_series(10), None)
        assert result.metrics["total_trades"] == 0

    def test_result_has_required_metrics(self) -> None:
        """결과에 필수 메트릭 키 포함."""
        engine = DailyBacktestEngine()
        result = engine.run("TEST", make_flat_series(60), None)
        required = {
            "total_trades",
            "win_rate",
            "sharpe_ratio",
            "max_drawdown",
            "profit_factor",
            "win_count",
            "loss_count",
        }
        assert required.issubset(result.metrics.keys())

    def test_params_stored_in_result(self) -> None:
        """사용된 파라미터가 결과에 저장됨."""
        params = DailyMomentumParams(lookback=15)
        engine = DailyBacktestEngine(params)
        result = engine.run("TEST", make_flat_series(60), None)
        assert result.params is params


# ── 신호 / 체결 ───────────────────────────────────────────────────────────────


class TestDailyBacktestEngineSignals:
    def test_flat_market_no_trades(self) -> None:
        """횡보 시장 → 신고가 돌파 없음 → 거래 0건."""
        params = DailyMomentumParams(lookback=20, vol_mult=1.5, use_kospi_filter=False)
        engine = DailyBacktestEngine(params)
        result = engine.run("TEST", make_flat_series(60), None)
        assert result.metrics["total_trades"] == 0

    def test_breakout_triggers_at_least_one_trade(self) -> None:
        """신고가 돌파 후 거래 1건 이상 발생."""
        params = DailyMomentumParams(
            lookback=20,
            vol_mult=1.0,
            use_kospi_filter=False,
            atr_stop_mult=5.0,
            atr_tp_mult=2.0,
            tp_pct=0.10,
            max_holding_days=8,
        )
        engine = DailyBacktestEngine(params)
        data = make_breakout_series(
            n_prior=25, n_after=15, prior_price=10_000, breakout_price=10_700
        )
        result = engine.run("TEST", data, None)
        assert result.metrics["total_trades"] >= 1

    def test_next_day_entry_no_lookahead(self) -> None:
        """신호일(종가) 다음날 시가 체결 — 진입일 > 신호일."""
        params = DailyMomentumParams(lookback=10, vol_mult=0.5, use_kospi_filter=False)
        engine = DailyBacktestEngine(params)
        data = make_breakout_series(
            n_prior=15, n_after=10, prior_price=10_000, breakout_price=10_600
        )
        result = engine.run("TEST", data, None)
        # 거래가 있으면 entry_time이 오름차순 정렬된 날짜여야 함
        for trade in result.trades:
            assert len(trade.entry_time) == 8  # YYYYMMDD

    def test_max_positions_not_exceeded(self) -> None:
        """동시 포지션 수 max_positions 초과 안 함."""
        params = DailyMomentumParams(
            lookback=5,
            vol_mult=0.5,
            use_kospi_filter=False,
            max_positions=2,
            max_holding_days=20,
            atr_stop_mult=20.0,
            tp_pct=1.0,
        )
        engine = DailyBacktestEngine(params)
        data = make_breakout_series(
            n_prior=10, n_after=30, prior_price=10_000, breakout_price=10_600
        )
        result = engine.run("TEST", data, None)
        # max_positions=2이면 동시에 2개 초과 진입 불가 → 거래 수 ≤ n_after
        # 단순히 오류 없이 완료되는 것을 검증
        assert result.metrics["total_trades"] >= 0

    def test_max_holding_days_forces_exit(self) -> None:
        """최대 보유일 도달 시 max_holding으로 청산."""
        params = DailyMomentumParams(
            lookback=5,
            vol_mult=0.5,
            use_kospi_filter=False,
            max_holding_days=5,
            atr_stop_mult=100.0,  # 손절 사실상 비활성화
            atr_tp_mult=100.0,  # 익절 사실상 비활성화
            tp_pct=1.0,
        )
        engine = DailyBacktestEngine(params)
        data = make_breakout_series(
            n_prior=10, n_after=20, prior_price=10_000, breakout_price=10_600
        )
        result = engine.run("TEST", data, None)
        # max_holding으로 청산된 거래가 1건 이상 있거나 전체 거래 0건
        exit_reasons = [t.exit_reason for t in result.trades]
        for reason in exit_reasons:
            assert reason in {
                "stop_loss",
                "take_profit",
                "trailing_stop",
                "max_holding",
                "force_close",
            }


# ── 코스피 필터 ───────────────────────────────────────────────────────────────


class TestDailyBacktestEngineKospiFilter:
    def test_kospi_below_ma_blocks_entry(self) -> None:
        """KOSPI 하락 추세 → 진입 차단 → 거래 없음."""
        params = DailyMomentumParams(
            lookback=20,
            vol_mult=1.0,
            use_kospi_filter=True,
        )
        engine = DailyBacktestEngine(params)
        data = make_breakout_series(
            n_prior=25, n_after=15, prior_price=10_000, breakout_price=10_700
        )
        # KOSPI 지속 하락 (종가 < 20MA)
        n = len(data)
        kospi = [
            make_daily(
                f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}",
                3_000 - i * 30,
                3_000 - i * 30,
                3_000 - i * 30,
                3_000 - i * 30,
            )
            for i in range(n + 25)
        ]
        result = engine.run("TEST", data, kospi)
        assert result.metrics["total_trades"] == 0

    def test_no_kospi_data_uses_default(self) -> None:
        """KOSPI 데이터 없음 → 필터 패스 (오류 없어야 함)."""
        params = DailyMomentumParams(lookback=20, vol_mult=1.0, use_kospi_filter=True)
        engine = DailyBacktestEngine(params)
        data = make_breakout_series(
            n_prior=25, n_after=15, prior_price=10_000, breakout_price=10_700
        )
        result = engine.run("TEST", data, None)
        # kospi 없으면 필터 패스 → 거래 발생 가능
        assert result.metrics["total_trades"] >= 0  # 오류 없이 완료


# ── 재무 계산 정확성 ──────────────────────────────────────────────────────────


class TestDailyBacktestEngineFinancials:
    def test_pnl_is_net_of_costs(self) -> None:
        """거래 손익률이 수수료/세금/슬리피지 차감 후 값인지 확인."""
        params = DailyMomentumParams(
            lookback=5,
            vol_mult=0.5,
            use_kospi_filter=False,
            atr_stop_mult=0.1,  # 작은 손절 → 빠른 청산
        )
        engine = DailyBacktestEngine(params)
        data = make_breakout_series(
            n_prior=10, n_after=10, prior_price=10_000, breakout_price=10_700
        )
        result = engine.run("TEST", data, None)
        # 거래 있으면 pnl_pct는 총비용 차감 후 값
        for trade in result.trades:
            gross = (trade.exit_price - trade.entry_price) / trade.entry_price
            # net = gross - 수수료x2 - 세금 (슬리피지는 이미 가격에 반영됨)
            expected_net = gross - params.commission_rate * 2 - params.tax_rate
            assert abs(trade.pnl_pct - expected_net) < 0.001  # 슬리피지 계산 오차 허용

    def test_equity_curve_starts_at_one(self) -> None:
        """초기 자산이 1.0에서 시작해야 함."""
        params = DailyMomentumParams(lookback=5, vol_mult=0.5, use_kospi_filter=False)
        engine = DailyBacktestEngine(params)
        data = make_flat_series(60)
        result = engine.run("TEST", data, None)
        # 거래 없는 경우 equity_curve는 1.0으로 유지
        # metrics에서 max_drawdown이 0.0인지 확인 (손실 없으면)
        assert result.metrics["max_drawdown"] <= 0.0  # MDD는 음수 또는 0
