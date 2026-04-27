"""일봉 모멘텀 백테스트 엔진.

일봉 데이터로 bar-by-bar 시뮬레이션.
신호는 당일 종가 기준, 체결은 익일 시가로 처리 (look-ahead bias 방지).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from src.backtest.metrics import calc_metrics
from src.backtest.result import BacktestResult, TradeRecord
from src.backtest.slippage import apply_slippage
from src.broker.schemas import DailyPrice
from src.strategy.momentum_daily import (
    DailyMomentumParams,
    calc_daily_trade_pnl,
    check_daily_entry_signal,
    check_daily_exit_signal,
)

logger = structlog.get_logger("backtest.daily_engine")

# 일봉 엔진 최소 데이터 요건 (lookback + 여유분)
_MIN_BARS_EXTRA = 5


@dataclass
class DailyPosition:
    """일봉 포지션 추적."""

    symbol: str
    entry_date: str
    entry_price: int
    holding_days: int = 0
    peak_price: int = 0
    entry_daily_snapshot: list[DailyPrice] = field(default_factory=list)

    def __post_init__(self) -> None:
        """초기 peak_price를 entry_price로 설정."""
        if self.peak_price == 0:
            self.peak_price = self.entry_price

    def update_peak(self, price: int) -> None:
        """최고가 갱신."""
        if price > self.peak_price:
            self.peak_price = price


class DailyBacktestEngine:
    """일봉 모멘텀 백테스트 엔진.

    bar-by-bar 시뮬레이션:
    - 신호: 당일 종가 기준 (prior_daily로 지표 계산 — look-ahead 없음)
    - 체결: 익일 시가 (슬리피지 0.15% 기본 적용)
    - MDD: 미실현 손익 포함 equity curve 기반
    """

    def __init__(self, params: DailyMomentumParams | None = None) -> None:
        """초기화.

        Args:
            params: 전략 파라미터 (None이면 기본값)
        """
        self.params = params or DailyMomentumParams()

    def run(
        self,
        symbol: str,
        daily_data: list[DailyPrice],
        kospi_daily: list[DailyPrice] | None = None,
    ) -> BacktestResult:
        """일봉 백테스트 실행.

        Args:
            symbol: 종목코드
            daily_data: 일봉 데이터 (날짜 오름차순)
            kospi_daily: KOSPI 지수 일봉 (날짜 오름차순, None이면 KOSPI 필터 미적용)

        Returns:
            BacktestResult: 백테스트 결과
        """
        min_bars = self.params.lookback + _MIN_BARS_EXTRA
        if len(daily_data) < min_bars:
            logger.warning(
                "일봉 데이터 부족 — 빈 결과 반환",
                symbol=symbol,
                bars=len(daily_data),
                required=min_bars,
            )
            return BacktestResult(params=self.params, metrics=calc_metrics([]))

        positions: list[DailyPosition] = []
        pending_entry = False  # 익일 시가 진입 대기 플래그
        pending_snapshot: list[DailyPrice] = []  # 진입 시 사용할 prior_daily 스냅샷

        trades: list[TradeRecord] = []
        equity = 1.0  # 실현 자산 (1.0 = 초기 자본)
        equity_curve: list[float] = []
        fraction = 1.0 / max(self.params.max_positions, 1)

        n = len(daily_data)

        for i in range(1, n):
            today = daily_data[i]
            prior_daily = daily_data[:i]  # 당일 이전 데이터 (look-ahead 방지)

            # KOSPI 필터용: 오늘 날짜 이전 데이터만 사용
            kospi_prior: list[DailyPrice] | None = None
            if kospi_daily:
                kospi_prior = [b for b in kospi_daily if b.date < today.date]

            # ── 1. 전일 신호 → 오늘 시가 체결 ─────────────────────────────
            if pending_entry and len(positions) < self.params.max_positions:
                entry_fill = apply_slippage(
                    today.open,
                    "BUY",
                    self.params.slippage_pct,
                    bar_high=today.high,
                    bar_low=today.low,
                )
                positions.append(
                    DailyPosition(
                        symbol=symbol,
                        entry_date=today.date,
                        entry_price=entry_fill,
                        entry_daily_snapshot=pending_snapshot,
                    )
                )
                logger.debug("진입 체결", symbol=symbol, date=today.date, price=entry_fill)
            pending_entry = False
            pending_snapshot = []

            # ── 2. 보유 포지션 갱신 ────────────────────────────────────────
            for pos in positions:
                pos.update_peak(today.high)
                pos.holding_days += 1

            # ── 3. 청산 체크 ───────────────────────────────────────────────
            closed: list[DailyPosition] = []
            for pos in positions:
                exit_reason = check_daily_exit_signal(
                    entry_price=pos.entry_price,
                    current_close=today.close,
                    peak_price=pos.peak_price,
                    holding_days=pos.holding_days,
                    prior_daily=pos.entry_daily_snapshot,
                    params=self.params,
                )
                if exit_reason:
                    exit_fill = apply_slippage(
                        today.close,
                        "SELL",
                        self.params.slippage_pct,
                        bar_high=today.high,
                        bar_low=today.low,
                    )
                    pnl = calc_daily_trade_pnl(pos.entry_price, exit_fill, self.params)
                    equity *= 1.0 + pnl
                    trades.append(
                        TradeRecord(
                            symbol=pos.symbol,
                            entry_time=pos.entry_date,
                            exit_time=today.date,
                            entry_price=pos.entry_price,
                            exit_price=exit_fill,
                            side="BUY",
                            pnl_pct=round(pnl, 6),
                            exit_reason=exit_reason,
                        )
                    )
                    closed.append(pos)
                    logger.debug(
                        "청산",
                        symbol=symbol,
                        date=today.date,
                        reason=exit_reason,
                        pnl=f"{pnl:.4f}",
                    )

            for pos in closed:
                positions.remove(pos)

            # ── 4. 진입 신호 확인 (오늘 종가 → 내일 시가 체결) ──────────
            if (
                len(positions) < self.params.max_positions
                and not pending_entry
                and check_daily_entry_signal(
                    prior_daily=prior_daily,
                    today_close=today.close,
                    today_volume=today.volume,
                    params=self.params,
                    kospi_prior=kospi_prior,
                )
            ):
                pending_entry = True
                pending_snapshot = list(prior_daily)

            # ── 5. 자산 곡선 스냅샷 (미실현 손익 포함) ───────────────────
            unrealized = sum(
                fraction * (today.close - pos.entry_price) / pos.entry_price
                for pos in positions
                if pos.entry_price > 0
            )
            equity_curve.append(equity * (1.0 + unrealized))

        # ── 미청산 포지션 강제 청산 (마지막 바 종가) ─────────────────────
        if positions and daily_data:
            last = daily_data[-1]
            for pos in positions:
                exit_fill = apply_slippage(
                    last.close,
                    "SELL",
                    self.params.slippage_pct,
                    bar_high=last.high,
                    bar_low=last.low,
                )
                pnl = calc_daily_trade_pnl(pos.entry_price, exit_fill, self.params)
                trades.append(
                    TradeRecord(
                        symbol=pos.symbol,
                        entry_time=pos.entry_date,
                        exit_time=last.date,
                        entry_price=pos.entry_price,
                        exit_price=exit_fill,
                        side="BUY",
                        pnl_pct=round(pnl, 6),
                        exit_reason="force_close",
                    )
                )

        metrics = calc_metrics(trades, equity_curve=equity_curve)
        return BacktestResult(trades=trades, metrics=metrics, params=self.params)
