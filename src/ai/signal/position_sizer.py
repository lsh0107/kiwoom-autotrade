"""주문 수량 계산."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from src.ai.analysis.models import TradingSignal
from src.broker.schemas import DailyPrice
from src.trading.drawdown_guard import MAX_ORDER_AMOUNT

logger = structlog.get_logger(__name__)


# ── 전략별 자금 버킷 ────────────────────────────────


@dataclass
class StrategyBudget:
    """전략별 자금 버킷 관리.

    전략마다 총 잔고의 일정 비율을 배분하고,
    사용중 금액을 추적하여 가용 예산을 계산한다.
    """

    total_balance: int = 0
    allocations: dict[str, float] = field(
        default_factory=lambda: {
            "momentum": 0.40,
            "mean_reversion": 0.60,
        }
    )
    _used: dict[str, int] = field(default_factory=dict)

    def reset(self, account_balance: int) -> None:
        """총 잔고를 설정하고 사용중 금액을 초기화한다."""
        self.total_balance = max(0, account_balance)
        self._used.clear()

    def budget_for(self, strategy: str) -> int:
        """전략별 총 배분액 반환."""
        ratio = self.allocations.get(strategy, 0.0)
        return int(self.total_balance * ratio)

    def used(self, strategy: str) -> int:
        """전략별 사용중 금액 반환."""
        return self._used.get(strategy, 0)

    def available(self, strategy: str) -> int:
        """전략별 가용 금액 반환 (배분액 - 사용중)."""
        return max(0, self.budget_for(strategy) - self.used(strategy))

    def allocate(self, strategy: str, amount: int) -> bool:
        """금액을 할당한다. 가용액 부족 시 False 반환."""
        if amount <= 0:
            return True
        if amount > self.available(strategy):
            return False
        self._used[strategy] = self.used(strategy) + amount
        return True

    def release(self, strategy: str, amount: int) -> None:
        """할당된 금액을 해제한다."""
        if amount <= 0:
            return
        current = self.used(strategy)
        self._used[strategy] = max(0, current - amount)

    def apply_regime(self, regime: object, total_capital: int) -> None:
        """레짐에 따라 전략별 자본 배분 비율을 조정한다.

        REGIME_ALLOCATION 매트릭스 기준:
        - pool_a → momentum
        - pool_b → mean_reversion
        CRISIS인 경우 두 전략 모두 0 (전량 현금).

        Args:
            regime: 현재 시장 레짐 (MarketRegime)
            total_capital: 총 자본금 (원)
        """
        from src.trading.market_regime import REGIME_ALLOCATION

        alloc = REGIME_ALLOCATION[regime]
        self.allocations["momentum"] = alloc["pool_a"]
        self.allocations["mean_reversion"] = alloc["pool_b"]
        self.total_balance = max(0, total_capital)

    def summary(self) -> dict[str, dict]:
        """현재 상태 요약 (로깅용)."""
        result: dict[str, dict] = {}
        for strategy in self.allocations:
            result[strategy] = {
                "budget": self.budget_for(strategy),
                "used": self.used(strategy),
                "available": self.available(strategy),
            }
        return result


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
    max_position_pct: float = 0.10,
    strategy: str = "momentum",
    budget: StrategyBudget | None = None,
) -> int:
    """변동성 기반 동적 포지션 사이징.

    ATR(20일) 기반으로 변동성이 클수록 투자금을 줄인다.
    킬스위치의 scale_factor를 적용해 주간 손실 시 추가 축소.

    budget가 주어지면 전략별 가용 예산 범위 내에서 계산한다.
    allocate는 호출자(live_trader)가 별도 수행한다.

    Args:
        price: 현재 주가
        daily: 일봉 데이터 (ATR 계산용)
        account_balance: 총 계좌 잔고
        scale_factor: 킬스위치 스케일 팩터 (1.0=정상, 0.5=축소)
        risk_pct: 1회 거래 리스크 비율 (계좌의 2%)
        atr_period: ATR 계산 기간
        max_position_pct: 최대 포지션 비율 (계좌의 10%)
        strategy: 전략 이름 (budget 사용 시 적용)
        budget: 전략별 자금 버킷 (None이면 기존 로직)

    Returns:
        매수 수량 (최소 1주, price/account_balance 조건 충족 불가 시 0)
    """
    if price <= 0 or account_balance <= 0:
        return 0

    # 버킷 적용: 가용 예산을 기준 잔고로 사용
    effective_balance = account_balance
    if budget is not None:
        effective_balance = budget.available(strategy)
        if effective_balance <= 0:
            return 0

    atr = calc_atr(daily, atr_period)

    # ATR이 0이면 (데이터 부족) 고정 사이징 폴백
    if atr <= 0:
        invest = int(effective_balance * risk_pct * scale_factor)
        quantity = invest // price
        if budget is None:
            return max(1, quantity)
        return max(0, quantity)

    # 리스크 기반 수량: risk_amount / (ATR * 2)
    risk_amount = effective_balance * risk_pct * scale_factor
    quantity = int(risk_amount / (atr * 2))

    # 최대 한도: 가용 잔고의 max_position_pct%
    max_qty = int(effective_balance * max_position_pct * scale_factor / price)
    quantity = min(quantity, max_qty)

    # 버킷 적용 시 금액이 가용액 초과하지 않도록 축소
    if budget is not None and quantity > 0:
        order_amount = quantity * price
        avail = budget.available(strategy)
        if order_amount > avail:
            quantity = avail // price

    if budget is None:
        return max(1, quantity)
    return max(0, quantity)
