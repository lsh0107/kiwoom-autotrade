"""Strategy Protocol 테스트."""

from src.backtest.strategy import MomentumParams
from src.broker.schemas import DailyPrice
from src.strategy.base import Strategy
from src.strategy.mean_reversion import MeanReversionStrategy
from src.strategy.momentum import MomentumStrategy


def _make_daily(close: int = 100) -> DailyPrice:
    return DailyPrice(
        date="20250101", open=close, high=close + 5, low=close - 5, close=close, volume=1000
    )


class TestStrategyProtocol:
    """Strategy Protocol 구조 테스트."""

    def test_momentum_implements_protocol(self) -> None:
        """MomentumStrategy가 Strategy Protocol을 구현한다."""
        strategy = MomentumStrategy()
        assert isinstance(strategy, Strategy)

    def test_mean_reversion_implements_protocol(self) -> None:
        """MeanReversionStrategy가 Strategy Protocol을 구현한다."""
        strategy = MeanReversionStrategy()
        assert isinstance(strategy, Strategy)

    def test_momentum_has_name(self) -> None:
        """MomentumStrategy.name 존재."""
        assert MomentumStrategy.name == "momentum"

    def test_mean_reversion_has_name(self) -> None:
        """MeanReversionStrategy.name 존재."""
        assert MeanReversionStrategy.name == "mean_reversion"

    def test_check_entry_returns_bool(self) -> None:
        """check_entry_signal은 bool 반환."""
        strategy = MomentumStrategy()
        daily = [_make_daily(100 + i) for i in range(30)]
        result = strategy.check_entry_signal(daily, current_price=110, current_volume=2000)
        assert isinstance(result, bool)

    def test_check_exit_returns_str_or_none(self) -> None:
        """check_exit_signal은 str 또는 None 반환."""
        strategy = MomentumStrategy()
        result = strategy.check_exit_signal(10000, 10100, 10200)
        assert result is None or isinstance(result, str)


class TestMomentumStrategy20DayAvg:
    """MomentumStrategy 20일 평균 거래량 테스트."""

    def _make_daily_with_volume(self, volume: int, high: int = 10000) -> DailyPrice:
        return DailyPrice(
            date="20250101", open=9000, high=high, low=8900, close=9500, volume=volume
        )

    def test_uses_recent_20_days_not_full_history(self) -> None:
        """전체 일봉이 아닌 최근 20일 평균 거래량을 사용한다.

        오래된 250일: 거래량 10000 (평균 높음)
        최근 20일: 거래량 1000 (평균 낮음)
        → 최근 20일 기준으로 current_volume=1500 > avg*1.5=1500 → 진입 가능
        → 전체 기준으로는 avg=9267 → 1500 < 9267*1.5 → 진입 불가
        """
        strategy = MomentumStrategy()

        # 오래된 250일: volume=10000 (높음)
        old_days = [self._make_daily_with_volume(10000, high=10000) for _ in range(250)]
        # 최근 20일: volume=1000 (낮음)
        recent_days = [self._make_daily_with_volume(1000, high=10000) for _ in range(20)]
        daily = old_days + recent_days

        # avg_volume (최근 20일) = 1000 → threshold = 1000 * 1.5 = 1500
        # current_volume=1500 → 1500 >= 1500 → True (최근 20일 기준)
        result = strategy.check_entry_signal(daily, current_price=10000, current_volume=1500)
        assert result is True

    def test_fewer_than_20_days_uses_all(self) -> None:
        """일봉이 20개 미만이면 전체 평균을 사용한다."""
        strategy = MomentumStrategy()

        # 5일치, volume=1000
        daily = [self._make_daily_with_volume(1000, high=10000) for _ in range(5)]
        # avg=1000 → threshold=1500
        result = strategy.check_entry_signal(daily, current_price=10000, current_volume=1500)
        assert result is True

    def test_time_ratio_scales_volume_threshold(self) -> None:
        """time_ratio=0.5이면 평균 거래량의 절반이 기준이 된다."""
        strategy = MomentumStrategy()
        daily = [self._make_daily_with_volume(1000, high=10000) for _ in range(20)]

        # time_ratio=0.5: avg_volume*0.5=500 → threshold=500*1.5=750
        # current_volume=800 >= 750 → True
        result = strategy.check_entry_signal(
            daily, current_price=10000, current_volume=800, time_ratio=0.5
        )
        assert result is True

    def test_time_ratio_default_no_entry_without_sufficient_volume(self) -> None:
        """time_ratio=1.0 (기본)에서 거래량 미달 시 False."""
        strategy = MomentumStrategy(params=MomentumParams(volume_ratio=1.5))
        daily = [self._make_daily_with_volume(1000, high=10000) for _ in range(20)]

        # avg=1000, volume_ratio=1.5 → threshold=1500, current=1400 → False
        result = strategy.check_entry_signal(daily, current_price=10000, current_volume=1400)
        assert result is False
