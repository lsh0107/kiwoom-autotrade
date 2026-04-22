"""시장 스타일(Market Style) 4사분면 판단 모듈.

Design 013 — 다중 레짐 전략.
기존 MarketRegime(VKOSPI+KOSPI 이평 기반 리스크 레짐)과 직교하는 개념으로,
추세 방향 x 거래 활발도 축에서 스타일을 구분해 전략 매트릭스에 매핑한다.

스타일 분류:
- TREND_BULL_STRONG : KOSPI > MA + ADX>25 + 거래대금 ≥ 평균*1.0 (강한 추세장)
- TREND_BULL_QUIET  : KOSPI > MA + 거래대금 < 평균*0.7 (조용한 상승장 — pullback/MR 유리)
- RANGE             : |KOSPI-MA|/MA < 1% + ATR% 낮음 (박스권)
- TREND_BEAR        : KOSPI < MA + 추세 하락
- CHOP              : 위 외 변동성 크고 추세 약함 (관망)

주의:
- MarketRegime(AGGRESSIVE/NEUTRAL/DEFENSIVE/CRISIS)과 별개 축이다.
- 호환성 유지: detect_style은 USE_MULTI_REGIME flag 활성화 전까지 호출되지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarketStyle(StrEnum):
    """시장 스타일 4사분면 + CHOP 분류."""

    TREND_BULL_STRONG = "trend_bull_strong"
    TREND_BULL_QUIET = "trend_bull_quiet"
    RANGE = "range"
    TREND_BEAR = "trend_bear"
    CHOP = "chop"


@dataclass
class StyleConfig:
    """시장 스타일 판단 임계값 설정.

    Attributes:
        adx_trend_threshold: ADX 이상이면 추세 강함 (기본 25.0)
        range_band_pct: |KOSPI-MA|/MA 이 값 이하면 박스권 후보 (기본 0.01 = 1%)
        range_atr_pct_max: ATR% 이 값 이하이면 박스권 확정 (기본 0.015 = 1.5%)
        quiet_volume_ratio: 시장 거래대금 비율이 이 값 미만이면 '조용한' 장 (기본 0.7)
        strong_volume_ratio: 시장 거래대금 비율이 이 값 이상이면 '활발한' 장 (기본 1.0)
    """

    adx_trend_threshold: float = 25.0
    range_band_pct: float = 0.01
    range_atr_pct_max: float = 0.015
    quiet_volume_ratio: float = 0.7
    strong_volume_ratio: float = 1.0


def detect_style(
    kospi_close: float,
    kospi_ma: float,
    kospi_adx: float | None,
    market_value_ratio: float,
    atr_pct: float,
    config: StyleConfig | None = None,
) -> MarketStyle:
    """시장 스타일(4사분면 + CHOP)을 판단한다.

    Args:
        kospi_close: KOSPI 현재/종가
        kospi_ma: KOSPI 이동평균(20일 또는 12개월 등 호출자 선택)
        kospi_adx: KOSPI ADX 값 (None 가능 — 없으면 추세 강도 판단 생략)
        market_value_ratio: 시장 전체 거래대금 / 최근 5거래일 평균 거래대금 (1.0 = 평균)
        atr_pct: KOSPI ATR% (ATR / 종가, 0.01 = 1%)
        config: 판단 임계값 (None이면 기본)

    Returns:
        MarketStyle: 판단된 스타일

    판단 우선순위:
        1. RANGE: |KOSPI-MA|/MA < band + atr% 낮음
        2. 상승장 (KOSPI > MA):
           - ADX>25 + 거래대금 충분 → TREND_BULL_STRONG
           - 거래대금 적음(<quiet) → TREND_BULL_QUIET
           - 그 외 → TREND_BULL_QUIET (보수적 기본)
        3. 하락장 (KOSPI < MA):
           - ADX>25 → TREND_BEAR
           - 그 외 → CHOP
        4. 미분류 → CHOP
    """
    cfg = config or StyleConfig()

    if kospi_ma <= 0:
        # 입력 이상 — 보수적 CHOP
        return MarketStyle.CHOP

    ma_gap_pct = abs(kospi_close - kospi_ma) / kospi_ma

    # 1. RANGE 판단: KOSPI가 이평선 근처 + 저변동
    if ma_gap_pct < cfg.range_band_pct and atr_pct <= cfg.range_atr_pct_max:
        return MarketStyle.RANGE

    # 2. 상승장
    if kospi_close > kospi_ma:
        adx_strong = kospi_adx is not None and kospi_adx >= cfg.adx_trend_threshold
        volume_strong = market_value_ratio >= cfg.strong_volume_ratio
        volume_quiet = market_value_ratio < cfg.quiet_volume_ratio

        if adx_strong and volume_strong:
            return MarketStyle.TREND_BULL_STRONG
        if volume_quiet:
            return MarketStyle.TREND_BULL_QUIET
        # 중간대: 추세는 있으나 거래량/ADX 애매 → QUIET (pullback 유리)
        return MarketStyle.TREND_BULL_QUIET

    # 3. 하락장 (KOSPI < MA)
    if kospi_close < kospi_ma:
        adx_strong = kospi_adx is not None and kospi_adx >= cfg.adx_trend_threshold
        if adx_strong:
            return MarketStyle.TREND_BEAR
        return MarketStyle.CHOP

    # 4. 정확히 kospi_close == kospi_ma (매우 드문 경계): CHOP
    return MarketStyle.CHOP
