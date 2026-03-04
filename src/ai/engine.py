"""AI 자동매매 엔진 — 메인 오케스트레이터."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.analysis.analyzer import analyze_symbol
from src.ai.analysis.models import AnalysisContext, TradingSignal
from src.ai.audit.logger import log_llm_call, log_signal
from src.ai.data.aggregator import aggregate_symbol_data
from src.ai.llm.manager import LLMManager
from src.ai.signal.order_builder import build_buy_order, build_sell_order
from src.ai.signal.validator import validate_signal
from src.broker.kiwoom import KiwoomClient
from src.models.order import OrderSide
from src.models.strategy import Strategy
from src.trading.order_service import create_order

logger = structlog.get_logger(__name__)


class AIEngine:
    """AI 자동매매 엔진."""

    def __init__(self) -> None:
        self._llm = LLMManager()
        self._running_strategies: dict[uuid.UUID, bool] = {}

    async def run_analysis(
        self,
        *,
        strategy: Strategy,
        broker_client: KiwoomClient,
        db: AsyncSession,
    ) -> list[TradingSignal]:
        """전략 기반 종목 분석 실행."""
        signals: list[TradingSignal] = []
        symbols: list[str] = strategy.symbols or []

        if not symbols:
            await logger.awarning("분석 대상 종목 없음", strategy_id=str(strategy.id))
            return signals

        # 계좌 정보
        try:
            balance = await broker_client.get_balance()
            available_cash = balance.available_cash
            holdings = balance.holdings
            holding_symbols = [h.symbol for h in holdings]
            total_value = balance.total_eval
        except Exception:
            await logger.aexception("계좌 정보 조회 실패")
            available_cash = 0
            holdings = []
            holding_symbols = []
            total_value = 0

        for symbol in symbols:
            try:
                # 데이터 수집
                data = await aggregate_symbol_data(broker_client, symbol)

                # 분석 컨텍스트
                context = AnalysisContext(
                    symbol=symbol,
                    name=data.quote.name if data.quote else "",
                    available_cash=available_cash,
                    daily_pnl=0,
                )

                # LLM 분석
                signal, llm_response = await analyze_symbol(
                    llm=self._llm,
                    data=data,
                    context=context,
                )

                # LLM 호출 로그
                await log_llm_call(
                    db=db,
                    user_id=strategy.user_id,
                    response=llm_response,
                    prompt_type="market_analysis",
                    strategy_id=strategy.id,
                )

                # 시그널 검증
                validation = await validate_signal(
                    signal,
                    current_holdings=holding_symbols,
                    total_portfolio_value=total_value,
                    max_position_pct=strategy.max_position_pct,
                    check_market_hours=False,  # 스케줄러가 시간 관리
                )

                if not validation.passed:
                    await log_signal(
                        db=db,
                        user_id=strategy.user_id,
                        signal=signal,
                        strategy_id=strategy.id,
                        is_executed=False,
                        rejection_reason="; ".join(validation.reasons),
                    )
                    continue

                # 자동매매 실행
                if strategy.is_auto_trading and signal.action != "HOLD":
                    await self._execute_signal(
                        signal=signal,
                        strategy=strategy,
                        broker_client=broker_client,
                        db=db,
                        available_cash=available_cash,
                        current_price=data.quote.price if data.quote else 0,
                        holdings=holdings,
                        total_value=total_value,
                    )
                else:
                    await log_signal(
                        db=db,
                        user_id=strategy.user_id,
                        signal=signal,
                        strategy_id=strategy.id,
                        is_executed=False,
                        rejection_reason="자동매매 비활성"
                        if not strategy.is_auto_trading
                        else None,
                    )

                signals.append(signal)

            except Exception:
                await logger.aexception("종목 분석 실패", symbol=symbol)

        await db.commit()
        return signals

    async def _execute_signal(
        self,
        *,
        signal: TradingSignal,
        strategy: Strategy,
        broker_client: KiwoomClient,  # noqa: ARG002
        db: AsyncSession,
        available_cash: int,
        current_price: int,
        holdings: list,
        total_value: int,
    ) -> None:
        """시그널 → 주문 실행."""
        from src.config.settings import get_settings

        settings = get_settings()
        order_request = None

        if signal.action == "BUY":
            order_request = build_buy_order(
                signal=signal,
                available_cash=available_cash,
                current_price=current_price,
                max_position_pct=strategy.max_position_pct,
                total_portfolio_value=total_value,
            )
        elif signal.action == "SELL":
            # 보유 수량 찾기
            holding_qty = 0
            for h in holdings:
                if h.symbol == signal.symbol:
                    holding_qty = h.quantity
                    break
            order_request = build_sell_order(
                signal=signal,
                holding_quantity=holding_qty,
                current_price=current_price,
            )

        if not order_request:
            await log_signal(
                db=db,
                user_id=strategy.user_id,
                signal=signal,
                strategy_id=strategy.id,
                is_executed=False,
                rejection_reason="주문 수량 0",
            )
            return

        try:
            order = await create_order(
                db=db,
                user_id=strategy.user_id,
                symbol=signal.symbol,
                symbol_name="",
                side=OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL,
                price=order_request.price,
                quantity=order_request.quantity,
                strategy_id=strategy.id,
                reason=f"AI 시그널: {signal.reasoning[:200]}",
                is_mock=settings.is_mock_trading,
                check_market_hours=False,
            )

            await log_signal(
                db=db,
                user_id=strategy.user_id,
                signal=signal,
                strategy_id=strategy.id,
                is_executed=True,
                order_id=order.id,
            )

            await logger.ainfo(
                "AI 주문 실행",
                symbol=signal.symbol,
                action=signal.action,
                quantity=order_request.quantity,
                price=order_request.price,
            )

        except Exception:
            await logger.aexception("AI 주문 실행 실패", symbol=signal.symbol)
            await log_signal(
                db=db,
                user_id=strategy.user_id,
                signal=signal,
                strategy_id=strategy.id,
                is_executed=False,
                rejection_reason="주문 실행 오류",
            )


# 싱글톤
_engine: AIEngine | None = None


def get_engine() -> AIEngine:
    """AI 엔진 싱글톤."""
    global _engine
    if _engine is None:
        _engine = AIEngine()
    return _engine
