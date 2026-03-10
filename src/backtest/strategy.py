"""백테스트 전략 정의.

모멘텀 돌파 전략 (MomentumBreakoutStrategy) 구현.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.broker.schemas import MinutePrice


@dataclass
class MomentumParams:
    """모멘텀 돌파 전략 파라미터."""

    volume_ratio: float = 1.5  # 거래량 배수 (전일 평균 대비)
    stop_loss: float = -0.005  # -0.5%
    take_profit: float = 0.010  # +1.0%
    trailing_stop: bool = False
    max_positions: int = 3
    high_52w_threshold: float = 0.80  # 52주 신고가 대비 80%+
    force_close_time: str = "14:30"  # 강제 청산 시각 (HH:MM)

    # 거래비용
    commission_rate: float = 0.00015  # 편도 수수료 0.015%
    tax_rate: float = 0.0018  # 매도 시 거래세 0.18%


def check_entry_signal(
    current_price: int,
    high_52w: int,
    current_volume: int,
    avg_volume: int,
    params: MomentumParams,
) -> bool:
    """진입 신호 확인.

    52주 신고가의 threshold 이상이고,
    당일 거래량이 전일 평균 거래량 * volume_ratio 이상이면 진입.

    Args:
        current_price: 현재가
        high_52w: 52주 최고가
        current_volume: 현재 거래량
        avg_volume: 전일 평균 거래량
        params: 전략 파라미터

    Returns:
        bool: 진입 여부
    """
    if high_52w <= 0 or avg_volume <= 0:
        return False

    price_condition = current_price >= high_52w * params.high_52w_threshold
    volume_condition = current_volume >= avg_volume * params.volume_ratio

    return price_condition and volume_condition


def check_exit_signal(
    entry_price: int,
    current_price: int,
    current_time: str,
    params: MomentumParams,
) -> str | None:
    """청산 신호 확인.

    Args:
        entry_price: 진입가
        current_price: 현재가
        current_time: 현재 시각 (HHMMSS 또는 HHMM 형식)
        params: 전략 파라미터

    Returns:
        str | None: 청산 사유 ("stop_loss", "take_profit", "force_close") 또는 None
    """
    if entry_price <= 0:
        return None

    pnl_pct = (current_price - entry_price) / entry_price

    # 손절
    if pnl_pct <= params.stop_loss:
        return "stop_loss"

    # 익절
    if pnl_pct >= params.take_profit:
        return "take_profit"

    # 강제 청산 시각 체크
    force_time = params.force_close_time.replace(":", "")
    # current_time이 HHMMSS 형식이면 HHMM으로 자름
    current_hhmm = current_time[:4]
    if current_hhmm >= force_time:
        return "force_close"

    return None


def calc_trade_pnl(
    entry_price: int,
    exit_price: int,
    params: MomentumParams,
) -> float:
    """거래 손익률 계산 (수수료/세금 차감).

    왕복 비용: 매수 수수료 + 매도 수수료 + 매도 거래세
    = 0.015% + 0.015% + 0.18% = 약 0.21%

    Args:
        entry_price: 진입가
        exit_price: 청산가
        params: 전략 파라미터

    Returns:
        float: 수수료 차감 후 손익률
    """
    if entry_price <= 0:
        return 0.0

    gross_pnl = (exit_price - entry_price) / entry_price
    # 매수 수수료 + 매도 수수료 + 매도 거래세
    total_cost = params.commission_rate * 2 + params.tax_rate
    return gross_pnl - total_cost


@dataclass
class Position:
    """진행 중인 포지션."""

    symbol: str
    entry_time: str
    entry_price: int


def extract_time_from_bar(bar: MinutePrice) -> str:
    """분봉 데이터에서 시간 부분 추출 (HHMMSS).

    Args:
        bar: 분봉 데이터

    Returns:
        str: 시간 문자열 (HHMMSS)
    """
    dt_str = bar.datetime
    # YYYYMMDDHHMMSS 형식이면 시간 부분만
    if len(dt_str) >= 14:
        return dt_str[8:14]
    # HHMMSS 형식이면 그대로
    if len(dt_str) == 6:
        return dt_str
    return dt_str
