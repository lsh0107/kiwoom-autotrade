"""시장 분석기 — 데이터 → LLM → 시그널."""

import structlog

from src.ai.analysis.models import AnalysisContext, TradingSignal
from src.ai.data.aggregator import AggregatedData, format_for_llm
from src.ai.llm.manager import LLMManager
from src.ai.llm.prompts import build_analysis_prompt, build_system_prompt
from src.ai.llm.provider import LLMRequest, LLMResponse

logger = structlog.get_logger(__name__)


async def analyze_symbol(
    *,
    llm: LLMManager,
    data: AggregatedData,
    context: AnalysisContext,
) -> tuple[TradingSignal, LLMResponse]:
    """종목 분석 → 시그널 생성.

    context.regime이 설정되어 있으면 레짐에 맞는 프롬프트를 사용한다.
    """
    formatted = format_for_llm(data)
    regime = context.regime

    system_prompt = build_system_prompt(regime)
    prompt = build_analysis_prompt(formatted, regime)

    request = LLMRequest(
        system_prompt=system_prompt,
        user_prompt=prompt,
        temperature=0.3,
        max_tokens=2000,
    )

    parsed, response = await llm.complete_json(
        request,
        TradingSignal,
        mode="quick",
    )
    signal = TradingSignal.model_validate(parsed.model_dump())

    # symbol 보정 (LLM이 다르게 응답할 수 있음)
    signal.symbol = data.symbol

    await logger.ainfo(
        "종목 분석 완료",
        symbol=data.symbol,
        action=signal.action,
        confidence=signal.confidence,
        regime=regime,
        provider=response.provider,
        cost=response.cost_usd,
    )

    return signal, response
