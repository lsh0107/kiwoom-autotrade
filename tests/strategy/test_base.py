"""Strategy Protocol 테스트."""

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
