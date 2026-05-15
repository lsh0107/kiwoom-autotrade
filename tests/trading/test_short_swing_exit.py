"""Short Swing 장중 청산 엔진 테스트.

설계 문서 12.3절 — stop_loss, take_profit, trailing, max_holding_days,
kill_switch, broker 실패 등 8+ 케이스.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import BrokerOrderResponse, Quote
from src.models.short_swing import PositionStatus, ShortSwingPosition
from src.trading.kill_switch import KillSwitchStatus
from src.trading.short_swing_exit import run_exit_check
from src.utils.time import KST

# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

_TEST_USER_ID = uuid.uuid4()

# 청산 시간대 (10:00)
_EXIT_TIME = datetime(2026, 5, 15, 10, 0, 0, tzinfo=KST)
# 청산 시간 밖 (08:00)
_BEFORE_EXIT = datetime(2026, 5, 15, 8, 0, 0, tzinfo=KST)
# 청산 시간 밖 (16:00)
_AFTER_EXIT = datetime(2026, 5, 15, 16, 0, 0, tzinfo=KST)


def _make_position(
    db: AsyncSession,
    symbol: str = "005930",
    name: str = "삼성전자",
    entry_price: int = 70000,
    quantity: int = 10,
    trailing_armed: bool = False,
    highest_price: int | None = None,
    max_holding_until: date | None = None,
    status: PositionStatus = PositionStatus.OPEN,
    user_id: uuid.UUID | None = None,
) -> ShortSwingPosition:
    """테스트 포지션 생성 (DB 세션에 add)."""
    pos = ShortSwingPosition(
        user_id=user_id or _TEST_USER_ID,
        symbol=symbol,
        name=name,
        entry_date=date(2026, 5, 14),
        entry_time=datetime(2026, 5, 14, 10, 0, 0, tzinfo=KST),
        entry_price=entry_price,
        quantity=quantity,
        highest_price_since_entry=highest_price or entry_price,
        stop_price=math.floor(entry_price * (1 + (-0.02))),
        take_profit_price=math.floor(entry_price * (1 + 0.04)),
        trailing_armed=trailing_armed,
        max_holding_until=max_holding_until or date(2026, 5, 23),
        status=status,
    )
    db.add(pos)
    return pos


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


def _make_broker_response(
    symbol: str = "005930",
    status: str = "submitted",
    message: str = "주문 접수",
) -> BrokerOrderResponse:
    return BrokerOrderResponse(
        order_no="T00001",
        symbol=symbol,
        side="sell",
        price=70000,
        quantity=10,
        status=status,
        message=message,
    )


def _mock_client(
    quote: Quote | None = None,
    broker_response: BrokerOrderResponse | None = None,
    holdings: list | None = None,
) -> AsyncMock:
    """표준 mock 브로커 클라이언트."""
    client = AsyncMock()
    client._is_mock = True
    client.get_quote.return_value = quote or _make_quote()
    client.place_order.return_value = broker_response or _make_broker_response()
    # holdings 기본: 포지션 symbol 보유 (exit 통과)
    if holdings is None:
        from src.broker.schemas import Holding

        holdings = [
            Holding(
                symbol="005930",
                name="삼성전자",
                quantity=100,
                avg_price=70000,
                current_price=72000,
                eval_amount=7_200_000,
                profit=200_000,
                profit_pct=2.86,
            ),
        ]
    client.get_holdings.return_value = holdings
    return client


# ── 테스트 ────────────────────────────────────────────────────────────────────


class TestActiveStrategyGuard:
    """ACTIVE_STRATEGY != short_swing이면 청산 안 함."""

    @pytest.mark.asyncio
    async def test_wrong_strategy_skips(self, db: AsyncSession) -> None:
        client = _mock_client()
        with patch(
            "src.trading.short_swing_exit.get_active_strategy",
            return_value="cross_momentum",
        ):
            result = await run_exit_check(db, client, user_id=_TEST_USER_ID, now=_EXIT_TIME)
        assert result.closed == 0
        assert any(s.get("reason") == "active_strategy_mismatch" for s in result.skipped)


class TestTimeGuard:
    """청산 시간대 외에는 청산 안 함."""

    @pytest.mark.asyncio
    async def test_before_exit_window(self, db: AsyncSession) -> None:
        client = _mock_client()
        with patch(
            "src.trading.short_swing_exit.get_active_strategy",
            return_value="short_swing",
        ):
            result = await run_exit_check(db, client, user_id=_TEST_USER_ID, now=_BEFORE_EXIT)
        assert result.closed == 0
        assert any(s.get("reason") == "outside_exit_window" for s in result.skipped)

    @pytest.mark.asyncio
    async def test_after_exit_window(self, db: AsyncSession) -> None:
        client = _mock_client()
        with patch(
            "src.trading.short_swing_exit.get_active_strategy",
            return_value="short_swing",
        ):
            result = await run_exit_check(db, client, user_id=_TEST_USER_ID, now=_AFTER_EXIT)
        assert result.closed == 0
        assert any(s.get("reason") == "outside_exit_window" for s in result.skipped)


class TestNoOpenPositions:
    """open 포지션 없으면 청산 안 함."""

    @pytest.mark.asyncio
    async def test_no_positions_skips(self, db: AsyncSession) -> None:
        client = _mock_client()
        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=_TEST_USER_ID, now=_EXIT_TIME)
        assert result.closed == 0
        assert any(s.get("reason") == "no_open_positions" for s in result.skipped)


class TestStopLoss:
    """stop_loss 발동 → SELL 주문 생성 + status='closing'."""

    @pytest.mark.asyncio
    async def test_stop_loss_triggers(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # entry_price=70000, stop_loss=-0.02 → 가격 68600 이하에서 발동
        _make_position(db, entry_price=70000, user_id=user_id)
        await db.commit()

        # 현재가 68000 < 68600
        quote = _make_quote(price=68000, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 1
        assert result.actions[0].reason == "stop_loss"
        assert result.actions[0].success is True
        client.place_order.assert_called_once()


class TestTakeProfit:
    """take_profit 발동."""

    @pytest.mark.asyncio
    async def test_take_profit_triggers(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # entry_price=70000, take_profit=0.04 → 가격 72800 이상에서 발동
        _make_position(db, entry_price=70000, user_id=user_id)
        await db.commit()

        # 현재가 73000 >= 72800
        quote = _make_quote(price=73000, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 1
        assert result.actions[0].reason == "take_profit"
        assert result.actions[0].success is True


class TestTrailingNotArmed:
    """trailing_armed 전에는 trailing_stop 미발동."""

    @pytest.mark.asyncio
    async def test_trailing_not_triggered_before_armed(
        self, db: AsyncSession, test_user: object
    ) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # trailing_armed=False, highest=72000
        # trailing_stop_pct=-0.015 → trailing_stop = 72000*(1-0.015) = 70920
        # 현재가 71000 > 70920 이지만 armed가 아니므로 미발동
        # 또한 stop_loss 68600 / take_profit 72800 조건도 미충족
        _make_position(
            db, entry_price=70000, highest_price=72000, trailing_armed=False, user_id=user_id
        )
        await db.commit()

        quote = _make_quote(price=71000, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 0
        assert any(s.get("reason") == "no_exit_condition" for s in result.skipped)


class TestTrailingArmedTriggers:
    """trailing_armed 후 trailing_stop 발동."""

    @pytest.mark.asyncio
    async def test_trailing_stop_triggers(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # trailing_armed=True, highest=74000
        # trailing_stop_pct=-0.015 → trailing_stop = 74000*(1-0.015) = 72890
        # 현재가 72500 <= 72890 → 발동
        # stop_loss 68600 / take_profit 72800: 72500 < 72800 이라 take_profit 미발동
        _make_position(
            db, entry_price=70000, highest_price=74000, trailing_armed=True, user_id=user_id
        )
        await db.commit()

        quote = _make_quote(price=72500, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 1
        assert result.actions[0].reason == "trailing_stop"
        assert result.actions[0].success is True


class TestMaxHoldingDays:
    """max_holding_days 발동."""

    @pytest.mark.asyncio
    async def test_max_holding_triggers(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # max_holding_until = 오늘 → 발동
        _make_position(db, entry_price=70000, max_holding_until=date(2026, 5, 15), user_id=user_id)
        await db.commit()

        # 현재가는 stop/take 범위 밖 (정상 영역)
        quote = _make_quote(price=71000, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 1
        assert result.actions[0].reason == "max_holding_days"
        assert result.actions[0].success is True


class TestKillSwitchTriggersExit:
    """kill_switch active → 전량 청산 발동."""

    @pytest.mark.asyncio
    async def test_kill_switch_exits(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        _make_position(db, entry_price=70000, user_id=user_id)
        await db.commit()

        # 현재가 정상 (stop/take 범위 밖)
        quote = _make_quote(price=71000, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.SOFT_STOPPED
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 1
        assert result.actions[0].reason == "kill_switch"
        assert result.actions[0].success is True


class TestBrokerFailure:
    """broker 실패 → order_failed 기록, status='open' 유지."""

    @pytest.mark.asyncio
    async def test_broker_failure_keeps_open(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        pos = _make_position(db, entry_price=70000, user_id=user_id)
        await db.commit()

        # stop_loss 발동 가격
        quote = _make_quote(price=68000, prev_close=70000)
        client = _mock_client(quote=quote)
        # place_order에서 예외 발생
        client.place_order.side_effect = Exception("브로커 연결 실패")

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 0
        assert len(result.errors) >= 1
        assert any(a.reason == "stop_loss" and not a.success for a in result.actions)

        # 포지션이 여전히 open인지 확인
        await db.refresh(pos)
        assert pos.status == PositionStatus.OPEN


class TestHighestPriceUpdate:
    """현재가 > highest_price_since_entry 시 갱신 확인."""

    @pytest.mark.asyncio
    async def test_highest_price_updated(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        pos = _make_position(db, entry_price=70000, highest_price=70000, user_id=user_id)
        await db.commit()

        # 현재가 71500 > 70000 (highest) — stop/take 범위 밖이므로 청산 안 함
        quote = _make_quote(price=71500, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 0
        await db.refresh(pos)
        assert pos.highest_price_since_entry == 71500


class TestTrailingArmedActivation:
    """현재가 >= entry_price*(1+trailing_armed_pct) 시 trailing_armed 활성화."""

    @pytest.mark.asyncio
    async def test_trailing_armed_activation(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # trailing_armed_pct=0.03 → 72100 이상이면 활성화
        pos = _make_position(db, entry_price=70000, trailing_armed=False, user_id=user_id)
        await db.commit()

        # 현재가 72200 >= 72100 — take_profit 72800 미만이라 청산 안 됨
        quote = _make_quote(price=72200, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 0
        await db.refresh(pos)
        assert pos.trailing_armed is True


class TestStopLossNegativeSign:
    """stop_loss 음수 부호 규칙 검증 — -0.02 = 2% 하락."""

    @pytest.mark.asyncio
    async def test_stop_loss_sign_convention(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # entry_price=100000, stop_loss=-0.02 → 98000
        _make_position(db, entry_price=100000, user_id=user_id)
        await db.commit()

        # 경계값: 98000 정확히 → 발동 (<=)
        quote = _make_quote(price=98000, prev_close=100000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=_EXIT_TIME)

        assert result.closed == 1
        assert result.actions[0].reason == "stop_loss"

        # 경계 바로 위: 98001 → 미발동
        _make_position(db, symbol="000660", name="SK하이닉스", entry_price=100000, user_id=user_id)
        await db.commit()

        quote2 = _make_quote(symbol="000660", price=98001, prev_close=100000)
        client2 = _mock_client(quote=quote2)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks2,
        ):
            mock_ks2.get_status.return_value = KillSwitchStatus.NORMAL
            result2 = await run_exit_check(db, client2, user_id=user_id, now=_EXIT_TIME)

        assert result2.closed == 0
        assert any(s.get("reason") == "no_exit_condition" for s in result2.skipped)


class TestMA20PendingNextDayExit:
    """MA20 이탈 마킹 후 다음 거래일 우선 청산 (테스트 #추가A)."""

    @pytest.mark.asyncio
    async def test_ma20_pending_triggers_next_day(
        self, db: AsyncSession, test_user: object
    ) -> None:
        """exit_reason=MA20_BREAKDOWN 마킹 포지션 → 다음 사이클 우선 청산."""
        from src.models.short_swing import ExitReason

        user_id = test_user.id  # type: ignore[attr-defined]

        # exit_reason이 이미 MA20_BREAKDOWN으로 마킹된 포지션
        pos = _make_position(db, entry_price=70000, user_id=user_id)
        pos.exit_reason = ExitReason.MA20_BREAKDOWN
        await db.commit()

        # 현재가는 stop/take 범위 밖 (일반 조건 미충족)
        # 다음 거래일 09:25 — 우선 청산 시간대
        next_day = datetime(2026, 5, 16, 9, 25, 0, tzinfo=KST)
        quote = _make_quote(price=71000, prev_close=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(db, client, user_id=user_id, now=next_day)

        assert result.closed == 1
        assert result.actions[0].reason == "ma20_breakdown"
        assert result.actions[0].success is True
        client.place_order.assert_called_once()
