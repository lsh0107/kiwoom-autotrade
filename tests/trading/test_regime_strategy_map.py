"""regime_strategy_map 매트릭스 테스트 (Design 013 PR 6)."""

from __future__ import annotations

import pytest

from src.trading.market_style import MarketStyle
from src.trading.regime_strategy_map import (
    REGIME_STRATEGY_WEIGHTS,
    get_strategy_weights,
    normalize_weights,
)


class TestRegimeStrategyWeights:
    """REGIME_STRATEGY_WEIGHTS 매트릭스 구조 검증."""

    def test_all_styles_have_entry(self) -> None:
        """모든 MarketStyle이 매트릭스에 존재."""
        for style in MarketStyle:
            assert style in REGIME_STRATEGY_WEIGHTS

    def test_weights_non_negative(self) -> None:
        """가중치 음수 없음."""
        for weights in REGIME_STRATEGY_WEIGHTS.values():
            for v in weights.values():
                assert v >= 0

    def test_bull_strong_focus_on_momentum(self) -> None:
        w = REGIME_STRATEGY_WEIGHTS[MarketStyle.TREND_BULL_STRONG]
        assert w["momentum"] == pytest.approx(0.70)
        assert w["pullback"] == pytest.approx(0.30)

    def test_bull_quiet_favors_pullback(self) -> None:
        w = REGIME_STRATEGY_WEIGHTS[MarketStyle.TREND_BULL_QUIET]
        assert w["pullback"] == pytest.approx(0.50)
        assert w["mean_reversion"] == pytest.approx(0.30)
        assert w["momentum"] == pytest.approx(0.20)

    def test_range_favors_range_trade(self) -> None:
        w = REGIME_STRATEGY_WEIGHTS[MarketStyle.RANGE]
        assert w["range_trade"] == pytest.approx(0.60)
        assert w["mean_reversion"] == pytest.approx(0.40)

    def test_bear_conservative_buffer(self) -> None:
        """TREND_BEAR는 합<1 (현금 보유)."""
        w = REGIME_STRATEGY_WEIGHTS[MarketStyle.TREND_BEAR]
        assert sum(w.values()) < 1.0

    def test_chop_most_conservative(self) -> None:
        """CHOP은 가장 보수적 — 합 0.3."""
        w = REGIME_STRATEGY_WEIGHTS[MarketStyle.CHOP]
        assert sum(w.values()) == pytest.approx(0.30)


class TestGetStrategyWeights:
    def test_returns_copy(self) -> None:
        """원본 매트릭스는 수정되지 않아야 함."""
        w = get_strategy_weights(MarketStyle.RANGE)
        w["range_trade"] = 999.0
        # 원본 불변
        assert REGIME_STRATEGY_WEIGHTS[MarketStyle.RANGE]["range_trade"] == pytest.approx(0.60)

    def test_all_styles_return_dict(self) -> None:
        for style in MarketStyle:
            assert isinstance(get_strategy_weights(style), dict)


class TestNormalizeWeights:
    def test_sum_under_one_unchanged(self) -> None:
        w = {"a": 0.3, "b": 0.4}
        result = normalize_weights(w)
        assert result == {"a": 0.3, "b": 0.4}

    def test_sum_exactly_one_unchanged(self) -> None:
        w = {"a": 0.5, "b": 0.5}
        assert normalize_weights(w) == {"a": 0.5, "b": 0.5}

    def test_sum_over_one_scaled(self) -> None:
        w = {"a": 0.8, "b": 0.8}  # 합 1.6
        result = normalize_weights(w)
        assert result["a"] == pytest.approx(0.5)
        assert result["b"] == pytest.approx(0.5)
        assert sum(result.values()) == pytest.approx(1.0)

    def test_empty_returns_empty(self) -> None:
        assert normalize_weights({}) == {}

    def test_all_zero_returns_empty(self) -> None:
        assert normalize_weights({"a": 0.0, "b": 0.0}) == {}
