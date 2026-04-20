"""AI 분석 모델 + AIConfig Pydantic 모델 검증 테스트.

Pydantic 생성/필드 boilerplate 는 parametrize 로 통합하고,
비즈니스 불변식(경계값, 유효성) 은 개별 테스트로 유지한다.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from src.ai.analysis.models import AnalysisContext, TradingSignal
from src.ai.config import AIConfig


class TestTradingSignal:
    """TradingSignal 모델 검증 테스트."""

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            # 필수 필드만: 선택 필드는 기본값.
            (
                {"symbol": "005930", "action": "BUY", "confidence": 0.8},
                {
                    "symbol": "005930",
                    "action": "BUY",
                    "confidence": 0.8,
                    "target_price": None,
                    "position_size_pct": 0.0,
                    "reasoning": "",
                    "risk_level": "MEDIUM",
                },
            ),
            # 전체 필드 지정.
            (
                {
                    "symbol": "005930",
                    "action": "SELL",
                    "confidence": 0.9,
                    "target_price": 75000,
                    "position_size_pct": 0.15,
                    "reasoning": "기술적 분석 기반 매도 판단",
                    "risk_level": "HIGH",
                },
                {
                    "symbol": "005930",
                    "action": "SELL",
                    "confidence": 0.9,
                    "target_price": 75000,
                    "position_size_pct": 0.15,
                    "reasoning": "기술적 분석 기반 매도 판단",
                    "risk_level": "HIGH",
                },
            ),
            # HOLD + 선택 필드 기본값 전체 확인.
            (
                {"symbol": "005930", "action": "HOLD", "confidence": 0.5},
                {
                    "action": "HOLD",
                    "target_price": None,
                    "position_size_pct": 0.0,
                    "reasoning": "",
                    "risk_level": "MEDIUM",
                },
            ),
        ],
        ids=["required-only", "all-fields", "hold-defaults"],
    )
    def test_create_and_field_values(
        self, kwargs: dict[str, Any], expected: dict[str, Any]
    ) -> None:
        """생성 후 필드 값이 기대와 일치한다."""
        signal = TradingSignal(**kwargs)
        for k, v in expected.items():
            assert getattr(signal, k) == v

    @pytest.mark.parametrize(
        "confidence",
        [0.0, 1.0],
        ids=["min-boundary", "max-boundary"],
    )
    def test_confidence_boundary_allowed(self, confidence: float) -> None:
        """confidence 0.0/1.0 경계값은 허용된다."""
        signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=confidence,
        )
        assert signal.confidence == confidence

    @pytest.mark.parametrize(
        "invalid_kwargs",
        [
            # confidence 범위 이탈.
            {"symbol": "005930", "action": "BUY", "confidence": -0.1},
            {"symbol": "005930", "action": "BUY", "confidence": 1.1},
            # 유효하지 않은 action.
            {"symbol": "005930", "action": "INVALID", "confidence": 0.5},
            # position_size_pct 범위 이탈.
            {
                "symbol": "005930",
                "action": "BUY",
                "confidence": 0.8,
                "position_size_pct": 1.5,
            },
        ],
        ids=[
            "confidence-below-zero",
            "confidence-above-one",
            "invalid-action",
            "position-size-out-of-range",
        ],
    )
    def test_validation_errors(self, invalid_kwargs: dict[str, Any]) -> None:
        """유효하지 않은 입력은 ValidationError 를 발생시킨다."""
        with pytest.raises(ValidationError):
            TradingSignal(**invalid_kwargs)


class TestAnalysisContext:
    """AnalysisContext 모델 검증 테스트."""

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            # symbol 만 지정 — 나머지 기본값.
            (
                {"symbol": "005930"},
                {
                    "symbol": "005930",
                    "name": "",
                    "available_cash": 0,
                    "current_holdings": [],
                    "daily_pnl": 0,
                },
            ),
            # 전체 필드 지정.
            (
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "available_cash": 5_000_000,
                    "current_holdings": [{"symbol": "005930", "qty": 10}],
                    "daily_pnl": 50000,
                },
                {
                    "name": "삼성전자",
                    "available_cash": 5_000_000,
                    "current_holdings": [{"symbol": "005930", "qty": 10}],
                    "daily_pnl": 50000,
                },
            ),
        ],
        ids=["symbol-only", "all-fields"],
    )
    def test_create_and_field_values(
        self, kwargs: dict[str, Any], expected: dict[str, Any]
    ) -> None:
        """생성 후 필드 값이 기대와 일치한다."""
        ctx = AnalysisContext(**kwargs)
        for k, v in expected.items():
            assert getattr(ctx, k) == v


class TestAIConfig:
    """AIConfig 모델 검증 테스트."""

    def test_default_values(self) -> None:
        """AIConfig 기본값 검증 (비즈니스 기본값 불변식)."""
        config = AIConfig()
        assert config.enable_auto_trading is False
        assert config.analysis_interval_minutes == 30
        assert config.buy_confidence_threshold == 0.7
        assert config.sell_confidence_threshold == 0.6
        assert config.max_position_pct == 30.0
        assert config.max_symbols == 10
        assert config.check_market_hours is True

    def test_custom_values(self) -> None:
        """커스텀 설정값이 그대로 반영된다."""
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
