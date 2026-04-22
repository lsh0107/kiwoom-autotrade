"""MarketStyle 판단 모듈 테스트."""

from __future__ import annotations

import pytest

from src.trading.market_style import MarketStyle, StyleConfig, detect_style


class TestDetectStyleRange:
    """RANGE 스타일 판단 테스트."""

    def test_range_within_band_and_low_atr(self) -> None:
        """KOSPI 이평 근처 + ATR% 낮음 → RANGE."""
        style = detect_style(
            kospi_close=2500.0,
            kospi_ma=2495.0,  # gap ~0.2%
            kospi_adx=30.0,  # ADX 높아도 band/atr 우선
            market_value_ratio=1.0,
            atr_pct=0.01,  # 1%
        )
        assert style == MarketStyle.RANGE

    def test_range_band_boundary_outside(self) -> None:
        """band 초과면 RANGE 아님."""
        style = detect_style(
            kospi_close=2550.0,
            kospi_ma=2500.0,  # gap 2%
            kospi_adx=30.0,
            market_value_ratio=1.2,
            atr_pct=0.01,
        )
        assert style != MarketStyle.RANGE

    def test_range_atr_too_high(self) -> None:
        """band 내여도 ATR% 높으면 RANGE 아님."""
        style = detect_style(
            kospi_close=2500.0,
            kospi_ma=2497.0,
            kospi_adx=30.0,
            market_value_ratio=1.2,
            atr_pct=0.03,  # 3%
        )
        assert style != MarketStyle.RANGE


class TestDetectStyleBull:
    """상승장 스타일 테스트."""

    def test_trend_bull_strong(self) -> None:
        """KOSPI > MA + ADX>25 + 거래대금 평균 이상 → TREND_BULL_STRONG."""
        style = detect_style(
            kospi_close=2600.0,
            kospi_ma=2500.0,
            kospi_adx=30.0,
            market_value_ratio=1.2,
            atr_pct=0.02,
        )
        assert style == MarketStyle.TREND_BULL_STRONG

    def test_trend_bull_quiet_low_volume(self) -> None:
        """KOSPI > MA + 거래대금 < 평균*0.7 → TREND_BULL_QUIET."""
        style = detect_style(
            kospi_close=2600.0,
            kospi_ma=2500.0,
            kospi_adx=30.0,
            market_value_ratio=0.5,
            atr_pct=0.02,
        )
        assert style == MarketStyle.TREND_BULL_QUIET

    def test_trend_bull_quiet_midrange_volume(self) -> None:
        """KOSPI > MA + 거래대금 중간대(0.7~1.0) → TREND_BULL_QUIET (보수적 기본)."""
        style = detect_style(
            kospi_close=2600.0,
            kospi_ma=2500.0,
            kospi_adx=30.0,
            market_value_ratio=0.85,
            atr_pct=0.02,
        )
        assert style == MarketStyle.TREND_BULL_QUIET

    def test_bull_without_adx_is_quiet(self) -> None:
        """ADX None + 거래대금 평균 미만 → TREND_BULL_QUIET."""
        style = detect_style(
            kospi_close=2600.0,
            kospi_ma=2500.0,
            kospi_adx=None,
            market_value_ratio=0.9,
            atr_pct=0.02,
        )
        assert style == MarketStyle.TREND_BULL_QUIET

    def test_bull_strong_requires_both_adx_and_volume(self) -> None:
        """ADX 높아도 거래대금 부족하면 STRONG 아님."""
        style = detect_style(
            kospi_close=2600.0,
            kospi_ma=2500.0,
            kospi_adx=30.0,
            market_value_ratio=0.8,
            atr_pct=0.02,
        )
        assert style != MarketStyle.TREND_BULL_STRONG


class TestDetectStyleBear:
    """하락장 스타일 테스트."""

    def test_trend_bear_with_strong_adx(self) -> None:
        """KOSPI < MA + ADX>25 → TREND_BEAR."""
        style = detect_style(
            kospi_close=2400.0,
            kospi_ma=2500.0,
            kospi_adx=30.0,
            market_value_ratio=1.0,
            atr_pct=0.02,
        )
        assert style == MarketStyle.TREND_BEAR

    def test_chop_bear_without_adx(self) -> None:
        """KOSPI < MA + ADX 약함 → CHOP."""
        style = detect_style(
            kospi_close=2400.0,
            kospi_ma=2500.0,
            kospi_adx=15.0,
            market_value_ratio=1.0,
            atr_pct=0.02,
        )
        assert style == MarketStyle.CHOP

    def test_chop_bear_adx_none(self) -> None:
        """KOSPI < MA + ADX None → CHOP."""
        style = detect_style(
            kospi_close=2400.0,
            kospi_ma=2500.0,
            kospi_adx=None,
            market_value_ratio=1.0,
            atr_pct=0.02,
        )
        assert style == MarketStyle.CHOP


class TestDetectStyleEdgeCases:
    """엣지 케이스."""

    def test_zero_ma_returns_chop(self) -> None:
        """ma=0 입력 이상 → 보수적 CHOP."""
        style = detect_style(
            kospi_close=2500.0,
            kospi_ma=0.0,
            kospi_adx=30.0,
            market_value_ratio=1.0,
            atr_pct=0.01,
        )
        assert style == MarketStyle.CHOP

    def test_exact_equal_close_and_ma_not_range(self) -> None:
        """kospi_close == kospi_ma인데 ATR 높음 → RANGE 아님, CHOP."""
        # gap=0 은 band 미만이지만 atr_pct가 range_atr_pct_max(0.015)보다 크면 RANGE 아님
        style = detect_style(
            kospi_close=2500.0,
            kospi_ma=2500.0,
            kospi_adx=10.0,
            market_value_ratio=1.0,
            atr_pct=0.05,  # 5% — high
        )
        assert style == MarketStyle.CHOP

    def test_custom_config_stricter_adx(self) -> None:
        """커스텀 config: adx_threshold 높이면 STRONG 조건 더 엄격."""
        cfg = StyleConfig(adx_trend_threshold=40.0)
        # ADX=30은 강한 추세로 분류 안 됨 → QUIET
        style = detect_style(
            kospi_close=2600.0,
            kospi_ma=2500.0,
            kospi_adx=30.0,
            market_value_ratio=1.5,
            atr_pct=0.02,
            config=cfg,
        )
        assert style == MarketStyle.TREND_BULL_QUIET


class TestMarketStyleEnum:
    """MarketStyle enum 정합성."""

    def test_enum_values_are_strings(self) -> None:
        assert isinstance(MarketStyle.RANGE.value, str)
        assert MarketStyle.RANGE.value == "range"

    @pytest.mark.parametrize(
        "style,expected",
        [
            (MarketStyle.TREND_BULL_STRONG, "trend_bull_strong"),
            (MarketStyle.TREND_BULL_QUIET, "trend_bull_quiet"),
            (MarketStyle.RANGE, "range"),
            (MarketStyle.TREND_BEAR, "trend_bear"),
            (MarketStyle.CHOP, "chop"),
        ],
    )
    def test_style_string_values(self, style: MarketStyle, expected: str) -> None:
        assert style.value == expected
