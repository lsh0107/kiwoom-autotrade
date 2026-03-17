"""시장 레짐(Market Regime) 판단 모듈.

Layer 0: VKOSPI + KOSPI 12이평 기반 레짐 판단.
- Layer 0-slow: VKOSPI 4주 평균 + 확증 기간 기반 안정적 레짐 판단
- Layer 0-fast: 당일 급변 감지 (조기 경보)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MarketRegime(StrEnum):
    """시장 레짐 분류."""

    AGGRESSIVE = "aggressive"  # 공격: KOSPI > 12이평 + VKOSPI < 20
    NEUTRAL = "neutral"  # 중립: KOSPI > 12이평 + VKOSPI 20~30
    DEFENSIVE = "defensive"  # 방어: KOSPI < 12이평 or VKOSPI > 30
    CRISIS = "crisis"  # 위기: KOSPI < 12이평 + VKOSPI > 30


@dataclass
class RegimeConfig:
    """레짐 판단 임계값 설정."""

    vkospi_aggressive: float = 20.0  # VKOSPI < 이 값 → 공격 레짐 조건
    vkospi_defensive: float = 30.0  # VKOSPI > 이 값 → 방어/위기 레짐 조건
    adx_trend_threshold: float = 25.0  # ADX > 이 값 → 추세 강함 (레짐 판단 보조)
    confirmation_days: int = 3  # 레짐 전환 확증 일수


# 레짐별 자본 배분 매트릭스
# pool_a: 모멘텀 풀, pool_b: 방어/안정 풀, buffer: 현금 버퍼
REGIME_ALLOCATION: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.AGGRESSIVE: {"pool_a": 0.60, "pool_b": 0.30, "buffer": 0.10},
    MarketRegime.NEUTRAL: {"pool_a": 0.40, "pool_b": 0.40, "buffer": 0.20},
    MarketRegime.DEFENSIVE: {"pool_a": 0.20, "pool_b": 0.50, "buffer": 0.30},
    MarketRegime.CRISIS: {"pool_a": 0.00, "pool_b": 0.00, "buffer": 1.00},
}


def detect_regime(
    vkospi: float,
    kospi_above_ma12: bool,
    adx: float | None = None,  # noqa: ARG001 — 향후 추세 강도 연동 예정
    config: RegimeConfig | None = None,
) -> MarketRegime:
    """시장 레짐을 판단한다 (Layer 0-slow).

    판단 기준:
    - AGGRESSIVE: KOSPI > 12이평 AND VKOSPI < vkospi_aggressive
    - NEUTRAL:    KOSPI > 12이평 AND vkospi_aggressive <= VKOSPI <= vkospi_defensive
    - DEFENSIVE:  (KOSPI < 12이평 AND VKOSPI <= vkospi_defensive)
                  OR (KOSPI > 12이평 AND VKOSPI > vkospi_defensive)
    - CRISIS:     KOSPI < 12이평 AND VKOSPI > vkospi_defensive

    Args:
        vkospi: 현재 VKOSPI(한국형 VIX) 값
        kospi_above_ma12: KOSPI 현재가 > 12개월 이동평균 여부
        adx: ADX 값 (현재 미사용, 향후 추세 강도 연동 예정)
        config: 레짐 판단 임계값 설정 (None이면 기본값 사용)

    Returns:
        MarketRegime: 판단된 레짐
    """
    cfg = config or RegimeConfig()

    kospi_bull = kospi_above_ma12
    vkospi_high = vkospi > cfg.vkospi_defensive

    if kospi_bull and not vkospi_high:
        if vkospi < cfg.vkospi_aggressive:
            return MarketRegime.AGGRESSIVE
        return MarketRegime.NEUTRAL

    if not kospi_bull and vkospi_high:
        return MarketRegime.CRISIS

    # KOSPI 약세 + VKOSPI 낮음, 또는 KOSPI 강세 + VKOSPI 높음
    return MarketRegime.DEFENSIVE


def detect_regime_fast(
    vkospi_change_pct: float,
    kospi_daily_change_pct: float,
) -> MarketRegime | None:
    """조기 경보 — 당일 급변 감지 (Layer 0-fast).

    장중 급변 시 레짐 즉시 조정. 해당 조건 없으면 None 반환.

    조건:
    - VKOSPI 일간 +20% 이상 급등 → DEFENSIVE
    - KOSPI 일간 -3% 이하 급락 → DEFENSIVE
    - VKOSPI 일간 +20% 이상 AND KOSPI -3% 이하 동시 → CRISIS

    Args:
        vkospi_change_pct: VKOSPI 일간 변화율 (%, 양수=상승)
        kospi_daily_change_pct: KOSPI 일간 변화율 (%, 음수=하락)

    Returns:
        MarketRegime: 조기 경보 레짐 (해당 없으면 None)
    """
    vkospi_spike = vkospi_change_pct >= 20.0
    kospi_crash = kospi_daily_change_pct <= -3.0

    if vkospi_spike and kospi_crash:
        return MarketRegime.CRISIS
    if vkospi_spike or kospi_crash:
        return MarketRegime.DEFENSIVE
    return None


@dataclass
class RegimeHistory:
    """레짐 전환 확증 추적 (Layer 0-slow 연속성 관리).

    confirmation_days 연속으로 동일 레짐 판단 시 레짐 전환 확정.
    """

    config: RegimeConfig = field(default_factory=RegimeConfig)
    _current_regime: MarketRegime = field(default=MarketRegime.NEUTRAL, init=False)
    _pending_regime: MarketRegime | None = field(default=None, init=False)
    _pending_count: int = field(default=0, init=False)

    @property
    def current_regime(self) -> MarketRegime:
        """현재 확정된 레짐."""
        return self._current_regime

    def update(self, new_regime: MarketRegime) -> MarketRegime:
        """새 레짐 판단을 입력하고, 확정된 레짐을 반환한다.

        confirmation_days 연속 동일 판단 시 레짐 전환 확정.
        CRISIS는 즉시 전환 (1일 조건).

        Args:
            new_regime: 새로 판단된 레짐

        Returns:
            MarketRegime: 현재 확정된 레짐
        """
        # CRISIS는 즉시 전환 (안전 우선)
        if new_regime == MarketRegime.CRISIS:
            self._current_regime = MarketRegime.CRISIS
            self._pending_regime = None
            self._pending_count = 0
            return self._current_regime

        if new_regime == self._current_regime:
            # 현재 레짐 유지
            self._pending_regime = None
            self._pending_count = 0
            return self._current_regime

        if new_regime == self._pending_regime:
            self._pending_count += 1
        else:
            # 새 후보 레짐 시작
            self._pending_regime = new_regime
            self._pending_count = 1

        if self._pending_count >= self.config.confirmation_days:
            # 확증 완료 → 레짐 전환
            self._current_regime = new_regime
            self._pending_regime = None
            self._pending_count = 0

        return self._current_regime
