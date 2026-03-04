"""감사 로깅 테스트."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from src.ai.analysis.models import TradingSignal
from src.ai.audit.logger import log_llm_call, log_signal
from src.ai.llm.provider import LLMResponse
from src.models.ai import AISignal, LLMCallLog


class TestLogLLMCall:
    """log_llm_call 함수 테스트."""

    async def test_log_llm_call_creates_record(self, db: AsyncSession) -> None:
        """LLM 호출 로그가 DB에 저장되는지 검증."""
        user_id = uuid.uuid4()
        response = LLMResponse(
            content="테스트 응답",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0012,
            latency_ms=150,
        )

        log_entry = await log_llm_call(
            db=db,
            user_id=user_id,
            response=response,
            prompt_type="market_analysis",
        )

        assert isinstance(log_entry, LLMCallLog)
        assert log_entry.user_id == user_id
        assert log_entry.provider == "openai"
        assert log_entry.model == "gpt-4o-mini"
        assert log_entry.prompt_type == "market_analysis"
        assert log_entry.input_tokens == 100
        assert log_entry.output_tokens == 50
        assert log_entry.cost_usd == 0.0012
        assert log_entry.success is True
        assert log_entry.error_message is None
        assert log_entry.latency_ms == 150

    async def test_log_llm_call_with_error(self, db: AsyncSession) -> None:
        """실패한 LLM 호출 로그 저장."""
        user_id = uuid.uuid4()
        response = LLMResponse(
            content="",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            input_tokens=50,
            output_tokens=0,
            cost_usd=0.0,
            latency_ms=5000,
        )

        log_entry = await log_llm_call(
            db=db,
            user_id=user_id,
            response=response,
            prompt_type="disclosure_analysis",
            success=False,
            error_message="API timeout",
        )

        assert log_entry.success is False
        assert log_entry.error_message == "API timeout"

    async def test_log_llm_call_with_strategy_id(self, db: AsyncSession) -> None:
        """strategy_id가 포함된 LLM 호출 로그 저장."""
        user_id = uuid.uuid4()
        strategy_id = uuid.uuid4()
        response = LLMResponse(
            content="응답",
            provider="openai",
            model="gpt-4o-mini",
            cost_usd=0.001,
        )

        log_entry = await log_llm_call(
            db=db,
            user_id=user_id,
            response=response,
            prompt_type="comprehensive_judgment",
            strategy_id=strategy_id,
        )

        assert log_entry.strategy_id == strategy_id


class TestLogSignal:
    """log_signal 함수 테스트."""

    async def test_log_signal_creates_record(self, db: AsyncSession) -> None:
        """AI 시그널 로그가 DB에 저장되는지 검증."""
        user_id = uuid.uuid4()
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.85,
            target_price=72000,
            position_size_pct=0.1,
            reasoning="상승 추세",
            risk_level="MEDIUM",
        )

        ai_signal = await log_signal(
            db=db,
            user_id=user_id,
            signal=signal,
        )

        assert isinstance(ai_signal, AISignal)
        assert ai_signal.user_id == user_id
        assert ai_signal.symbol == "005930"
        assert ai_signal.action == "BUY"
        assert ai_signal.confidence == 0.85
        assert ai_signal.target_price == 72000
        assert ai_signal.position_size_pct == 0.1
        assert ai_signal.reasoning == "상승 추세"
        assert ai_signal.risk_level == "MEDIUM"
        assert ai_signal.is_executed is False
        assert ai_signal.order_id is None
        assert ai_signal.rejection_reason is None

    async def test_log_signal_with_execution(self, db: AsyncSession) -> None:
        """실행된 시그널 로그 저장."""
        user_id = uuid.uuid4()
        order_id = uuid.uuid4()
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.9,
            position_size_pct=0.1,
        )

        ai_signal = await log_signal(
            db=db,
            user_id=user_id,
            signal=signal,
            is_executed=True,
            order_id=order_id,
        )

        assert ai_signal.is_executed is True
        assert ai_signal.order_id == order_id

    async def test_log_signal_with_rejection(self, db: AsyncSession) -> None:
        """거절된 시그널 로그 저장."""
        user_id = uuid.uuid4()
        signal = TradingSignal(
            symbol="005930",
            action="BUY",
            confidence=0.6,
            position_size_pct=0.1,
        )

        ai_signal = await log_signal(
            db=db,
            user_id=user_id,
            signal=signal,
            is_executed=False,
            rejection_reason="신뢰도 임계값 미달",
        )

        assert ai_signal.is_executed is False
        assert ai_signal.rejection_reason == "신뢰도 임계값 미달"

    async def test_log_signal_with_raw_analysis(self, db: AsyncSession) -> None:
        """raw_analysis 포함 시그널 로그 저장."""
        user_id = uuid.uuid4()
        signal = TradingSignal(
            symbol="005930",
            action="HOLD",
            confidence=0.5,
        )
        raw = {"trend": "sideways", "support": 65000, "resistance": 72000}

        ai_signal = await log_signal(
            db=db,
            user_id=user_id,
            signal=signal,
            raw_analysis=raw,
        )

        assert ai_signal.raw_analysis == raw
