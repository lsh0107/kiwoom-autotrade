"""live_trader Design 013 통합 테스트 (PR 7 + PR9).

PR7: flag off 기본값 확인 + 헬퍼 함수 동작 검증.
PR9: _assign_symbol_strategies 가중치 분배 + build_strategies Pullback/Range 추가
     + DEFENSIVE/CRISIS 차단 확장.
기존 live_trader 회귀는 tests/test_live_trader.py에서 커버.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.live_trader import (
    _assign_symbol_strategies,
    _clamp,
    _compute_volume_ratio_override,
    _distribute_strategies,
    _load_market_style,
    _log_strategy_distribution,
    build_strategies,
)
from src.broker.schemas import DailyPrice
from src.config.active_strategy import ActiveStrategy, get_active_strategy
from src.trading.market_context import MarketContext
from src.trading.market_regime import MarketRegime
from src.trading.market_style import MarketStyle

# ── 픽스처 헬퍼 ──────────────────────────────────────


def _daily(close: int, volume: int = 1000, *, high: int = 0, low: int = 0) -> DailyPrice:
    """단순 일봉 생성."""
    hi = high or close + 50
    lo = low or max(1, close - 50)
    return DailyPrice(date="20260101", open=close, high=hi, low=lo, close=close, volume=volume)


def _make_momentum_daily(n: int = 30) -> list[DailyPrice]:
    """ATR% 높고 ADX 높은 (classify_volatility → MOMENTUM) 일봉."""
    out: list[DailyPrice] = []
    price = 10000
    for i in range(n):
        out.append(
            DailyPrice(
                date=f"2026{i:04d}",
                open=price,
                high=price + 500,  # 변동폭 5% — high ATR
                low=price - 500,
                close=price + 200,
                volume=100_000,
            )
        )
        price += 200
    return out


def _make_mean_reversion_daily(n: int = 30) -> list[DailyPrice]:
    """변동폭 최소 (classify_volatility → MEAN_REVERSION) 일봉."""
    out: list[DailyPrice] = []
    price = 10000
    for _ in range(n):
        out.append(
            DailyPrice(
                date="20260101",
                open=price,
                high=price + 1,  # 변동폭 <0.1% — very low ATR
                low=price - 1,
                close=price,
                volume=500,
            )
        )
    return out


# ── PR7: flag / 헬퍼 함수 테스트 (기존 유지) ──────────────────────────────


class TestMultiRegimeFlag:
    """ADR-024: ACTIVE_STRATEGY enum 기반 multi_regime 활성 판정."""

    def test_default_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ACTIVE_STRATEGY", raising=False)
        assert get_active_strategy() != ActiveStrategy.MULTI_REGIME

    def test_enabled_multi_regime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        assert get_active_strategy() == ActiveStrategy.MULTI_REGIME

    def test_cross_momentum_disables_multi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        assert get_active_strategy() != ActiveStrategy.MULTI_REGIME

    def test_none_disables_multi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "none")
        assert get_active_strategy() != ActiveStrategy.MULTI_REGIME

    def test_invalid_value_falls_back_to_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "garbage")
        assert get_active_strategy() == ActiveStrategy.NONE


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


# ── PR9: _distribute_strategies 단위 테스트 ─────────────────────────────────


class TestDistributeStrategies:
    def test_single_strategy_all_assigned(self) -> None:
        """단일 전략이면 전체 종목이 해당 전략으로."""
        syms = ["A", "B", "C"]
        out: dict[str, str] = {}
        _distribute_strategies(syms, {"momentum": 1.0}, out)
        assert out == {"A": "momentum", "B": "momentum", "C": "momentum"}

    def test_two_strategies_proportional(self) -> None:
        """momentum 70%, pullback 30% → 7:3 분배."""
        syms = [f"S{i:02d}" for i in range(10)]
        out: dict[str, str] = {}
        _distribute_strategies(syms, {"momentum": 0.70, "pullback": 0.30}, out)
        assert len(out) == 10
        mom = sum(1 for v in out.values() if v == "momentum")
        pb = sum(1 for v in out.values() if v == "pullback")
        assert mom == 7
        assert pb == 3

    def test_all_symbols_assigned(self) -> None:
        """가중치 불균등해도 전체 종목이 할당된다."""
        syms = ["X", "Y", "Z", "W", "V"]
        out: dict[str, str] = {}
        _distribute_strategies(
            syms, {"pullback": 0.50, "mean_reversion": 0.30, "momentum": 0.20}, out
        )
        assert len(out) == 5
        assert set(out.keys()) == set(syms)

    def test_empty_syms_no_error(self) -> None:
        """빈 종목 리스트 — 오류 없음."""
        out: dict[str, str] = {}
        _distribute_strategies([], {"momentum": 1.0}, out)
        assert out == {}

    def test_empty_weights_no_error(self) -> None:
        """빈 가중치 — 오류 없음."""
        out: dict[str, str] = {}
        _distribute_strategies(["A", "B"], {}, out)
        assert out == {}

    def test_deterministic_sorted_order(self) -> None:
        """같은 입력 → 항상 동일한 분배 결과."""
        syms = ["C", "A", "B"]
        out1: dict[str, str] = {}
        out2: dict[str, str] = {}
        _distribute_strategies(syms, {"momentum": 0.7, "pullback": 0.3}, out1)
        _distribute_strategies(syms, {"momentum": 0.7, "pullback": 0.3}, out2)
        assert out1 == out2

    def test_last_strategy_gets_remainder(self) -> None:
        """round() 반올림 오차로 나머지 종목이 마지막 전략에 배정."""
        syms = [f"S{i}" for i in range(7)]  # 7종목
        out: dict[str, str] = {}
        # momentum 70% = round(7*0.7) = 5, pullback 나머지 = 2
        _distribute_strategies(syms, {"momentum": 0.70, "pullback": 0.30}, out)
        assert len(out) == 7
        assert sum(1 for v in out.values() if v == "momentum") == 5
        assert sum(1 for v in out.values() if v == "pullback") == 2


# ── PR9: _assign_symbol_strategies 단위 테스트 ──────────────────────────────


class TestAssignSymbolStrategies:
    """_assign_symbol_strategies 동작 검증."""

    def test_flag_off_momentum_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag off → classify_volatility 기반 기존 동작 (모멘텀 기본값)."""
        monkeypatch.delenv("ACTIVE_STRATEGY", raising=False)
        daily = _make_momentum_daily()
        result = _assign_symbol_strategies({"A": daily}, market_style=None)
        assert result["A"] == "momentum"

    def test_flag_off_mean_reversion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag off → 저변동 종목은 mean_reversion."""
        monkeypatch.delenv("ACTIVE_STRATEGY", raising=False)
        daily = _make_mean_reversion_daily()
        result = _assign_symbol_strategies({"A": daily}, market_style=None)
        assert result["A"] == "mean_reversion"

    def test_flag_on_market_style_none_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag on + market_style=None → 기존 동작 폴백."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        daily = _make_momentum_daily()
        result = _assign_symbol_strategies({"A": daily}, market_style=None)
        assert result["A"] == "momentum"

    def test_flag_on_trend_bull_strong_splits_momentum_pullback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TREND_BULL_STRONG (momentum 70%, pullback 30%) → 고변동 종목 7:3 분배."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        # 10개 고변동 종목 (MOMENTUM volatility class)
        daily_map = {f"M{i:02d}": _make_momentum_daily() for i in range(10)}
        result = _assign_symbol_strategies(daily_map, market_style=MarketStyle.TREND_BULL_STRONG)
        mom = sum(1 for v in result.values() if v == "momentum")
        pb = sum(1 for v in result.values() if v == "pullback")
        assert mom == 7
        assert pb == 3

    def test_flag_on_range_assigns_range_trade(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RANGE (range_trade 60%, mean_reversion 40%) → 저변동 종목에 range_trade 배정."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        # 10개 저변동 종목 (MEAN_REVERSION volatility class)
        daily_map = {f"R{i:02d}": _make_mean_reversion_daily() for i in range(10)}
        result = _assign_symbol_strategies(daily_map, market_style=MarketStyle.RANGE)
        rt = sum(1 for v in result.values() if v == "range_trade")
        mr = sum(1 for v in result.values() if v == "mean_reversion")
        assert rt == 6
        assert mr == 4

    def test_flag_on_chop_no_high_vol_strategy_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CHOP (mean_reversion only) → 고변동 종목은 momentum 폴백."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        daily_map = {"M": _make_momentum_daily()}
        result = _assign_symbol_strategies(daily_map, market_style=MarketStyle.CHOP)
        assert result["M"] == "momentum"

    def test_flag_on_mixed_volatility_correct_pools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """혼합 변동성 — 고변동은 momentum/pullback, 저변동은 range_trade로."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        # TREND_BULL_QUIET: pullback 50%, mean_reversion 30%, momentum 20%
        daily_map = {
            "HIGH1": _make_momentum_daily(),
            "HIGH2": _make_momentum_daily(),
            "LOW1": _make_mean_reversion_daily(),
            "LOW2": _make_mean_reversion_daily(),
        }
        result = _assign_symbol_strategies(daily_map, market_style=MarketStyle.TREND_BULL_QUIET)
        # 고변동(HIGH1, HIGH2) → pullback(50%) or momentum(20%) — HIGH_VOL_STRATEGIES
        assert result["HIGH1"] in ("momentum", "pullback")
        assert result["HIGH2"] in ("momentum", "pullback")
        # 저변동(LOW1, LOW2) → mean_reversion(30%) — LOW_VOL_STRATEGIES
        assert result["LOW1"] == "mean_reversion"
        assert result["LOW2"] == "mean_reversion"

    def test_all_symbols_assigned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """멀티레짐 활성 시 전체 종목이 빠짐없이 할당된다."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")
        daily_map = {
            "A": _make_momentum_daily(),
            "B": _make_mean_reversion_daily(),
            "C": _make_momentum_daily(),
        }
        result = _assign_symbol_strategies(daily_map, market_style=MarketStyle.TREND_BULL_STRONG)
        assert set(result.keys()) == {"A", "B", "C"}
        assert all(
            v in ("momentum", "pullback", "mean_reversion", "range_trade") for v in result.values()
        )


# ── PR9: build_strategies Pullback/Range 포함 테스트 ─────────────────────────


class TestBuildStrategiesMultiRegime:
    def test_flag_off_no_pullback_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """include_multi_regime=False → PullbackStrategy / RangeStrategy 없음."""
        from src.backtest.strategy import MomentumParams

        monkeypatch.delenv("ACTIVE_STRATEGY", raising=False)
        strategies = build_strategies("both", MomentumParams(), include_multi_regime=False)
        names = {s.name for s in strategies}
        assert "pullback" not in names
        assert "range_trade" not in names

    def test_flag_on_includes_pullback_and_range(self) -> None:
        """include_multi_regime=True → PullbackStrategy / RangeStrategy 포함."""
        from src.backtest.strategy import MomentumParams

        strategies = build_strategies("both", MomentumParams(), include_multi_regime=True)
        names = {s.name for s in strategies}
        assert "pullback" in names
        assert "range_trade" in names

    def test_four_strategies_when_both_and_multi_regime(self) -> None:
        """both + multi_regime → 4개 전략 인스턴스."""
        from src.backtest.strategy import MomentumParams

        strategies = build_strategies("both", MomentumParams(), include_multi_regime=True)
        assert len(strategies) == 4
        names = {s.name for s in strategies}
        assert names == {"momentum", "mean_reversion", "pullback", "range_trade"}

    def test_momentum_only_with_multi_regime(self) -> None:
        """momentum + multi_regime → 3개 (momentum + pullback + range_trade)."""
        from src.backtest.strategy import MomentumParams

        strategies = build_strategies("momentum", MomentumParams(), include_multi_regime=True)
        names = {s.name for s in strategies}
        assert "momentum" in names
        assert "pullback" in names
        assert "range_trade" in names
        assert "mean_reversion" not in names


# ── PR9: DEFENSIVE/CRISIS 차단 확장 (단위 테스트) ───────────────────────────


class TestDefensiveCrisisBlock:
    """DEFENSIVE/CRISIS 레짐에서 전략별 차단 로직 검증.

    실제 trading loop 호출 없이, 차단 판정 조건만 직접 테스트한다.
    """

    _BLOCKED_IN_DEFENSIVE = ("momentum", "pullback", "range_trade")
    _ALLOWED_IN_DEFENSIVE = ("mean_reversion",)

    def _is_blocked(self, strat_name: str, regime: MarketRegime) -> bool:
        """DEFENSIVE/CRISIS 차단 조건 (live_trader 로직과 동일)."""
        return strat_name in ("momentum", "pullback", "range_trade") and regime in (
            MarketRegime.DEFENSIVE,
            MarketRegime.CRISIS,
        )

    @pytest.mark.parametrize("strat_name", ["momentum", "pullback", "range_trade"])
    def test_defensive_blocks_aggressive_strategies(self, strat_name: str) -> None:
        """DEFENSIVE → momentum/pullback/range_trade 모두 차단."""
        assert self._is_blocked(strat_name, MarketRegime.DEFENSIVE) is True

    @pytest.mark.parametrize("strat_name", ["momentum", "pullback", "range_trade"])
    def test_crisis_blocks_aggressive_strategies(self, strat_name: str) -> None:
        """CRISIS → momentum/pullback/range_trade 모두 차단."""
        assert self._is_blocked(strat_name, MarketRegime.CRISIS) is True

    def test_defensive_allows_mean_reversion(self) -> None:
        """DEFENSIVE → mean_reversion 허용."""
        assert self._is_blocked("mean_reversion", MarketRegime.DEFENSIVE) is False

    def test_crisis_allows_mean_reversion(self) -> None:
        """CRISIS → mean_reversion 허용."""
        assert self._is_blocked("mean_reversion", MarketRegime.CRISIS) is False

    @pytest.mark.parametrize(
        "strat_name", ["momentum", "pullback", "range_trade", "mean_reversion"]
    )
    def test_neutral_blocks_nothing(self, strat_name: str) -> None:
        """NEUTRAL → 어떤 전략도 차단 안 함."""
        assert self._is_blocked(strat_name, MarketRegime.NEUTRAL) is False

    @pytest.mark.parametrize(
        "strat_name", ["momentum", "pullback", "range_trade", "mean_reversion"]
    )
    def test_aggressive_blocks_nothing(self, strat_name: str) -> None:
        """AGGRESSIVE → 어떤 전략도 차단 안 함."""
        assert self._is_blocked(strat_name, MarketRegime.AGGRESSIVE) is False


# ── PR9: _log_strategy_distribution 단위 테스트 ─────────────────────────────


class TestLogStrategyDistribution:
    def test_no_error_on_empty(self) -> None:
        """빈 맵 — 오류 없이 실행."""
        _log_strategy_distribution({})

    def test_no_error_on_populated(self) -> None:
        """다양한 전략 맵 — 오류 없이 실행."""
        strategies = {
            "A": "momentum",
            "B": "pullback",
            "C": "range_trade",
            "D": "mean_reversion",
        }
        _log_strategy_distribution(strategies)

    def test_log_called_for_pullback(self, caplog: pytest.LogCaptureFixture) -> None:
        """pullback 있을 때 'pullback 종목 N개' 로그 출력."""
        import logging

        with caplog.at_level(logging.INFO, logger="live_trader"):
            _log_strategy_distribution({"A": "pullback", "B": "pullback"})
        assert any("pullback 종목 2개" in m for m in caplog.messages)

    def test_log_called_for_range(self, caplog: pytest.LogCaptureFixture) -> None:
        """range_trade 있을 때 'range 종목 N개' 로그 출력."""
        import logging

        with caplog.at_level(logging.INFO, logger="live_trader"):
            _log_strategy_distribution({"X": "range_trade"})
        assert any("range 종목 1개" in m for m in caplog.messages)
