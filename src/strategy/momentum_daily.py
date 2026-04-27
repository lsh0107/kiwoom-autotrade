"""52주 신고가 일봉 모멘텀 전략.

진입: N일 신고가 돌파 + 거래량 >vol_mult x N일 평균 + KOSPI 20MA 상승 필터
청산: ATR 1.5x 손절 / ATR 4~6x 또는 +5% 익절 / Trailing(+2% armed) / 최대 10거래일
"""

from __future__ import annotations

from dataclasses import dataclass

from src.broker.schemas import DailyPrice
from src.strategy.indicators import calc_atr


@dataclass
class DailyMomentumParams:
    """52주 신고가 일봉 모멘텀 전략 파라미터."""

    # 진입 조건
    lookback: int = 20  # 신고가 lookback (거래일 수, 10/20/30 grid)
    vol_mult: float = 1.5  # 거래량 배수 (1.2/1.5/2.0 grid)
    use_kospi_filter: bool = True  # KOSPI 20MA 상승 필터

    # 청산 조건
    atr_stop_mult: float = 1.5  # ATR 손절 배수 (1.0/1.5/2.0 grid)
    atr_tp_mult: float = 4.0  # ATR 익절 배수 (4/5/6/7/8 grid)
    tp_pct: float | None = 0.05  # 고정 익절 상한 (+5% 기본). None이면 ATR 기반 상한 없음
    trailing_armed_pct: float = 0.02  # 트레일링 armed 기준 +2%
    trailing_stop_pct: float = 0.01  # 고점 대비 트레일링 손절 (1%)
    max_holding_days: int = 10  # 최대 보유 거래일

    # 포지션 관리
    max_positions: int = 3  # 최대 동시 포지션 수

    # 거래 비용
    commission_rate: float = 0.00015  # 편도 수수료 0.015%
    tax_rate: float = 0.0020  # 매도 거래세 0.20%
    slippage_pct: float = 0.0015  # 슬리피지 0.15%


def calc_n_day_high(daily: list[DailyPrice], lookback: int = 20) -> int:
    """lookback일 최고가 계산 (look-ahead 방지: 당일 이전 데이터만 사용).

    Args:
        daily: 당일 이전 일봉 데이터 (날짜 오름차순)
        lookback: 조회 기간 (거래일 수)

    Returns:
        int: lookback일 최고가. 데이터 부족 시 0
    """
    if not daily:
        return 0
    recent = daily[-lookback:] if len(daily) >= lookback else daily
    return max(bar.high for bar in recent)


def calc_avg_volume(daily: list[DailyPrice], period: int = 20) -> int:
    """최근 period일 평균 거래량 계산.

    Args:
        daily: 일봉 데이터 (날짜 오름차순)
        period: 평균 기간 (거래일 수)

    Returns:
        int: 평균 거래량. 데이터 없으면 0
    """
    if not daily:
        return 0
    recent = daily[-period:] if len(daily) >= period else daily
    return int(sum(bar.volume for bar in recent) / len(recent))


def calc_kospi_ma(kospi_daily: list[DailyPrice], period: int = 20) -> float:
    """KOSPI N일 단순이동평균 계산.

    Args:
        kospi_daily: KOSPI 일봉 데이터 (날짜 오름차순)
        period: 이동평균 기간

    Returns:
        float: SMA 값. 데이터 부족 시 0.0
    """
    if len(kospi_daily) < period:
        return 0.0
    recent = kospi_daily[-period:]
    return sum(bar.close for bar in recent) / period


def check_daily_entry_signal(
    prior_daily: list[DailyPrice],
    today_close: int,
    today_volume: int,
    params: DailyMomentumParams,
    *,
    kospi_prior: list[DailyPrice] | None = None,
) -> bool:
    """일봉 모멘텀 진입 신호 확인.

    조건:
    1. 당일 종가 > lookback일 최고가 (돌파)
    2. 당일 거래량 > 20일 평균 x vol_mult
    3. KOSPI 종가 > KOSPI 20MA (use_kospi_filter=True 시)

    Args:
        prior_daily: 당일 이전 일봉 데이터 (look-ahead 방지)
        today_close: 당일 종가
        today_volume: 당일 거래량
        params: 전략 파라미터
        kospi_prior: KOSPI 이전 일봉 데이터 (keyword-only)

    Returns:
        bool: 진입 여부
    """
    if len(prior_daily) < params.lookback:
        return False

    # 1. 신고가 돌파
    high_n = calc_n_day_high(prior_daily, params.lookback)
    if high_n <= 0 or today_close <= high_n:
        return False

    # 2. 거래량 조건
    avg_vol = calc_avg_volume(prior_daily)
    if avg_vol <= 0 or today_volume < avg_vol * params.vol_mult:
        return False

    # 3. KOSPI 20MA 상승 필터
    if params.use_kospi_filter and kospi_prior and len(kospi_prior) >= 2:
        kospi_ma = calc_kospi_ma(kospi_prior)
        if kospi_ma > 0:
            kospi_last = float(kospi_prior[-1].close)
            if kospi_last < kospi_ma:
                return False

    return True


def check_daily_exit_signal(
    entry_price: int,
    current_close: int,
    peak_price: int,
    holding_days: int,
    prior_daily: list[DailyPrice],
    params: DailyMomentumParams,
) -> str | None:
    """일봉 모멘텀 청산 신호 확인.

    우선순위:
    1. ATR 손절 (stop_loss)
    2. 익절 (take_profit)
    3. Trailing stop (armed +2% 이후)
    4. 최대 보유일 초과 (max_holding)

    Args:
        entry_price: 진입가
        current_close: 당일 종가
        peak_price: 진입 후 최고가
        holding_days: 보유 거래일 수
        prior_daily: 진입 시점 이전 일봉 데이터 (ATR 계산용)
        params: 전략 파라미터

    Returns:
        str | None: 청산 사유 또는 None
    """
    if entry_price <= 0:
        return None

    pnl_pct = (current_close - entry_price) / entry_price

    # ATR 기반 동적 손절/익절 계산
    atr_val = calc_atr(prior_daily) if prior_daily else 0.0
    recent_price = float(prior_daily[-1].close) if prior_daily else float(entry_price)

    if atr_val > 0 and recent_price > 0:
        atr_pct = atr_val / recent_price
        dynamic_stop = -params.atr_stop_mult * atr_pct
        atr_based_tp = params.atr_tp_mult * atr_pct
        dynamic_tp = atr_based_tp if params.tp_pct is None else min(atr_based_tp, params.tp_pct)
    else:
        # ATR 없으면 손절 2% x 배수, 익절은 고정 상한 또는 ATR 배수 x 2%
        dynamic_stop = -(params.atr_stop_mult * 0.02)
        dynamic_tp = (params.atr_tp_mult * 0.02) if params.tp_pct is None else params.tp_pct

    # 1. 손절
    if pnl_pct <= dynamic_stop:
        return "stop_loss"

    # 2. 익절
    if pnl_pct >= dynamic_tp:
        return "take_profit"

    # 3. Trailing stop (armed threshold 달성 후)
    armed_threshold = entry_price * (1 + params.trailing_armed_pct)
    if peak_price >= armed_threshold:
        drop_from_peak = (current_close - peak_price) / peak_price
        if drop_from_peak <= -params.trailing_stop_pct:
            return "trailing_stop"

    # 4. 최대 보유일 초과
    if holding_days >= params.max_holding_days:
        return "max_holding"

    return None


def calc_daily_trade_pnl(
    entry_price: int,
    exit_price: int,
    params: DailyMomentumParams,
) -> float:
    """거래 손익률 계산 (수수료 + 세금 차감).

    왕복 비용: 매수 수수료 + 매도 수수료 + 매도 거래세
    ≈ 0.015% x 2 + 0.20% = 0.23%

    Args:
        entry_price: 진입가 (슬리피지 포함)
        exit_price: 청산가 (슬리피지 포함)
        params: 전략 파라미터

    Returns:
        float: 순손익률 (음수 = 손실)
    """
    if entry_price <= 0:
        return 0.0
    gross_pnl = (exit_price - entry_price) / entry_price
    total_cost = params.commission_rate * 2 + params.tax_rate
    return gross_pnl - total_cost
