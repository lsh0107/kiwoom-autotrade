"""시장 분석기 — 데이터 → LLM → 시그널."""

import structlog

from src.ai.analysis.models import AnalysisContext, TradingSignal
from src.ai.data.aggregator import AggregatedData, format_for_llm
from src.ai.llm.manager import LLMManager
from src.ai.llm.prompts import MARKET_ANALYSIS_PROMPT, SYSTEM_MARKET_ANALYST
from src.ai.llm.provider import LLMRequest, LLMResponse

logger = structlog.get_logger(__name__)


async def analyze_symbol(
    *,
    llm: LLMManager,
    data: AggregatedData,
    context: AnalysisContext,  # noqa: ARG001
) -> tuple[TradingSignal, LLMResponse]:
    """종목 분석 → 시그널 생성."""
    formatted = format_for_llm(data)

    prompt = MARKET_ANALYSIS_PROMPT.format(**formatted)

    request = LLMRequest(
        system_prompt=SYSTEM_MARKET_ANALYST,
        user_prompt=prompt,
        temperature=0.3,
        max_tokens=2000,
    )

    signal, response = await llm.complete_json(
        request,
        TradingSignal,
        mode="quick",
    )

    # symbol 보정 (LLM이 다르게 응답할 수 있음)
    if isinstance(signal, TradingSignal):
        signal.symbol = data.symbol

    await logger.ainfo(
        "종목 분석 완료",
        symbol=data.symbol,
        action=signal.action,
        confidence=signal.confidence,
        provider=response.provider,
        cost=response.cost_usd,
    )

    return signal, response
