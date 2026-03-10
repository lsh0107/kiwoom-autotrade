"""RSI 과매도 + 볼린저밴드 하단 돌파 기반 평균회귀 전략."""

from __future__ import annotations

from dataclasses import dataclass

from src.broker.schemas import DailyPrice
from src.strategy.indicators import calc_bollinger, calc_rsi


@dataclass
class MeanReversionParams:
    """평균회귀 전략 파라미터."""

    rsi_period: int = 14
    rsi_oversold: float = 30.0  # 매수 진입 기준 RSI
    rsi_overbought: float = 70.0  # 매도 청산 기준 RSI
    bb_period: int = 20
    bb_std: float = 2.0
    volume_ratio: float = 1.2  # 거래량 배수 (20일 평균 대비)
    stop_loss: float = -0.03  # -3%
    take_profit: float = 0.05  # +5%
    max_positions: int = 3


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
    ) -> bool:
        """매수 진입 신호 — RSI 과매도 + 볼린저밴드 하단 + 거래량 확인.

        세 조건이 모두 충족될 때만 True 반환.

        Args:
            daily: 일봉 데이터 리스트 (오래된 것부터)
            current_price: 현재가
            current_volume: 현재 거래량

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
        vol_ratio = current_volume / avg_vol if avg_vol > 0 else 0.0

        return (
            rsi < self.params.rsi_oversold
            and current_price < lower
            and vol_ratio >= self.params.volume_ratio
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
