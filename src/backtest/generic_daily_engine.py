"""일봉 다중 전략 백테스트 엔진 — Strategy Protocol 기반.

Pullback / Range / MeanReversion 등 Strategy Protocol 구현체를
일봉 데이터로 bar-by-bar 시뮬레이션한다.

신호: 당일 종가 기준 (look-ahead 없음) → 체결: 익일 시가 (슬리피지 적용).
기존 DailyBacktestEngine(momentum_daily 전용)과 독립 파일로 분리해 하위 호환 유지.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from src.backtest.metrics import calc_metrics
from src.backtest.result import BacktestResult, TradeRecord
from src.backtest.slippage import apply_slippage
from src.broker.schemas import DailyPrice
from src.strategy.base import Strategy

logger = structlog.get_logger("backtest.generic_daily_engine")

# 최소 데이터 요건 기본 여유분 (전략 lookback 이후)
_DEFAULT_MIN_BARS = 25


@dataclass
class GenericPosition:
    """일봉 포지션 추적 (Generic Engine 전용)."""

    symbol: str
    entry_date: str
    entry_price: int
    holding_days: int = 0
    peak_price: int = 0
    entry_snapshot: list[DailyPrice] = field(default_factory=list)

    def __post_init__(self) -> None:
        """초기 peak_price를 entry_price로 설정."""
        if self.peak_price == 0:
            self.peak_price = self.entry_price

    def update_peak(self, price: int) -> None:
        """최고가 갱신."""
        if price > self.peak_price:
            self.peak_price = price


class GenericDailyEngine:
    """Strategy Protocol 기반 일봉 백테스트 엔진.

    bar-by-bar 시뮬레이션:
    - 신호: 당일 종가 기준 (prior_daily + today.close + today.volume, time_ratio=1.0)
    - 체결: 익일 시가 (슬리피지 적용)
    - 청산: check_exit_signal → check_exit_with_indicators(선택) → max_holding_days
    - MDD: 미실현 손익 포함 equity curve 기반

    Pullback / Range / MeanReversion 전략 모두 호환.
    """

    def __init__(
        self,
        strategy: Strategy,
        *,
        max_positions: int = 1,
        max_holding_days: int = 20,
        min_bars: int = _DEFAULT_MIN_BARS,
    ) -> None:
        """초기화.

        Args:
            strategy: Strategy Protocol 구현체 (Pullback / Range / MR 등)
            max_positions: 최대 동시 포지션 수
            max_holding_days: 최대 보유 거래일 (타임컷)
            min_bars: 최소 데이터 요건 (전략 lookback + 여유분)
        """
        self.strategy = strategy
        self.max_positions = max_positions
        self.max_holding_days = max_holding_days
        self.min_bars = min_bars

        # 전략 params에서 거래비용 추출
        p = getattr(strategy, "params", None)
        self.commission_rate: float = float(getattr(p, "commission_rate", 0.00015))
        self.tax_rate: float = float(getattr(p, "tax_rate", 0.0020))
        self.slippage_pct: float = float(getattr(p, "slippage_pct", 0.0))

    def _calc_pnl(self, entry_price: int, exit_price: int) -> float:
        """순손익률 계산 (수수료 x 2 + 거래세 차감).

        Args:
            entry_price: 진입가
            exit_price: 청산가

        Returns:
            float: 순손익률
        """
        if entry_price <= 0:
            return 0.0
        gross = (exit_price - entry_price) / entry_price
        cost = self.commission_rate * 2 + self.tax_rate
        return gross - cost

    def _check_exit(
        self,
        pos: GenericPosition,
        today_close: int,
        prior_daily: list[DailyPrice],
    ) -> str | None:
        """청산 신호 우선순위 체크.

        1. 기본 stop_loss / take_profit (check_exit_signal)
        2. 지표 기반 청산 (check_exit_with_indicators — 전략별 선택 구현)
        3. 최대 보유일 타임컷

        Args:
            pos: 현재 포지션
            today_close: 당일 종가
            prior_daily: 당일 이전 일봉 데이터 (look-ahead 방지)

        Returns:
            str | None: 청산 사유 또는 None
        """
        # 1. 기본 청산 (stop_loss / take_profit)
        reason = self.strategy.check_exit_signal(
            pos.entry_price,
            today_close,
            pos.peak_price,
        )
        if reason:
            return reason

        # 2. 지표 기반 청산 (선택 구현 — Range/MR만 있음)
        exit_with_ind = getattr(self.strategy, "check_exit_with_indicators", None)
        if exit_with_ind is not None and callable(exit_with_ind):
            ind_reason: str | None = exit_with_ind(pos.entry_price, today_close, prior_daily)
            if ind_reason:
                return ind_reason

        # 3. 최대 보유일 타임컷
        if pos.holding_days >= self.max_holding_days:
            return "max_holding"

        return None

    def run(
        self,
        symbol: str,
        daily_data: list[DailyPrice],
    ) -> BacktestResult:
        """일봉 백테스트 실행.

        Args:
            symbol: 종목코드
            daily_data: 일봉 데이터 (날짜 오름차순)

        Returns:
            BacktestResult: 백테스트 결과
        """
        strategy_params = getattr(self.strategy, "params", None)

        if len(daily_data) < self.min_bars:
            logger.warning(
                "일봉 데이터 부족 — 빈 결과 반환",
                symbol=symbol,
                strategy=self.strategy.name,
                bars=len(daily_data),
                required=self.min_bars,
            )
            return BacktestResult(params=strategy_params, metrics=calc_metrics([]))

        positions: list[GenericPosition] = []
        pending_entry = False  # 익일 시가 진입 대기 플래그
        pending_snapshot: list[DailyPrice] = []  # 진입 시 prior_daily 스냅샷

        trades: list[TradeRecord] = []
        equity = 1.0
        equity_curve: list[float] = []
        fraction = 1.0 / max(self.max_positions, 1)

        n = len(daily_data)

        for i in range(1, n):
            today = daily_data[i]
            prior_daily = daily_data[:i]  # look-ahead 방지: 당일 이전만

            # ── 1. 전일 신호 → 오늘 시가 체결 ─────────────────────────────
            if pending_entry and len(positions) < self.max_positions:
                entry_fill = apply_slippage(
                    today.open,
                    "BUY",
                    self.slippage_pct,
                    bar_high=today.high,
                    bar_low=today.low,
                )
                positions.append(
                    GenericPosition(
                        symbol=symbol,
                        entry_date=today.date,
                        entry_price=entry_fill,
                        entry_snapshot=pending_snapshot,
                    )
                )
                logger.debug(
                    "진입 체결",
                    symbol=symbol,
                    strategy=self.strategy.name,
                    date=today.date,
                    price=entry_fill,
                )

            pending_entry = False
            pending_snapshot = []

            # ── 2. 보유 포지션 갱신 ────────────────────────────────────────
            for pos in positions:
                pos.update_peak(today.high)
                pos.holding_days += 1

            # ── 3. 청산 체크 ───────────────────────────────────────────────
            closed: list[GenericPosition] = []
            for pos in positions:
                exit_reason = self._check_exit(pos, today.close, prior_daily)
                if exit_reason:
                    exit_fill = apply_slippage(
                        today.close,
                        "SELL",
                        self.slippage_pct,
                        bar_high=today.high,
                        bar_low=today.low,
                    )
                    pnl = self._calc_pnl(pos.entry_price, exit_fill)
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
                        strategy=self.strategy.name,
                        date=today.date,
                        reason=exit_reason,
                        pnl=f"{pnl:.4f}",
                    )

            for pos in closed:
                positions.remove(pos)

            # ── 4. 진입 신호 확인 (오늘 종가 → 내일 시가 체결) ──────────
            if (
                len(positions) < self.max_positions
                and not pending_entry
                and self.strategy.check_entry_signal(
                    prior_daily,
                    today.close,
                    today.volume,
                    1.0,  # time_ratio=1.0: 일봉 장 마감 기준 어댑터
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
                    self.slippage_pct,
                    bar_high=last.high,
                    bar_low=last.low,
                )
                pnl = self._calc_pnl(pos.entry_price, exit_fill)
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
        return BacktestResult(trades=trades, metrics=metrics, params=strategy_params)
