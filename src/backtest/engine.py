"""백테스트 엔진.

분봉 데이터를 시간순으로 재생하며 전략 신호에 따라 거래를 시뮬레이션한다.
look-ahead bias 방지: 각 거래일의 지표는 해당일 이전 일봉 데이터만으로 계산한다.
"""

from __future__ import annotations

import structlog

from src.backtest.metrics import calc_metrics
from src.backtest.result import BacktestResult, TradeRecord
from src.backtest.slippage import apply_slippage
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

# 52주 최고가 계산에 필요한 권장 일봉 수 (250거래일 ≈ 1년)
_52W_MIN_BARS = 250


class BacktestEngine:
    """백테스트 엔진.

    분봉 데이터를 시간순으로 재생하며 모멘텀 돌파 전략을 시뮬레이션한다.
    bar-by-bar 지표 계산으로 look-ahead bias를 방지한다.
    """

    def __init__(self, params: MomentumParams | None = None) -> None:
        """엔진 초기화.

        Args:
            params: 전략 파라미터 (None이면 기본값)
        """
        self.params = params or MomentumParams()

    def _build_daily_indicators(
        self,
        trading_dates: list[str],
        daily_data: list[DailyPrice],
    ) -> dict[str, dict]:
        """거래일별 일봉 기반 지표 사전 계산 (bar-by-bar, look-ahead bias 방지).

        날짜 D의 지표는 D 이전 일봉 데이터만 사용한다. 당일 종가는 포함되지 않는다.

        Args:
            trading_dates: 분봉 데이터에서 추출한 거래일 목록 (오름차순)
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            dict[str, dict]: 날짜 → {high_52w, avg_volume, rsi_value, dynamic_stop, dynamic_tp}
        """
        lookup: dict[str, dict] = {}
        for trade_date in trading_dates:
            # 해당 거래일 직전 일봉만 사용 (당일 종가 미포함 → look-ahead 차단)
            prior_daily = [d for d in daily_data if d.date < trade_date]

            high_52w = self._calc_52w_high(prior_daily)
            avg_volume = self._calc_avg_volume(prior_daily)
            rsi_value, dynamic_stop, dynamic_tp = self._calc_indicators(prior_daily)

            lookup[trade_date] = {
                "high_52w": high_52w,
                "avg_volume": avg_volume,
                "rsi_value": rsi_value,
                "dynamic_stop": dynamic_stop,
                "dynamic_tp": dynamic_tp,
            }
        return lookup

    def _check_survivorship_bias(
        self,
        symbol: str,
        daily_data: list[DailyPrice],
        first_bar_date: str,
    ) -> None:
        """Survivorship bias 경고 로깅.

        백테스트 시작일 이전 일봉 수가 52주(250일) 미만이면 경고를 기록한다.
        오늘 살아남은 종목의 과거 데이터만으로 시뮬레이션하므로 과거 상장폐지 종목은
        포함되지 않는다.

        Args:
            symbol: 종목코드 (빈 문자열 가능)
            daily_data: 일봉 데이터
            first_bar_date: 최초 분봉 날짜 (YYYYMMDD)
        """
        prior_count = sum(1 for d in daily_data if d.date < first_bar_date)
        if prior_count < _52W_MIN_BARS:
            logger.warning(
                "Survivorship bias 경고: 시작일(%s) 이전 일봉 %d개 (권장 %d+). "
                "종목=%s. 현재 살아남은 종목으로만 시뮬레이션 중 — 과거 상장폐지 종목 미반영.",
                first_bar_date,
                prior_count,
                _52W_MIN_BARS,
                symbol or "(없음)",
            )

    def _simulate(
        self,
        symbol: str,
        minute_data: list[MinutePrice],
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """공통 시뮬레이션 로직 (bar-by-bar 지표 계산, look-ahead bias 없음).

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

        first_bar_date = minute_data[0].datetime[:8]

        # Survivorship bias 경고
        self._check_survivorship_bias(symbol, daily_data, first_bar_date)

        # 거래일별 지표 사전 계산 (bar-by-bar, look-ahead 방지)
        trading_dates = sorted({bar.datetime[:8] for bar in minute_data})
        daily_lookup = self._build_daily_indicators(trading_dates, daily_data)

        positions: list[Position] = []
        trades: list[TradeRecord] = []

        # 미실현 손익 포함 자산 곡선 (unrealized MDD 계산용)
        equity = 1.0  # 실현된 복리 자산 (체결 거래 누적)
        equity_curve: list[float] = []
        fraction = 1.0 / max(self.params.max_positions, 1)

        # 당일 누적 변수
        cumulative_volume = 0
        current_date = ""
        day_open = 0

        # 당일 지표 (날짜 변경 시 갱신)
        high_52w = 0
        avg_volume = 0
        rsi_value: float | None = None
        dynamic_stop: float | None = None
        dynamic_tp: float | None = None

        for bar in minute_data:
            bar_time = extract_time_from_bar(bar)
            bar_date = bar.datetime[:8]

            # 날짜 변경: 해당일 이전 일봉 기반 지표로 갱신
            if bar_date != current_date:
                current_date = bar_date
                cumulative_volume = 0
                day_open = bar.open
                day_ind = daily_lookup.get(bar_date, {})
                high_52w = day_ind.get("high_52w", 0)
                avg_volume = day_ind.get("avg_volume", 0)
                rsi_value = day_ind.get("rsi_value")
                dynamic_stop = day_ind.get("dynamic_stop")
                dynamic_tp = day_ind.get("dynamic_tp")

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
                    exit_fill = apply_slippage(
                        bar.close,
                        "SELL",
                        self.params.slippage_pct,
                        bar_high=bar.high,
                        bar_low=bar.low,
                    )
                    pnl, _ = calc_trade_pnl(pos.entry_price, exit_fill, self.params)
                    equity *= 1.0 + pnl  # 실현 자산 갱신
                    trades.append(
                        TradeRecord(
                            symbol=pos.symbol,
                            entry_time=pos.entry_time,
                            exit_time=bar.datetime,
                            entry_price=pos.entry_price,
                            exit_price=exit_fill,
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
                entry_fill = apply_slippage(
                    bar.close,
                    "BUY",
                    self.params.slippage_pct,
                    bar_high=bar.high,
                    bar_low=bar.low,
                )
                positions.append(
                    Position(
                        symbol=symbol,
                        entry_time=bar.datetime,
                        entry_price=entry_fill,
                    )
                )

            # 미실현 손익 포함 자산 스냅샷 (unrealized MDD 계산용)
            total_unrealized = sum(
                fraction * (bar.close - pos.entry_price) / pos.entry_price
                for pos in positions
                if pos.entry_price > 0
            )
            equity_curve.append(equity * (1.0 + total_unrealized))

        # 미청산 강제 청산
        if positions and minute_data:
            last_bar = minute_data[-1]
            for pos in positions:
                exit_fill = apply_slippage(
                    last_bar.close,
                    "SELL",
                    self.params.slippage_pct,
                    bar_high=last_bar.high,
                    bar_low=last_bar.low,
                )
                pnl, _ = calc_trade_pnl(pos.entry_price, exit_fill, self.params)
                trades.append(
                    TradeRecord(
                        symbol=pos.symbol,
                        entry_time=pos.entry_time,
                        exit_time=last_bar.datetime,
                        entry_price=pos.entry_price,
                        exit_price=exit_fill,
                        side="BUY",
                        pnl_pct=round(pnl, 6),
                        exit_reason="force_close",
                    )
                )

        metrics = calc_metrics(trades, equity_curve=equity_curve)
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
