"""월봉 12이평 추세 분석 모듈.

월봉 종가와 12개월 이동평균을 비교해 매수/매도/홀드 신호를 생성한다.
진입 조건: 종가 > MA12 x 1.01 + MA12 상향 기울기 + 거래량 1.5x + ADX > 25
청산 조건: 종가 < MA12
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MonthlySignal:
    """월봉 12이평 신호."""

    symbol: str
    name: str
    signal: str  # "buy" | "sell" | "hold"
    close: float  # 현재 월봉 종가
    ma12: float  # 12이평 값
    adx: float  # ADX 값
    volume_ratio: float  # 거래량 배수 (현재 월 / 6개월 평균)
    reason: str  # 신호 근거


def calc_monthly_ma(prices: list[float], period: int = 12) -> float:
    """월봉 이동평균 계산.

    Args:
        prices: 종가 목록 (시간순, 최신이 마지막).
        period: 이동평균 기간.

    Returns:
        마지막 period 개 값의 단순 이동평균. 데이터 부족 시 0.0 반환.
    """
    if len(prices) < period:
        return 0.0
    window = prices[-period:]
    return sum(window) / period


def calc_monthly_adx(monthly_ohlcv: list[dict], period: int = 14) -> float:
    """월봉 ADX 계산 (Wilder 스무딩).

    Args:
        monthly_ohlcv: 월봉 OHLCV 목록. 각 항목은 high, low, close 키를 포함.
            시간순 정렬 (최신이 마지막).
        period: ADX 기간.

    Returns:
        ADX 값 (0.0~100.0). 데이터 부족 시 0.0 반환.
    """
    n = len(monthly_ohlcv)
    # ADX 계산에는 period + 1 이상의 데이터 필요
    if n < period + 1:
        return 0.0

    plus_dm_list: list[float] = []
    minus_dm_list: list[float] = []
    tr_list: list[float] = []

    for i in range(1, n):
        prev = monthly_ohlcv[i - 1]
        curr = monthly_ohlcv[i]

        high = float(curr["high"])
        low = float(curr["low"])
        close = float(curr["close"])  # noqa: F841
        prev_high = float(prev["high"])
        prev_low = float(prev["low"])
        prev_close = float(prev["close"])

        # True Range
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        tr_list.append(tr)

        # Directional Movement
        up_move = high - prev_high
        down_move = prev_low - low
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

    # Wilder 스무딩 초기값 (첫 period 합산)
    atr = sum(tr_list[:period])
    plus_di_smooth = sum(plus_dm_list[:period])
    minus_di_smooth = sum(minus_dm_list[:period])

    dx_list: list[float] = []

    for i in range(period, len(tr_list)):
        atr = atr - atr / period + tr_list[i]
        plus_di_smooth = plus_di_smooth - plus_di_smooth / period + plus_dm_list[i]
        minus_di_smooth = minus_di_smooth - minus_di_smooth / period + minus_dm_list[i]

        if atr == 0:
            dx_list.append(0.0)
            continue

        plus_di = 100.0 * plus_di_smooth / atr
        minus_di = 100.0 * minus_di_smooth / atr
        di_sum = plus_di + minus_di
        dx = 100.0 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0.0
        dx_list.append(dx)

    if not dx_list:
        return 0.0

    # ADX = DX의 Wilder 이동평균
    adx = sum(dx_list[:period]) / period
    for dx in dx_list[period:]:
        adx = (adx * (period - 1) + dx) / period

    return round(adx, 2)


def _is_ma_slope_up(prices: list[float], period: int = 12, lookback: int = 3) -> bool:
    """MA12 기울기가 상향인지 판별.

    최근 lookback 개월 전 MA12와 현재 MA12를 비교한다.

    Args:
        prices: 종가 목록 (시간순, 최신이 마지막).
        period: 이동평균 기간.
        lookback: 기울기 비교 기간 (개월).

    Returns:
        현재 MA > lookback 개월 전 MA이면 True.
    """
    if len(prices) < period + lookback:
        return False
    current_ma = calc_monthly_ma(prices, period)
    past_ma = calc_monthly_ma(prices[:-lookback], period)
    return current_ma > past_ma


def _calc_volume_ratio(volumes: list[float], lookback: int = 6) -> float:
    """현재 월 거래량 vs 최근 N개월 평균 거래량 비율 계산.

    Args:
        volumes: 거래량 목록 (시간순, 최신이 마지막).
        lookback: 평균 계산 기간 (개월).

    Returns:
        거래량 비율. 데이터 부족 시 1.0 반환.
    """
    # 현재 월 포함 lookback + 1 개 필요
    if len(volumes) < lookback + 1:
        return 1.0
    current_vol = volumes[-1]
    avg_vol = sum(volumes[-(lookback + 1) : -1]) / lookback
    if avg_vol <= 0:
        return 1.0
    return round(current_vol / avg_vol, 4)


def check_monthly_ma12(
    symbol: str,
    monthly_prices: list[dict],
    name: str = "",
) -> MonthlySignal:
    """월봉 12이평 돌파/이탈 체크.

    진입 조건 (전부 충족):
        1. 월봉 종가 > 12이평 x 1.01 (1% 이상 돌파)
        2. 12이평 자체가 상향 기울기 (3개월 전 MA보다 현재 MA가 높음)
        3. 돌파 월 거래량 > 6개월 평균 x 1.5
        4. ADX > 25

    청산 조건:
        1. 월봉 종가 < 12이평

    Args:
        symbol: 종목 코드 (예: "005930").
        monthly_prices: 월봉 데이터 목록. 각 항목은 date, close, volume,
            high, low 키를 포함. 시간순 정렬 (최신이 마지막).
        name: 종목명 (없으면 symbol로 대체).

    Returns:
        MonthlySignal. 데이터 부족 시 signal="hold" 반환.
    """
    stock_name = name or symbol

    if len(monthly_prices) < 13:
        logger.warning("데이터 부족 — 최소 13개월 필요 (%s: %d개)", symbol, len(monthly_prices))
        return MonthlySignal(
            symbol=symbol,
            name=stock_name,
            signal="hold",
            close=0.0,
            ma12=0.0,
            adx=0.0,
            volume_ratio=1.0,
            reason="데이터 부족",
        )

    closes = [float(p["close"]) for p in monthly_prices]
    volumes = [float(p.get("volume", 0)) for p in monthly_prices]

    close = closes[-1]
    ma12 = calc_monthly_ma(closes, period=12)
    adx = calc_monthly_adx(monthly_prices, period=14)
    volume_ratio = _calc_volume_ratio(volumes, lookback=6)
    slope_up = _is_ma_slope_up(closes, period=12, lookback=3)

    # 청산 조건 우선 체크
    if close < ma12:
        return MonthlySignal(
            symbol=symbol,
            name=stock_name,
            signal="sell",
            close=close,
            ma12=round(ma12, 2),
            adx=adx,
            volume_ratio=volume_ratio,
            reason=f"종가({close:,.0f}) < MA12({ma12:,.0f}) 이탈",
        )

    # 진입 조건 전부 확인
    breakout = close > ma12 * 1.01
    vol_ok = volume_ratio >= 1.5
    adx_ok = adx > 25.0

    if breakout and slope_up and vol_ok and adx_ok:
        return MonthlySignal(
            symbol=symbol,
            name=stock_name,
            signal="buy",
            close=close,
            ma12=round(ma12, 2),
            adx=adx,
            volume_ratio=volume_ratio,
            reason=(
                f"종가({close:,.0f}) > MA12({ma12:,.0f}) x 1.01 돌파"
                f" | MA12 상향기울기 | 거래량 {volume_ratio:.1f}x"
                f" | ADX {adx:.1f}"
            ),
        )

    # 홀드: 어떤 조건이 미달인지 기록
    reasons: list[str] = []
    if not breakout:
        reasons.append(f"돌파 미충족(종가 {close:,.0f}, MA12x1.01 = {ma12 * 1.01:,.0f})")
    if not slope_up:
        reasons.append("MA12 하향 기울기")
    if not vol_ok:
        reasons.append(f"거래량 부족({volume_ratio:.1f}x < 1.5x)")
    if not adx_ok:
        reasons.append(f"ADX 약함({adx:.1f} ≤ 25)")

    return MonthlySignal(
        symbol=symbol,
        name=stock_name,
        signal="hold",
        close=close,
        ma12=round(ma12, 2),
        adx=adx,
        volume_ratio=volume_ratio,
        reason=" | ".join(reasons) if reasons else "조건 미충족",
    )
