"""레짐 연동 프롬프트 테스트."""

from unittest.mock import AsyncMock, patch

from src.ai.analysis.analyzer import analyze_symbol
from src.ai.analysis.models import AnalysisContext, TradingSignal
from src.ai.data.aggregator import AggregatedData
from src.ai.data.market_collector import DailyPrice
from src.ai.llm.prompts import (
    SYSTEM_MARKET_ANALYST,
    build_analysis_prompt,
    build_system_prompt,
)
from src.ai.llm.provider import LLMRequest, LLMResponse
from src.broker.schemas import Quote


def _formatted_data() -> dict[str, str | int | float]:
    return {
        "symbol": "005930",
        "name": "삼성전자",
        "price": 70000,
        "change": 1000,
        "change_pct": 1.45,
        "volume": 10_000_000,
        "high": 71000,
        "low": 69000,
        "daily_prices": "  20260303: 시69,000 종70,000\n",
        "disclosures": "  없음\n",
        "overseas_data": "  데이터 없음",
    }


# ── build_system_prompt ──


class TestBuildSystemPrompt:
    """레짐별 시스템 프롬프트 테스트."""

    def test_no_regime_returns_base(self) -> None:
        """레짐 없으면 기본 시스템 프롬프트."""
        result = build_system_prompt(None)
        assert result == SYSTEM_MARKET_ANALYST

    def test_unknown_regime_returns_base(self) -> None:
        """알 수 없는 레짐은 기본."""
        result = build_system_prompt("unknown")
        assert result == SYSTEM_MARKET_ANALYST

    def test_aggressive_regime(self) -> None:
        """공격 레짐 → 적극적 매수 지시."""
        result = build_system_prompt("aggressive")
        assert "공격 레짐" in result
        assert "적극적 매수" in result
        assert "0.15~0.25" in result

    def test_neutral_regime(self) -> None:
        """중립 레짐 → 균형 분석."""
        result = build_system_prompt("neutral")
        assert "중립 레짐" in result
        assert "0.10~0.15" in result

    def test_defensive_regime(self) -> None:
        """방어 레짐 → 보수적 분석."""
        result = build_system_prompt("defensive")
        assert "방어 레짐" in result
        assert "보수적" in result
        assert "0.05~0.10" in result

    def test_crisis_regime(self) -> None:
        """위기 레짐 → 매수 금지."""
        result = build_system_prompt("crisis")
        assert "위기 레짐" in result
        assert "BUY는 금지" in result  # 신규 BUY 금지
        assert "자본 보전" in result


# ── build_analysis_prompt ──


class TestBuildAnalysisPrompt:
    """레짐별 분석 프롬프트 테스트."""

    def test_no_regime_no_block(self) -> None:
        """레짐 없으면 레짐 블록 없음."""
        result = build_analysis_prompt(_formatted_data(), None)
        assert "시장 레짐" not in result
        assert "005930" in result

    def test_aggressive_includes_block(self) -> None:
        """공격 레짐 블록 삽입."""
        result = build_analysis_prompt(_formatted_data(), "aggressive")
        assert "시장 레짐: 공격 (AGGRESSIVE)" in result
        assert "모멘텀 55%" in result

    def test_neutral_includes_block(self) -> None:
        """중립 레짐 블록 삽입."""
        result = build_analysis_prompt(_formatted_data(), "neutral")
        assert "시장 레짐: 중립 (NEUTRAL)" in result
        assert "모멘텀 40%" in result

    def test_defensive_includes_block(self) -> None:
        """방어 레짐 블록 삽입."""
        result = build_analysis_prompt(_formatted_data(), "defensive")
        assert "시장 레짐: 방어 (DEFENSIVE)" in result
        assert "현금 35%" in result

    def test_crisis_includes_block(self) -> None:
        """위기 레짐 블록 삽입."""
        result = build_analysis_prompt(_formatted_data(), "crisis")
        assert "시장 레짐: 위기 (CRISIS)" in result
        assert "100% 현금" in result

    def test_regime_block_before_analysis_section(self) -> None:
        """레짐 블록이 '분석 지시' 앞에 위치."""
        result = build_analysis_prompt(_formatted_data(), "aggressive")
        regime_pos = result.index("시장 레짐")
        analysis_pos = result.index("## 분석 지시")
        assert regime_pos < analysis_pos

    def test_unknown_regime_no_block(self) -> None:
        """알 수 없는 레짐이면 블록 미삽입."""
        result = build_analysis_prompt(_formatted_data(), "invalid")
        assert "시장 레짐" not in result


# ── analyze_symbol with regime ──


def _make_aggregated_data() -> AggregatedData:
    return AggregatedData(
        symbol="005930",
        quote=Quote(
            symbol="005930",
            name="삼성전자",
            price=70000,
            change=1000,
            change_pct=1.45,
            volume=10_000_000,
            high=71000,
            low=69000,
            open=69500,
            prev_close=69000,
        ),
        daily_prices=[
            DailyPrice(
                date="20260303",
                open=69000,
                high=71000,
                low=68500,
                close=70000,
                volume=10_000_000,
                change_pct=1.45,
            ),
        ],
        disclosures=[],
        overseas_indices=[],
    )


class TestAnalyzeSymbolWithRegime:
    """analyze_symbol의 레짐 전달 테스트."""

    async def test_regime_injected_into_system_prompt(self) -> None:
        """context.regime이 시스템 프롬프트에 반영."""
        data = _make_aggregated_data()
        context = AnalysisContext(
            symbol="005930",
            name="삼성전자",
            available_cash=5_000_000,
            regime="aggressive",
        )

        mock_signal = TradingSignal(symbol="005930", action="BUY", confidence=0.8)
        mock_response = LLMResponse(content="결과", provider="openai", model="gpt-4o-mini")
        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (mock_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_formatted_data(),
        ):
            await analyze_symbol(llm=mock_llm, data=data, context=context)

        request: LLMRequest = mock_llm.complete_json.call_args.args[0]
        assert "공격 레짐" in request.system_prompt
        assert "적극적 매수" in request.system_prompt

    async def test_regime_injected_into_user_prompt(self) -> None:
        """context.regime이 사용자 프롬프트(분석 프롬프트)에 반영."""
        data = _make_aggregated_data()
        context = AnalysisContext(
            symbol="005930",
            name="삼성전자",
            available_cash=5_000_000,
            regime="defensive",
        )

        mock_signal = TradingSignal(symbol="005930", action="HOLD", confidence=0.4)
        mock_response = LLMResponse(content="결과", provider="openai", model="gpt-4o-mini")
        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (mock_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_formatted_data(),
        ):
            await analyze_symbol(llm=mock_llm, data=data, context=context)

        request: LLMRequest = mock_llm.complete_json.call_args.args[0]
        assert "시장 레짐: 방어 (DEFENSIVE)" in request.user_prompt

    async def test_no_regime_keeps_base_prompts(self) -> None:
        """regime=None이면 기본 프롬프트 사용."""
        data = _make_aggregated_data()
        context = AnalysisContext(
            symbol="005930",
            name="삼성전자",
            available_cash=5_000_000,
        )

        mock_signal = TradingSignal(symbol="005930", action="HOLD", confidence=0.5)
        mock_response = LLMResponse(content="결과", provider="openai", model="gpt-4o-mini")
        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (mock_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_formatted_data(),
        ):
            await analyze_symbol(llm=mock_llm, data=data, context=context)

        request: LLMRequest = mock_llm.complete_json.call_args.args[0]
        assert request.system_prompt == SYSTEM_MARKET_ANALYST
        assert "시장 레짐" not in request.user_prompt

    async def test_crisis_regime_in_prompt(self) -> None:
        """위기 레짐이 프롬프트에 반영."""
        data = _make_aggregated_data()
        context = AnalysisContext(
            symbol="005930",
            name="삼성전자",
            available_cash=5_000_000,
            regime="crisis",
        )

        mock_signal = TradingSignal(symbol="005930", action="HOLD", confidence=0.3)
        mock_response = LLMResponse(content="결과", provider="openai", model="gpt-4o-mini")
        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (mock_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_formatted_data(),
        ):
            await analyze_symbol(llm=mock_llm, data=data, context=context)

        request: LLMRequest = mock_llm.complete_json.call_args.args[0]
        assert "위기 레짐" in request.system_prompt
        assert "BUY는 금지" in request.system_prompt  # 신규 BUY 금지
        assert "시장 레짐: 위기 (CRISIS)" in request.user_prompt
