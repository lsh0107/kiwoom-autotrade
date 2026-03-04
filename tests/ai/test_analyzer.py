"""시장 분석기 테스트."""

from unittest.mock import AsyncMock, patch

from src.ai.analysis.analyzer import analyze_symbol
from src.ai.analysis.models import AnalysisContext, TradingSignal
from src.ai.data.aggregator import AggregatedData
from src.ai.data.market_collector import DailyPrice
from src.ai.llm.provider import LLMRequest, LLMResponse
from src.broker.schemas import Quote


def _make_aggregated_data() -> AggregatedData:
    """테스트용 AggregatedData 생성."""
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


def _make_formatted_data() -> dict[str, str]:
    """format_for_llm이 반환할 정수 포함 딕셔너리 (프롬프트 포맷팅 호환)."""
    return {
        "symbol": "005930",
        "name": "삼성전자",
        "price": 70000,
        "change": 1000,
        "change_pct": 1.45,
        "volume": 10_000_000,
        "high": 71000,
        "low": 69000,
        "daily_prices": "  20260303: 시69,000 고71,000 저68,500 종70,000 량10,000,000 (+1.45%)\n",
        "disclosures": "  최근 7일 내 공시 없음\n",
        "overseas_data": "  데이터 없음",
    }


def _make_context() -> AnalysisContext:
    """테스트용 AnalysisContext 생성."""
    return AnalysisContext(
        symbol="005930",
        name="삼성전자",
        available_cash=5_000_000,
    )


class TestAnalyzeSymbol:
    """analyze_symbol 함수 테스트."""

    async def test_analyze_symbol_returns_signal(self) -> None:
        """정상 분석 시 TradingSignal과 LLMResponse 반환."""
        data = _make_aggregated_data()
        context = _make_context()

        expected_signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.85,
            target_price=72000,
            position_size_pct=0.1,
            reasoning="상승 추세 확인",
            risk_level="MEDIUM",
        )
        expected_response = LLMResponse(
            content="분석 결과",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.002,
            latency_ms=300,
        )

        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (expected_signal, expected_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_make_formatted_data(),
        ):
            signal, response = await analyze_symbol(
                llm=mock_llm,
                data=data,
                context=context,
            )

        assert isinstance(signal, TradingSignal)
        assert signal.symbol == "005930"
        assert signal.action == "BUY"
        assert signal.confidence == 0.85
        assert response.provider == "openai"
        mock_llm.complete_json.assert_called_once()

    async def test_analyze_symbol_corrects_symbol(self) -> None:
        """LLM이 다른 심볼을 반환해도 원래 심볼로 보정."""
        data = _make_aggregated_data()
        context = _make_context()

        # LLM이 잘못된 심볼을 반환하는 경우
        wrong_signal = TradingSignal(
            symbol="WRONG_SYMBOL",
            action="HOLD",
            confidence=0.5,
        )
        mock_response = LLMResponse(
            content="분석 결과",
            provider="openai",
            model="gpt-4o-mini",
        )

        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (wrong_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_make_formatted_data(),
        ):
            signal, _ = await analyze_symbol(
                llm=mock_llm,
                data=data,
                context=context,
            )

        # 원래 심볼(005930)으로 보정되어야 함
        assert signal.symbol == "005930"

    async def test_analyze_symbol_uses_quick_mode(self) -> None:
        """기본적으로 quick 모드로 LLM 호출."""
        data = _make_aggregated_data()
        context = _make_context()

        mock_signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=0.4,
        )
        mock_response = LLMResponse(
            content="결과",
            provider="openai",
            model="gpt-4o-mini",
        )

        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (mock_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_make_formatted_data(),
        ):
            await analyze_symbol(llm=mock_llm, data=data, context=context)

        # complete_json 호출 시 mode="quick" 확인
        call_kwargs = mock_llm.complete_json.call_args
        assert call_kwargs.kwargs.get("mode") == "quick"

    async def test_analyze_symbol_passes_correct_schema(self) -> None:
        """TradingSignal 스키마로 complete_json 호출."""
        data = _make_aggregated_data()
        context = _make_context()

        mock_signal = TradingSignal(
            symbol="005930",
            action="SELL",
            confidence=0.7,
        )
        mock_response = LLMResponse(
            content="결과",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )

        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (mock_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_make_formatted_data(),
        ):
            await analyze_symbol(llm=mock_llm, data=data, context=context)

        # 두 번째 인수가 TradingSignal 스키마인지 확인
        call_args = mock_llm.complete_json.call_args
        assert call_args.args[1] is TradingSignal

    async def test_analyze_symbol_uses_formatted_prompt(self) -> None:
        """LLM 요청에 포맷팅된 프롬프트가 포함되는지 확인."""
        data = _make_aggregated_data()
        context = _make_context()

        mock_signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=0.5,
        )
        mock_response = LLMResponse(
            content="결과",
            provider="openai",
            model="gpt-4o-mini",
        )

        mock_llm = AsyncMock()
        mock_llm.complete_json.return_value = (mock_signal, mock_response)

        with patch(
            "src.ai.analysis.analyzer.format_for_llm",
            return_value=_make_formatted_data(),
        ):
            await analyze_symbol(llm=mock_llm, data=data, context=context)

        # LLMRequest에 심볼 정보가 포함되어야 함
        call_args = mock_llm.complete_json.call_args
        request: LLMRequest = call_args.args[0]
        assert "005930" in request.user_prompt
        assert "삼성전자" in request.user_prompt
