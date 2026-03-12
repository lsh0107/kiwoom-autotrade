"""백테스트 전략 정의.

모멘텀 돌파 전략 (MomentumBreakoutStrategy) 구현.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.broker.schemas import MinutePrice


@dataclass
class MomentumParams:
    """모멘텀 돌파 전략 파라미터."""

    volume_ratio: float = 0.5  # 거래량 배수 (전일 평균 대비)
    stop_loss: float = -0.005  # -0.5% (타이트 손절)
    take_profit: float = 0.015  # +1.5% (3:1 리워드)
    trailing_stop_pct: float | None = None  # 트레일링 스탑 (예: -0.003 = 고점 대비 -0.3%)
    max_positions: int = 3  # 집중 투자 (분산 줄임)
    high_52w_threshold: float = 0.0  # 0이면 비활성 (단타 모드)
    price_change_min: float = 0.003  # 당일 시가 대비 최소 상승률 (0.3%)
    force_close_time: str = "14:00"  # 강제 청산 시각 (14:00 — 마감 노이즈 회피)

    # 진입 시간 필터 (HH:MM)
    entry_start_time: str = "09:05"  # 장 시작 5분 후부터 (초반 노이즈 회피)
    entry_end_time: str = "13:00"  # 오후 1시까지만 진입

    # 양봉 필터
    require_bullish_bar: bool = True  # 진입 봉이 양봉이어야 함

    # RSI 필터 (None = 비활성)
    rsi_min: float | None = None

    # ATR 기반 동적 손절/익절 (None = 고정 stop_loss/take_profit 사용)
    atr_stop_multiplier: float | None = None

    # 거래비용
    commission_rate: float = 0.00015  # 편도 수수료 0.015%
    tax_rate: float = 0.0018  # 매도 시 거래세 0.18%


def check_entry_signal(
    current_price: int,
    high_52w: int,
    current_volume: int,
    avg_volume: int,
    params: MomentumParams,
    *,
    rsi: float | None = None,
    day_open: int = 0,
    bar_open: int = 0,
    current_time: str = "",
) -> bool:
    """진입 신호 확인.

    조건:
    1. 진입 시간 필터 (entry_start_time ~ entry_end_time)
    2. 양봉 필터 (close > open)
    3. 거래량 급등 (당일 누적 >= 평균 * volume_ratio)
    4. 52주 신고가 조건 (threshold > 0이면 활성, 0이면 비활성)
    5. 당일 양봉 조건 (price_change_min > 0이면 시가 대비 상승률 체크)
    6. RSI 필터 (rsi_min 설정 시)

    Args:
        current_price: 현재가
        high_52w: 52주 최고가
        current_volume: 현재 거래량
        avg_volume: 전일 평균 거래량
        params: 전략 파라미터
        rsi: 사전 계산된 RSI 값 (keyword-only)
        day_open: 당일 시가 (keyword-only)
        bar_open: 현재 봉 시가 (keyword-only, 양봉 판단)
        current_time: 현재 시각 HHMM or HHMMSS (keyword-only)

    Returns:
        bool: 진입 여부
    """
    # 진입 시간 필터
    if current_time and params.entry_start_time:
        entry_start = params.entry_start_time.replace(":", "")
        entry_end = params.entry_end_time.replace(":", "")
        current_hhmm = current_time[:4]
        if current_hhmm < entry_start or current_hhmm >= entry_end:
            return False

    # 양봉 필터 (진입 봉의 close > open)
    if params.require_bullish_bar and bar_open > 0 and current_price <= bar_open:
        return False

    if avg_volume <= 0:
        return False

    # 거래량 급등
    if current_volume < avg_volume * params.volume_ratio:
        return False

    # 52주 신고가 조건 (threshold > 0이면 활성)
    if params.high_52w_threshold > 0 and (
        high_52w <= 0 or current_price < high_52w * params.high_52w_threshold
    ):
        return False

    # 당일 시가 대비 상승률 조건
    if params.price_change_min > 0 and day_open > 0:
        change = (current_price - day_open) / day_open
        if change < params.price_change_min:
            return False

    # RSI 필터
    return not (params.rsi_min is not None and rsi is not None and rsi < params.rsi_min)


def check_exit_signal(
    entry_price: int,
    current_price: int,
    current_time: str,
    params: MomentumParams,
    *,
    dynamic_stop: float | None = None,
    dynamic_tp: float | None = None,
    peak_price: int = 0,
) -> str | None:
    """청산 신호 확인.

    Args:
        entry_price: 진입가
        current_price: 현재가
        current_time: 현재 시각 (HHMMSS 또는 HHMM 형식)
        params: 전략 파라미터
        dynamic_stop: ATR 기반 동적 손절 (음수, keyword-only)
        dynamic_tp: ATR 기반 동적 익절 (양수, keyword-only)
        peak_price: 진입 후 최고가 (트레일링 스탑용, keyword-only)

    Returns:
        str | None: 청산 사유 또는 None
    """
    if entry_price <= 0:
        return None

    pnl_pct = (current_price - entry_price) / entry_price

    stop = dynamic_stop if dynamic_stop is not None else params.stop_loss
    tp = dynamic_tp if dynamic_tp is not None else params.take_profit

    # 손절
    if pnl_pct <= stop:
        return "stop_loss"

    # 트레일링 스탑 (고점 대비 하락폭 체크)
    if params.trailing_stop_pct is not None and peak_price > entry_price:
        drop_from_peak = (current_price - peak_price) / peak_price
        if drop_from_peak <= params.trailing_stop_pct:
            return "trailing_stop"

    # 익절 (트레일링 스탑이 없을 때만, 있으면 트레일링이 수익 관리)
    if params.trailing_stop_pct is None and pnl_pct >= tp:
        return "take_profit"

    # 강제 청산 시각 체크
    force_time = params.force_close_time.replace(":", "")
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
    peak_price: int = 0  # 진입 후 최고가 (트레일링 스탑용)

    def __post_init__(self) -> None:
        """초기 peak_price를 entry_price로 설정."""
        if self.peak_price == 0:
            self.peak_price = self.entry_price

    def update_peak(self, price: int) -> None:
        """최고가 갱신."""
        if price > self.peak_price:
            self.peak_price = price


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
