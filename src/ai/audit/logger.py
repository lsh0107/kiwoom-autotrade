"""LLM 결정 감사 추적."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.analysis.models import TradingSignal
from src.ai.llm.provider import LLMResponse
from src.models.ai import AISignal, LLMCallLog

logger = structlog.get_logger(__name__)


async def log_llm_call(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    response: LLMResponse,
    prompt_type: str,
    strategy_id: uuid.UUID | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> LLMCallLog:
    """LLM API 호출 로그 저장."""
    log_entry = LLMCallLog(
        user_id=user_id,
        strategy_id=strategy_id,
        provider=response.provider,
        model=response.model,
        prompt_type=prompt_type,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        success=success,
        error_message=error_message,
        latency_ms=response.latency_ms,
    )
    db.add(log_entry)

    await logger.ainfo(
        "LLM 호출 기록",
        provider=response.provider,
        model=response.model,
        prompt_type=prompt_type,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
    )

    return log_entry


async def log_signal(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    signal: TradingSignal,
    strategy_id: uuid.UUID | None = None,
    is_executed: bool = False,
    order_id: uuid.UUID | None = None,
    rejection_reason: str | None = None,
    raw_analysis: dict | None = None,
) -> AISignal:
    """AI 시그널 저장."""
    ai_signal = AISignal(
        user_id=user_id,
        strategy_id=strategy_id,
        symbol=signal.symbol,
        action=signal.action,
        confidence=signal.confidence,
        target_price=signal.target_price,
        position_size_pct=signal.position_size_pct,
        risk_level=signal.risk_level,
        reasoning=signal.reasoning,
        raw_analysis=raw_analysis or {},
        is_executed=is_executed,
        order_id=order_id,
        rejection_reason=rejection_reason,
    )
    db.add(ai_signal)

    await logger.ainfo(
        "AI 시그널 기록",
        symbol=signal.symbol,
        action=signal.action,
        confidence=signal.confidence,
        is_executed=is_executed,
        rejection_reason=rejection_reason,
    )

    return ai_signal
