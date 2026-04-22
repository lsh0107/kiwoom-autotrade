"""Pullback(눌림목 재진입) 전략 — Design 013 PR 4.

상승 추세 내 단기 조정 구간에서 재진입을 노리는 전략.

진입 조건:
- 일봉 종가 > MA20 (상승 추세 유지)
- 현재가가 MA20 ±1% 근처 (조정 구간)
- 직전 5봉 중 양봉 ≥ 1개 (반등 신호)
- RSI 35~55 (과매도 아님, 과매수 아님)
- 거래량 >= 최근 20봉 평균 * volume_ratio (거래량 유지)

청산 조건:
- take_profit +2.5%
- stop_loss -1.2%
- trailing 비활성 (pullback 이후 단기 수익 목표)

Strategy Protocol 호환. USE_MULTI_REGIME flag 켜진 경우에만 live_trader가 활성.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.broker.schemas import DailyPrice
from src.strategy.indicators import calc_rsi


@dataclass
class PullbackParams:
    """Pullback 전략 파라미터."""

    ma_period: int = 20
    ma_band_pct: float = 0.01  # MA20 ±1% 근처 판정
    rsi_period: int = 14
    rsi_min: float = 35.0
    rsi_max: float = 55.0
    lookback_bars: int = 5  # 직전 N봉에서 양봉 찾기
    min_bullish_bars: int = 1  # 양봉 최소 개수
    volume_ratio: float = 0.5  # 거래량 요건 (기본 완화)

    # 청산
    stop_loss: float = -0.012  # -1.2%
    take_profit: float = 0.025  # +2.5%
    # trailing 비활성 — 단기 수익 확보 우선

    # 거래비용
    commission_rate: float = 0.00015
    tax_rate: float = 0.0020
    slippage_pct: float = 0.0


class PullbackStrategy:
    """Pullback(눌림목) 전략.

    Strategy Protocol 구현체.
    상승 추세 내 조정 국면에서 RSI 중립 + 거래량 요건 충족 시 재진입.
    """

    name = "pullback"

    def __init__(self, params: PullbackParams | None = None) -> None:
        """초기화.

        Args:
            params: 전략 파라미터. None이면 기본값 사용.
        """
        self.params = params or PullbackParams()

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
            daily: 일봉 데이터 리스트 (오래된 것부터, 최소 ma_period+lookback)
            current_price: 현재가
            current_volume: 현재 거래량 (당일 누적)
            time_ratio: 장 경과 비율 (elapsed_minutes / 390)
            current_time: 미사용 (Protocol 호환)
            day_open: 미사용 (Protocol 호환)
            bar_open: 미사용 (Protocol 호환)
            volume_ratio_override: 거래량 임계치 override (Design 013).

        Returns:
            bool: 진입 여부
        """
        p = self.params
        min_bars = max(p.ma_period, p.rsi_period + 1, p.lookback_bars + 1)
        if len(daily) < min_bars:
            return False

        closes = [float(d.close) for d in daily]

        # 1) MA20 계산
        ma_window = closes[-p.ma_period :]
        ma20 = sum(ma_window) / len(ma_window)
        if ma20 <= 0:
            return False

        # 2) 일봉 종가 > MA20 (상승 추세 유지)
        last_close = closes[-1]
        if last_close <= ma20:
            return False

        # 3) 현재가가 MA20 ±band_pct 내 (조정 국면)
        gap_pct = abs(current_price - ma20) / ma20
        if gap_pct > p.ma_band_pct:
            return False

        # 4) 직전 lookback 봉 중 양봉 ≥ min_bullish_bars
        recent = daily[-p.lookback_bars :]
        bullish_count = sum(1 for d in recent if d.close > d.open)
        if bullish_count < p.min_bullish_bars:
            return False

        # 5) RSI 범위
        rsi = calc_rsi(closes, p.rsi_period)
        if rsi < p.rsi_min or rsi > p.rsi_max:
            return False

        # 6) 거래량 요건 (time_ratio 고려 — MeanReversion과 동일 방식)
        recent_20 = daily[-20:] if len(daily) >= 20 else daily
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
        """매도 청산 신호 — take_profit/stop_loss.

        Pullback은 단기 수익을 목표로 하므로 trailing stop을 쓰지 않는다.

        Args:
            entry_price: 진입가
            current_price: 현재가
            high_since_entry: 진입 후 최고가 (미사용 — trailing 비활성)

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
