"""백테스트 결과 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.backtest.strategy import MomentumParams


@dataclass
class TradeRecord:
    """개별 거래 기록."""

    symbol: str
    entry_time: str
    exit_time: str
    entry_price: int
    exit_price: int
    side: str  # "BUY"
    pnl_pct: float  # 수수료 차감 후 손익률
    exit_reason: str  # "stop_loss" | "take_profit" | "force_close"


@dataclass
class BacktestResult:
    """백테스트 실행 결과."""

    trades: list[TradeRecord] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    params: MomentumParams | None = None
