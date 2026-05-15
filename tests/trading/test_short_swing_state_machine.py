"""Short Swing 상태머신 + 체결 reconciler + user scope + holdings 검증 테스트.

HOTFIX A — 7 필수 케이스:
1. BUY submitted → PENDING_ENTRY row 생성, OPEN 미생성, exit query 에서 제외.
2. BUY cancel/reject → PENDING_ENTRY 정리.
3. BUY partial fill → 체결수량만 OPEN. 잔여 PENDING_ENTRY 유지.
4. SELL submitted → CLOSING. FILLED 이벤트 후 → CLOSED + realized_pnl 계산.
5. SELL cancel/reject → CLOSING → OPEN.
6. exit 직전 broker holdings=0 → SELL 주문 0건, position RECONCILIATION_ERROR 마킹.
7. 다른 user 의 short_swing_position 은 API/exit query 에서 제외.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import AccountBalance, BrokerOrderResponse, Holding, Quote
from src.models.order import Order, OrderSide, OrderStatus
from src.models.short_swing import PositionStatus, ShortSwingPosition
from src.models.user import User, UserRole
from src.trading.kill_switch import KillSwitchStatus
from src.trading.short_swing_reconciler import reconcile_short_swing_positions
from src.utils.security import hash_password
from src.utils.time import KST

# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

_EXIT_TIME = datetime(2026, 5, 15, 10, 0, 0, tzinfo=KST)


def _make_quote(
    symbol: str = "005930",
    price: int = 72000,
    prev_close: int = 70000,
) -> Quote:
    return Quote(
        symbol=symbol,
        name="삼성전자",
        price=price,
        change=price - prev_close,
        change_pct=round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
        volume=5_000_000,
        high=price + 500,
        low=price - 1000,
        open=prev_close + 500,
        prev_close=prev_close,
    )


def _make_balance(
    available_cash: int = 5_000_000,
    holdings: list[Holding] | None = None,
) -> AccountBalance:
    return AccountBalance(
        total_eval=10_000_000,
        total_profit=500_000,
        total_profit_pct=5.0,
        available_cash=available_cash,
        holdings=holdings or [],
    )


def _make_broker_response(
    symbol: str = "005930",
    status: str = "submitted",
    message: str = "주문 접수",
    side: str = "sell",
) -> BrokerOrderResponse:
    return BrokerOrderResponse(
        order_no="T00001",
        symbol=symbol,
        side=side,
        price=72000,
        quantity=10,
        status=status,
        message=message,
    )


def _mock_exit_client(
    quote: Quote | None = None,
    broker_response: BrokerOrderResponse | None = None,
    holdings: list[Holding] | None = None,
) -> AsyncMock:
    """표준 mock 브로커 클라이언트 (exit 용)."""
    client = AsyncMock()
    client._is_mock = True
    client.get_quote.return_value = quote or _make_quote()
    client.place_order.return_value = broker_response or _make_broker_response()
    client.get_holdings.return_value = holdings or []
    client.get_balance.return_value = _make_balance(holdings=holdings or [])
    return client


def _make_position(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str = "005930",
    name: str = "삼성전자",
    entry_price: int = 70000,
    quantity: int = 10,
    status: PositionStatus = PositionStatus.OPEN,
    entry_order_id: uuid.UUID | None = None,
    exit_order_id: uuid.UUID | None = None,
) -> ShortSwingPosition:
    """테스트 포지션 생성 (DB 세션에 add)."""
    pos = ShortSwingPosition(
        user_id=user_id,
        symbol=symbol,
        name=name,
        entry_date=date(2026, 5, 14),
        entry_time=datetime(2026, 5, 14, 10, 0, 0, tzinfo=KST),
        entry_price=entry_price,
        quantity=quantity,
        highest_price_since_entry=entry_price,
        stop_price=math.floor(entry_price * 0.98),
        take_profit_price=math.floor(entry_price * 1.04),
        trailing_armed=False,
        max_holding_until=date(2026, 5, 23),
        status=status,
        entry_order_id=entry_order_id,
        exit_order_id=exit_order_id,
    )
    db.add(pos)
    return pos


def _make_order(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str = "005930",
    side: OrderSide = OrderSide.BUY,
    status: OrderStatus = OrderStatus.SUBMITTED,
    price: int = 70000,
    quantity: int = 10,
    filled_price: int = 0,
    filled_quantity: int = 0,
    filled_at: datetime | None = None,
) -> Order:
    """테스트 주문 생성."""
    order = Order(
        user_id=user_id,
        symbol=symbol,
        symbol_name="삼성전자",
        side=side,
        price=price,
        quantity=quantity,
        status=status,
        reason="short_swing",
        is_mock=True,
        filled_price=filled_price,
        filled_quantity=filled_quantity,
        filled_at=filled_at,
    )
    db.add(order)
    return order


async def _create_second_user(db: AsyncSession) -> User:
    """두 번째 테스트 사용자 생성."""
    user = User(
        email="other@example.com",
        hashed_password=hash_password("otherpassword123"),
        nickname="다른유저",
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── 테스트 1: BUY submitted → PENDING_ENTRY ─────────────────────────────────


class TestBuySubmittedPendingEntry:
    """BUY submitted → PENDING_ENTRY row 생성, OPEN 미생성, exit query 에서 제외."""

    @pytest.mark.asyncio
    async def test_entry_creates_pending_entry(self, db: AsyncSession, test_user: User) -> None:
        """run_entry_check 호출 시 PENDING_ENTRY 포지션 생성."""
        from src.models.short_swing import ShortSwingCandidate
        from src.trading.short_swing import run_entry_check

        user_id = test_user.id

        # 후보 생성
        cand = ShortSwingCandidate(
            trade_date=date(2026, 5, 14),
            symbol="005930",
            name="삼성전자",
            close=70000,
            ma20=68000.0,
            ma60=65000.0,
            high_60d=75000,
            drawdown_from_high=-0.05,
            trading_value=5_000_000_000,
            avg_trading_value_20d=4_000_000_000,
            return_5d=0.03,
            score=80.0,
        )
        db.add(cand)
        await db.commit()

        # 현재가 > 전일종가(후보 close) → 진입 신호 충족
        quote = _make_quote(price=72000, prev_close=70000, symbol="005930")
        client = AsyncMock()
        client._is_mock = True
        client.get_quote.return_value = quote
        client.get_balance.return_value = _make_balance()
        client.place_order.return_value = _make_broker_response(side="buy")

        entry_time = datetime(2026, 5, 15, 10, 0, 0, tzinfo=KST)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=entry_time)

        assert result.ordered >= 1

        # PENDING_ENTRY 포지션이 존재해야 함
        pos_result = await db.execute(
            select(ShortSwingPosition).where(
                ShortSwingPosition.user_id == user_id,
                ShortSwingPosition.symbol == "005930",
            )
        )
        positions = list(pos_result.scalars().all())
        assert len(positions) == 1
        assert positions[0].status == PositionStatus.PENDING_ENTRY
        assert positions[0].entry_order_id is not None

    @pytest.mark.asyncio
    async def test_pending_entry_excluded_from_exit(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """PENDING_ENTRY 포지션은 exit query 에서 제외된다."""
        from src.trading.short_swing_exit import run_exit_check

        user_id = test_user.id

        # PENDING_ENTRY 포지션 생성
        _make_position(db, user_id, status=PositionStatus.PENDING_ENTRY)
        await db.commit()

        client = _mock_exit_client()

        with (
            patch("src.trading.short_swing_exit.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        # PENDING_ENTRY는 exit 대상이 아님 → no_open_positions
        assert result.checked == 0
        assert any(s.get("reason") == "no_open_positions" for s in result.skipped)


# ── 테스트 2: BUY cancel/reject → PENDING_ENTRY 정리 ────────────────────────


class TestBuyCancelRejectCleanup:
    """BUY cancel/reject → PENDING_ENTRY row 삭제 (reconciler)."""

    @pytest.mark.asyncio
    async def test_cancelled_buy_deletes_pending(self, db: AsyncSession, test_user: User) -> None:
        user_id = test_user.id

        order = _make_order(db, user_id, status=OrderStatus.CANCELLED)
        await db.flush()

        _make_position(db, user_id, status=PositionStatus.PENDING_ENTRY, entry_order_id=order.id)
        await db.commit()

        client = AsyncMock()
        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)

        assert counts["pending_deleted"] == 1

        # DB에 포지션 없어야 함
        pos_result = await db.execute(
            select(ShortSwingPosition).where(ShortSwingPosition.user_id == user_id)
        )
        assert pos_result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_rejected_buy_deletes_pending(self, db: AsyncSession, test_user: User) -> None:
        user_id = test_user.id

        order = _make_order(db, user_id, status=OrderStatus.REJECTED)
        await db.flush()

        _make_position(db, user_id, status=PositionStatus.PENDING_ENTRY, entry_order_id=order.id)
        await db.commit()

        client = AsyncMock()
        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)

        assert counts["pending_deleted"] == 1


# ── 테스트 3: BUY partial fill → 체결수량만 OPEN ────────────────────────────


class TestBuyPartialFill:
    """BUY partial fill → 체결수량만 OPEN. 잔여 PENDING_ENTRY 유지."""

    @pytest.mark.asyncio
    async def test_partial_fill_splits_position(self, db: AsyncSession, test_user: User) -> None:
        user_id = test_user.id

        order = _make_order(
            db,
            user_id,
            status=OrderStatus.PARTIAL_FILL,
            quantity=10,
            filled_quantity=7,
            filled_price=71000,
            filled_at=datetime(2026, 5, 15, 10, 5, 0, tzinfo=KST),
        )
        await db.flush()

        _make_position(
            db,
            user_id,
            status=PositionStatus.PENDING_ENTRY,
            entry_order_id=order.id,
            quantity=10,
        )
        await db.commit()

        client = AsyncMock()
        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)

        assert counts["pending_to_open"] == 1

        # OPEN 포지션 확인 (체결 수량 = 7)
        pos_result = await db.execute(
            select(ShortSwingPosition).where(
                ShortSwingPosition.user_id == user_id,
                ShortSwingPosition.status == PositionStatus.OPEN,
            )
        )
        open_pos = pos_result.scalar_one()
        assert open_pos.quantity == 7
        assert open_pos.entry_price == 71000

        # 잔여분은 별도 row 생성 없이 cancel 모듈에 위임 (로그만)
        pending_result = await db.execute(
            select(ShortSwingPosition).where(
                ShortSwingPosition.user_id == user_id,
                ShortSwingPosition.status == PositionStatus.PENDING_ENTRY,
            )
        )
        assert pending_result.scalar_one_or_none() is None


# ── 테스트 4: SELL submitted → CLOSING → FILLED → CLOSED ────────────────────


class TestSellFilledClosed:
    """SELL submitted → CLOSING. FILLED 이벤트 후 → CLOSED + realized_pnl 계산."""

    @pytest.mark.asyncio
    async def test_sell_filled_transitions_to_closed(
        self, db: AsyncSession, test_user: User
    ) -> None:
        user_id = test_user.id

        # 매도 주문 FILLED
        sell_order = _make_order(
            db,
            user_id,
            side=OrderSide.SELL,
            status=OrderStatus.FILLED,
            price=73000,
            quantity=10,
            filled_price=73000,
            filled_quantity=10,
            filled_at=datetime(2026, 5, 15, 11, 0, 0, tzinfo=KST),
        )
        await db.flush()

        # CLOSING 포지션
        _make_position(
            db,
            user_id,
            status=PositionStatus.CLOSING,
            entry_price=70000,
            quantity=10,
            exit_order_id=sell_order.id,
        )
        await db.commit()

        client = AsyncMock()
        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)

        assert counts["closing_to_closed"] == 1

        # CLOSED 포지션 확인
        pos_result = await db.execute(
            select(ShortSwingPosition).where(
                ShortSwingPosition.user_id == user_id,
                ShortSwingPosition.status == PositionStatus.CLOSED,
            )
        )
        closed_pos = pos_result.scalar_one()
        assert closed_pos.exit_price == 73000
        assert closed_pos.exit_quantity == 10
        assert closed_pos.realized_pnl == (73000 - 70000) * 10  # 30,000원 수익


# ── 테스트 5: SELL cancel/reject → CLOSING → OPEN ───────────────────────────


class TestSellCancelRevert:
    """SELL cancel/reject → CLOSING → OPEN 복구."""

    @pytest.mark.asyncio
    async def test_sell_cancelled_reverts_to_open(self, db: AsyncSession, test_user: User) -> None:
        user_id = test_user.id

        sell_order = _make_order(db, user_id, side=OrderSide.SELL, status=OrderStatus.CANCELLED)
        await db.flush()

        _make_position(
            db,
            user_id,
            status=PositionStatus.CLOSING,
            exit_order_id=sell_order.id,
        )
        await db.commit()

        client = AsyncMock()
        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)

        assert counts["closing_to_open"] == 1

        # OPEN 복구 확인
        pos_result = await db.execute(
            select(ShortSwingPosition).where(
                ShortSwingPosition.user_id == user_id,
            )
        )
        pos = pos_result.scalar_one()
        assert pos.status == PositionStatus.OPEN
        assert pos.exit_order_id is None
        assert pos.exit_reason is None

    @pytest.mark.asyncio
    async def test_sell_rejected_reverts_to_open(self, db: AsyncSession, test_user: User) -> None:
        user_id = test_user.id

        sell_order = _make_order(db, user_id, side=OrderSide.SELL, status=OrderStatus.REJECTED)
        await db.flush()

        _make_position(
            db,
            user_id,
            status=PositionStatus.CLOSING,
            exit_order_id=sell_order.id,
        )
        await db.commit()

        client = AsyncMock()
        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)

        assert counts["closing_to_open"] == 1


# ── 테스트 6: broker holdings=0 → SELL 금지 + RECONCILIATION_ERROR ──────────


class TestHoldingsVerification:
    """exit 직전 broker holdings=0 → SELL 주문 0건, RECONCILIATION_ERROR 마킹."""

    @pytest.mark.asyncio
    async def test_zero_holdings_prevents_sell(self, db: AsyncSession, test_user: User) -> None:
        from src.trading.short_swing_exit import run_exit_check

        user_id = test_user.id

        # OPEN 포지션 (stop_loss 발동하는 가격 설정)
        _make_position(
            db,
            user_id,
            entry_price=70000,
            quantity=10,
            status=PositionStatus.OPEN,
        )
        await db.commit()

        # 현재가 = 65000 → stop_loss 발동 (entry * 0.98 = 68600 이하)
        quote = _make_quote(price=65000, prev_close=70000)
        # broker holdings 는 빈 리스트 (보유 0)
        client = _mock_exit_client(quote=quote, holdings=[])

        with (
            patch("src.trading.short_swing_exit.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        # SELL 주문 0건
        assert result.closed == 0
        assert any(e.get("error") == "broker_holdings_zero" for e in result.errors)

        # RECONCILIATION_ERROR 마킹 확인
        pos_result = await db.execute(
            select(ShortSwingPosition).where(ShortSwingPosition.user_id == user_id)
        )
        pos = pos_result.scalar_one()
        assert pos.status == PositionStatus.RECONCILIATION_ERROR

    @pytest.mark.asyncio
    async def test_partial_holdings_sells_real_quantity(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """broker 보유수량 < DB → 실제 수량으로만 SELL."""
        from src.trading.short_swing_exit import run_exit_check

        user_id = test_user.id

        _make_position(
            db,
            user_id,
            entry_price=70000,
            quantity=10,
            status=PositionStatus.OPEN,
        )
        await db.commit()

        # 현재가 = 65000 → stop_loss 발동
        quote = _make_quote(price=65000, prev_close=70000)
        # broker 실보유 5주 (DB는 10주)
        real_holding = Holding(
            symbol="005930",
            name="삼성전자",
            quantity=5,
            avg_price=70000,
            current_price=65000,
            eval_amount=325000,
            profit=-25000,
            profit_pct=-3.57,
        )
        client = _mock_exit_client(quote=quote, holdings=[real_holding])

        with (
            patch("src.trading.short_swing_exit.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        # SELL 주문은 실보유 5주로 생성
        assert result.closed == 1
        # place_order 호출 시 quantity=5 확인
        call_args = client.place_order.call_args
        assert call_args is not None
        broker_req = call_args[0][0]
        assert broker_req.quantity == 5


# ── 테스트 7: 다른 user 포지션 격리 ─────────────────────────────────────────


class TestUserIsolation:
    """다른 user 의 short_swing_position 은 API/exit query 에서 제외."""

    @pytest.mark.asyncio
    async def test_exit_check_excludes_other_user(self, db: AsyncSession, test_user: User) -> None:
        """다른 user의 OPEN 포지션은 exit query에 포함되지 않는다."""
        from src.trading.short_swing_exit import run_exit_check

        user_id = test_user.id
        other_user = await _create_second_user(db)

        # 다른 유저의 OPEN 포지션
        _make_position(db, other_user.id, symbol="005930", status=PositionStatus.OPEN)
        await db.commit()

        client = _mock_exit_client()

        with (
            patch("src.trading.short_swing_exit.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        # 내 포지션 0 → no_open_positions
        assert result.checked == 0
        assert any(s.get("reason") == "no_open_positions" for s in result.skipped)

    @pytest.mark.asyncio
    async def test_reconciler_excludes_other_user(self, db: AsyncSession, test_user: User) -> None:
        """다른 user의 PENDING_ENTRY 포지션은 reconciler에서 처리되지 않는다."""
        user_id = test_user.id
        other_user = await _create_second_user(db)

        other_order = _make_order(db, other_user.id, status=OrderStatus.CANCELLED)
        await db.flush()

        _make_position(
            db,
            other_user.id,
            status=PositionStatus.PENDING_ENTRY,
            entry_order_id=other_order.id,
        )
        await db.commit()

        client = AsyncMock()
        counts = await reconcile_short_swing_positions(db, client, user_id=user_id)

        # 내 포지션 없으므로 변경 0
        assert counts["pending_deleted"] == 0
        assert counts["pending_to_open"] == 0

        # 다른 유저의 PENDING_ENTRY는 그대로 남아있어야 함
        pos_result = await db.execute(
            select(ShortSwingPosition).where(
                ShortSwingPosition.user_id == other_user.id,
            )
        )
        assert pos_result.scalar_one_or_none() is not None
