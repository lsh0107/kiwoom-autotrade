"""백테스트 엔진.

분봉 데이터를 시간순으로 재생하며 전략 신호에 따라 거래를 시뮬레이션한다.
"""

from __future__ import annotations

import structlog

from src.backtest.metrics import calc_metrics
from src.backtest.result import BacktestResult, TradeRecord
from src.backtest.strategy import (
    MomentumParams,
    Position,
    calc_trade_pnl,
    check_entry_signal,
    check_exit_signal,
    extract_time_from_bar,
)
from src.broker.schemas import DailyPrice, MinutePrice

logger = structlog.get_logger("backtest.engine")


class BacktestEngine:
    """백테스트 엔진.

    분봉 데이터를 시간순으로 재생하며 모멘텀 돌파 전략을 시뮬레이션한다.
    """

    def __init__(self, params: MomentumParams | None = None) -> None:
        """엔진 초기화.

        Args:
            params: 전략 파라미터 (None이면 기본값)
        """
        self.params = params or MomentumParams()

    def _simulate(
        self,
        symbol: str,
        minute_data: list[MinutePrice],
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """공통 시뮬레이션 로직.

        Args:
            symbol: 종목코드 (빈 문자열 가능)
            minute_data: 분봉 데이터 (시간 오름차순)
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            BacktestResult: 백테스트 결과
        """
        if not minute_data:
            logger.warning("분봉 데이터 없음, 빈 결과 반환")
            return BacktestResult(params=self.params, metrics=calc_metrics([]))

        high_52w = self._calc_52w_high(daily_data)
        avg_volume = self._calc_avg_volume(daily_data)
        rsi_value, dynamic_stop, dynamic_tp = self._calc_indicators(daily_data)

        positions: list[Position] = []
        trades: list[TradeRecord] = []

        cumulative_volume = 0
        current_date = ""
        day_open = 0

        for bar in minute_data:
            bar_time = extract_time_from_bar(bar)

            bar_date = bar.datetime[:8]
            if bar_date != current_date:
                cumulative_volume = 0
                day_open = bar.open
                current_date = bar_date
            cumulative_volume += bar.volume

            # 포지션 peak_price 갱신 (트레일링 스탑용)
            for pos in positions:
                pos.update_peak(bar.high)

            # 청산 체크
            closed_positions: list[Position] = []
            for pos in positions:
                exit_reason = check_exit_signal(
                    pos.entry_price,
                    bar.close,
                    bar_time,
                    self.params,
                    dynamic_stop=dynamic_stop,
                    dynamic_tp=dynamic_tp,
                    peak_price=pos.peak_price,
                )
                if exit_reason:
                    pnl = calc_trade_pnl(pos.entry_price, bar.close, self.params)
                    trades.append(
                        TradeRecord(
                            symbol=pos.symbol,
                            entry_time=pos.entry_time,
                            exit_time=bar.datetime,
                            entry_price=pos.entry_price,
                            exit_price=bar.close,
                            side="BUY",
                            pnl_pct=round(pnl, 6),
                            exit_reason=exit_reason,
                        )
                    )
                    closed_positions.append(pos)

            for pos in closed_positions:
                positions.remove(pos)

            # 진입 체크
            if len(positions) < self.params.max_positions and check_entry_signal(
                bar.close,
                high_52w,
                cumulative_volume,
                avg_volume,
                self.params,
                rsi=rsi_value,
                day_open=day_open,
                bar_open=bar.open,
                current_time=bar_time,
            ):
                positions.append(
                    Position(
                        symbol=symbol,
                        entry_time=bar.datetime,
                        entry_price=bar.close,
                    )
                )

        # 미청산 강제 청산
        if positions and minute_data:
            last_bar = minute_data[-1]
            for pos in positions:
                pnl = calc_trade_pnl(pos.entry_price, last_bar.close, self.params)
                trades.append(
                    TradeRecord(
                        symbol=pos.symbol,
                        entry_time=pos.entry_time,
                        exit_time=last_bar.datetime,
                        entry_price=pos.entry_price,
                        exit_price=last_bar.close,
                        side="BUY",
                        pnl_pct=round(pnl, 6),
                        exit_reason="force_close",
                    )
                )

        metrics = calc_metrics(trades)
        return BacktestResult(trades=trades, metrics=metrics, params=self.params)

    def run(
        self,
        minute_data: list[MinutePrice],
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """백테스트 실행.

        Args:
            minute_data: 분봉 데이터 (시간 오름차순)
            daily_data: 일봉 데이터 (날짜 오름차순, 52주 이상 권장)

        Returns:
            BacktestResult: 백테스트 결과
        """
        return self._simulate("", minute_data, daily_data)

    def run_with_symbol(
        self,
        symbol: str,
        minute_data: list[MinutePrice],
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """심볼 지정 백테스트 실행.

        Args:
            symbol: 종목코드
            minute_data: 분봉 데이터 (시간 오름차순)
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            BacktestResult: 백테스트 결과
        """
        return self._simulate(symbol, minute_data, daily_data)

    @staticmethod
    def _calc_52w_high(daily_data: list[DailyPrice]) -> int:
        """일봉 데이터에서 52주(약 250거래일) 최고가 계산."""
        if not daily_data:
            return 0
        recent = daily_data[-250:] if len(daily_data) > 250 else daily_data
        return max(bar.high for bar in recent)

    @staticmethod
    def _calc_avg_volume(daily_data: list[DailyPrice]) -> int:
        """일봉 데이터에서 최근 20일 평균 거래량 계산."""
        if not daily_data:
            return 0
        recent = daily_data[-20:] if len(daily_data) > 20 else daily_data
        total = sum(bar.volume for bar in recent)
        return total // len(recent)

    def _calc_indicators(
        self, daily_data: list[DailyPrice]
    ) -> tuple[float | None, float | None, float | None]:
        """RSI / ATR 사전 계산.

        Returns:
            (rsi_value, dynamic_stop, dynamic_tp) — 비활성 파라미터는 None
        """
        rsi_value: float | None = None
        dynamic_stop: float | None = None
        dynamic_tp: float | None = None

        if self.params.rsi_min is not None and daily_data:
            from src.strategy.indicators import calc_rsi

            close_prices = [float(d.close) for d in daily_data]
            rsi_value = calc_rsi(close_prices)

        if self.params.atr_stop_multiplier is not None and daily_data:
            from src.strategy.indicators import calc_atr

            atr_value = calc_atr(daily_data)
            recent_price = float(daily_data[-1].close)
            if atr_value > 0 and recent_price > 0:
                atr_pct = atr_value / recent_price
                # 변동성 필터: ATR% < 0.35% → 동적 손절 비활성 (live_trader와 동일)
                if atr_pct < 0.0035:
                    pass  # dynamic_stop/tp는 None 유지 → 고정 SL/TP 사용
                else:
                    stop_mult = self.params.atr_stop_multiplier
                    tp_mult = self.params.atr_tp_multiplier or (stop_mult * 2)
                    # 바닥값: SL 최소 0.5%, TP 최소 1.0%
                    dynamic_stop = -max(stop_mult * atr_pct, 0.005)
                    dynamic_tp = max(tp_mult * atr_pct, 0.010)

        return rsi_value, dynamic_stop, dynamic_tp
