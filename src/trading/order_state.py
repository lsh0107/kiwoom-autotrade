"""주문 상태 머신."""

from src.models.order import OrderStatus

# 유효한 상태 전이 정의
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.SUBMITTED, OrderStatus.FAILED},
    OrderStatus.SUBMITTED: {
        OrderStatus.ACCEPTED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
    },
    OrderStatus.ACCEPTED: {
        OrderStatus.FILLED,
        OrderStatus.PARTIAL_FILL,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
    },
    OrderStatus.PARTIAL_FILL: {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.FAILED,
    },
    OrderStatus.FILLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.EXPIRED: set(),
    OrderStatus.FAILED: set(),
}

# 최종 상태 (더 이상 전이 불가)
TERMINAL_STATUSES: set[OrderStatus] = {
    OrderStatus.FILLED,
    OrderStatus.REJECTED,
    OrderStatus.CANCELLED,
    OrderStatus.EXPIRED,
    OrderStatus.FAILED,
}


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    """상태 전이 가능 여부."""
    return target in VALID_TRANSITIONS.get(current, set())


def is_terminal(status: OrderStatus) -> bool:
    """최종 상태인지 확인."""
    return status in TERMINAL_STATUSES


def validate_transition(current: OrderStatus, target: OrderStatus) -> None:
    """상태 전이 검증. 불가능하면 ValueError."""
    if not can_transition(current, target):
        msg = f"주문 상태 전이 불가: {current.value} → {target.value}"
        raise ValueError(msg)
