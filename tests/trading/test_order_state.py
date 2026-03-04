"""주문 상태 머신 테스트."""

import pytest
from src.models.order import OrderStatus
from src.trading.order_state import can_transition, is_terminal, validate_transition


class TestOrderStateMachine:
    """상태 전이 테스트."""

    def test_created_to_submitted(self) -> None:
        """CREATED → SUBMITTED 가능."""
        assert can_transition(OrderStatus.CREATED, OrderStatus.SUBMITTED)

    def test_created_to_filled_impossible(self) -> None:
        """CREATED → FILLED 불가."""
        assert not can_transition(OrderStatus.CREATED, OrderStatus.FILLED)

    def test_submitted_to_accepted(self) -> None:
        """SUBMITTED → ACCEPTED 가능."""
        assert can_transition(OrderStatus.SUBMITTED, OrderStatus.ACCEPTED)

    def test_accepted_to_filled(self) -> None:
        """ACCEPTED → FILLED 가능."""
        assert can_transition(OrderStatus.ACCEPTED, OrderStatus.FILLED)

    def test_accepted_to_partial_fill(self) -> None:
        """ACCEPTED → PARTIAL_FILL 가능."""
        assert can_transition(OrderStatus.ACCEPTED, OrderStatus.PARTIAL_FILL)

    def test_partial_fill_to_filled(self) -> None:
        """PARTIAL_FILL → FILLED 가능."""
        assert can_transition(OrderStatus.PARTIAL_FILL, OrderStatus.FILLED)

    def test_filled_is_terminal(self) -> None:
        """FILLED는 최종 상태."""
        assert is_terminal(OrderStatus.FILLED)
        assert not can_transition(OrderStatus.FILLED, OrderStatus.CANCELLED)

    def test_rejected_is_terminal(self) -> None:
        """REJECTED는 최종 상태."""
        assert is_terminal(OrderStatus.REJECTED)

    def test_cancelled_is_terminal(self) -> None:
        """CANCELLED는 최종 상태."""
        assert is_terminal(OrderStatus.CANCELLED)

    def test_created_not_terminal(self) -> None:
        """CREATED는 최종 상태가 아님."""
        assert not is_terminal(OrderStatus.CREATED)

    def test_validate_transition_raises(self) -> None:
        """불가능한 전이 시 ValueError."""
        with pytest.raises(ValueError, match="상태 전이 불가"):
            validate_transition(OrderStatus.CREATED, OrderStatus.FILLED)

    def test_validate_transition_ok(self) -> None:
        """가능한 전이는 통과."""
        validate_transition(OrderStatus.CREATED, OrderStatus.SUBMITTED)
