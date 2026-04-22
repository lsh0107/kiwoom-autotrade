"""live_trader Design 013 통합 테스트 (PR 7).

flag off 기본값 확인 + 헬퍼 함수 동작 검증.
기존 live_trader 회귀는 tests/test_live_trader.py에서 커버.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.live_trader import (
    _clamp,
    _compute_volume_ratio_override,
    _is_multi_regime_enabled,
    _load_market_style,
)
from src.trading.market_context import MarketContext
from src.trading.market_style import MarketStyle


class TestMultiRegimeFlag:
    def test_default_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USE_MULTI_REGIME", raising=False)
        assert _is_multi_regime_enabled() is False

    def test_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USE_MULTI_REGIME", "true")
        assert _is_multi_regime_enabled() is True

    @pytest.mark.parametrize("val", ["1", "yes", "True", "YES"])
    def test_enabled_various(self, monkeypatch: pytest.MonkeyPatch, val: str) -> None:
        monkeypatch.setenv("USE_MULTI_REGIME", val)
        assert _is_multi_regime_enabled() is True

    def test_disabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USE_MULTI_REGIME", "false")
        assert _is_multi_regime_enabled() is False

    def test_disabled_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USE_MULTI_REGIME", "")
        assert _is_multi_regime_enabled() is False


class TestClamp:
    def test_within_range(self) -> None:
        assert _clamp(1.0, 0.5, 1.5) == pytest.approx(1.0)

    def test_below_lo(self) -> None:
        assert _clamp(0.3, 0.5, 1.5) == pytest.approx(0.5)

    def test_above_hi(self) -> None:
        assert _clamp(2.0, 0.5, 1.5) == pytest.approx(1.5)

    def test_exact_boundaries(self) -> None:
        assert _clamp(0.5, 0.5, 1.5) == pytest.approx(0.5)
        assert _clamp(1.5, 0.5, 1.5) == pytest.approx(1.5)


class TestVolumeRatioOverride:
    def test_neutral_market(self) -> None:
        """market_value_ratio=1.0 → 임계치 변화 없음."""
        assert _compute_volume_ratio_override(0.5, 1.0) == pytest.approx(0.5)

    def test_quiet_market_relaxes(self) -> None:
        """market_value_ratio=0.6 → 임계치 완화."""
        result = _compute_volume_ratio_override(1.0, 0.6)
        assert result == pytest.approx(0.6)

    def test_clamp_extreme_low(self) -> None:
        """ratio=0.1 → clamp 0.5 적용."""
        result = _compute_volume_ratio_override(1.0, 0.1)
        assert result == pytest.approx(0.5)

    def test_clamp_extreme_high(self) -> None:
        """ratio=3.0 → clamp 1.5 적용."""
        result = _compute_volume_ratio_override(1.0, 3.0)
        assert result == pytest.approx(1.5)

    def test_custom_clamp_range(self) -> None:
        """사용자 clamp 범위 적용."""
        result = _compute_volume_ratio_override(1.0, 2.0, clamp_low=0.8, clamp_high=1.2)
        assert result == pytest.approx(1.2)


class TestLoadMarketStyle:
    def test_none_context_returns_none(self) -> None:
        assert _load_market_style(None) is None

    def test_non_marketcontext_returns_none(self) -> None:
        # MagicMock은 MarketContext 아님
        mock = MagicMock()
        assert _load_market_style(mock) is None

    def test_bull_strong_when_above_ma_high_volume(self) -> None:
        """above_ma12=True + ratio>=1.0 (내부 atr_pct=0.02로 RANGE 탈락)
        → TREND_BULL_STRONG or QUIET (ADX=None이므로 QUIET).
        """
        ctx = MarketContext()
        ctx._apply_kospi_regime({"above_ma12": True})
        ctx._apply_market_value(
            {
                "value_today": 10e12,
                "value_avg_5d": 10e12,
                "ratio": 1.0,
                "available": True,
            }
        )
        style = _load_market_style(ctx)
        # adx=None이므로 STRONG 불가 → QUIET
        assert style == MarketStyle.TREND_BULL_QUIET

    def test_bull_quiet_when_above_ma_low_volume(self) -> None:
        ctx = MarketContext()
        ctx._apply_kospi_regime({"above_ma12": True})
        ctx._apply_market_value(
            {
                "value_today": 5e12,
                "value_avg_5d": 10e12,
                "ratio": 0.5,
                "available": True,
            }
        )
        style = _load_market_style(ctx)
        assert style == MarketStyle.TREND_BULL_QUIET

    def test_bear_returns_chop_without_adx(self) -> None:
        """below MA + adx None → CHOP (bear 탈락)."""
        ctx = MarketContext()
        ctx._apply_kospi_regime({"above_ma12": False})
        style = _load_market_style(ctx)
        assert style == MarketStyle.CHOP
