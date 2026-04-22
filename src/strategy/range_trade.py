"""Range(박스권 역추세) 전략 — Design 013 PR 5.

저변동 박스권에서 BB 하단 접근 시 역추세 매수를 노리는 전략.

진입 조건:
- 최근 20봉 (high-low)/close 평균 < 2% (저변동 박스권)
- BB(20, 1.8) 하단 ±0.5% 근처 (하단 접근)
- RSI < 45 (약한 과매도)
- 거래량 >= 최근 20봉 평균 * volume_ratio

청산 조건:
- BB 중심선 회귀 (익절)
- BB 하단 추가 -1% 이탈 (손절 — 지지선 붕괴)
- 진입 후 2시간 미회귀 (타임컷 — entry_ts 기반)
- 고정 stop_loss -1.5% / take_profit +2.0% (폴백 — daily 부재 시)

Strategy Protocol 호환. USE_MULTI_REGIME flag on일 때만 live_trader가 활성.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.broker.schemas import DailyPrice
from src.strategy.indicators import calc_bollinger, calc_rsi


@dataclass
class RangeParams:
    """Range 전략 파라미터."""

    bb_period: int = 20
    bb_std: float = 1.8
    rsi_period: int = 14
    rsi_max: float = 45.0
    range_width_pct: float = 0.02  # 최근 20봉 (high-low)/close 평균 상한
    lower_band_tolerance_pct: float = 0.005  # BB 하단 ±0.5%
    volume_ratio: float = 0.4

    # 청산 (폴백 — daily 부재 시)
    stop_loss: float = -0.015
    take_profit: float = 0.02

    # 시간 기반 청산 (분 단위) — live_trader가 경과시간 계산해 check_time_exit 호출
    time_exit_minutes: int = 120

    # 거래비용
    commission_rate: float = 0.00015
    tax_rate: float = 0.0020
    slippage_pct: float = 0.0


class RangeStrategy:
    """Range(박스권) 전략.

    Strategy Protocol 구현체.
    저변동 박스권에서 BB 하단 접근 + RSI 약한 과매도 + 거래량 유지 시 진입.
    BB 중심선 회귀 시 익절, 하단 추가 이탈 시 손절.
    """

    name = "range_trade"

    def __init__(self, params: RangeParams | None = None) -> None:
        """초기화.

        Args:
            params: 전략 파라미터. None이면 기본값.
        """
        self.params = params or RangeParams()

    def check_entry_signal(
        self,
        daily: list[DailyPrice],
        current_price: int,
        current_volume: int,
        time_ratio: float = 1.0,
        *,
        current_time: str = "",  # noqa: ARG002
        day_open: int = 0,  # noqa: ARG002
        bar_open: int = 0,  # noqa: ARG002
        volume_ratio_override: float | None = None,
    ) -> bool:
        """매수 진입 신호.

        Args:
            daily: 일봉 리스트 (오래된 것부터, 최소 bb_period)
            current_price: 현재가
            current_volume: 현재 거래량 (당일 누적)
            time_ratio: 장 경과 비율
            current_time: 미사용
            day_open: 미사용
            bar_open: 미사용
            volume_ratio_override: 거래량 임계치 override.

        Returns:
            bool: 진입 여부
        """
        p = self.params
        min_bars = max(p.bb_period, p.rsi_period + 1, 20)
        if len(daily) < min_bars:
            return False

        closes = [float(d.close) for d in daily]

        # 1) 박스권 판정: 최근 20봉 (high-low)/close 평균
        recent_20 = daily[-20:]
        widths = []
        for d in recent_20:
            if d.close <= 0:
                return False
            widths.append((d.high - d.low) / d.close)
        avg_width = sum(widths) / len(widths)
        if avg_width >= p.range_width_pct:
            return False

        # 2) BB 하단 ±tolerance
        lower, _middle, _upper = calc_bollinger(closes, p.bb_period, p.bb_std)
        if lower <= 0:
            return False
        gap_pct = abs(current_price - lower) / lower
        if gap_pct > p.lower_band_tolerance_pct:
            return False

        # 3) RSI < 45
        rsi = calc_rsi(closes, p.rsi_period)
        if rsi >= p.rsi_max:
            return False

        # 4) 거래량 요건
        avg_vol = sum(d.volume for d in recent_20) / len(recent_20)
        effective_ratio = (
            volume_ratio_override if volume_ratio_override is not None else p.volume_ratio
        )
        return current_volume >= avg_vol * time_ratio * effective_ratio

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,  # noqa: ARG002
    ) -> str | None:
        """매도 청산 신호 (기본 — daily 부재 시 폴백).

        고정 stop_loss/take_profit만 판단.
        BB 중심선 회귀 / BB 하단 추가 이탈 / 시간 컷은
        check_exit_with_indicators / check_time_exit에서 처리.

        Args:
            entry_price: 진입가
            current_price: 현재가
            high_since_entry: 진입 후 최고가 (미사용)

        Returns:
            str | None: 청산 사유 또는 None
        """
        if entry_price <= 0:
            return None
        pnl_pct = (current_price - entry_price) / entry_price
        if pnl_pct <= self.params.stop_loss:
            return "stop_loss"
        if pnl_pct >= self.params.take_profit:
            return "take_profit"
        return None

    def check_exit_with_indicators(
        self,
        entry_price: int,
        current_price: int,
        daily: list[DailyPrice],
    ) -> str | None:
        """지표 기반 청산 — BB 중심선 회귀 / BB 하단 추가 이탈.

        기본 stop_loss/take_profit은 check_exit_signal에서 먼저 처리.

        Args:
            entry_price: 진입가
            current_price: 현재가
            daily: 일봉 데이터 리스트

        Returns:
            str | None: 청산 사유 또는 None
        """
        basic = self.check_exit_signal(entry_price, current_price, 0)
        if basic:
            return basic

        p = self.params
        if len(daily) < p.bb_period:
            return None

        closes = [float(d.close) for d in daily]
        lower, middle, _upper = calc_bollinger(closes, p.bb_period, p.bb_std)

        # BB 중심선 회귀 익절
        if middle > 0 and current_price >= middle and current_price > entry_price:
            return "bb_center_reversion"

        # BB 하단 추가 -1% 이탈 손절
        if lower > 0 and current_price < lower * 0.99:
            return "bb_lower_breakdown"

        return None

    def check_time_exit(self, minutes_since_entry: int) -> str | None:
        """시간 기반 청산 — 진입 후 일정 시간 미회귀 시 타임컷.

        Args:
            minutes_since_entry: 진입 이후 경과 분

        Returns:
            "time_exit" 또는 None
        """
        if minutes_since_entry >= self.params.time_exit_minutes:
            return "time_exit"
        return None
