"""RSI 과매도 + 볼린저밴드 하단 돌파 기반 평균회귀 전략."""

from __future__ import annotations

from dataclasses import dataclass

from src.broker.schemas import DailyPrice
from src.strategy.indicators import calc_bollinger, calc_rsi


@dataclass
class MeanReversionParams:
    """평균회귀 전략 파라미터."""

    rsi_period: int = 14
    rsi_oversold: float = 40.0  # 매수 진입 기준 RSI (30→40: 월 2-3회 신호)
    rsi_overbought: float = 70.0  # 매도 청산 기준 RSI
    bb_period: int = 20
    bb_std: float = 1.5  # 2.0→1.5: 밴드 폭 좁혀 하단 돌파 빈도 증가
    volume_ratio: float = 0.8  # 1.2→0.8: 과매도 시 거래량 감소가 일반적
    stop_loss: float = -0.015  # -3%→-1.5%: 빠른 반등 기대
    take_profit: float = 0.015  # +5%→+1.5%: 중심선 회귀 목표
    max_positions: int = 5


class MeanReversionStrategy:
    """평균회귀 전략.

    Strategy Protocol 구현체.
    RSI 과매도 + 볼린저밴드 하단 + 거래량 급증 조건이 동시에 충족되면 진입.
    RSI 과매수 또는 손절/익절 시 청산.
    볼린저밴드 중심선 회귀 청산은 live_trader에서 daily 데이터로 별도 처리.
    """

    name = "mean_reversion"

    def __init__(self, params: MeanReversionParams | None = None) -> None:
        """초기화.

        Args:
            params: 전략 파라미터. None이면 기본값 사용.
        """
        self.params = params or MeanReversionParams()

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
    ) -> bool:
        """매수 진입 신호 — RSI 과매도 + 볼린저밴드 하단 + 거래량 확인.

        세 조건이 모두 충족될 때만 True 반환.

        Args:
            daily: 일봉 데이터 리스트 (오래된 것부터)
            current_price: 현재가
            current_volume: 현재 거래량 (당일 누적)
            time_ratio: 장 경과 비율 (elapsed_minutes / 390)
            current_time: 미사용 (Protocol 호환)
            day_open: 미사용 (Protocol 호환)
            bar_open: 미사용 (Protocol 호환)

        Returns:
            bool: 진입 여부
        """
        min_bars = max(self.params.rsi_period + 1, self.params.bb_period)
        if len(daily) < min_bars:
            return False

        closes = [float(d.close) for d in daily]
        rsi = calc_rsi(closes, self.params.rsi_period)
        lower, _middle, _upper = calc_bollinger(closes, self.params.bb_period, self.params.bb_std)

        recent_20 = daily[-20:] if len(daily) >= 20 else daily
        avg_vol = sum(d.volume for d in recent_20) / len(recent_20)

        return (
            rsi < self.params.rsi_oversold
            and current_price < lower
            and current_volume >= avg_vol * time_ratio * self.params.volume_ratio
        )

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,  # noqa: ARG002
    ) -> str | None:
        """매도 청산 신호 — 손절/익절 확인.

        RSI 과매수 청산과 볼린저밴드 중심선 회귀 청산은
        live_trader에서 daily 데이터를 활용해 별도 처리.

        Args:
            entry_price: 진입가
            current_price: 현재가
            high_since_entry: 진입 후 최고가 (현재 미사용)

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
        """지표 기반 청산 — RSI 과매수 또는 볼린저밴드 중심선 회귀.

        stop_loss/take_profit은 check_exit_signal에서 먼저 처리.
        이 메서드는 추가 청산 조건을 체크한다.

        Args:
            entry_price: 진입가
            current_price: 현재가
            daily: 일봉 데이터 리스트 (오래된 것부터)

        Returns:
            str | None: 청산 사유 또는 None
        """
        basic_exit = self.check_exit_signal(entry_price, current_price, 0)
        if basic_exit:
            return basic_exit

        min_bars = max(self.params.rsi_period + 1, self.params.bb_period)
        if len(daily) < min_bars:
            return None

        closes = [float(d.close) for d in daily]
        rsi = calc_rsi(closes, self.params.rsi_period)
        _lower, middle, _upper = calc_bollinger(closes, self.params.bb_period, self.params.bb_std)

        if rsi > self.params.rsi_overbought:
            return "rsi_overbought"

        if current_price > middle and current_price > entry_price:
            return "bb_center_reversion"

        return None
