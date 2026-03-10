"""기술 지표 계산 유틸."""

from __future__ import annotations

from src.broker.schemas import DailyPrice


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
