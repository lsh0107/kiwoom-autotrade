"""AI 분석 모델 (AnalysisContext, TradingSignal)."""

from typing import Literal

from pydantic import BaseModel, Field


class TradingSignal(BaseModel):
    """매매 시그널."""

    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)
    target_price: int | None = None
    position_size_pct: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"


class AnalysisContext(BaseModel):
    """분석 컨텍스트."""

    symbol: str
    name: str = ""
    available_cash: int = 0
    current_holdings: list[dict] = Field(default_factory=list)
    daily_pnl: int = 0
