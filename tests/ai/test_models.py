"""AI 분석 모델 + AIConfig Pydantic 모델 검증 테스트."""

import pytest
from pydantic import ValidationError

from src.ai.analysis.models import AnalysisContext, TradingSignal
from src.ai.config import AIConfig


class TestTradingSignal:
    """TradingSignal 모델 검증 테스트."""

    def test_create_with_required_fields(self) -> None:
        """필수 필드만으로 생성."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.8,
        )
        assert signal.symbol == "005930"
        assert signal.action == "BUY"
        assert signal.confidence == 0.8

    def test_create_with_all_fields(self) -> None:
        """전체 필드 포함 생성."""
        signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.9,
            target_price=75000,
            position_size_pct=0.15,
            reasoning="기술적 분석 기반 매도 판단",
            risk_level="HIGH",
        )
        assert signal.target_price == 75000
        assert signal.position_size_pct == 0.15
        assert signal.reasoning == "기술적 분석 기반 매도 판단"
        assert signal.risk_level == "HIGH"

    def test_default_values(self) -> None:
        """선택 필드 기본값 검증."""
        signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=0.5,
        )
        assert signal.target_price is None
        assert signal.position_size_pct == 0.0
        assert signal.reasoning == ""
        assert signal.risk_level == "MEDIUM"

    def test_confidence_min_boundary(self) -> None:
        """confidence 최솟값(0.0) 허용."""
        signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=0.0,
        )
        assert signal.confidence == 0.0

    def test_confidence_max_boundary(self) -> None:
        """confidence 최댓값(1.0) 허용."""
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=1.0,
        )
        assert signal.confidence == 1.0

    def test_confidence_below_zero_raises(self) -> None:
        """confidence가 0 미만이면 ValidationError."""
        with pytest.raises(ValidationError):
            TradingSignal(
                symbol="005930",
                action="BUY",
                confidence=-0.1,
            )

    def test_confidence_above_one_raises(self) -> None:
        """confidence가 1 초과하면 ValidationError."""
        with pytest.raises(ValidationError):
            TradingSignal(
                symbol="005930",
                action="BUY",
                confidence=1.1,
            )

    def test_invalid_action_raises(self) -> None:
        """유효하지 않은 action 값이면 ValidationError."""
        with pytest.raises(ValidationError):
            TradingSignal(
                symbol="005930",
                action="INVALID",
                confidence=0.5,
            )

    def test_position_size_pct_out_of_range(self) -> None:
        """position_size_pct이 범위(0.0~1.0)를 벗어나면 ValidationError."""
        with pytest.raises(ValidationError):
            TradingSignal(
                symbol="005930",
                action="BUY",
                confidence=0.8,
                position_size_pct=1.5,
            )


class TestAnalysisContext:
    """AnalysisContext 모델 검증 테스트."""

    def test_create_with_symbol_only(self) -> None:
        """symbol만으로 생성 (나머지 기본값)."""
        ctx = AnalysisContext(symbol="005930")
        assert ctx.symbol == "005930"
        assert ctx.name == ""
        assert ctx.available_cash == 0
        assert ctx.current_holdings == []
        assert ctx.daily_pnl == 0

    def test_create_with_all_fields(self) -> None:
        """전체 필드 포함 생성."""
        ctx = AnalysisContext(
            symbol="005930",
            name="삼성전자",
            available_cash=5_000_000,
            current_holdings=[{"symbol": "005930", "qty": 10}],
            daily_pnl=50000,
        )
        assert ctx.name == "삼성전자"
        assert ctx.available_cash == 5_000_000
        assert len(ctx.current_holdings) == 1
        assert ctx.daily_pnl == 50000


class TestAIConfig:
    """AIConfig 모델 검증 테스트."""

    def test_default_values(self) -> None:
        """AIConfig 기본값 검증."""
        config = AIConfig()
        assert config.enable_auto_trading is False
        assert config.analysis_interval_minutes == 30
        assert config.buy_confidence_threshold == 0.7
        assert config.sell_confidence_threshold == 0.6
        assert config.max_position_pct == 30.0
        assert config.max_symbols == 10
        assert config.check_market_hours is True

    def test_custom_values(self) -> None:
        """커스텀 설정값 생성."""
        config = AIConfig(
            enable_auto_trading=True,
            analysis_interval_minutes=15,
            buy_confidence_threshold=0.8,
            sell_confidence_threshold=0.7,
            max_position_pct=20.0,
            max_symbols=5,
            check_market_hours=False,
        )
        assert config.enable_auto_trading is True
        assert config.analysis_interval_minutes == 15
        assert config.max_symbols == 5
