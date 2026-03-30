"""슬리피지 모델.

백테스트에서 실거래 체결 가격과의 괴리를 시뮬레이션한다.
"""

from __future__ import annotations


def apply_slippage(
    price: int,
    side: str,
    slippage_pct: float,
    *,
    bar_high: int = 0,
    bar_low: int = 0,
    volatility_factor: float = 0.0,
) -> int:
    """슬리피지를 반영한 체결 가격 계산.

    BUY: 불리한 방향(위)으로 체결 → 더 비싸게
    SELL: 불리한 방향(아래)로 체결 → 더 싸게

    변동성 기반 모드: volatility_factor > 0이면 봉의 high-low 범위를 반영하여
    변동성이 클수록 슬리피지가 커진다.

    Args:
        price: 기준 가격 (보통 bar.close)
        side: "BUY" 또는 "SELL"
        slippage_pct: 고정 슬리피지 비율 (0.001 = 0.1%)
        bar_high: 봉 최고가 (변동성 모드용)
        bar_low: 봉 최저가 (변동성 모드용)
        volatility_factor: 변동성 비례 계수 (0 = 비활성)

    Returns:
        int: 슬리피지 적용된 체결 가격
    """
    if slippage_pct == 0.0 and volatility_factor == 0.0:
        return price

    effective_pct = slippage_pct

    # 변동성 기반 추가 슬리피지
    if volatility_factor > 0.0 and bar_high > 0 and bar_low > 0 and price > 0:
        bar_range_pct = (bar_high - bar_low) / price
        effective_pct += bar_range_pct * volatility_factor

    slippage_amt = int(price * effective_pct)

    if side == "BUY":
        return price + slippage_amt
    return price - slippage_amt
