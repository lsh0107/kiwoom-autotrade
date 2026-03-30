"""평균회귀 전략 백테스트 엔진.

일봉 데이터를 시간순으로 재생하며 RSI+볼린저밴드 평균회귀 전략을 시뮬레이션한다.
"""

from __future__ import annotations

import structlog

from src.backtest.metrics import calc_metrics
from src.backtest.result import BacktestResult, TradeRecord
from src.backtest.strategy import Position
from src.broker.schemas import DailyPrice
from src.strategy.mean_reversion import MeanReversionParams, MeanReversionStrategy

logger = structlog.get_logger("backtest.mr_engine")


class MRBacktestEngine:
    """평균회귀 백테스트 엔진.

    일봉 데이터를 시간순으로 재생하며 RSI+BB 평균회귀 전략을 시뮬레이션한다.
    """

    def __init__(self, params: MeanReversionParams | None = None) -> None:
        self.params = params or MeanReversionParams()
        self.strategy = MeanReversionStrategy(self.params)

    def _simulate(
        self,
        symbol: str,
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """일봉 기반 시뮬레이션.

        Args:
            symbol: 종목코드 (빈 문자열 가능)
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            BacktestResult: 백테스트 결과
        """
        min_bars = max(self.params.rsi_period + 1, self.params.bb_period)

        if len(daily_data) < min_bars:
            logger.warning(
                "일봉 데이터 부족",
                required=min_bars,
                got=len(daily_data),
            )
            return BacktestResult(params=self.params, metrics=calc_metrics([]))

        positions: list[Position] = []
        trades: list[TradeRecord] = []

        for i, bar in enumerate(daily_data):
            # lookahead bias 방지: 현재 봉까지만 사용
            history = daily_data[: i + 1]

            # 포지션 peak_price 갱신
            for pos in positions:
                pos.update_peak(bar.high)

            # 청산 체크 (지표 기반: SL/TP + RSI 과매수 + BB 중심선 회귀)
            closed: list[Position] = []
            for pos in positions:
                exit_reason = self.strategy.check_exit_with_indicators(
                    pos.entry_price, bar.close, history
                )
                if exit_reason:
                    pnl = self._calc_trade_pnl(pos.entry_price, bar.close)
                    trades.append(
                        TradeRecord(
                            symbol=pos.symbol,
                            entry_time=pos.entry_time,
                            exit_time=bar.date,
                            entry_price=pos.entry_price,
                            exit_price=bar.close,
                            side="BUY",
                            pnl_pct=round(pnl, 6),
                            exit_reason=exit_reason,
                        )
                    )
                    closed.append(pos)

            for pos in closed:
                positions.remove(pos)

            # 진입 체크
            if len(positions) < self.params.max_positions and self.strategy.check_entry_signal(
                daily=history,
                current_price=bar.close,
                current_volume=bar.volume,
                time_ratio=1.0,
            ):
                positions.append(
                    Position(
                        symbol=symbol,
                        entry_time=bar.date,
                        entry_price=bar.close,
                    )
                )

        # 미청산 포지션 강제 청산
        if positions and daily_data:
            last_bar = daily_data[-1]
            for pos in positions:
                pnl = self._calc_trade_pnl(pos.entry_price, last_bar.close)
                trades.append(
                    TradeRecord(
                        symbol=pos.symbol,
                        entry_time=pos.entry_time,
                        exit_time=last_bar.date,
                        entry_price=pos.entry_price,
                        exit_price=last_bar.close,
                        side="BUY",
                        pnl_pct=round(pnl, 6),
                        exit_reason="force_close",
                    )
                )

        metrics = calc_metrics(trades)
        return BacktestResult(trades=trades, metrics=metrics, params=self.params)

    def run(self, daily_data: list[DailyPrice]) -> BacktestResult:
        """백테스트 실행.

        Args:
            daily_data: 일봉 데이터 (날짜 오름차순, 최소 20봉)

        Returns:
            BacktestResult: 백테스트 결과
        """
        return self._simulate("", daily_data)

    def run_with_symbol(self, symbol: str, daily_data: list[DailyPrice]) -> BacktestResult:
        """심볼 지정 백테스트 실행.

        Args:
            symbol: 종목코드
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            BacktestResult: 백테스트 결과
        """
        return self._simulate(symbol, daily_data)

    def _calc_trade_pnl(self, entry_price: int, exit_price: int) -> float:
        """거래 손익률 계산 (수수료/세금 차감)."""
        if entry_price <= 0:
            return 0.0
        gross_pnl = (exit_price - entry_price) / entry_price
        total_cost = self.params.commission_rate * 2 + self.params.tax_rate
        return gross_pnl - total_cost
