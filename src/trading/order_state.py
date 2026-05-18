"""주문 상태 머신."""

from src.models.order import OrderStatus

# 유효한 상태 전이 정의
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.SUBMITTED, OrderStatus.FAILED},
    OrderStatus.SUBMITTED: {
        OrderStatus.ACCEPTED,
        # 키움 WebSocket 체결 이벤트는 ACCEPTED 단계 없이 SUBMITTED → FILLED/PARTIAL_FILL
        # 로 바로 전이하는 경우가 많다. cancel API 응답도 SUBMITTED → CANCELLED 직접.
        # 사용자 리뷰 (2026-05-18) — realtime.py 체결 핸들러가 invalid transition 으로
        # update drop 되던 결함 + short_swing_cancel 의 cancel_order() 예외 해소.
        OrderStatus.FILLED,
        OrderStatus.PARTIAL_FILL,
        OrderStatus.CANCELLED,
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
        # 두 번째 부분체결 이벤트는 PARTIAL_FILL → PARTIAL_FILL self-transition.
        # 키움은 체결번호(909) 가 다른 단발 이벤트로 전달하므로 누적 처리 필요.
        # 사용자 리뷰 (2026-05-18) HOTFIX E — small-real 게이트 1.
        OrderStatus.PARTIAL_FILL,
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
