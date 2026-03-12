"""백테스트 엔진 테스트."""

from src.backtest.engine import BacktestEngine
from src.backtest.strategy import MomentumParams
from src.broker.schemas import DailyPrice, MinutePrice


def _daily(date: str, high: int, volume: int, close: int = 10000) -> DailyPrice:
    """테스트용 DailyPrice 생성."""
    return DailyPrice(
        date=date,
        open=close - 100,
        high=high,
        low=close - 200,
        close=close,
        volume=volume,
    )


def _minute(dt: str, close: int, volume: int) -> MinutePrice:
    """테스트용 MinutePrice 생성."""
    return MinutePrice(
        datetime=dt,
        open=close - 10,
        high=close + 10,
        low=close - 20,
        close=close,
        volume=volume,
    )


class TestBacktestEngine:
    """BacktestEngine 테스트."""

    def test_empty_data(self) -> None:
        """데이터 없으면 빈 결과."""
        engine = BacktestEngine()
        result = engine.run([], [])
        assert result.trades == []
        assert result.metrics["total_trades"] == 0

    def test_no_entry_signal(self) -> None:
        """진입 조건 미충족 시 거래 없음."""
        params = MomentumParams(high_52w_threshold=0.95, volume_ratio=1.5)
        engine = BacktestEngine(params)

        # 52주 최고가 10000, 현재가 8000 (80% → 95% 미만)
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]
        minute = [_minute(f"20250106{h:02d}0000", 8000, 500) for h in range(9, 16)]

        result = engine.run(minute, daily)
        assert result.trades == []

    def test_entry_and_take_profit(self) -> None:
        """진입 후 익절 시나리오."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.01,
            stop_loss=-0.005,
        )
        engine = BacktestEngine(params)

        # 52주 최고가 10000, 평균 거래량 1000
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        # 진입: 가격 9500 (95%), 거래량 1500 (150%)
        # 익절: 가격 9600 (1.05% 수익 > 1%)
        minute = [
            _minute("20250106090000", 9500, 1500),  # 진입
            _minute("20250106091000", 9550, 1000),
            _minute("20250106092000", 9600, 1000),  # 익절
        ]

        result = engine.run(minute, daily)
        assert len(result.trades) >= 1
        assert result.trades[0].exit_reason == "take_profit"

    def test_entry_and_stop_loss(self) -> None:
        """진입 후 손절 시나리오."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.01,
            stop_loss=-0.005,
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        minute = [
            _minute("20250106090000", 9500, 1500),  # 진입
            _minute("20250106091000", 9460, 1000),
            _minute("20250106092000", 9440, 1000),  # 손절 (-0.63%)
        ]

        result = engine.run(minute, daily)
        assert len(result.trades) >= 1
        assert result.trades[0].exit_reason == "stop_loss"

    def test_force_close(self) -> None:
        """장 마감 전 강제 청산."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            force_close_time="14:30",
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        minute = [
            _minute("20250106090000", 9500, 1500),  # 진입
            _minute("20250106130000", 9510, 1000),  # 유지
            _minute("20250106143000", 9510, 1000),  # 강제 청산
        ]

        result = engine.run(minute, daily)
        assert len(result.trades) >= 1
        # 강제 청산 또는 force_close 둘 중 하나
        close_reasons = [t.exit_reason for t in result.trades]
        assert "force_close" in close_reasons

    def test_max_positions_limit(self) -> None:
        """최대 포지션 제한."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            max_positions=2,
            take_profit=0.1,  # 높게 설정하여 청산 방지
            stop_loss=-0.1,
            force_close_time="15:30",
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        # 3개 바 모두 진입 조건 충족하지만, max_positions=2이므로 2개만 진입
        minute = [
            _minute("20250106090000", 9500, 1500),
            _minute("20250106091000", 9510, 1600),
            _minute("20250106092000", 9520, 1700),
            _minute("20250106140000", 9530, 1000),
        ]

        result = engine.run(minute, daily)
        # 마지막에 강제 청산되므로 최소 2개 거래
        assert len(result.trades) >= 2

    def test_run_with_symbol(self) -> None:
        """심볼 지정 백테스트."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.01,
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]
        minute = [
            _minute("20250106090000", 9500, 1500),
            _minute("20250106091000", 9600, 1000),
        ]

        result = engine.run_with_symbol("005930", minute, daily)
        if result.trades:
            assert result.trades[0].symbol == "005930"

    def test_result_has_params(self) -> None:
        """결과에 파라미터 포함."""
        params = MomentumParams(volume_ratio=2.0)
        engine = BacktestEngine(params)
        result = engine.run([], [])
        assert result.params is not None
        assert result.params.volume_ratio == 2.0

    def test_calc_52w_high(self) -> None:
        """52주 최고가 계산."""
        daily = [
            _daily("20250101", 9000, 1000),
            _daily("20250102", 10000, 1000),
            _daily("20250103", 9500, 1000),
        ]
        assert BacktestEngine._calc_52w_high(daily) == 10000

    def test_calc_52w_high_empty(self) -> None:
        """데이터 없으면 0."""
        assert BacktestEngine._calc_52w_high([]) == 0

    def test_calc_avg_volume(self) -> None:
        """평균 거래량 계산."""
        daily = [
            _daily("20250101", 10000, 1000),
            _daily("20250102", 10000, 2000),
            _daily("20250103", 10000, 3000),
        ]
        assert BacktestEngine._calc_avg_volume(daily) == 2000

    def test_calc_avg_volume_empty(self) -> None:
        """데이터 없으면 0."""
        assert BacktestEngine._calc_avg_volume([]) == 0

    def test_unclosed_positions_force_closed(self) -> None:
        """미청산 포지션은 마지막 바에서 강제 청산."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.1,  # 높게 설정하여 자동 청산 방지
            stop_loss=-0.1,
            force_close_time="15:30",  # 늦게 설정하여 강제 청산 시각 회피
            max_positions=1,  # 누적 거래량 증가로 복수 진입 방지
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]
        minute = [
            _minute("20250106090000", 9500, 1500),  # 진입 (누적=1500 >= 1500)
            _minute("20250106100000", 9510, 1000),  # 유지 (max_positions=1 차단)
        ]

        result = engine.run(minute, daily)
        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == "force_close"

    def test_metrics_included(self) -> None:
        """결과에 지표 포함."""
        engine = BacktestEngine()
        result = engine.run([], [])
        assert "total_trades" in result.metrics
        assert "win_rate" in result.metrics
        assert "max_drawdown" in result.metrics
        assert "sharpe_ratio" in result.metrics

    def test_run_with_symbol_empty_data(self) -> None:
        """run_with_symbol: 데이터 없으면 빈 결과."""
        engine = BacktestEngine()
        result = engine.run_with_symbol("005930", [], [])
        assert result.trades == []
        assert result.metrics["total_trades"] == 0

    def test_run_with_symbol_force_close_unclosed(self) -> None:
        """run_with_symbol: 미청산 포지션 강제 청산."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.1,
            stop_loss=-0.1,
            force_close_time="15:30",
            max_positions=1,  # 누적 거래량 증가로 복수 진입 방지
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]
        minute = [
            _minute("20250106090000", 9500, 1500),  # 진입 (누적=1500 >= 1500)
            _minute("20250106100000", 9510, 1000),  # 유지 (max_positions=1 차단)
        ]

        result = engine.run_with_symbol("005930", minute, daily)
        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == "force_close"
        assert result.trades[0].symbol == "005930"

    def test_entry_exit_reentry_cycle(self) -> None:
        """진입 → 청산 → 재진입 사이클.

        누적 거래량 로직 하에서 1차 청산 바에서 바로 재진입이 일어난다.
        - bar0: 진입 (누적=1500 >= 1500)
        - bar1: 1차 익절 (9600 > 9500*1.01) + 재진입 (누적 충분)
        - bar2: 2차 익절 (9700 >= 9600*1.01=9696)
        """
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.01,
            stop_loss=-0.1,
            force_close_time="15:30",
            max_positions=1,
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]
        minute = [
            _minute("20250106090000", 9500, 1500),  # 1차 진입 (누적=1500)
            _minute("20250106091000", 9600, 1000),  # 1차 익절 + 2차 진입 (누적=2500)
            _minute("20250106092000", 9700, 1000),  # 2차 익절 (9700 >= 9600*1.01=9696)
        ]

        result = engine.run(minute, daily)
        assert len(result.trades) >= 2
        assert result.trades[0].exit_reason == "take_profit"
        assert result.trades[1].exit_reason == "take_profit"

    def test_max_positions_blocks_third_entry(self) -> None:
        """max_positions=2일 때 3번째 진입 거부 확인."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            max_positions=2,
            take_profit=0.1,
            stop_loss=-0.1,
            force_close_time="15:30",
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        # 3개 진입 시도, 2개만 허용
        minute = [
            _minute("20250106090000", 9500, 1500),
            _minute("20250106091000", 9510, 1600),
            _minute("20250106092000", 9520, 1700),
        ]

        result = engine.run(minute, daily)
        # 마지막에 미청산 강제 청산 → 정확히 2개
        assert len(result.trades) == 2

    def test_cumulative_volume_resets_on_date_change(self) -> None:
        """날짜가 바뀌면 누적 거래량이 리셋된다."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.1,
            stop_loss=-0.1,
            force_close_time="15:30",
            max_positions=1,
        )
        engine = BacktestEngine(params)

        # avg_volume=1000, threshold=1500 (1000*1.5)
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        # 날짜1: 거래량 800 (누적 800 < 1500 → 진입 안 됨)
        # 날짜2: 거래량 800 (누적 리셋 후 800 < 1500 → 진입 안 됨)
        minute = [
            _minute("20250106090000", 9500, 800),
            _minute("20250107090000", 9500, 800),
        ]

        result = engine.run(minute, daily)
        assert len(result.trades) == 0

    def test_cumulative_volume_accumulates_within_day(self) -> None:
        """같은 날 분봉 거래량이 누적되어 진입 기준을 충족한다."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.1,
            stop_loss=-0.1,
            force_close_time="15:30",
            max_positions=1,
        )
        engine = BacktestEngine(params)

        # avg_volume=1000, threshold=1500
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        # 각 바 거래량 800: 첫 바 누적 800 < 1500 → 미진입
        # 두 번째 바 누적 1600 >= 1500 → 진입
        minute = [
            _minute("20250106090000", 9500, 800),
            _minute("20250106091000", 9500, 800),
            _minute("20250106140000", 9500, 100),  # 청산 (force_close_time 지남)
        ]

        result = engine.run(minute, daily)
        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == "force_close"

    def test_run_with_symbol_cumulative_volume(self) -> None:
        """run_with_symbol도 누적 거래량 기반 진입 검증."""
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.1,
            stop_loss=-0.1,
            force_close_time="15:30",
            max_positions=1,
        )
        engine = BacktestEngine(params)

        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        # 누적 800+800=1600 >= 1500 → 두 번째 바에서 진입
        minute = [
            _minute("20250106090000", 9500, 800),
            _minute("20250106091000", 9500, 800),
            _minute("20250106140000", 9500, 100),
        ]

        result = engine.run_with_symbol("005930", minute, daily)
        assert len(result.trades) == 1
        assert result.trades[0].symbol == "005930"
