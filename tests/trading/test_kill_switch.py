"""Kill Switch 테스트."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.order import Order, OrderSide
from src.models.user import User
from src.trading.kill_switch import (
    DRAWDOWN_FORCE_CLOSE_PCT,
    DRAWDOWN_STOP_BUY_PCT,
    WEEKLY_LOSS_SCALE_PCT,
    WEEKLY_SCALE_FACTOR,
    DrawdownAction,
    _user_states,
    activate_manual_kill,
    check_drawdown,
    check_level1,
    check_level2,
    check_level3,
    deactivate_manual_kill,
    get_user_state,
    run_all_checks,
    update_drawdown,
    update_weekly_loss,
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


class TestDrawdown:
    """드로우다운 3단계 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _user_states.pop(self.user_id, None)

    def test_initial_call_returns_none(self) -> None:
        """최초 호출 시 NONE 반환 및 시작값 초기화."""
        action = update_drawdown(self.user_id, 10_000_000)
        assert action == DrawdownAction.NONE
        state = get_user_state(self.user_id)
        assert state.daily_start_value == 10_000_000

    def test_no_drawdown_returns_none(self) -> None:
        """손실 없으면 NONE."""
        update_drawdown(self.user_id, 10_000_000)  # 초기화
        action = update_drawdown(self.user_id, 10_100_000)  # +1%
        assert action == DrawdownAction.NONE

    def test_stop_buy_at_2pct(self) -> None:
        """드로우다운 -2% 시 STOP_BUY."""
        update_drawdown(self.user_id, 10_000_000)
        # 정확히 -2%
        action = update_drawdown(self.user_id, int(10_000_000 * (1 + DRAWDOWN_STOP_BUY_PCT / 100)))
        assert action == DrawdownAction.STOP_BUY

    def test_force_close_at_3pct(self) -> None:
        """드로우다운 -3% 시 FORCE_CLOSE."""
        update_drawdown(self.user_id, 10_000_000)
        # 정확히 -3%
        action = update_drawdown(
            self.user_id, int(10_000_000 * (1 + DRAWDOWN_FORCE_CLOSE_PCT / 100))
        )
        assert action == DrawdownAction.FORCE_CLOSE

    def test_drawdown_between_2_and_3_pct(self) -> None:
        """드로우다운 -2.5%: STOP_BUY."""
        update_drawdown(self.user_id, 10_000_000)
        action = update_drawdown(self.user_id, 9_750_000)  # -2.5%
        assert action == DrawdownAction.STOP_BUY

    def test_high_water_mark_updated(self) -> None:
        """고점 갱신 확인."""
        update_drawdown(self.user_id, 10_000_000)
        update_drawdown(self.user_id, 11_000_000)  # 고점 갱신
        state = get_user_state(self.user_id)
        assert state.daily_high_water_mark == 11_000_000

    def test_check_drawdown_blocks_buy_on_stop_buy(self) -> None:
        """STOP_BUY 상태에서 BUY 차단."""
        update_drawdown(self.user_id, 10_000_000)
        update_drawdown(self.user_id, 9_800_000)  # -2%

        with pytest.raises(KillSwitchError, match="신규 매수 중단"):
            check_drawdown(self.user_id, "BUY")

    def test_check_drawdown_allows_sell_on_stop_buy(self) -> None:
        """STOP_BUY 상태에서 SELL 허용."""
        update_drawdown(self.user_id, 10_000_000)
        update_drawdown(self.user_id, 9_800_000)  # -2%

        # SELL은 통과 (예외 없음)
        check_drawdown(self.user_id, "SELL")

    def test_check_drawdown_blocks_all_on_force_close(self) -> None:
        """FORCE_CLOSE 상태에서 모든 주문 차단."""
        update_drawdown(self.user_id, 10_000_000)
        update_drawdown(self.user_id, 9_700_000)  # -3%

        with pytest.raises(KillSwitchError, match="전량 청산"):
            check_drawdown(self.user_id, "BUY")

        with pytest.raises(KillSwitchError, match="전량 청산"):
            check_drawdown(self.user_id, "SELL")


class TestWeeklyLoss:
    """주간 손실 스케일 팩터 테스트."""

    def setup_method(self) -> None:
        """매 테스트 전 상태 초기화."""
        self.user_id = uuid.uuid4()
        _user_states.pop(self.user_id, None)

    def test_initial_call_returns_default_scale(self) -> None:
        """최초 호출 시 기본 scale_factor(1.0) 반환."""
        factor = update_weekly_loss(self.user_id, 10_000_000)
        assert factor == 1.0

    def test_no_weekly_loss_returns_1(self) -> None:
        """주간 손실 없으면 scale_factor=1.0."""
        update_weekly_loss(self.user_id, 10_000_000)  # 초기화
        factor = update_weekly_loss(self.user_id, 10_200_000)  # +2%
        assert factor == 1.0

    def test_weekly_loss_under_4pct_returns_1(self) -> None:
        """주간 손실 -3.9%: scale_factor=1.0."""
        update_weekly_loss(self.user_id, 10_000_000)
        factor = update_weekly_loss(self.user_id, 9_610_000)  # -3.9%
        assert factor == 1.0

    def test_weekly_loss_at_4pct_reduces_scale(self) -> None:
        """주간 손실 -4%: scale_factor=0.5."""
        update_weekly_loss(self.user_id, 10_000_000)
        target = int(10_000_000 * (1 + WEEKLY_LOSS_SCALE_PCT / 100))
        factor = update_weekly_loss(self.user_id, target)
        assert factor == WEEKLY_SCALE_FACTOR

    def test_scale_factor_persists_in_state(self) -> None:
        """스케일 팩터가 상태에 반영됨."""
        update_weekly_loss(self.user_id, 10_000_000)
        update_weekly_loss(self.user_id, 9_600_000)  # -4%
        state = get_user_state(self.user_id)
        assert state.scale_factor == WEEKLY_SCALE_FACTOR
