"""기술 지표 계산 유틸."""

from __future__ import annotations

from enum import StrEnum

from src.broker.schemas import DailyPrice


class VolatilityClass(StrEnum):
    """변동성 기반 전략 분류."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    CONSERVATIVE = "conservative_momentum"


def calc_rsi(prices: list[float], period: int = 14) -> float:
    """RSI(Relative Strength Index) 계산.

    데이터 부족(period + 1 미만)이면 중립값 50.0 반환.

    Args:
        prices: 종가 리스트 (오래된 것부터)
        period: RSI 기간 (기본 14)

    Returns:
        float: RSI 값 (0~100)
    """
    if len(prices) < period + 1:
        return 50.0

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]

    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_bollinger(
    prices: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[float, float, float]:
    """볼린저밴드 계산.

    데이터 부족(period 미만)이면 마지막 가격으로 upper=middle=lower 반환.

    Args:
        prices: 종가 리스트 (오래된 것부터)
        period: 이동평균 기간 (기본 20)
        num_std: 표준편차 배수 (기본 2.0)

    Returns:
        tuple[float, float, float]: (lower, middle, upper)
    """
    if len(prices) < period:
        mid = prices[-1] if prices else 0.0
        return mid, mid, mid

    recent = prices[-period:]
    middle = sum(recent) / period
    variance = sum((p - middle) ** 2 for p in recent) / period
    std = variance**0.5

    return middle - num_std * std, middle, middle + num_std * std


def calc_atr(daily: list[DailyPrice], period: int = 20) -> float:
    """ATR(Average True Range) 계산.

    Args:
        daily: 일봉 데이터 리스트 (오래된 것부터)
        period: ATR 기간 (기본 20)

    Returns:
        float: ATR 값. 데이터 부족 시 0.0
    """
    if len(daily) < 2:
        return 0.0

    true_ranges = []
    for i in range(1, len(daily)):
        prev_close = daily[i - 1].close
        curr = daily[i]
        tr = max(
            curr.high - curr.low,
            abs(curr.high - prev_close),
            abs(curr.low - prev_close),
        )
        true_ranges.append(float(tr))

    recent = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return sum(recent) / len(recent) if recent else 0.0


def calc_adx(daily: list[DailyPrice], period: int = 14) -> float:
    """ADX(Average Directional Index) 계산 — Wilder 방식.

    데이터 부족(period*2 미만)이면 0.0 반환.

    Args:
        daily: 일봉 데이터 리스트 (오래된 것부터)
        period: ADX 기간 (기본 14)

    Returns:
        float: ADX 값 (0~100). 데이터 부족 시 0.0
    """
    if len(daily) < period * 2:
        return 0.0

    # 1. +DM, -DM, TR 계산
    plus_dm_list: list[float] = []
    minus_dm_list: list[float] = []
    tr_list: list[float] = []

    for i in range(1, len(daily)):
        curr = daily[i]
        prev = daily[i - 1]

        up_move = float(curr.high - prev.high)
        down_move = float(prev.low - curr.low)

        plus_dm = up_move if up_move > 0 and up_move > down_move else 0.0
        minus_dm = down_move if down_move > 0 and down_move > up_move else 0.0

        tr = max(
            float(curr.high - curr.low),
            abs(float(curr.high - prev.close)),
            abs(float(curr.low - prev.close)),
        )

        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)

    # 2. Wilder 평활화 초기값 (첫 period개의 합)
    smoothed_plus_dm = sum(plus_dm_list[:period])
    smoothed_minus_dm = sum(minus_dm_list[:period])
    smoothed_tr = sum(tr_list[:period])

    # 3. DX 시리즈 계산
    dx_list: list[float] = []

    for i in range(period, len(plus_dm_list)):
        # Wilder 평활화: prev * (period-1)/period + current
        smoothed_plus_dm = smoothed_plus_dm * (period - 1) / period + plus_dm_list[i]
        smoothed_minus_dm = smoothed_minus_dm * (period - 1) / period + minus_dm_list[i]
        smoothed_tr = smoothed_tr * (period - 1) / period + tr_list[i]

        if smoothed_tr == 0:
            dx_list.append(0.0)
            continue

        plus_di = smoothed_plus_dm / smoothed_tr * 100
        minus_di = smoothed_minus_dm / smoothed_tr * 100

        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx_list.append(0.0)
            continue

        dx = abs(plus_di - minus_di) / di_sum * 100
        dx_list.append(dx)

    if len(dx_list) < period:
        return 0.0

    # 4. ADX = Wilder 평활화 of DX
    adx = sum(dx_list[:period]) / period
    for i in range(period, len(dx_list)):
        adx = adx * (period - 1) / period + dx_list[i] / period

    return adx


def classify_volatility(
    daily: list[DailyPrice],
    *,
    atr_period: int = 20,
    adx_period: int = 14,
    high_atr_pct: float = 0.03,
    low_atr_pct: float = 0.02,
    adx_threshold: float = 25.0,
) -> VolatilityClass:
    """변동성 + 추세 강도 기반 전략 자동 분류.

    - ATR% > high_atr_pct AND ADX > adx_threshold → MOMENTUM
    - ATR% < low_atr_pct → MEAN_REVERSION
    - 그 외 → CONSERVATIVE (보수적 모멘텀)
    - 데이터 부족 시 → CONSERVATIVE (안전 폴백)

    Args:
        daily: 일봉 데이터 리스트 (오래된 것부터)
        atr_period: ATR 계산 기간 (기본 20)
        adx_period: ADX 계산 기간 (기본 14)
        high_atr_pct: 고변동성 기준 ATR% (기본 3%)
        low_atr_pct: 저변동성 기준 ATR% (기본 2%)
        adx_threshold: 강추세 기준 ADX (기본 25)

    Returns:
        VolatilityClass: 분류 결과
    """
    if len(daily) < 2:
        return VolatilityClass.CONSERVATIVE

    atr = calc_atr(daily, period=atr_period)
    last_close = float(daily[-1].close)

    if last_close == 0:
        return VolatilityClass.CONSERVATIVE

    atr_pct = atr / last_close

    adx = calc_adx(daily, period=adx_period)

    if atr_pct > high_atr_pct and adx > adx_threshold:
        return VolatilityClass.MOMENTUM

    if atr_pct < low_atr_pct:
        return VolatilityClass.MEAN_REVERSION

    return VolatilityClass.CONSERVATIVE
