"""모멘텀 돌파 전략 — 기존 backtest.strategy 래퍼."""

from __future__ import annotations

import os

from src.backtest.strategy import (
    MomentumParams,
    check_entry_signal,
    check_exit_signal,
)
from src.broker.schemas import DailyPrice


def _is_trailing_armed_enabled() -> bool:
    """환경변수 USE_TRAILING_ARMED 읽기 (기본값 False).

    진입 직후 trailing_stop 과민 반응을 방지하는 armed threshold 기능을
    활성화하는 feature flag. off인 경우 기존 동작 그대로 유지.
    """
    value = os.environ.get("USE_TRAILING_ARMED", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _get_trailing_armed_pct() -> float:
    """환경변수 TRAILING_ARMED_PCT 읽기 (기본값 0.005 = 0.5%).

    armed 활성화 기준. 현재가가 진입가 대비 이 비율 이상 상승한 경우에만
    trailing_stop을 평가한다.
    """
    try:
        return float(os.environ.get("TRAILING_ARMED_PCT", "0.005"))
    except ValueError:
        return 0.005


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
        volume_ratio_override: float | None = None,
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
            volume_ratio_override: 거래량 임계치 override (Design 013).
                None(기본)이면 self.params.volume_ratio 사용.

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
            volume_ratio_override=volume_ratio_override,
        )

    def check_exit_signal(
        self,
        entry_price: int,
        current_price: int,
        high_since_entry: int,
        *,
        dynamic_stop: float | None = None,
        dynamic_tp: float | None = None,
    ) -> str | None:
        """매도 청산 신호 — 손절/익절/트레일링 확인.

        강제 청산 시각 체크는 live_trader에서 직접 수행.

        Args:
            entry_price: 진입가
            current_price: 현재가
            high_since_entry: 진입 후 최고가 (trailing stop 용)
            dynamic_stop: ATR 기반 동적 손절 (keyword-only)
            dynamic_tp: ATR 기반 동적 익절 (keyword-only)

        Returns:
            str | None: 청산 사유 또는 None
        """
        # Trailing armed threshold (feature flag: USE_TRAILING_ARMED)
        # 진입 후 최고가가 진입가 대비 TRAILING_ARMED_PCT 이상 상승하기 전까지는
        # trailing_stop을 발동시키지 않는다. 진입 직후 ±노이즈 구간에서의 과민
        # 반응(예: 299660 사례, -0.11%에서 trailing_stop 발동)을 방지한다.
        # armed 전에는 stop_loss/dynamic_stop만 작동.
        effective_peak = high_since_entry
        if _is_trailing_armed_enabled() and entry_price > 0:
            armed_pct = _get_trailing_armed_pct()
            armed_threshold = entry_price * (1 + armed_pct)
            if high_since_entry < armed_threshold:
                # armed 미달: peak_price를 entry_price로 전달해 trailing 무효화
                # (backtest.strategy.check_exit_signal은 peak_price > entry_price
                # 일 때만 trailing을 평가하므로 동일 값을 넘기면 trailing 스킵됨)
                effective_peak = entry_price

        result = check_exit_signal(
            entry_price=entry_price,
            current_price=current_price,
            current_time="0000",
            params=self.params,
            dynamic_stop=dynamic_stop,
            dynamic_tp=dynamic_tp,
            peak_price=effective_peak,
        )
        # force_close는 live_trader가 직접 판단하므로 여기서 무시
        if result == "force_close":
            return None
        return result
