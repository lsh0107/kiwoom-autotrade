"""시그널 5단계 검증."""

import structlog

from src.ai.analysis.models import TradingSignal
from src.utils.time import is_trading_hours

logger = structlog.get_logger(__name__)

# 신뢰도 임계값
BUY_CONFIDENCE_THRESHOLD = 0.7
SELL_CONFIDENCE_THRESHOLD = 0.6

# 리스크 레벨별 허용
RISK_ALLOWED = {"LOW", "MEDIUM", "HIGH"}


class ValidationResult:
    """검증 결과."""

    def __init__(self) -> None:
        self.passed: bool = True
        self.reasons: list[str] = []

    def fail(self, reason: str) -> None:
        """검증 실패 추가."""
        self.passed = False
        self.reasons.append(reason)


async def validate_signal(
    signal: TradingSignal,
    *,
    current_holdings: list[str] | None = None,
    total_portfolio_value: int = 0,
    max_position_pct: float = 30.0,
    check_market_hours: bool = True,
) -> ValidationResult:
    """5단계 시그널 검증."""
    result = ValidationResult()
    current_holdings = current_holdings or []

    # 1. 신뢰도 검증
    if signal.action == "BUY" and signal.confidence < BUY_CONFIDENCE_THRESHOLD:
        result.fail(f"매수 신뢰도 {signal.confidence:.2f} < 임계값 {BUY_CONFIDENCE_THRESHOLD}")
    elif signal.action == "SELL" and signal.confidence < SELL_CONFIDENCE_THRESHOLD:
        result.fail(f"매도 신뢰도 {signal.confidence:.2f} < 임계값 {SELL_CONFIDENCE_THRESHOLD}")

    # 2. 포지션 체크
    if signal.action == "SELL" and signal.symbol not in current_holdings:
        result.fail(f"보유하지 않은 종목 매도 시도: {signal.symbol}")

    # 3. 리스크 검증
    if signal.risk_level == "HIGH" and signal.action == "BUY" and signal.confidence < 0.85:
        result.fail(f"고위험 매수 신호 — 신뢰도 {signal.confidence:.2f} < 0.85")

    # 4. 포지션 비중 체크
    if (
        signal.action == "BUY"
        and total_portfolio_value > 0
        and signal.position_size_pct * 100 > max_position_pct
    ):
        result.fail(
            f"포지션 비중 {signal.position_size_pct * 100:.1f}% > 최대 {max_position_pct}%"
        )

    # 5. 시장 시간 체크
    if check_market_hours and signal.action != "HOLD" and not is_trading_hours():
        result.fail("현재 거래 가능 시간이 아닙니다")

    if not result.passed:
        await logger.awarning(
            "시그널 검증 실패",
            symbol=signal.symbol,
            action=signal.action,
            reasons=result.reasons,
        )

    return result
