"""주문 수량 계산."""

import structlog

from src.ai.analysis.models import TradingSignal
from src.broker.schemas import DailyPrice
from src.trading.kill_switch import MAX_ORDER_AMOUNT

logger = structlog.get_logger(__name__)


def calculate_order_quantity(
    *,
    signal: TradingSignal,
    available_cash: int,
    current_price: int,
    max_position_pct: float = 30.0,
    total_portfolio_value: int = 0,
) -> int:
    """매수 수량 계산."""
    if signal.action != "BUY" or current_price <= 0:
        return 0

    # 1. 시그널의 포지션 비중 기반 금액
    if total_portfolio_value > 0:
        target_amount = int(total_portfolio_value * signal.position_size_pct)
    else:
        target_amount = int(available_cash * signal.position_size_pct)

    # 2. 최대 주문 금액 제한
    target_amount = min(target_amount, MAX_ORDER_AMOUNT)

    # 3. 가용 현금 제한
    target_amount = min(target_amount, available_cash)

    # 4. 포트폴리오 비중 제한
    if total_portfolio_value > 0:
        max_amount = int(total_portfolio_value * max_position_pct / 100)
        target_amount = min(target_amount, max_amount)

    # 5. 수량 계산 (내림)
    quantity = target_amount // current_price

    if quantity <= 0:
        logger.warning(
            "계산된 수량이 0",
            symbol=signal.symbol,
            target_amount=target_amount,
            current_price=current_price,
        )

    return quantity


# ── 동적 포지션 사이징 ────────────────────────────────


def calc_atr(daily: list[DailyPrice], period: int = 20) -> float:
    """ATR(Average True Range) 계산.

    Args:
        daily: 일봉 데이터 (최신 순 또는 오름차순 모두 가능)
        period: ATR 계산 기간 (기본 20일)

    Returns:
        ATR 값 (0.0 = 데이터 부족)
    """
    if len(daily) < 2:
        return 0.0

    true_ranges: list[float] = []
    for i in range(1, len(daily)):
        prev_close = daily[i - 1].close
        curr = daily[i]
        tr = max(
            curr.high - curr.low,
            abs(curr.high - prev_close),
            abs(curr.low - prev_close),
        )
        true_ranges.append(float(tr))

    recent = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return sum(recent) / len(recent) if recent else 0.0


def calc_dynamic_position_size(
    *,
    price: int,
    daily: list[DailyPrice],
    account_balance: int,
    scale_factor: float = 1.0,
    risk_pct: float = 0.02,
    atr_period: int = 20,
    max_position_pct: float = 0.15,
) -> int:
    """변동성 기반 동적 포지션 사이징.

    ATR(20일) 기반으로 변동성이 클수록 투자금을 줄인다.
    킬스위치의 scale_factor를 적용해 주간 손실 시 추가 축소.

    Args:
        price: 현재 주가
        daily: 일봉 데이터 (ATR 계산용)
        account_balance: 총 계좌 잔고
        scale_factor: 킬스위치 스케일 팩터 (1.0=정상, 0.5=축소)
        risk_pct: 1회 거래 리스크 비율 (계좌의 2%)
        atr_period: ATR 계산 기간
        max_position_pct: 최대 포지션 비율 (계좌의 15%)

    Returns:
        매수 수량 (최소 1주, price/account_balance 조건 충족 불가 시 0)
    """
    if price <= 0 or account_balance <= 0:
        return 0

    atr = calc_atr(daily, atr_period)

    # ATR이 0이면 (데이터 부족) 고정 사이징 폴백
    if atr <= 0:
        invest = int(account_balance * risk_pct * scale_factor)
        return max(1, invest // price)

    # 리스크 기반 수량: risk_amount / (ATR * 2)
    risk_amount = account_balance * risk_pct * scale_factor
    quantity = int(risk_amount / (atr * 2))

    # 최대 한도: 계좌의 15%
    max_qty = int(account_balance * max_position_pct * scale_factor / price)
    quantity = min(quantity, max_qty)

    return max(1, quantity)
