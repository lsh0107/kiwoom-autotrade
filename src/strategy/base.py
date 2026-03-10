"""전략 Protocol 정의."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.broker.schemas import DailyPrice


@runtime_checkable
class Strategy(Protocol):
    """전략 공통 인터페이스.

    모멘텀, 평균회귀 등 모든 전략이 구현해야 하는 Protocol.
    """

    name: str

    def check_entry_signal(
        self,
        daily: list[DailyPrice],
        current_price: int,
        current_volume: int,
    ) -> bool:
        """매수 진입 신호 확인.

        Args:
            daily: 일봉 데이터 리스트 (오래된 것부터)
            current_price: 현재가
            current_volume: 현재 거래량

        Returns:
            bool: 진입 여부
        """
        ...

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,
    ) -> str | None:
        """매도 청산 신호 확인.

        Args:
            entry_price: 진입가
            current_price: 현재가
            high_since_entry: 진입 후 최고가 (trailing stop 용)

        Returns:
            str | None: 청산 사유 ("stop_loss", "take_profit" 등) 또는 None
        """
        ...
