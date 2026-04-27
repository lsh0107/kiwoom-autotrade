"""tests/strategy/test_momentum_daily.py — 일봉 모멘텀 전략 신호 함수 단위 테스트."""

from __future__ import annotations

from src.broker.schemas import DailyPrice
from src.strategy.momentum_daily import (
    DailyMomentumParams,
    calc_avg_volume,
    calc_daily_trade_pnl,
    calc_kospi_ma,
    calc_n_day_high,
    check_daily_entry_signal,
    check_daily_exit_signal,
)

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def make_daily(
    date: str,
    close: int,
    *,
    high: int | None = None,
    low: int | None = None,
    volume: int = 1_000_000,
) -> DailyPrice:
    """테스트용 DailyPrice 생성."""
    return DailyPrice(
        date=date,
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=volume,
    )


def make_series(n: int, base: int = 10_000, step: int = 10) -> list[DailyPrice]:
    """n개 단조 상승 가격 시리즈 생성."""
    result = []
    for i in range(n):
        date = f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}"
        close = base + i * step
        result.append(make_daily(date, close))
    return result


# ── calc_n_day_high ───────────────────────────────────────────────────────────


class TestCalcNDayHigh:
    def test_empty_returns_zero(self) -> None:
        assert calc_n_day_high([]) == 0

    def test_uses_high_field_not_close(self) -> None:
        daily = [make_daily("20250101", 1000, high=1500)]
        assert calc_n_day_high(daily) == 1500

    def test_uses_lookback_period(self) -> None:
        # 30개 (i=0..29): i=29 → close = 1000+29*10 = 1290
        # 마지막 20개 (i=10..29): close 1100~1290 → max_high = 1290
        daily = [
            make_daily(f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}", 1000 + i * 10) for i in range(30)
        ]
        result = calc_n_day_high(daily, lookback=20)
        assert result == 1290

    def test_fewer_than_lookback_uses_all(self) -> None:
        daily = [make_daily(f"202501{i + 1:02d}", 1000 + i * 10) for i in range(5)]
        assert calc_n_day_high(daily, lookback=20) == 1040


# ── calc_avg_volume ───────────────────────────────────────────────────────────


class TestCalcAvgVolume:
    def test_empty_returns_zero(self) -> None:
        assert calc_avg_volume([]) == 0

    def test_average_of_recent_period(self) -> None:
        # 30개: 처음 10개 volume=500, 나머지 20개 volume=2000
        daily = [make_daily(f"202501{i + 1:02d}", 1000, volume=500) for i in range(10)]
        daily += [make_daily(f"202502{i + 1:02d}", 1000, volume=2000) for i in range(20)]
        # period=20 → 마지막 20개 평균 = 2000
        assert calc_avg_volume(daily, period=20) == 2000

    def test_fewer_than_period_uses_all(self) -> None:
        daily = [make_daily(f"202501{i + 1:02d}", 1000, volume=1000) for i in range(5)]
        assert calc_avg_volume(daily, period=20) == 1000


# ── calc_kospi_ma ─────────────────────────────────────────────────────────────


class TestCalcKospiMa:
    def test_insufficient_data_returns_zero(self) -> None:
        kospi = [make_daily("20250101", 3000) for _ in range(5)]
        assert calc_kospi_ma(kospi, period=20) == 0.0

    def test_sma_computation(self) -> None:
        # 20개, close = 1000 → MA = 1000
        kospi = [make_daily(f"202501{i + 1:02d}", 1000) for i in range(20)]
        assert calc_kospi_ma(kospi, period=20) == 1000.0

    def test_uses_recent_period(self) -> None:
        # 30개, 처음 10개=500, 마지막 20개=2000 → MA(20)=2000
        kospi = [make_daily(f"202501{i + 1:02d}", 500) for i in range(10)]
        kospi += [make_daily(f"202502{i + 1:02d}", 2000) for i in range(20)]
        assert calc_kospi_ma(kospi, period=20) == 2000.0


# ── check_daily_entry_signal ──────────────────────────────────────────────────


class TestCheckDailyEntrySignal:
    def _prior(self, n: int = 25, base: int = 9_000) -> list[DailyPrice]:
        """n개 횡보 prior 데이터 (신고가 = base + (n-1)*10)."""
        return [
            make_daily(
                f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}",
                base + i * 10,
                volume=1_000_000,
            )
            for i in range(n)
        ]

    def test_all_conditions_met(self) -> None:
        prior = self._prior(25, 9_000)
        params = DailyMomentumParams(lookback=20, vol_mult=1.5, use_kospi_filter=False)
        # prior[-20:]의 최고가 = 9000 + (25-1)*10 = 9240
        # 오늘 종가 9300 > 9240 → 돌파
        # 거래량 2_000_000 > 1_000_000 * 1.5 → 충족
        assert check_daily_entry_signal(
            prior_daily=prior,
            today_close=9_300,
            today_volume=2_000_000,
            params=params,
        )

    def test_price_below_high_no_signal(self) -> None:
        prior = self._prior(25, 9_000)
        params = DailyMomentumParams(lookback=20, vol_mult=1.5, use_kospi_filter=False)
        # 종가 9200 ≤ 신고가 9240 → 신호 없음
        assert not check_daily_entry_signal(
            prior_daily=prior,
            today_close=9_200,
            today_volume=2_000_000,
            params=params,
        )

    def test_volume_insufficient_no_signal(self) -> None:
        prior = self._prior(25, 9_000)
        params = DailyMomentumParams(lookback=20, vol_mult=1.5, use_kospi_filter=False)
        # 거래량 500_000 < 1_000_000 * 1.5 → 신호 없음
        assert not check_daily_entry_signal(
            prior_daily=prior,
            today_close=9_300,
            today_volume=500_000,
            params=params,
        )

    def test_insufficient_prior_data_no_signal(self) -> None:
        prior = [make_daily("20250101", 9_000)] * 5  # lookback=20보다 적음
        params = DailyMomentumParams(lookback=20, use_kospi_filter=False)
        assert not check_daily_entry_signal(
            prior_daily=prior,
            today_close=9_500,
            today_volume=5_000_000,
            params=params,
        )

    def test_kospi_filter_below_ma_blocks_signal(self) -> None:
        prior = self._prior(25, 9_000)
        params = DailyMomentumParams(lookback=20, vol_mult=1.5, use_kospi_filter=True)
        # KOSPI 하락 추세: 종가 < 20MA → 필터 차단
        kospi = [
            make_daily(f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}", 3_000 - i * 20) for i in range(25)
        ]
        assert not check_daily_entry_signal(
            prior_daily=prior,
            today_close=9_300,
            today_volume=2_000_000,
            params=params,
            kospi_prior=kospi,
        )

    def test_kospi_filter_above_ma_allows_signal(self) -> None:
        prior = self._prior(25, 9_000)
        params = DailyMomentumParams(lookback=20, vol_mult=1.5, use_kospi_filter=True)
        # KOSPI 상승 추세: 종가 > 20MA → 필터 통과
        kospi = [
            make_daily(f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}", 2_000 + i * 20) for i in range(25)
        ]
        assert check_daily_entry_signal(
            prior_daily=prior,
            today_close=9_300,
            today_volume=2_000_000,
            params=params,
            kospi_prior=kospi,
        )

    def test_kospi_filter_disabled_ignores_kospi(self) -> None:
        prior = self._prior(25, 9_000)
        params = DailyMomentumParams(lookback=20, vol_mult=1.5, use_kospi_filter=False)
        # KOSPI 하락이어도 필터 비활성화 → 신호 발생
        kospi = [
            make_daily(f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}", 3_000 - i * 50) for i in range(25)
        ]
        assert check_daily_entry_signal(
            prior_daily=prior,
            today_close=9_300,
            today_volume=2_000_000,
            params=params,
            kospi_prior=kospi,
        )


# ── check_daily_exit_signal ───────────────────────────────────────────────────


def _atr_prior(n: int = 25, price: int = 10_000, atr_range: int = 300) -> list[DailyPrice]:
    """ATR 계산용 prior 일봉 (high-low = atr_range)."""
    result = []
    for i in range(n):
        date = f"2025{i // 28 + 1:02d}{i % 28 + 1:02d}"
        close = price + i * 10
        result.append(
            DailyPrice(
                date=date,
                open=close,
                high=close + atr_range,
                low=close - atr_range,
                close=close,
                volume=1_000_000,
            )
        )
    return result


class TestCheckDailyExitSignal:
    def test_stop_loss_triggered(self) -> None:
        """ATR 손절 발동."""
        prior = _atr_prior(25, 10_000, atr_range=300)
        params = DailyMomentumParams(atr_stop_mult=1.5)
        entry_price = 10_000
        # ATR ≈ 600 (TR = high-low = 600), recent_price ≈ 10240
        # atr_pct = 600/10240 ≈ 5.86% → stop = -1.5 * 5.86% ≈ -8.8%
        current_close = int(entry_price * 0.90)  # -10% → 손절 초과
        result = check_daily_exit_signal(
            entry_price=entry_price,
            current_close=current_close,
            peak_price=entry_price,
            holding_days=1,
            prior_daily=prior,
            params=params,
        )
        assert result == "stop_loss"

    def test_take_profit_triggered(self) -> None:
        """익절 발동."""
        prior = _atr_prior(25, 10_000, atr_range=50)  # 작은 ATR → dynamic_tp 낮음
        params = DailyMomentumParams(
            atr_tp_mult=1.0,
            tp_pct=0.05,
            atr_stop_mult=10.0,  # 손절 비활성화
            max_holding_days=20,
            trailing_armed_pct=0.10,  # trailing armed 비활성화
        )
        entry_price = 10_000
        # ATR 작음 → dynamic_tp = min(atr_tp*atr_pct, 0.05) 가 낮음
        # +5% 이상이면 tp_pct 기준으로 익절
        current_close = int(entry_price * 1.06)  # +6%
        result = check_daily_exit_signal(
            entry_price=entry_price,
            current_close=current_close,
            peak_price=current_close,
            holding_days=3,
            prior_daily=prior,
            params=params,
        )
        assert result == "take_profit"

    def test_trailing_stop_not_armed_no_trigger(self) -> None:
        """Trailing armed 미달 → trailing_stop 미발동."""
        prior = _atr_prior(25, 10_000)
        params = DailyMomentumParams(
            trailing_armed_pct=0.02,
            trailing_stop_pct=0.01,
            atr_stop_mult=10.0,  # 손절 비활성화
            max_holding_days=20,
        )
        entry_price = 10_000
        # peak = 10100 (+1%) < armed threshold 10200 (+2%) → armed 미달
        result = check_daily_exit_signal(
            entry_price=entry_price,
            current_close=10_000,
            peak_price=10_100,
            holding_days=5,
            prior_daily=prior,
            params=params,
        )
        assert result != "trailing_stop"

    def test_trailing_stop_armed_and_triggered(self) -> None:
        """Trailing armed 달성 후 하락 → trailing_stop."""
        prior = _atr_prior(25, 10_000)
        params = DailyMomentumParams(
            trailing_armed_pct=0.02,
            trailing_stop_pct=0.01,  # 고점 대비 1% 하락 시 청산
            atr_stop_mult=100.0,  # 손절 사실상 비활성화
            atr_tp_mult=100.0,  # 익절 사실상 비활성화
            tp_pct=1.0,
            max_holding_days=20,
        )
        entry_price = 10_000
        peak_price = 10_300  # +3% > armed +2% → armed 상태
        current_close = int(10_300 * 0.984)  # 고점 대비 -1.6% → trailing 발동
        result = check_daily_exit_signal(
            entry_price=entry_price,
            current_close=current_close,
            peak_price=peak_price,
            holding_days=5,
            prior_daily=prior,
            params=params,
        )
        assert result == "trailing_stop"

    def test_max_holding_days_triggers_exit(self) -> None:
        """최대 보유일 초과 → max_holding."""
        prior = _atr_prior(25, 10_000)
        params = DailyMomentumParams(max_holding_days=10, atr_stop_mult=100.0, tp_pct=1.0)
        result = check_daily_exit_signal(
            entry_price=10_000,
            current_close=10_050,
            peak_price=10_050,
            holding_days=10,
            prior_daily=prior,
            params=params,
        )
        assert result == "max_holding"

    def test_no_exit_condition(self) -> None:
        """청산 조건 없음 → None."""
        prior = _atr_prior(25, 10_000)
        params = DailyMomentumParams()
        result = check_daily_exit_signal(
            entry_price=10_000,
            current_close=10_050,  # 소폭 상승
            peak_price=10_050,
            holding_days=3,
            prior_daily=prior,
            params=params,
        )
        assert result is None

    def test_zero_entry_price_returns_none(self) -> None:
        """진입가 0 → None."""
        result = check_daily_exit_signal(
            entry_price=0,
            current_close=10_000,
            peak_price=10_000,
            holding_days=1,
            prior_daily=[],
            params=DailyMomentumParams(),
        )
        assert result is None

    def test_empty_prior_uses_fallback(self) -> None:
        """prior_daily 없을 때 fallback ATR 적용 — 오류 없어야 함."""
        params = DailyMomentumParams(atr_stop_mult=1.5)
        # fallback: stop = -1.5 * 2% = -3%
        result = check_daily_exit_signal(
            entry_price=10_000,
            current_close=int(10_000 * 0.96),  # -4% → 손절
            peak_price=10_000,
            holding_days=1,
            prior_daily=[],
            params=params,
        )
        assert result == "stop_loss"

    def test_tp_pct_none_no_fixed_cap_allows_higher_exit(self) -> None:
        """tp_pct=None 시 고정 상한 제거 — ATR 기반 익절이 더 높은 지점에서 작동.

        atr_range=50 시리즈: ATR≈100, recent_price≈10240
        → atr_pct≈0.98%, atr_tp_mult=6 → dynamic_tp≈5.86%
        - tp_pct=0.05: dynamic_tp = min(5.86%, 5%) = 5% → +5.5%에서 익절
        - tp_pct=None:  dynamic_tp = 5.86% → +5.5% 미달, 익절 미발동
        """
        prior = _atr_prior(25, 10_000, atr_range=50)
        params_with_cap = DailyMomentumParams(
            atr_tp_mult=6.0,
            tp_pct=0.05,
            atr_stop_mult=100.0,
            max_holding_days=30,
            trailing_armed_pct=0.50,
        )
        params_no_cap = DailyMomentumParams(
            atr_tp_mult=6.0,
            tp_pct=None,  # 상한 없음 → ATR 기반 5.86%가 기준
            atr_stop_mult=100.0,
            max_holding_days=30,
            trailing_armed_pct=0.50,
        )
        # +5.5%: tp_pct=0.05 기준은 초과, ATR 기준 5.86%는 미달
        current_close = int(10_000 * 1.055)

        result_with = check_daily_exit_signal(
            entry_price=10_000,
            current_close=current_close,
            peak_price=current_close,
            holding_days=2,
            prior_daily=prior,
            params=params_with_cap,
        )
        result_none = check_daily_exit_signal(
            entry_price=10_000,
            current_close=current_close,
            peak_price=current_close,
            holding_days=2,
            prior_daily=prior,
            params=params_no_cap,
        )

        # tp_pct=0.05: +5.5% > 5% 상한 → 익절
        assert result_with == "take_profit"
        # tp_pct=None: +5.5% < ATR 기반 5.86% → 익절 미발동
        assert result_none is None

    def test_tp_pct_none_fallback_no_error(self) -> None:
        """tp_pct=None + prior 없을 때 fallback 정상 작동."""
        params = DailyMomentumParams(
            atr_tp_mult=6.0,
            tp_pct=None,
            atr_stop_mult=100.0,
            max_holding_days=30,
        )
        # fallback: dynamic_tp = atr_tp_mult * 2% = 12%
        result = check_daily_exit_signal(
            entry_price=10_000,
            current_close=int(10_000 * 1.13),  # +13% → fallback 익절 초과
            peak_price=int(10_000 * 1.13),
            holding_days=2,
            prior_daily=[],
            params=params,
        )
        assert result == "take_profit"


# ── calc_daily_trade_pnl ──────────────────────────────────────────────────────


class TestCalcDailyTradePnl:
    def test_positive_pnl(self) -> None:
        params = DailyMomentumParams(commission_rate=0.00015, tax_rate=0.002, slippage_pct=0.0)
        pnl = calc_daily_trade_pnl(10_000, 10_500, params)
        expected = 0.05 - (0.00015 * 2 + 0.002)
        assert abs(pnl - expected) < 1e-9

    def test_negative_pnl(self) -> None:
        params = DailyMomentumParams(commission_rate=0.00015, tax_rate=0.002, slippage_pct=0.0)
        pnl = calc_daily_trade_pnl(10_000, 9_500, params)
        expected = -0.05 - (0.00015 * 2 + 0.002)
        assert abs(pnl - expected) < 1e-9

    def test_zero_entry_price_returns_zero(self) -> None:
        assert calc_daily_trade_pnl(0, 10_000, DailyMomentumParams()) == 0.0

    def test_breakeven_is_negative_after_costs(self) -> None:
        """동일가 청산 → 거래 비용만큼 손실."""
        params = DailyMomentumParams(commission_rate=0.00015, tax_rate=0.002)
        pnl = calc_daily_trade_pnl(10_000, 10_000, params)
        assert pnl < 0  # 비용 차감으로 손실
