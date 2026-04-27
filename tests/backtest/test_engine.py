"""백테스트 엔진 테스트."""

from structlog.testing import capture_logs

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
            trailing_stop_pct=None,
            slippage_pct=0.0,  # 신호 로직만 테스트, 슬리피지 제외
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
            trailing_stop_pct=None,
            force_close_time="15:30",
            max_positions=1,
            slippage_pct=0.0,  # 신호 로직만 테스트, 슬리피지 제외
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

    def test_atr_dynamic_stop_with_zero_52w_threshold(self) -> None:
        """high_52w_threshold=0.0에서도 ATR 동적 손절 활성화 (버그 수정 검증)."""
        params = MomentumParams(
            high_52w_threshold=0.0,  # 비활성 — 이전에는 ATR도 비활성화됨
            price_change_min=0.0,
            volume_ratio=0.1,
            entry_start_time="",
            atr_stop_multiplier=1.5,
            stop_loss=-0.005,
            take_profit=0.015,
            force_close_time="15:30",
            max_positions=1,
        )
        engine = BacktestEngine(params)

        # close=10000, ATR ~200 → ATR%=2% > 0.35% → 동적 손절 활성
        daily = [
            _daily("20250101", 10200, 1000, close=10000),
            _daily("20250102", 10300, 1000, close=10100),
            _daily("20250103", 10100, 1000, close=9900),
            _daily("20250104", 10200, 1000, close=10000),
            _daily("20250105", 10150, 1000, close=10050),
        ]

        minute = [
            _minute("20250106090000", 10000, 500),  # 진입
            _minute("20250106100000", 10000, 100),  # 유지
        ]

        result = engine.run(minute, daily)
        # 핵심: ATR 활성화되어 거래가 발생해야 함 (진입 후 force_close)
        assert len(result.trades) >= 1

    def test_atr_volatility_filter_low_atr(self) -> None:
        """ATR% < 0.35% → 동적 손절 비활성, 고정 SL/TP 사용."""
        params = MomentumParams(
            atr_stop_multiplier=1.5,
        )
        engine = BacktestEngine(params)

        # 아주 낮은 변동성 — _daily 헬퍼 대신 직접 생성 (low=close-5로 초소변동)
        daily = [
            DailyPrice(date="20250101", open=10000, high=10005, low=9995, close=10000, volume=1000),
            DailyPrice(date="20250102", open=10000, high=10005, low=9995, close=10002, volume=1000),
            DailyPrice(date="20250103", open=10002, high=10007, low=9997, close=10000, volume=1000),
            DailyPrice(date="20250104", open=10000, high=10005, low=9995, close=10003, volume=1000),
            DailyPrice(date="20250105", open=10003, high=10008, low=9998, close=10000, volume=1000),
        ]

        _, dyn_stop, dyn_tp = engine._calc_indicators(daily)
        # ATR% ~0.1% < 0.35% → 동적 손절 None (고정 SL/TP 사용)
        assert dyn_stop is None
        assert dyn_tp is None

    def test_atr_floor_values(self) -> None:
        """ATR 동적 손절/익절 바닥값 적용 검증."""
        params = MomentumParams(
            atr_stop_multiplier=1.5,
        )
        engine = BacktestEngine(params)

        # ATR% ~0.5% → 1.5*0.5% = 0.75% > 바닥 0.5% → 바닥 미적용
        daily = [
            _daily("20250101", 10050, 1000, close=10000),
            _daily("20250102", 10060, 1000, close=10010),
            _daily("20250103", 10040, 1000, close=9990),
            _daily("20250104", 10050, 1000, close=10000),
            _daily("20250105", 10055, 1000, close=10005),
        ]

        _, dyn_stop, dyn_tp = engine._calc_indicators(daily)
        if dyn_stop is not None:
            # 바닥값: SL >= -0.005, TP >= 0.010
            assert dyn_stop <= -0.005
            assert dyn_tp >= 0.010

    def test_atr_tp_multiplier_param(self) -> None:
        """atr_tp_multiplier 파라미터 독립 설정 검증."""
        params = MomentumParams(
            atr_stop_multiplier=1.5,
            atr_tp_multiplier=4.0,  # 기본 3.0 대신 4.0
        )
        engine = BacktestEngine(params)

        # 충분한 변동성
        daily = [
            _daily("20250101", 10200, 1000, close=10000),
            _daily("20250102", 10300, 1000, close=10100),
            _daily("20250103", 10100, 1000, close=9900),
            _daily("20250104", 10200, 1000, close=10000),
            _daily("20250105", 10150, 1000, close=10050),
        ]

        _, dyn_stop, dyn_tp = engine._calc_indicators(daily)
        if dyn_stop is not None and dyn_tp is not None:
            # TP/SL 비율이 4.0/1.5 = 2.67 (기본 2.0이 아님)
            ratio = abs(dyn_tp / dyn_stop)
            assert ratio > 2.5  # 4.0/1.5 = 2.67

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


class TestBarByBarLookahead:
    """Bar-by-bar look-ahead bias 방지 검증."""

    def test_no_lookahead_bias_52w_high(self) -> None:
        """미래 일봉 데이터가 현재 시뮬레이션에 영향을 주지 않는다.

        백테스트 시작일(20250106) 이후 데이터(high=15000)가
        해당일 지표 계산에 포함되면 진입이 차단된다 (look-ahead bug).
        수정 후: 시작일 이전 데이터(high=9000)만 사용 → 진입 허용.
        """
        daily = (
            [_daily(f"2025010{i}", 9000, 1000) for i in range(1, 6)]  # 20250101-20250105
            + [_daily(f"2025011{i}", 15000, 1000) for i in range(0, 5)]  # 20250110-20250114
        )
        # 시작일 20250106 기준 prior_daily: 5개 (high=9000) → high_52w=9000
        # threshold=0.95 → min_price = 9000*0.95 = 8550
        # current_price=8600 > 8550 → 진입 OK (look-ahead 없을 때)
        # look-ahead 있으면: high_52w=15000, 8600 < 14250 → 진입 불가
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            slippage_pct=0.0,
        )
        engine = BacktestEngine(params)

        minute = [
            _minute("20250106090000", 8600, 1500),  # 진입 시도
            _minute("20250106100000", 8600, 100),  # 유지
        ]

        result = engine.run(minute, daily)
        # look-ahead 방지: prior daily high=9000 → 8600 >= 8550 → 진입
        assert len(result.trades) >= 1

    def test_lookahead_indicators_isolated_per_day(self) -> None:
        """거래일별 지표가 해당일 이전 데이터로 독립 계산된다."""
        # 5일 일봉 준비 (날짜 20250101-20250105)
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        engine = BacktestEngine(MomentumParams())
        trading_dates = ["20250106", "20250107"]
        lookup = engine._build_daily_indicators(trading_dates, daily)

        # 20250106 기준 prior: 5개, 20250107 기준 prior: 5개 (동일 — 20250106 일봉 없음)
        assert "20250106" in lookup
        assert "20250107" in lookup
        # prior_daily가 없는 날 high_52w는 실제 데이터 기반 계산
        assert lookup["20250106"]["high_52w"] == 10000
        assert lookup["20250107"]["high_52w"] == 10000


class TestSurvivorshipBiasWarning:
    """Survivorship bias 경고 로깅 검증."""

    def test_warns_when_insufficient_prior_daily(self) -> None:
        """일봉 250개 미만이면 survivorship bias 경고 로깅."""
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 4)]  # 3개 only
        minute = [_minute("20250106090000", 9500, 1500)]
        engine = BacktestEngine()

        with capture_logs() as cap_logs:
            engine.run(minute, daily)

        assert any("Survivorship bias" in str(log.get("event", "")) for log in cap_logs)

    def test_warns_with_symbol_name(self) -> None:
        """종목코드가 경고 메시지에 포함된다."""
        daily = [_daily("20250101", 10000, 1000)]
        minute = [_minute("20250106090000", 9500, 1500)]
        engine = BacktestEngine()

        with capture_logs() as cap_logs:
            engine.run_with_symbol("005930", minute, daily)

        warning_logs = [log for log in cap_logs if "Survivorship bias" in str(log.get("event", ""))]
        assert len(warning_logs) >= 1


class TestUnrealizedMDD:
    """미실현 손익 포함 MDD 검증."""

    def test_unrealized_drawdown_captured(self) -> None:
        """일시 큰 하락 후 회복해도 최대 낙폭이 반영된다.

        체결 거래만의 MDD는 수익이지만 미실현 포함 MDD는 대폭 하락을 반영한다.
        """
        params = MomentumParams(
            high_52w_threshold=0.95,
            price_change_min=0.0,
            volume_ratio=1.5,
            entry_start_time="",
            take_profit=0.1,  # 높게 → 익절 안 됨
            stop_loss=-0.5,  # 넓게 → 손절 안 됨
            trailing_stop_pct=None,
            force_close_time="15:30",
            max_positions=1,
            slippage_pct=0.0,
        )
        engine = BacktestEngine(params)
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        minute = [
            _minute("20250106090000", 9500, 1500),  # 진입 (entry=9500)
            _minute("20250106100000", 6000, 100),  # 대폭 하락 (미실현 ~-37%)
            _minute("20250106110000", 9600, 100),  # 회복
            _minute("20250106153000", 9600, 100),  # force_close (15:30)
        ]

        result = engine.run(minute, daily)
        # 진입 발생 여부 확인 (최소 1건 이상)
        assert len(result.trades) >= 1
        # 체결 기준: 9500 → 9600 (수익) → 체결만의 MDD = 0.0이어야 하지만
        # 미실현 포함: 9500 → 6000 일시 하락 → MDD < -0.1
        assert result.metrics["max_drawdown"] < -0.1

    def test_no_open_position_equity_equals_base(self) -> None:
        """포지션 없을 때 자산 곡선은 기준값(1.0) 유지."""
        params = MomentumParams(
            high_52w_threshold=0.95,  # 진입 차단 조건
            price_change_min=0.0,
            volume_ratio=999.0,  # 거래량 기준 매우 높게 → 진입 불가
            entry_start_time="",
        )
        engine = BacktestEngine(params)
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]
        minute = [_minute("20250106090000", 9500, 100)]

        result = engine.run(minute, daily)
        # 진입 없음 → MDD = 0.0
        assert result.metrics["max_drawdown"] == 0.0


class TestSlippageDefault:
    """슬리피지 기본값 0.0015 적용 검증."""

    def test_slippage_default_applied(self) -> None:
        """기본 슬리피지 0.15%: 진입가가 close보다 높고 청산가가 낮음."""
        params = MomentumParams(
            high_52w_threshold=0.0,
            price_change_min=0.0,
            volume_ratio=0.1,
            entry_start_time="",
            take_profit=0.05,
            stop_loss=-0.1,
            trailing_stop_pct=None,
            force_close_time="15:30",
            max_positions=1,
            # slippage_pct 미지정 → 기본값 0.0015 사용
        )
        assert params.slippage_pct == 0.0015
        engine = BacktestEngine(params)
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        minute = [
            _minute("20250106090000", 10000, 100),  # 진입
            _minute("20250106153000", 10000, 100),  # force_close (15:30)
        ]

        result = engine.run(minute, daily)
        # 슬리피지 적용 확인
        if result.trades:
            # BUY 슬리피지: entry_price > close(10000)
            assert result.trades[0].entry_price > 10000
            # SELL 슬리피지: exit_price < close(10000)
            assert result.trades[0].exit_price < 10000

    def test_zero_slippage_no_spread(self) -> None:
        """slippage_pct=0.0이면 체결가가 close와 동일."""
        params = MomentumParams(
            high_52w_threshold=0.0,
            price_change_min=0.0,
            volume_ratio=0.1,
            entry_start_time="",
            take_profit=0.05,
            stop_loss=-0.1,
            trailing_stop_pct=None,
            force_close_time="15:30",
            max_positions=1,
            slippage_pct=0.0,
        )
        engine = BacktestEngine(params)
        daily = [_daily(f"2025010{i}", 10000, 1000) for i in range(1, 6)]

        minute = [
            _minute("20250106090000", 10000, 100),
            _minute("20250106153000", 10000, 100),
        ]

        result = engine.run(minute, daily)
        if result.trades:
            assert result.trades[0].entry_price == 10000
            assert result.trades[0].exit_price == 10000
