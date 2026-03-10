"""평균회귀 전략 테스트."""

from src.broker.schemas import DailyPrice
from src.strategy.mean_reversion import MeanReversionParams, MeanReversionStrategy


def _make_daily(
    close: int,
    high: int | None = None,
    low: int | None = None,
    volume: int = 1000,
) -> DailyPrice:
    """테스트용 DailyPrice 생성 헬퍼."""
    return DailyPrice(
        date="20250101",
        open=close,
        high=high if high is not None else close + 5,
        low=low if low is not None else close - 5,
        close=close,
        volume=volume,
    )


def _make_declining_daily(n: int = 30, start: int = 200) -> list[DailyPrice]:
    """RSI 과매도 유발 — 지속 하락 일봉 데이터."""
    return [_make_daily(start - i * 3) for i in range(n)]


class TestMeanReversionParams:
    """MeanReversionParams 기본값 테스트."""

    def test_default_values(self) -> None:
        """기본 파라미터 확인."""
        p = MeanReversionParams()
        assert p.rsi_period == 14
        assert p.rsi_oversold == 30.0
        assert p.rsi_overbought == 70.0
        assert p.bb_period == 20
        assert p.bb_std == 2.0
        assert p.volume_ratio == 1.2
        assert p.stop_loss == -0.03
        assert p.take_profit == 0.05
        assert p.max_positions == 3

    def test_custom_params(self) -> None:
        """커스텀 파라미터 설정."""
        p = MeanReversionParams(rsi_oversold=25.0, stop_loss=-0.05)
        assert p.rsi_oversold == 25.0
        assert p.stop_loss == -0.05


class TestMeanReversionCheckEntry:
    """check_entry_signal 테스트."""

    def test_insufficient_data_returns_false(self) -> None:
        """데이터 부족 시 False."""
        strategy = MeanReversionStrategy()
        daily = [_make_daily(100) for _ in range(5)]
        assert strategy.check_entry_signal(daily, 100, 2000) is False

    def test_no_signal_when_rsi_high(self) -> None:
        """RSI가 높으면(과매수) 진입 없음."""
        strategy = MeanReversionStrategy()
        # 계속 상승 → RSI 높음
        daily = [_make_daily(100 + i * 3, volume=1000) for i in range(30)]
        last_close = daily[-1].close
        # 볼린저밴드 하단보다 높은 현재가로 호출
        result = strategy.check_entry_signal(daily, last_close, 5000)
        assert result is False

    def test_entry_signal_all_conditions_met(self) -> None:
        """RSI 과매도 + 볼린저 하단 돌파 + 거래량 급증 → True."""
        strategy = MeanReversionStrategy()
        # 지속 하락으로 RSI 낮게
        daily = _make_declining_daily(n=30, start=200)
        last_close = daily[-1].close
        # 볼린저밴드 하단보다 더 낮은 가격, 거래량 급증
        avg_vol = 1000
        high_volume = int(avg_vol * 1.5)
        result = strategy.check_entry_signal(daily, last_close - 20, high_volume)
        assert result is True

    def test_no_signal_volume_insufficient(self) -> None:
        """거래량 기준 미달 시 False."""
        strategy = MeanReversionStrategy()
        daily = _make_declining_daily(n=30, start=200)
        last_close = daily[-1].close
        low_volume = 500  # 평균 1000의 0.5배 → 기준 1.2 미달
        result = strategy.check_entry_signal(daily, last_close - 20, low_volume)
        assert result is False

    def test_no_signal_price_above_lower_band(self) -> None:
        """현재가가 볼린저 하단 위이면 False."""
        strategy = MeanReversionStrategy()
        daily = _make_declining_daily(n=30, start=200)
        # 마지막 종가보다 훨씬 높은 가격
        high_price = daily[-1].close + 200
        high_volume = 2000
        result = strategy.check_entry_signal(daily, high_price, high_volume)
        assert result is False


class TestMeanReversionCheckExit:
    """check_exit_signal 테스트."""

    def test_stop_loss_triggered(self) -> None:
        """손절 -3% 발동."""
        strategy = MeanReversionStrategy()
        # 10000 → 9690 = -3.1%
        result = strategy.check_exit_signal(10000, 9690, 10000)
        assert result == "stop_loss"

    def test_take_profit_triggered(self) -> None:
        """익절 +5% 발동."""
        strategy = MeanReversionStrategy()
        # 10000 → 10510 = +5.1%
        result = strategy.check_exit_signal(10000, 10510, 10510)
        assert result == "take_profit"

    def test_no_exit_within_range(self) -> None:
        """범위 내에서는 None."""
        strategy = MeanReversionStrategy()
        result = strategy.check_exit_signal(10000, 10100, 10200)
        assert result is None

    def test_zero_entry_price_returns_none(self) -> None:
        """진입가 0이면 None."""
        strategy = MeanReversionStrategy()
        assert strategy.check_exit_signal(0, 10000, 10000) is None

    def test_negative_entry_price_returns_none(self) -> None:
        """음수 진입가이면 None."""
        strategy = MeanReversionStrategy()
        assert strategy.check_exit_signal(-100, 10000, 10000) is None

    def test_exact_stop_loss_boundary(self) -> None:
        """정확히 -3% 경계에서 손절 발동."""
        strategy = MeanReversionStrategy()
        # 10000 → 9700 = -3.0%
        result = strategy.check_exit_signal(10000, 9700, 9700)
        assert result == "stop_loss"

    def test_exact_take_profit_boundary(self) -> None:
        """정확히 +5% 경계에서 익절 발동."""
        strategy = MeanReversionStrategy()
        # 10000 → 10500 = +5.0%
        result = strategy.check_exit_signal(10000, 10500, 10500)
        assert result == "take_profit"

    def test_custom_params_stop_loss(self) -> None:
        """커스텀 손절 파라미터 반영."""
        params = MeanReversionParams(stop_loss=-0.05)
        strategy = MeanReversionStrategy(params)
        # -3%는 기본 손절이지만 커스텀 -5%이므로 None
        result = strategy.check_exit_signal(10000, 9700, 9700)
        assert result is None
        # -5.1%는 손절 발동
        result2 = strategy.check_exit_signal(10000, 9490, 9490)
        assert result2 == "stop_loss"


class TestMeanReversionStrategy:
    """MeanReversionStrategy 전체 흐름 테스트."""

    def test_default_params_on_init(self) -> None:
        """파라미터 없이 초기화 시 기본값 사용."""
        strategy = MeanReversionStrategy()
        assert strategy.params.rsi_period == 14

    def test_custom_params_on_init(self) -> None:
        """커스텀 파라미터 적용."""
        params = MeanReversionParams(rsi_oversold=25.0)
        strategy = MeanReversionStrategy(params)
        assert strategy.params.rsi_oversold == 25.0
