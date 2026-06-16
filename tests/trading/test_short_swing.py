"""Short Swing 장중 진입 엔진 테스트.

설계 문서 12.2절 — 진입 가드, 진입 신호, 수량 계산, 시간 가드 등 13+ 케이스.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import AccountBalance, BrokerOrderResponse, Holding, Quote
from src.models.order import Order, OrderSide, OrderStatus
from src.models.short_swing import ShortSwingCandidate
from src.trading.kill_switch import KillSwitchStatus
from src.trading.short_swing import (
    _count_today_new_entries,
    _has_pending_buy,
    _is_held,
    _parse_time,
    load_short_swing_params,
    run_entry_check,
)
from src.utils.time import KST

# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

_TEST_USER_ID = uuid.uuid4()

# 진입 시간대 (10:00)
_ENTRY_TIME = datetime(2026, 5, 15, 10, 0, 0, tzinfo=KST)
# 진입 시간 밖 (08:00)
_BEFORE_ENTRY = datetime(2026, 5, 15, 8, 0, 0, tzinfo=KST)
# 진입 시간 밖 (14:00)
_AFTER_ENTRY = datetime(2026, 5, 15, 14, 0, 0, tzinfo=KST)


def _make_quote(
    symbol: str = "005930",
    name: str = "삼성전자",
    price: int = 72000,
    prev_close: int = 70000,
    open_price: int = 70500,
    high: int = 72500,
    low: int = 70000,
    volume: int = 5_000_000,
) -> Quote:
    return Quote(
        symbol=symbol,
        name=name,
        price=price,
        change=price - prev_close,
        change_pct=round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
        volume=volume,
        high=high,
        low=low,
        open=open_price,
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


def _make_candidate(
    db: AsyncSession,
    symbol: str = "005930",
    name: str = "삼성전자",
    trade_date: date | None = None,
    close: int = 70000,
    score: float = 80.0,
    prev_day_high: int | None = None,
) -> ShortSwingCandidate:
    """후보 종목 생성 (DB 세션에 add)."""
    cand = ShortSwingCandidate(
        trade_date=trade_date or date(2026, 5, 14),
        symbol=symbol,
        name=name,
        close=close,
        prev_day_high=prev_day_high if prev_day_high is not None else close + 500,
        ma20=68000.0,
        ma60=65000.0,
        high_60d=75000,
        drawdown_from_high=-0.05,
        trading_value=5_000_000_000,
        avg_trading_value_20d=4_000_000_000,
        return_5d=0.03,
        score=score,
    )
    db.add(cand)
    return cand


def _make_broker_response(symbol: str = "005930") -> BrokerOrderResponse:
    return BrokerOrderResponse(
        order_no="T00001",
        symbol=symbol,
        side="buy",
        price=72000,
        quantity=10,
        status="submitted",
        message="주문 접수",
    )


def _mock_client(
    quote: Quote | None = None,
    balance: AccountBalance | None = None,
    broker_response: BrokerOrderResponse | None = None,
) -> AsyncMock:
    """표준 mock 브로커 클라이언트."""
    client = AsyncMock()
    client._is_mock = True
    client.get_quote.return_value = quote or _make_quote()
    client.get_balance.return_value = balance or _make_balance()
    client.place_order.return_value = broker_response or _make_broker_response()
    return client


# ── PR B: mock-only guard + regime overlay 회귀 ──────────────────────────────


class TestMockOnlyGuard:
    """PR B: is_mock_trading=False 면 run_entry_check 가 RuntimeError."""

    @pytest.mark.asyncio
    async def test_raises_when_not_mock(self, db: AsyncSession) -> None:
        client = _mock_client()
        from src.config.settings import Settings, get_settings

        get_settings.cache_clear()
        with (
            patch(
                "src.config.settings.Settings",
                lambda **_: Settings(is_mock_trading=False),  # type: ignore[call-arg]
            ),
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            pytest.raises(RuntimeError, match="mock-only"),
        ):
            await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)
        get_settings.cache_clear()


class TestRegimeOverlayBlock:
    """PR B: regime_overlay.allow_new_entry=False 면 신규 진입 차단."""

    @pytest.mark.asyncio
    async def test_risk_off_blocks_entry(self, db: AsyncSession) -> None:
        from src.trading.short_swing_regime import RegimeOverlay

        overlay = RegimeOverlay(
            regime="risk_off",
            allow_new_entry=False,
            max_new_entries_override=0,
            reason="regime_block_risk_off",
        )
        client = _mock_client()
        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(
                db,
                client,
                user_id=_TEST_USER_ID,
                now=_ENTRY_TIME,
                regime_overlay=overlay,
            )
        assert result.ordered == 0
        assert any(s.get("reason") == "regime_block_risk_off" for s in result.skipped), (
            f"unexpected skips: {result.skipped}"
        )


class TestRegimeOverlayMaxNewEntriesOverride:
    """PR B: max_new_entries_override 가 effective 상한을 낮춤."""

    @pytest.mark.asyncio
    async def test_override_zero_skips_immediately(self, db: AsyncSession) -> None:
        from src.trading.short_swing_regime import RegimeOverlay

        # allow_new_entry=True 지만 override=0 → today_new(0) >= effective(0) → skip
        overlay = RegimeOverlay(
            regime="custom",
            allow_new_entry=True,
            max_new_entries_override=0,
            reason="regime_custom_zero",
        )
        client = _mock_client()
        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(
                db,
                client,
                user_id=_TEST_USER_ID,
                now=_ENTRY_TIME,
                regime_overlay=overlay,
            )
        assert result.ordered == 0
        assert any(s.get("reason") == "regime_max_new_entries_reached" for s in result.skipped)


# ── 테스트 ────────────────────────────────────────────────────────────────────


class TestParseTime:
    """_parse_time 유틸."""

    def test_normal(self) -> None:
        assert _parse_time("09:20") == time(9, 20)
        assert _parse_time("13:00") == time(13, 0)

    def test_midnight(self) -> None:
        assert _parse_time("00:00") == time(0, 0)


class TestIsHeld:
    """_is_held 유틸."""

    def test_held(self) -> None:
        h = Holding(
            symbol="005930",
            name="삼성전자",
            quantity=10,
            avg_price=70000,
            current_price=72000,
            eval_amount=720000,
            profit=20000,
            profit_pct=2.86,
        )
        assert _is_held([h], "005930") is True

    def test_not_held(self) -> None:
        assert _is_held([], "005930") is False


class TestActiveStrategyGuard:
    """ACTIVE_STRATEGY != short_swing이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_wrong_strategy_skips(self, db: AsyncSession) -> None:
        client = _mock_client()
        with patch(
            "src.trading.short_swing.is_strategy_enabled_db",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)
        assert result.ordered == 0
        assert any(s.get("reason") == "strategy_disabled" for s in result.skipped)
        client.get_quote.assert_not_called()


class TestKillSwitchGuard:
    """kill switch active면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_kill_switch_active_skips(self, db: AsyncSession) -> None:
        client = _mock_client()
        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            from src.trading.kill_switch import KillSwitchStatus

            mock_ks.get_status.return_value = KillSwitchStatus.SOFT_STOPPED
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)
        assert result.ordered == 0
        assert any(s.get("reason") == "kill_switch_active" for s in result.skipped)


class TestMaxPositionsGuard:
    """short_swing 활성 포지션 >= max_positions 이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_max_positions_skips(self, db: AsyncSession, test_user: object) -> None:
        """short_swing 포지션 5개 → max_positions(5) 도달 → 스킵."""
        from src.models.short_swing import PositionStatus, ShortSwingPosition

        user_id = test_user.id  # type: ignore[attr-defined]

        # short_swing 포지션 5개 생성 (OPEN)
        for i in range(5):
            db.add(
                ShortSwingPosition(
                    user_id=user_id,
                    symbol=f"00{i}000",
                    name=f"종목{i}",
                    entry_date=date(2026, 5, 14),
                    entry_time=_ENTRY_TIME,
                    entry_price=10000,
                    quantity=10,
                    highest_price_since_entry=10000,
                    stop_price=9800,
                    take_profit_price=10400,
                    trailing_armed=False,
                    max_holding_until=date(2026, 5, 23),
                    status=PositionStatus.OPEN,
                )
            )
        await db.commit()

        client = _mock_client()

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "max_positions_reached" for s in result.skipped)

    @pytest.mark.asyncio
    async def test_other_strategy_holdings_ignored(
        self, db: AsyncSession, test_user: object
    ) -> None:
        """다른 전략 holdings 5개 보유해도 short_swing 포지션 0개 → 진입 가능 (테스트 #추가B)."""
        user_id = test_user.id  # type: ignore[attr-defined]

        # holdings에 5개 보유하지만 short_swing 포지션은 0개
        holdings = [
            Holding(
                symbol=f"00{i}000",
                name=f"종목{i}",
                quantity=10,
                avg_price=10000,
                current_price=10000,
                eval_amount=100000,
                profit=0,
                profit_pct=0,
            )
            for i in range(5)
        ]
        balance = _make_balance(holdings=holdings)
        client = _mock_client(balance=balance)

        # 후보 1건 생성 (진입 시도 가능하도록)
        _make_candidate(db, symbol="005930", trade_date=date(2026, 5, 14), prev_day_high=71000)
        await db.commit()

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        # max_positions_reached로 스킵되지 않아야 함
        assert not any(s.get("reason") == "max_positions_reached" for s in result.skipped)


class TestMaxDailyNewPositionsGuard:
    """오늘 신규 진입 수 >= max_daily_new_positions 이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_max_daily_skips(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # 오늘 short_swing 매수 주문 2건 생성
        for _ in range(2):
            order = Order(
                user_id=user_id,
                symbol="005930",
                symbol_name="삼성전자",
                side=OrderSide.BUY,
                price=70000,
                quantity=10,
                reason="short_swing",
                is_mock=True,
            )
            db.add(order)
        await db.commit()

        client = _mock_client()

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "max_daily_new_positions_reached" for s in result.skipped)


class TestInsufficientCashGuard:
    """available_cash <= min_order_amount 이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_low_cash_skips(self, db: AsyncSession) -> None:
        balance = _make_balance(available_cash=100_000)  # < 500,000
        client = _mock_client(balance=balance)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "insufficient_cash" for s in result.skipped)


class TestGapUpGuard:
    """시초 갭상승률 > avoid_gap_up_pct 이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_gap_up_skips(self, db: AsyncSession) -> None:
        # 갭상승 10% (> 기본 8%)
        quote = _make_quote(price=77000, prev_close=70000, open_price=77000)
        client = _mock_client(quote=quote)

        _make_candidate(db, close=70000)
        await db.commit()

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "gap_up_exceeded" for s in result.skipped)


class TestIntradayRiseGuard:
    """당일 상승률 > avoid_intraday_rise_pct 이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_intraday_rise_skips(self, db: AsyncSession) -> None:
        # 당일 상승 20% (> 기본 15%)
        quote = _make_quote(price=84000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        _make_candidate(db, close=70000)
        await db.commit()

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "intraday_rise_exceeded" for s in result.skipped)


class TestAlreadyHeldGuard:
    """이미 보유 중이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_already_held_skips(self, db: AsyncSession) -> None:
        holdings = [
            Holding(
                symbol="005930",
                name="삼성전자",
                quantity=10,
                avg_price=70000,
                current_price=72000,
                eval_amount=720000,
                profit=20000,
                profit_pct=2.86,
            )
        ]
        balance = _make_balance(holdings=holdings)
        client = _mock_client(balance=balance)

        _make_candidate(db, symbol="005930", close=70000)
        await db.commit()

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "already_held" for s in result.skipped)


class TestPendingBuyGuard:
    """pending buy order 있으면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_pending_buy_skips(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # pending 매수 주문 생성
        pending = Order(
            user_id=user_id,
            symbol="005930",
            symbol_name="삼성전자",
            side=OrderSide.BUY,
            price=70000,
            quantity=10,
            status=OrderStatus.SUBMITTED,
            is_mock=True,
        )
        db.add(pending)

        _make_candidate(db, symbol="005930", close=70000)
        await db.commit()

        # 현재가 > 전일종가(=cand.close) → 진입 신호 충족
        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "pending_buy_exists" for s in result.skipped)


class TestEntrySignal:
    """전일 고가 돌파 + VWAP 위면 주문 생성."""

    @pytest.mark.asyncio
    async def test_entry_signal_creates_order(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # 전일 종가 70000, prev_day_high 70500, 현재가 72000 → 돌파
        _make_candidate(db, symbol="005930", name="삼성전자", close=70000)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        assert result.ordered == 1
        assert result.checked >= 1
        client.place_order.assert_called_once()


class TestNoEntrySignal:
    """전일 고가 미돌파면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_no_breakout_skips(self, db: AsyncSession) -> None:
        # prev_day_high=70500, 현재가 69000 → 미돌파
        _make_candidate(db, close=70000)
        await db.commit()

        quote = _make_quote(price=69000, prev_close=70000, open_price=70000)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=70000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "no_entry_signal" for s in result.skipped)


class TestZeroQuantity:
    """수량 <= 0이면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_zero_quantity_skips(self, db: AsyncSession) -> None:
        # 매우 비싼 주가 → quantity = floor(500000 / 10000000) = 0
        _make_candidate(db, close=9_000_000)
        await db.commit()

        quote = _make_quote(price=10_000_000, prev_close=9_000_000, open_price=9_100_000)
        balance = _make_balance(available_cash=600_000)
        client = _mock_client(quote=quote, balance=balance)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=9_500_000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "zero_quantity" for s in result.skipped)


class TestBudgetInjection:
    """PR 2a: allowed_budget / max_order_amount 가 entry sizing 에 실제 반영되는지.

    short_swing handler 가 orchestrator budget 을 버리던 결함의 회귀 방지.
    dry_run 으로 sizing 결과(would_order)만 검사 (broker 주문/체결 호출 없음).
    """

    async def _run(
        self,
        db: AsyncSession,
        *,
        allowed_budget: int | None,
        max_order_amount: int | None = None,
        available_cash: int = 5_000_000,
        symbols: tuple[str, ...] = ("005930",),
    ) -> object:
        for i, sym in enumerate(symbols):
            _make_candidate(db, symbol=sym, name=f"종목{i}", close=70000)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote, balance=_make_balance(available_cash=available_cash))

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            return await run_entry_check(
                db,
                client,
                user_id=_TEST_USER_ID,
                now=_ENTRY_TIME,
                dry_run=True,
                allowed_budget=allowed_budget,
                max_order_amount=max_order_amount,
            )

    @pytest.mark.asyncio
    async def test_budget_caps_sizing_below_full_cash(self, db: AsyncSession) -> None:
        """allowed_budget(1M) < 전체 현금(5M) → sizing 이 예산 기준으로 축소."""
        result = await self._run(db, allowed_budget=1_000_000)

        assert len(result.would_order) == 1
        order = result.would_order[0]
        # 6주 x 72,000 = 432,000 <= allowed_budget
        assert order["quantity"] == 6
        assert order["price"] * order["quantity"] <= 1_000_000

    @pytest.mark.asyncio
    async def test_legacy_none_uses_full_cash(self, db: AsyncSession) -> None:
        """allowed_budget=None → 레거시(전체 현금) 사이징 유지 (하위호환)."""
        result = await self._run(db, allowed_budget=None)

        assert len(result.would_order) == 1
        # 전체 현금 5M 기준 → 11주 (예산 적용 시 6주보다 큼)
        assert result.would_order[0]["quantity"] == 11

    @pytest.mark.asyncio
    async def test_budget_zero_blocks_entry(self, db: AsyncSession) -> None:
        """allowed_budget<=0 → 신규 진입 차단 + 명확한 reason."""
        result = await self._run(db, allowed_budget=0)

        assert result.ordered == 0
        assert result.would_order == []
        assert any(s.get("reason") == "insufficient_budget" for s in result.skipped)

    @pytest.mark.asyncio
    async def test_budget_negative_blocks_entry(self, db: AsyncSession) -> None:
        result = await self._run(db, allowed_budget=-1)
        assert result.would_order == []
        assert any(s.get("reason") == "insufficient_budget" for s in result.skipped)

    @pytest.mark.asyncio
    async def test_max_order_amount_caps_per_order(self, db: AsyncSession) -> None:
        """max_order_amount(>min_order) 가 1회 주문 금액을 제한.

        예산 무제한이면 target≈850,000(11주)이지만 cap 600,000 → 8주.
        """
        result = await self._run(db, allowed_budget=5_000_000, max_order_amount=600_000)

        assert len(result.would_order) == 1
        order = result.would_order[0]
        # target_value 가 600,000 으로 캡 → floor(600000/72000)=8
        assert order["quantity"] == 8
        assert order["price"] * order["quantity"] <= 600_000

    @pytest.mark.asyncio
    async def test_max_order_amount_below_min_blocks(self, db: AsyncSession) -> None:
        """max_order_amount < min_order_amount → 주문 불가 (target_value_below_min)."""
        result = await self._run(db, allowed_budget=5_000_000, max_order_amount=400_000)

        assert result.would_order == []
        assert any(s.get("reason") == "target_value_below_min" for s in result.skipped)

    @pytest.mark.asyncio
    async def test_budget_decrements_across_candidates(self, db: AsyncSession) -> None:
        """한 run 의 다음 후보는 잔여 예산만 사용 → 예산 소진 시 추가 주문 차단."""
        result = await self._run(db, allowed_budget=900_000, symbols=("005930", "000660"))

        # 첫 후보만 주문(432,000 차감), 잔여 예산은 min_order_amount 미만 → 두번째 SKIP
        assert len(result.would_order) == 1
        assert any(s.get("reason") == "target_value_below_min" for s in result.skipped)


class TestTimeGuard:
    """진입 시간대 외에는 주문 안 함."""

    @pytest.mark.asyncio
    async def test_before_entry_window(self, db: AsyncSession) -> None:
        client = _mock_client()
        with patch(
            "src.trading.short_swing.is_strategy_enabled_db",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_BEFORE_ENTRY)
        assert result.ordered == 0
        assert any(s.get("reason") == "outside_entry_window" for s in result.skipped)

    @pytest.mark.asyncio
    async def test_after_entry_window(self, db: AsyncSession) -> None:
        client = _mock_client()
        with patch(
            "src.trading.short_swing.is_strategy_enabled_db",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_AFTER_ENTRY)
        assert result.ordered == 0
        assert any(s.get("reason") == "outside_entry_window" for s in result.skipped)


class TestNoCandidates:
    """후보 없으면 주문 안 함."""

    @pytest.mark.asyncio
    async def test_empty_candidates_skips(self, db: AsyncSession) -> None:
        client = _mock_client()

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "no_candidates" for s in result.skipped)


class TestDrawdownGuardBlocks:
    """drawdown_guard 차단 시 주문 안 함."""

    @pytest.mark.asyncio
    async def test_drawdown_blocks(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        _make_candidate(db, close=70000)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.drawdown_guard.run_all_checks",
                new_callable=AsyncMock,
                side_effect=Exception("드로우다운 초과"),
            ),
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any("drawdown_guard" in s.get("reason", "") for s in result.skipped)


class TestCountTodayNewEntries:
    """_count_today_new_entries 헬퍼 테스트."""

    @pytest.mark.asyncio
    async def test_counts_today_short_swing_buys(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]
        today = date(2026, 5, 15)

        # short_swing 매수 1건
        order = Order(
            user_id=user_id,
            symbol="005930",
            symbol_name="삼성전자",
            side=OrderSide.BUY,
            price=70000,
            quantity=10,
            reason="short_swing",
            is_mock=True,
        )
        db.add(order)
        await db.commit()

        count = await _count_today_new_entries(db, user_id, today)
        assert count == 1

    @pytest.mark.asyncio
    async def test_ignores_failed_orders(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]
        today = date(2026, 5, 15)

        order = Order(
            user_id=user_id,
            symbol="005930",
            symbol_name="삼성전자",
            side=OrderSide.BUY,
            price=70000,
            quantity=10,
            reason="short_swing",
            status=OrderStatus.FAILED,
            is_mock=True,
        )
        db.add(order)
        await db.commit()

        count = await _count_today_new_entries(db, user_id, today)
        assert count == 0


class TestHasPendingBuy:
    """_has_pending_buy 헬퍼 테스트."""

    @pytest.mark.asyncio
    async def test_detects_pending(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        order = Order(
            user_id=user_id,
            symbol="005930",
            symbol_name="삼성전자",
            side=OrderSide.BUY,
            price=70000,
            quantity=10,
            status=OrderStatus.SUBMITTED,
            is_mock=True,
        )
        db.add(order)
        await db.commit()

        assert await _has_pending_buy(db, user_id, "005930") is True
        assert await _has_pending_buy(db, user_id, "000660") is False


class TestLoadShortSwingParams:
    """load_short_swing_params DB 로더."""

    @pytest.mark.asyncio
    async def test_defaults_on_empty_db(self, db: AsyncSession) -> None:
        """strategy_config 테이블 없으면 기본값 반환."""
        params = await load_short_swing_params(db)
        assert params.max_positions == 5
        assert params.min_order_amount == 500_000
        assert params.avoid_gap_up_pct == 0.08


class TestMultipleCandidatesOrdering:
    """여러 후보 중 score 높은 순으로 진입."""

    @pytest.mark.asyncio
    async def test_high_score_first(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        _make_candidate(db, symbol="005930", name="삼성전자", close=70000, score=90)
        _make_candidate(db, symbol="000660", name="SK하이닉스", close=150000, score=70)
        await db.commit()

        # 두 종목 모두 돌파 조건 충족
        async def mock_get_quote(symbol: str) -> Quote:
            if symbol == "005930":
                return _make_quote(symbol="005930", price=72000, prev_close=70000, open_price=70500)
            return _make_quote(
                symbol="000660",
                name="SK하이닉스",
                price=155000,
                prev_close=150000,
                open_price=151000,
            )

        client = _mock_client()
        client.get_quote = AsyncMock(side_effect=mock_get_quote)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=70000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        # max_daily_new_positions=2 이므로 둘 다 주문 가능
        assert result.ordered == 2


class TestPositionCreatedOnEntry:
    """매수 주문 SUBMITTED 시 short_swing_positions row 생성 확인."""

    @pytest.mark.asyncio
    async def test_position_row_created(self, db: AsyncSession, test_user: object) -> None:
        from sqlalchemy import select as sa_select

        from src.models.short_swing import PositionStatus, ShortSwingPosition

        user_id = test_user.id  # type: ignore[attr-defined]

        _make_candidate(db, symbol="005930", name="삼성전자", close=70000)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch(
                "src.trading.short_swing.is_strategy_enabled_db",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME)

        assert result.ordered == 1

        # position row 검증
        pos_result = await db.execute(
            sa_select(ShortSwingPosition).where(ShortSwingPosition.symbol == "005930")
        )
        pos = pos_result.scalar_one()
        assert pos.status == PositionStatus.PENDING_ENTRY
        assert pos.entry_price == 72000
        assert pos.trailing_armed is False
        assert pos.highest_price_since_entry == 72000
        assert pos.entry_date == date(2026, 5, 15)
        assert pos.entry_order_id is not None
        assert pos.user_id == user_id
