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

    def run(
        self,
        minute_data: list[MinutePrice],
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """백테스트 실행.

        daily_data에서 52주 최고가와 평균 거래량을 계산하고,
        minute_data를 시간순으로 재생하며 전략을 적용한다.

        Args:
            minute_data: 분봉 데이터 (시간 오름차순)
            daily_data: 일봉 데이터 (날짜 오름차순, 52주 이상 권장)

        Returns:
            BacktestResult: 백테스트 결과
        """
        if not minute_data:
            logger.warning("분봉 데이터 없음, 빈 결과 반환")
            return BacktestResult(params=self.params, metrics=calc_metrics([]))

        # 일봉에서 52주 최고가 + 평균 거래량 계산
        high_52w = self._calc_52w_high(daily_data)
        avg_volume = self._calc_avg_volume(daily_data)

        logger.info(
            "백테스트 시작",
            bars=len(minute_data),
            daily_bars=len(daily_data),
            high_52w=high_52w,
            avg_volume=avg_volume,
        )

        positions: list[Position] = []
        trades: list[TradeRecord] = []
        symbol = self._extract_symbol()

        # 날짜별 누적 거래량 추적 (5분봉 단일 거래량 → 당일 누적으로 변환)
        cumulative_volume = 0
        current_date = ""

        for bar in minute_data:
            bar_time = extract_time_from_bar(bar)

            # 날짜 변경 시 누적 거래량 리셋
            bar_date = bar.datetime[:8]  # YYYYMMDD
            if bar_date != current_date:
                cumulative_volume = 0
                current_date = bar_date
            cumulative_volume += bar.volume

            # 1. 기존 포지션 청산 체크
            closed_positions: list[Position] = []
            for pos in positions:
                exit_reason = check_exit_signal(pos.entry_price, bar.close, bar_time, self.params)
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

            # 2. 신규 진입 체크 (최대 포지션 미만일 때만, 당일 누적 거래량 사용)
            if len(positions) < self.params.max_positions and check_entry_signal(
                bar.close, high_52w, cumulative_volume, avg_volume, self.params
            ):
                positions.append(
                    Position(
                        symbol=symbol,
                        entry_time=bar.datetime,
                        entry_price=bar.close,
                    )
                )

        # 3. 미청산 포지션 강제 청산 (마지막 바 기준)
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

        logger.info(
            "백테스트 완료",
            total_trades=metrics.get("total_trades", 0),
            win_rate=metrics.get("win_rate", 0),
            max_drawdown=metrics.get("max_drawdown", 0),
        )

        return BacktestResult(
            trades=trades,
            metrics=metrics,
            params=self.params,
        )

    @staticmethod
    def _calc_52w_high(daily_data: list[DailyPrice]) -> int:
        """일봉 데이터에서 52주(약 250거래일) 최고가 계산.

        Args:
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            int: 52주 최고가 (데이터 없으면 0)
        """
        if not daily_data:
            return 0
        # 최근 250거래일 (약 52주)
        recent = daily_data[-250:] if len(daily_data) > 250 else daily_data
        return max(bar.high for bar in recent)

    @staticmethod
    def _calc_avg_volume(daily_data: list[DailyPrice]) -> int:
        """일봉 데이터에서 최근 20일 평균 거래량 계산.

        Args:
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            int: 평균 거래량 (데이터 없으면 0)
        """
        if not daily_data:
            return 0
        recent = daily_data[-20:] if len(daily_data) > 20 else daily_data
        total = sum(bar.volume for bar in recent)
        return total // len(recent)

    @staticmethod
    def _extract_symbol() -> str:
        """심볼 추출 (현재는 빈 문자열 반환).

        MinutePrice에 symbol 필드가 없으므로 빈 문자열 반환.
        실제 사용 시 run_with_symbol()을 사용한다.

        Returns:
            str: 심볼 (빈 문자열)
        """
        return ""

    def run_with_symbol(
        self,
        symbol: str,
        minute_data: list[MinutePrice],
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """심볼 지정 백테스트 실행.

        run()과 동일하되 거래 기록에 심볼이 포함된다.

        Args:
            symbol: 종목코드
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

        positions: list[Position] = []
        trades: list[TradeRecord] = []

        # 날짜별 누적 거래량 추적 (5분봉 단일 거래량 → 당일 누적으로 변환)
        cumulative_volume = 0
        current_date = ""

        for bar in minute_data:
            bar_time = extract_time_from_bar(bar)

            # 날짜 변경 시 누적 거래량 리셋
            bar_date = bar.datetime[:8]  # YYYYMMDD
            if bar_date != current_date:
                cumulative_volume = 0
                current_date = bar_date
            cumulative_volume += bar.volume

            # 청산 체크
            closed_positions: list[Position] = []
            for pos in positions:
                exit_reason = check_exit_signal(pos.entry_price, bar.close, bar_time, self.params)
                if exit_reason:
                    pnl = calc_trade_pnl(pos.entry_price, bar.close, self.params)
                    trades.append(
                        TradeRecord(
                            symbol=symbol,
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

            # 진입 체크 (당일 누적 거래량 사용)
            if len(positions) < self.params.max_positions and check_entry_signal(
                bar.close, high_52w, cumulative_volume, avg_volume, self.params
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
                        symbol=symbol,
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

        return BacktestResult(
            trades=trades,
            metrics=metrics,
            params=self.params,
        )
