"""시장 레짐 판단 모듈 테스트."""

import pytest

from src.trading.market_regime import (
    REGIME_ALLOCATION,
    MarketRegime,
    RegimeConfig,
    RegimeHistory,
    detect_regime,
    detect_regime_fast,
)


class TestDetectRegime:
    """detect_regime — Layer 0-slow 레짐 판단 테스트."""

    def test_aggressive_kospi_bull_vkospi_low(self) -> None:
        """KOSPI 강세 + VKOSPI < 20 → AGGRESSIVE."""
        assert detect_regime(vkospi=15.0, kospi_above_ma12=True) == MarketRegime.AGGRESSIVE

    def test_aggressive_vkospi_exactly_at_boundary(self) -> None:
        """VKOSPI = 19.99 → AGGRESSIVE (경계값 미만)."""
        assert detect_regime(vkospi=19.99, kospi_above_ma12=True) == MarketRegime.AGGRESSIVE

    def test_neutral_kospi_bull_vkospi_mid(self) -> None:
        """KOSPI 강세 + VKOSPI 20~30 → NEUTRAL."""
        assert detect_regime(vkospi=25.0, kospi_above_ma12=True) == MarketRegime.NEUTRAL

    def test_neutral_vkospi_at_lower_boundary(self) -> None:
        """VKOSPI = 20.0 → NEUTRAL (경계값 포함)."""
        assert detect_regime(vkospi=20.0, kospi_above_ma12=True) == MarketRegime.NEUTRAL

    def test_neutral_vkospi_at_upper_boundary(self) -> None:
        """VKOSPI = 30.0 → DEFENSIVE (경계 초과 판단)."""
        # 30.0 > 30.0 은 False이므로 NEUTRAL에 해당
        result = detect_regime(vkospi=30.0, kospi_above_ma12=True)
        assert result == MarketRegime.NEUTRAL

    def test_defensive_kospi_bull_vkospi_high(self) -> None:
        """KOSPI 강세 + VKOSPI > 30 → DEFENSIVE."""
        assert detect_regime(vkospi=35.0, kospi_above_ma12=True) == MarketRegime.DEFENSIVE

    def test_defensive_kospi_bear_vkospi_low(self) -> None:
        """KOSPI 약세 + VKOSPI < 30 → DEFENSIVE."""
        assert detect_regime(vkospi=18.0, kospi_above_ma12=False) == MarketRegime.DEFENSIVE

    def test_defensive_kospi_bear_vkospi_mid(self) -> None:
        """KOSPI 약세 + VKOSPI 20~30 → DEFENSIVE."""
        assert detect_regime(vkospi=25.0, kospi_above_ma12=False) == MarketRegime.DEFENSIVE

    def test_crisis_kospi_bear_vkospi_high(self) -> None:
        """KOSPI 약세 + VKOSPI > 30 → CRISIS."""
        assert detect_regime(vkospi=45.0, kospi_above_ma12=False) == MarketRegime.CRISIS

    def test_crisis_vkospi_exactly_above_30(self) -> None:
        """VKOSPI = 30.01, KOSPI 약세 → CRISIS."""
        assert detect_regime(vkospi=30.01, kospi_above_ma12=False) == MarketRegime.CRISIS

    def test_adx_parameter_accepted(self) -> None:
        """adx 파라미터 전달 시 오류 없이 동작."""
        result = detect_regime(vkospi=15.0, kospi_above_ma12=True, adx=30.0)
        assert result == MarketRegime.AGGRESSIVE

    def test_custom_config_lower_thresholds(self) -> None:
        """커스텀 config — 임계값 변경 반영."""
        config = RegimeConfig(vkospi_aggressive=15.0, vkospi_defensive=25.0)
        # VKOSPI=20.0, KOSPI 강세: aggressive=15 미만 아니므로 NEUTRAL
        assert (
            detect_regime(vkospi=20.0, kospi_above_ma12=True, config=config) == MarketRegime.NEUTRAL
        )
        # VKOSPI=26.0, KOSPI 강세: 25 초과이므로 DEFENSIVE
        assert (
            detect_regime(vkospi=26.0, kospi_above_ma12=True, config=config)
            == MarketRegime.DEFENSIVE
        )


class TestDetectRegimeFast:
    """detect_regime_fast — Layer 0-fast 조기 경보 테스트."""

    def test_no_alert_normal_conditions(self) -> None:
        """정상 시장 → None 반환."""
        assert detect_regime_fast(vkospi_change_pct=5.0, kospi_daily_change_pct=-1.0) is None

    def test_defensive_on_vkospi_spike(self) -> None:
        """VKOSPI +20% 급등 단독 → DEFENSIVE."""
        assert (
            detect_regime_fast(vkospi_change_pct=20.0, kospi_daily_change_pct=0.0)
            == MarketRegime.DEFENSIVE
        )

    def test_defensive_on_vkospi_spike_above_threshold(self) -> None:
        """VKOSPI +25% 급등 → DEFENSIVE."""
        assert (
            detect_regime_fast(vkospi_change_pct=25.0, kospi_daily_change_pct=-1.0)
            == MarketRegime.DEFENSIVE
        )

    def test_defensive_on_kospi_crash(self) -> None:
        """KOSPI -3% 급락 단독 → DEFENSIVE."""
        assert (
            detect_regime_fast(vkospi_change_pct=10.0, kospi_daily_change_pct=-3.0)
            == MarketRegime.DEFENSIVE
        )

    def test_defensive_on_kospi_crash_below_threshold(self) -> None:
        """KOSPI -5% 급락 → DEFENSIVE."""
        assert (
            detect_regime_fast(vkospi_change_pct=5.0, kospi_daily_change_pct=-5.0)
            == MarketRegime.DEFENSIVE
        )

    def test_crisis_on_both_conditions(self) -> None:
        """VKOSPI +20% AND KOSPI -3% 동시 → CRISIS."""
        assert (
            detect_regime_fast(vkospi_change_pct=20.0, kospi_daily_change_pct=-3.0)
            == MarketRegime.CRISIS
        )

    def test_crisis_on_extreme_both(self) -> None:
        """VKOSPI +50% AND KOSPI -7% 동시 → CRISIS."""
        assert (
            detect_regime_fast(vkospi_change_pct=50.0, kospi_daily_change_pct=-7.0)
            == MarketRegime.CRISIS
        )

    def test_boundary_vkospi_just_below_spike(self) -> None:
        """VKOSPI +19.99% → 조기 경보 없음."""
        assert detect_regime_fast(vkospi_change_pct=19.99, kospi_daily_change_pct=-1.0) is None

    def test_boundary_kospi_just_above_crash(self) -> None:
        """KOSPI -2.99% → 조기 경보 없음."""
        assert detect_regime_fast(vkospi_change_pct=5.0, kospi_daily_change_pct=-2.99) is None

    def test_vkospi_decrease_no_alert(self) -> None:
        """VKOSPI 하락(-10%) → 조기 경보 없음."""
        assert detect_regime_fast(vkospi_change_pct=-10.0, kospi_daily_change_pct=1.0) is None

    def test_kospi_positive_no_alert(self) -> None:
        """KOSPI 상승 시장 → 조기 경보 없음."""
        assert detect_regime_fast(vkospi_change_pct=3.0, kospi_daily_change_pct=2.0) is None


class TestRegimeAllocation:
    """REGIME_ALLOCATION 자본 배분 매트릭스 검증."""

    def test_all_regimes_have_allocation(self) -> None:
        """모든 레짐에 배분 정보 존재."""
        for regime in MarketRegime:
            assert regime in REGIME_ALLOCATION

    def test_allocation_sums_to_one(self) -> None:
        """각 레짐의 배분 합계 = 1.0."""
        for regime, alloc in REGIME_ALLOCATION.items():
            total = alloc["pool_a"] + alloc["pool_b"] + alloc["buffer"]
            assert abs(total - 1.0) < 1e-9, f"{regime}: 합계 {total} != 1.0"

    def test_aggressive_allocation(self) -> None:
        """AGGRESSIVE: pool_a=0.60, pool_b=0.30, buffer=0.10."""
        alloc = REGIME_ALLOCATION[MarketRegime.AGGRESSIVE]
        assert alloc["pool_a"] == pytest.approx(0.60)
        assert alloc["pool_b"] == pytest.approx(0.30)
        assert alloc["buffer"] == pytest.approx(0.10)

    def test_neutral_allocation(self) -> None:
        """NEUTRAL: pool_a=0.40, pool_b=0.40, buffer=0.20."""
        alloc = REGIME_ALLOCATION[MarketRegime.NEUTRAL]
        assert alloc["pool_a"] == pytest.approx(0.40)
        assert alloc["pool_b"] == pytest.approx(0.40)
        assert alloc["buffer"] == pytest.approx(0.20)

    def test_defensive_allocation(self) -> None:
        """DEFENSIVE: pool_a=0.20, pool_b=0.50, buffer=0.30."""
        alloc = REGIME_ALLOCATION[MarketRegime.DEFENSIVE]
        assert alloc["pool_a"] == pytest.approx(0.20)
        assert alloc["pool_b"] == pytest.approx(0.50)
        assert alloc["buffer"] == pytest.approx(0.30)

    def test_crisis_full_buffer(self) -> None:
        """CRISIS: pool_a=0.00, pool_b=0.00, buffer=1.00 (전량 현금)."""
        alloc = REGIME_ALLOCATION[MarketRegime.CRISIS]
        assert alloc["pool_a"] == pytest.approx(0.00)
        assert alloc["pool_b"] == pytest.approx(0.00)
        assert alloc["buffer"] == pytest.approx(1.00)

    def test_pool_a_decreases_with_risk(self) -> None:
        """레짐이 위험할수록 pool_a 비중 감소."""
        assert (
            REGIME_ALLOCATION[MarketRegime.AGGRESSIVE]["pool_a"]
            > REGIME_ALLOCATION[MarketRegime.NEUTRAL]["pool_a"]
            > REGIME_ALLOCATION[MarketRegime.DEFENSIVE]["pool_a"]
            > REGIME_ALLOCATION[MarketRegime.CRISIS]["pool_a"]
        )

    def test_buffer_increases_with_risk(self) -> None:
        """레짐이 위험할수록 buffer 비중 증가."""
        assert (
            REGIME_ALLOCATION[MarketRegime.CRISIS]["buffer"]
            > REGIME_ALLOCATION[MarketRegime.DEFENSIVE]["buffer"]
            > REGIME_ALLOCATION[MarketRegime.NEUTRAL]["buffer"]
            > REGIME_ALLOCATION[MarketRegime.AGGRESSIVE]["buffer"]
        )


class TestRegimeHistory:
    """RegimeHistory — 레짐 전환 확증 테스트."""

    def test_initial_regime_is_neutral(self) -> None:
        """초기 레짐은 NEUTRAL."""
        history = RegimeHistory()
        assert history.current_regime == MarketRegime.NEUTRAL

    def test_same_regime_stays(self) -> None:
        """동일 레짐 반복 입력 → 변화 없음."""
        history = RegimeHistory()
        # 초기값 NEUTRAL에서 NEUTRAL 계속 입력
        history.update(MarketRegime.NEUTRAL)
        history.update(MarketRegime.NEUTRAL)
        assert history.current_regime == MarketRegime.NEUTRAL

    def test_regime_change_requires_confirmation(self) -> None:
        """레짐 전환: confirmation_days 미만이면 아직 전환 안 됨."""
        config = RegimeConfig(confirmation_days=3)
        history = RegimeHistory(config=config)
        # NEUTRAL → AGGRESSIVE 전환 시도
        history.update(MarketRegime.AGGRESSIVE)  # 1번
        assert history.current_regime == MarketRegime.NEUTRAL  # 아직
        history.update(MarketRegime.AGGRESSIVE)  # 2번
        assert history.current_regime == MarketRegime.NEUTRAL  # 아직

    def test_regime_change_confirmed_after_n_days(self) -> None:
        """confirmation_days 연속 동일 판단 → 레짐 전환 확정."""
        config = RegimeConfig(confirmation_days=3)
        history = RegimeHistory(config=config)
        history.update(MarketRegime.AGGRESSIVE)  # 1번
        history.update(MarketRegime.AGGRESSIVE)  # 2번
        history.update(MarketRegime.AGGRESSIVE)  # 3번 → 확정
        assert history.current_regime == MarketRegime.AGGRESSIVE

    def test_regime_pending_reset_on_different_signal(self) -> None:
        """중간에 다른 레짐 신호 → 카운터 리셋."""
        config = RegimeConfig(confirmation_days=3)
        history = RegimeHistory(config=config)
        history.update(MarketRegime.AGGRESSIVE)  # 1번
        history.update(MarketRegime.AGGRESSIVE)  # 2번
        history.update(MarketRegime.DEFENSIVE)  # 다른 신호 → 리셋
        history.update(MarketRegime.AGGRESSIVE)  # 다시 1번
        history.update(MarketRegime.AGGRESSIVE)  # 2번
        assert history.current_regime == MarketRegime.NEUTRAL  # 아직 전환 안됨

    def test_crisis_immediate_transition(self) -> None:
        """CRISIS는 즉시 전환 (확증 기간 불필요)."""
        config = RegimeConfig(confirmation_days=3)
        history = RegimeHistory(config=config)
        history.update(MarketRegime.CRISIS)
        assert history.current_regime == MarketRegime.CRISIS

    def test_crisis_overrides_pending(self) -> None:
        """CRISIS 발생 시 기존 pending 레짐 무시."""
        config = RegimeConfig(confirmation_days=3)
        history = RegimeHistory(config=config)
        history.update(MarketRegime.AGGRESSIVE)  # pending 시작
        history.update(MarketRegime.AGGRESSIVE)  # pending 진행
        history.update(MarketRegime.CRISIS)  # CRISIS 즉시 전환
        assert history.current_regime == MarketRegime.CRISIS

    def test_confirmation_days_1_immediate_change(self) -> None:
        """confirmation_days=1이면 한 번에 레짐 전환."""
        config = RegimeConfig(confirmation_days=1)
        history = RegimeHistory(config=config)
        history.update(MarketRegime.DEFENSIVE)
        assert history.current_regime == MarketRegime.DEFENSIVE

    def test_after_crisis_new_regime_needs_confirmation(self) -> None:
        """CRISIS 이후 다른 레짐도 확증 기간 적용."""
        config = RegimeConfig(confirmation_days=2)
        history = RegimeHistory(config=config)
        history.update(MarketRegime.CRISIS)
        history.update(MarketRegime.NEUTRAL)  # 1번
        assert history.current_regime == MarketRegime.CRISIS  # 아직
        history.update(MarketRegime.NEUTRAL)  # 2번 → 확정
        assert history.current_regime == MarketRegime.NEUTRAL


class TestMarketRegimeEnum:
    """MarketRegime StrEnum 기본 동작 테스트."""

    def test_string_equality(self) -> None:
        """StrEnum: 문자열 비교 가능."""
        assert MarketRegime.AGGRESSIVE == "aggressive"
        assert MarketRegime.CRISIS == "crisis"

    def test_all_values_defined(self) -> None:
        """4개 레짐 모두 정의됨."""
        values = {r.value for r in MarketRegime}
        assert values == {"aggressive", "neutral", "defensive", "crisis"}
