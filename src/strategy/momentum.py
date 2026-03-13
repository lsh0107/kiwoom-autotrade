"""모멘텀 돌파 전략 — 기존 backtest.strategy 래퍼."""

from __future__ import annotations

from src.backtest.strategy import (
    MomentumParams,
    check_entry_signal,
    check_exit_signal,
)
from src.broker.schemas import DailyPrice


class MomentumStrategy:
    """모멘텀 돌파 전략.

    Strategy Protocol 구현체.
    기존 src/backtest/strategy.py 함수를 위임해 사용한다.
    """

    name = "momentum"

    def __init__(self, params: MomentumParams | None = None) -> None:
        """초기화.

        Args:
            params: 전략 파라미터. None이면 기본값 사용.
        """
        self.params = params or MomentumParams()

    def check_entry_signal(
        self,
        daily: list[DailyPrice],
        current_price: int,
        current_volume: int,
        time_ratio: float = 1.0,
        *,
        current_time: str = "",
        day_open: int = 0,
        bar_open: int = 0,
    ) -> bool:
        """매수 진입 신호 — 거래량 급등 + 양봉 + 시간 필터.

        Args:
            daily: 일봉 데이터 리스트 (오래된 것부터, 최소 52주치 권장)
            current_price: 현재가
            current_volume: 현재 거래량 (당일 누적)
            time_ratio: 장 경과 비율 (elapsed_minutes / 390)
            current_time: 현재 시각 "HH:MM" (진입 시간 필터용)
            day_open: 당일 시가 (시가 상승률 필터용)
            bar_open: 현재 봉 시가 (양봉 필터용)

        Returns:
            bool: 진입 여부
        """
        if not daily:
            return False

        high_52w = max(d.high for d in daily)
        recent_20 = daily[-20:] if len(daily) >= 20 else daily
        avg_volume = sum(d.volume for d in recent_20) / len(recent_20)

        return check_entry_signal(
            current_price=current_price,
            high_52w=high_52w,
            current_volume=current_volume,
            avg_volume=int(avg_volume * time_ratio),
            params=self.params,
            current_time=current_time,
            day_open=day_open,
            bar_open=bar_open,
        )

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,
    ) -> str | None:
        """매도 청산 신호 — 손절/익절/트레일링 확인.

        강제 청산 시각 체크는 live_trader에서 직접 수행.

        Args:
            entry_price: 진입가
            current_price: 현재가
            high_since_entry: 진입 후 최고가 (trailing stop 용)

        Returns:
            str | None: 청산 사유 또는 None
        """
        result = check_exit_signal(
            entry_price=entry_price,
            current_price=current_price,
            current_time="0000",
            params=self.params,
            peak_price=high_since_entry,
        )
        # force_close는 live_trader가 직접 판단하므로 여기서 무시
        if result == "force_close":
            return None
        return result
