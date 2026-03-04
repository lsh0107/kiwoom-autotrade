"""시그널 검증 테스트."""

from src.ai.analysis.models import TradingSignal
from src.ai.signal.validator import validate_signal


class TestSignalValidator:
    """시그널 검증 테스트."""

    async def test_high_confidence_buy_passes(self) -> None:
        """높은 신뢰도 매수 통과."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.8,
            target_price=70000,
            position_size_pct=0.1,
            reasoning="테스트",
            risk_level="MEDIUM",
        )
        result = await validate_signal(signal, check_market_hours=False)
        assert result.passed

    async def test_low_confidence_buy_fails(self) -> None:
        """낮은 신뢰도 매수 차단."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.5,
            position_size_pct=0.1,
            reasoning="테스트",
        )
        result = await validate_signal(signal, check_market_hours=False)
        assert not result.passed
        assert "신뢰도" in result.reasons[0]

    async def test_sell_without_holding_fails(self) -> None:
        """미보유 종목 매도 차단."""
        signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.8,
            position_size_pct=0.1,
            reasoning="테스트",
        )
        result = await validate_signal(
            signal,
            current_holdings=["000660"],
            check_market_hours=False,
        )
        assert not result.passed
        assert "보유하지 않은" in result.reasons[0]

    async def test_hold_always_passes(self) -> None:
        """HOLD 신호는 항상 통과."""
        signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=0.3,
            reasoning="관망",
        )
        result = await validate_signal(signal, check_market_hours=False)
        assert result.passed

    async def test_high_risk_buy_needs_high_confidence(self) -> None:
        """고위험 매수는 높은 신뢰도 필요."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.75,
            position_size_pct=0.1,
            reasoning="테스트",
            risk_level="HIGH",
        )
        result = await validate_signal(signal, check_market_hours=False)
        assert not result.passed

    async def test_position_size_limit(self) -> None:
        """포지션 비중 초과 차단."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.9,
            position_size_pct=0.5,  # 50% > 30%
            reasoning="테스트",
        )
        result = await validate_signal(
            signal,
            total_portfolio_value=10000000,
            max_position_pct=30.0,
            check_market_hours=False,
        )
        assert not result.passed
