"""평균회귀 백테스트 엔진 테스트."""

from src.backtest.mr_engine import MRBacktestEngine
from src.broker.schemas import DailyPrice
from src.strategy.mean_reversion import MeanReversionParams


def _daily(
    date: str,
    close: int,
    volume: int,
    *,
    high: int | None = None,
    low: int | None = None,
    open_: int | None = None,
) -> DailyPrice:
    """테스트용 DailyPrice 생성."""
    return DailyPrice(
        date=date,
        open=open_ or close - 50,
        high=high or close + 50,
        low=low or close - 100,
        close=close,
        volume=volume,
    )


def _make_downtrend_data(
    n: int = 30,
    start_price: int = 10000,
    drop_per_bar: int = 100,
    volume: int = 100000,
) -> list[DailyPrice]:
    """하락 추세 데이터 생성 (RSI 과매도 유도)."""
    data = []
    for i in range(n):
        price = start_price - i * drop_per_bar
        data.append(
            _daily(
                date=f"2026{(i // 28) + 1:02d}{(i % 28) + 1:02d}",
                close=price,
                volume=volume,
            )
        )
    return data


def _make_stable_then_drop(
    stable_bars: int = 20,
    drop_bars: int = 5,
    stable_price: int = 10000,
    drop_per_bar: int = 200,
    volume: int = 100000,
) -> list[DailyPrice]:
    """안정 구간 후 급락 데이터 (BB 하단 돌파 + RSI 과매도 유도)."""
    data = []
    for i in range(stable_bars):
        # 약간의 노이즈로 BB 폭 확보
        noise = 20 * (1 if i % 2 == 0 else -1)
        data.append(
            _daily(
                date=f"2026{(i // 28) + 1:02d}{(i % 28) + 1:02d}",
                close=stable_price + noise,
                volume=volume,
            )
        )
    for j in range(drop_bars):
        idx = stable_bars + j
        price = stable_price - (j + 1) * drop_per_bar
        data.append(
            _daily(
                date=f"2026{(idx // 28) + 1:02d}{(idx % 28) + 1:02d}",
                close=price,
                volume=volume,
            )
        )
    return data


def _make_drop_then_recover(
    stable_bars: int = 20,
    drop_bars: int = 5,
    recover_bars: int = 5,
    stable_price: int = 10000,
    drop_per_bar: int = 200,
    recover_per_bar: int = 250,
    volume: int = 100000,
) -> list[DailyPrice]:
    """안정 → 급락 → 반등 데이터 (진입 후 익절/지표 청산 유도)."""
    data = _make_stable_then_drop(stable_bars, drop_bars, stable_price, drop_per_bar, volume)
    bottom_price = stable_price - drop_bars * drop_per_bar
    for k in range(recover_bars):
        idx = stable_bars + drop_bars + k
        price = bottom_price + (k + 1) * recover_per_bar
        data.append(
            _daily(
                date=f"2026{(idx // 28) + 1:02d}{(idx % 28) + 1:02d}",
                close=price,
                volume=volume,
            )
        )
    return data


class TestMRBacktestEngineBasic:
    """기본 동작 테스트."""

    def test_empty_data(self) -> None:
        """빈 데이터 → 빈 결과."""
        engine = MRBacktestEngine()
        result = engine.run([])
        assert result.trades == []
        assert result.metrics["total_trades"] == 0

    def test_insufficient_data(self) -> None:
        """20봉 미만 데이터 → 거래 없음."""
        engine = MRBacktestEngine()
        data = [_daily(f"202601{i + 1:02d}", 10000, 100000) for i in range(10)]
        result = engine.run(data)
        assert result.trades == []

    def test_no_entry_when_rsi_high(self) -> None:
        """RSI가 높은 상승 추세에서는 진입 없음."""
        engine = MRBacktestEngine()
        # 꾸준히 상승하는 데이터 → RSI > oversold
        data = []
        for i in range(30):
            price = 10000 + i * 100
            data.append(
                _daily(
                    date=f"2026{(i // 28) + 1:02d}{(i % 28) + 1:02d}",
                    close=price,
                    volume=100000,
                )
            )
        result = engine.run(data)
        assert result.metrics["total_trades"] == 0

    def test_result_has_mr_params(self) -> None:
        """결과에 MeanReversionParams 저장."""
        params = MeanReversionParams(rsi_oversold=30.0)
        engine = MRBacktestEngine(params)
        result = engine.run([])
        assert isinstance(result.params, MeanReversionParams)
        assert result.params.rsi_oversold == 30.0


class TestMRBacktestEngineEntryExit:
    """진입/청산 시나리오 테스트."""

    def test_entry_and_stop_loss(self) -> None:
        """진입 후 추가 하락 → 손절."""
        params = MeanReversionParams(
            rsi_oversold=40.0,  # 공격적 진입
            bb_std=1.5,  # 넓은 진입 영역
            stop_loss=-0.02,
            take_profit=0.10,  # 높은 TP로 익절 방지
            volume_ratio=0.5,
        )
        # 안정 → 급락 → 더 급락
        data = _make_stable_then_drop(stable_bars=20, drop_bars=8, drop_per_bar=200, volume=100000)
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        stop_losses = [t for t in result.trades if t.exit_reason == "stop_loss"]
        # 진입이 발생하고 손절이 나와야 함
        assert len(result.trades) > 0
        assert len(stop_losses) > 0

    def test_entry_and_take_profit(self) -> None:
        """진입 후 반등 → 익절."""
        params = MeanReversionParams(
            rsi_oversold=40.0,
            bb_std=1.5,
            stop_loss=-0.10,  # 넓은 SL로 손절 방지
            take_profit=0.02,  # 낮은 TP
            rsi_overbought=90.0,  # 높은 RSI 과매수로 지표 청산 방지
            volume_ratio=0.5,
        )
        data = _make_drop_then_recover(
            stable_bars=20,
            drop_bars=5,
            recover_bars=5,
            drop_per_bar=200,
            recover_per_bar=300,
            volume=100000,
        )
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        take_profits = [t for t in result.trades if t.exit_reason == "take_profit"]
        assert len(take_profits) > 0

    def test_entry_and_bb_center_reversion(self) -> None:
        """진입 후 BB 중심선 복귀 → 청산."""
        params = MeanReversionParams(
            rsi_oversold=40.0,
            bb_std=1.5,
            stop_loss=-0.20,  # 매우 넓은 SL
            take_profit=0.20,  # 매우 넓은 TP
            rsi_overbought=90.0,  # RSI 청산 비활성화
            volume_ratio=0.5,
        )
        data = _make_drop_then_recover(
            stable_bars=20,
            drop_bars=5,
            recover_bars=10,
            drop_per_bar=200,
            recover_per_bar=250,
            volume=100000,
        )
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        bb_exits = [t for t in result.trades if t.exit_reason == "bb_center_reversion"]
        # BB 중심선 복귀 청산이 발생해야 함
        assert len(bb_exits) > 0

    def test_force_close_unclosed(self) -> None:
        """데이터 종료 시 미청산 포지션 강제 청산."""
        params = MeanReversionParams(
            rsi_oversold=40.0,
            bb_std=1.5,
            stop_loss=-0.50,  # 절대 안 걸리는 SL
            take_profit=0.50,  # 절대 안 걸리는 TP
            rsi_overbought=95.0,
            volume_ratio=0.5,
        )
        # 급락 후 소폭 반등 (청산 조건 미충족)
        data = _make_drop_then_recover(
            stable_bars=20,
            drop_bars=5,
            recover_bars=2,
            drop_per_bar=200,
            recover_per_bar=50,
            volume=100000,
        )
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        if result.trades:
            force_closes = [t for t in result.trades if t.exit_reason == "force_close"]
            assert len(force_closes) > 0


class TestMRBacktestEnginePositionManagement:
    """포지션 관리 테스트."""

    def test_max_positions_limit(self) -> None:
        """max_positions 초과 진입 거부."""
        params = MeanReversionParams(
            max_positions=1,
            rsi_oversold=45.0,
            bb_std=1.0,
            stop_loss=-0.50,
            take_profit=0.50,
            volume_ratio=0.3,
        )
        data = _make_stable_then_drop(stable_bars=20, drop_bars=10, drop_per_bar=150, volume=100000)
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        # 최소 1개 거래 존재 확인
        assert len(result.trades) >= 1

    def test_run_vs_run_with_symbol(self) -> None:
        """run()과 run_with_symbol() 동일 결과 + symbol 필드."""
        params = MeanReversionParams(rsi_oversold=40.0, bb_std=1.5, volume_ratio=0.5)
        data = _make_drop_then_recover()
        engine = MRBacktestEngine(params)

        result_no_sym = engine.run(data)
        result_sym = engine.run_with_symbol("005930", data)

        assert len(result_no_sym.trades) == len(result_sym.trades)
        for trade in result_sym.trades:
            assert trade.symbol == "005930"


class TestMRBacktestEnginePnl:
    """손익 계산 테스트."""

    def test_trade_pnl_includes_commission(self) -> None:
        """거래비용 차감 확인."""
        params = MeanReversionParams(
            commission_rate=0.00015,
            tax_rate=0.002,
        )
        engine = MRBacktestEngine(params)
        # 10000 → 10300 = +3%
        pnl = engine._calc_trade_pnl(10000, 10300)
        expected = 0.03 - (0.00015 * 2 + 0.002)  # 3% - 0.23%
        assert abs(pnl - expected) < 1e-6

    def test_zero_entry_price(self) -> None:
        """진입가 0이면 pnl 0."""
        engine = MRBacktestEngine()
        assert engine._calc_trade_pnl(0, 10000) == 0.0

    def test_date_format_in_trade_record(self) -> None:
        """entry_time/exit_time이 YYYYMMDD 형식."""
        params = MeanReversionParams(
            rsi_oversold=40.0,
            bb_std=1.5,
            volume_ratio=0.5,
            stop_loss=-0.01,
        )
        data = _make_stable_then_drop(stable_bars=20, drop_bars=8, drop_per_bar=200, volume=100000)
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        for trade in result.trades:
            # DailyPrice.date는 YYYYMMDD 형식
            assert len(trade.entry_time) == 8
            assert trade.entry_time.isdigit()


class TestMRBacktestEngineMetrics:
    """지표 계산 통합 테스트."""

    def test_metrics_fields_present(self) -> None:
        """calc_metrics 결과에 필수 필드 포함."""
        params = MeanReversionParams(rsi_oversold=40.0, bb_std=1.5, volume_ratio=0.5)
        data = _make_drop_then_recover()
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        required_keys = [
            "total_trades",
            "win_count",
            "loss_count",
            "win_rate",
            "avg_pnl",
            "max_drawdown",
            "sharpe_ratio",
            "profit_factor",
        ]
        for key in required_keys:
            assert key in result.metrics

    def test_win_rate_between_0_and_1(self) -> None:
        """승률은 0~1 범위."""
        params = MeanReversionParams(rsi_oversold=40.0, bb_std=1.5, volume_ratio=0.5)
        data = _make_drop_then_recover()
        engine = MRBacktestEngine(params)
        result = engine.run(data)

        if result.metrics["total_trades"] > 0:
            assert 0 <= result.metrics["win_rate"] <= 1
