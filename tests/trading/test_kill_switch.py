"""Kill Switch 테스트."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.order import Order, OrderSide
from src.models.user import User
from src.trading.kill_switch import (
    _user_states,
    activate_manual_kill,
    check_level1,
    check_level2,
    check_level3,
    deactivate_manual_kill,
    get_user_state,
    run_all_checks,
)
from src.utils.exceptions import KillSwitchError


class TestLevel1:
    """Level 1 (주문별) 테스트."""

    def test_valid_order(self) -> None:
        """정상 주문 통과."""
        check_level1(
            symbol="005930",
            side="BUY",
            price=70000,
            quantity=10,
            check_market_hours=False,
        )

    def test_max_amount_exceeded(self) -> None:
        """최대 금액 초과."""
        with pytest.raises(KillSwitchError, match="한도"):
            check_level1(
                symbol="005930",
                side="BUY",
                price=100000,
                quantity=20,  # 200만원 > 100만원
                check_market_hours=False,
            )

    def test_zero_price(self) -> None:
        """가격 0 차단."""
        with pytest.raises(KillSwitchError, match="0보다"):
            check_level1(
                symbol="005930",
                side="BUY",
                price=0,
                quantity=10,
                check_market_hours=False,
            )

    def test_price_limit(self) -> None:
        """가격제한폭 초과."""
        with pytest.raises(KillSwitchError, match="가격제한폭"):
            check_level1(
                symbol="005930",
                side="BUY",
                price=100000,  # +45% > ±30%
                quantity=1,
                prev_close=69000,
                check_market_hours=False,
            )

    def test_price_within_limit(self) -> None:
        """가격제한폭 내."""
        check_level1(
            symbol="005930",
            side="BUY",
            price=75000,  # +8.7% < ±30%
            quantity=1,
            prev_close=69000,
            check_market_hours=False,
        )


class TestLevel2:
    """Level 2 (전략별) 테스트."""

    def test_investment_exceeded(self) -> None:
        """투자금 한도 초과."""
        with pytest.raises(KillSwitchError, match="투자금 한도"):
            check_level2(
                order_amount=600000,
                max_investment=1000000,
                current_invested=500000,
            )

    def test_loss_exceeded(self) -> None:
        """손실률 한도 초과."""
        with pytest.raises(KillSwitchError, match="손실률"):
            check_level2(
                order_amount=100000,
                strategy_pnl_pct=-5.0,
                max_loss_pct=-3.0,
            )

    def test_valid_strategy(self) -> None:
        """정상 전략 통과."""
        check_level2(
            order_amount=100000,
            max_investment=1000000,
            current_invested=200000,
            strategy_pnl_pct=-1.0,
            max_loss_pct=-3.0,
        )


class TestManualKillSwitch:
    """수동 킬스위치 테스트."""

    def test_activate_deactivate(self) -> None:
        """수동 킬스위치 활성화/해제."""
        user_id = uuid.uuid4()
        activate_manual_kill(user_id)
        state = get_user_state(user_id)
        assert state.manual_kill is True

        deactivate_manual_kill(user_id)
        state = get_user_state(user_id)
        assert state.manual_kill is False


class TestLevel3:
    """Level 3 (사용자별 DB 기반) 테스트."""

    async def test_daily_order_count_exceeded(self, db: AsyncSession, test_user: User) -> None:
        """일일 주문 수 초과."""
        from src.utils.time import now_kst

        now = now_kst()
        # 주문 3개 생성 (max_daily_orders=3으로 테스트)
        for i in range(3):
            order = Order(
                user_id=test_user.id,
                symbol=f"00593{i}",
                symbol_name=f"테스트{i}",
                side=OrderSide.BUY,
                price=10000,
                quantity=1,
                is_mock=True,
                created_at=now,
            )
            db.add(order)
        await db.flush()

        with pytest.raises(KillSwitchError, match="일일 주문 한도"):
            await check_level3(
                user_id=test_user.id,
                db=db,
                max_daily_orders=3,
            )

    async def test_manual_kill_switch_active(self, db: AsyncSession, test_user: User) -> None:
        """수동 킬스위치 활성화 시 차단."""
        activate_manual_kill(test_user.id)

        try:
            with pytest.raises(KillSwitchError, match="수동 킬스위치"):
                await check_level3(
                    user_id=test_user.id,
                    db=db,
                )
        finally:
            deactivate_manual_kill(test_user.id)


class TestRunAllChecks:
    """run_all_checks 전체 통과 테스트."""

    async def test_run_all_checks_pass(self, db: AsyncSession, test_user: User) -> None:
        """3단계 전체 통과."""
        # 인메모리 상태 초기화
        _user_states.pop(test_user.id, None)

        await run_all_checks(
            user_id=test_user.id,
            symbol="005930",
            side="buy",
            price=70000,
            quantity=10,
            db=db,
            check_market_hours=False,
        )
