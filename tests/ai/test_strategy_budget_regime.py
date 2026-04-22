"""StrategyBudget.apply_regime style 확장 테스트 (Design 013 PR 6)."""

from __future__ import annotations

import pytest

from src.ai.signal.position_sizer import StrategyBudget
from src.trading.market_regime import MarketRegime
from src.trading.market_style import MarketStyle


class TestApplyRegimeBackwardsCompat:
    """style=None (기본) → 기존 동작."""

    def test_aggressive_default(self) -> None:
        budget = StrategyBudget()
        budget.apply_regime(MarketRegime.AGGRESSIVE, total_capital=10_000_000)
        assert budget.allocations["momentum"] == pytest.approx(0.55)
        assert budget.allocations["mean_reversion"] == pytest.approx(0.30)

    def test_neutral_default(self) -> None:
        budget = StrategyBudget()
        budget.apply_regime(MarketRegime.NEUTRAL, total_capital=10_000_000)
        assert budget.allocations["momentum"] == pytest.approx(0.40)
        assert budget.allocations["mean_reversion"] == pytest.approx(0.40)

    def test_crisis_zeroed(self) -> None:
        budget = StrategyBudget()
        budget.apply_regime(MarketRegime.CRISIS, total_capital=10_000_000)
        assert budget.allocations["momentum"] == pytest.approx(0.0)
        assert budget.allocations["mean_reversion"] == pytest.approx(0.0)

    def test_invalid_style_type_falls_back(self) -> None:
        """잘못된 style 타입 → 기존 동작 폴백."""
        budget = StrategyBudget()
        budget.apply_regime(MarketRegime.AGGRESSIVE, total_capital=10_000_000, style="invalid")
        # 폴백: 기존 동작
        assert budget.allocations["momentum"] == pytest.approx(0.55)
        assert budget.allocations["mean_reversion"] == pytest.approx(0.30)


class TestApplyRegimeWithStyle:
    """Design 013 — style 지정 시 가중치 분배."""

    def test_bull_strong_distributes_investable(self) -> None:
        """AGGRESSIVE + TREND_BULL_STRONG
        investable = pool_a+pool_b = 0.55+0.30 = 0.85
        weights momentum=0.70, pullback=0.30 → sum=1.0
        결과: momentum=0.85*0.70=0.595, pullback=0.85*0.30=0.255.
        """
        budget = StrategyBudget()
        budget.apply_regime(
            MarketRegime.AGGRESSIVE,
            total_capital=10_000_000,
            style=MarketStyle.TREND_BULL_STRONG,
        )
        assert budget.allocations["momentum"] == pytest.approx(0.85 * 0.70)
        assert budget.allocations["pullback"] == pytest.approx(0.85 * 0.30)
        assert budget.allocations["mean_reversion"] == pytest.approx(0.0)

    def test_range_allocates_range_trade(self) -> None:
        """NEUTRAL + RANGE: investable=0.80, range_trade=0.60, mean_reversion=0.40."""
        budget = StrategyBudget()
        budget.apply_regime(MarketRegime.NEUTRAL, total_capital=10_000_000, style=MarketStyle.RANGE)
        assert budget.allocations["range_trade"] == pytest.approx(0.80 * 0.60)
        assert budget.allocations["mean_reversion"] == pytest.approx(0.80 * 0.40)
        assert budget.allocations["momentum"] == pytest.approx(0.0)

    def test_chop_conservative_buffer(self) -> None:
        """DEFENSIVE + CHOP: investable=0.65, mean_reversion=0.30 → 0.195.
        나머지 합<1 이므로 현금 버퍼로 남음.
        """
        budget = StrategyBudget()
        budget.apply_regime(
            MarketRegime.DEFENSIVE, total_capital=10_000_000, style=MarketStyle.CHOP
        )
        assert budget.allocations["mean_reversion"] == pytest.approx(0.65 * 0.30)
        # 총 합 < investable
        assert sum(budget.allocations.values()) < 0.65

    def test_crisis_style_still_zero(self) -> None:
        """CRISIS + 어떤 style이든 investable=0 → 전부 0."""
        budget = StrategyBudget()
        budget.apply_regime(
            MarketRegime.CRISIS,
            total_capital=10_000_000,
            style=MarketStyle.TREND_BULL_STRONG,
        )
        assert budget.allocations["momentum"] == pytest.approx(0.0)
        assert budget.allocations.get("pullback", 0.0) == pytest.approx(0.0)

    def test_total_capital_set(self) -> None:
        budget = StrategyBudget()
        budget.apply_regime(
            MarketRegime.AGGRESSIVE,
            total_capital=5_000_000,
            style=MarketStyle.TREND_BULL_STRONG,
        )
        assert budget.total_balance == 5_000_000

    def test_budget_for_new_strategy_accessible(self) -> None:
        """신규 전략(pullback)도 budget_for로 조회 가능."""
        budget = StrategyBudget()
        budget.apply_regime(
            MarketRegime.AGGRESSIVE,
            total_capital=10_000_000,
            style=MarketStyle.TREND_BULL_STRONG,
        )
        # 0.85 * 0.30 = 0.255 → 2_550_000
        assert budget.budget_for("pullback") == int(10_000_000 * 0.85 * 0.30)

    def test_bull_quiet_distributes_three_strategies(self) -> None:
        """TREND_BULL_QUIET: pullback=0.5, mean_reversion=0.3, momentum=0.2."""
        budget = StrategyBudget()
        budget.apply_regime(
            MarketRegime.AGGRESSIVE,
            total_capital=10_000_000,
            style=MarketStyle.TREND_BULL_QUIET,
        )
        investable = 0.85  # aggressive pool_a+pool_b
        assert budget.allocations["pullback"] == pytest.approx(investable * 0.50)
        assert budget.allocations["mean_reversion"] == pytest.approx(investable * 0.30)
        assert budget.allocations["momentum"] == pytest.approx(investable * 0.20)
