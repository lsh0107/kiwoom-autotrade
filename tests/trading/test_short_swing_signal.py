"""Short Swing 진입 신호 테스트 — VWAP, prev_day_high, dry_run.

HOTFIX B 테스트 8: 실데이터 신호 + dry_run 시뮬레이션.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import AccountBalance, BrokerOrderResponse, Holding, MinutePrice, Quote
from src.models.short_swing import PositionStatus, ShortSwingCandidate, ShortSwingPosition
from src.trading.kill_switch import KillSwitchStatus
from src.trading.short_swing import (
    calculate_intraday_vwap,
    run_entry_check,
)
from src.trading.short_swing_exit import run_exit_check
from src.utils.time import KST

# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

_TEST_USER_ID = uuid.uuid4()
_ENTRY_TIME = datetime(2026, 5, 15, 10, 0, 0, tzinfo=KST)


def _make_quote(
    symbol: str = "005930",
    price: int = 72000,
    prev_close: int = 70000,
    open_price: int = 70500,
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
        open=open_price,
        prev_close=prev_close,
    )


def _make_balance(available_cash: int = 5_000_000) -> AccountBalance:
    return AccountBalance(
        total_eval=10_000_000,
        total_profit=500_000,
        total_profit_pct=5.0,
        available_cash=available_cash,
        holdings=[],
    )


def _make_candidate(
    db: AsyncSession,
    symbol: str = "005930",
    name: str = "삼성전자",
    close: int = 70000,
    prev_day_high: int | None = 70500,
    score: float = 80.0,
) -> ShortSwingCandidate:
    """후보 종목 생성."""
    cand = ShortSwingCandidate(
        trade_date=date(2026, 5, 14),
        symbol=symbol,
        name=name,
        close=close,
        prev_day_high=prev_day_high,
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


def _make_broker_response() -> BrokerOrderResponse:
    return BrokerOrderResponse(
        order_no="T00001",
        symbol="005930",
        side="buy",
        price=72000,
        quantity=10,
        status="submitted",
        message="주문 접수",
    )


def _mock_client(
    quote: Quote | None = None,
    balance: AccountBalance | None = None,
) -> AsyncMock:
    client = AsyncMock()
    client._is_mock = True
    client.get_quote.return_value = quote or _make_quote()
    client.get_balance.return_value = balance or _make_balance()
    client.place_order.return_value = _make_broker_response()
    return client


# ── VWAP 계산 헬퍼 단위 테스트 ──────────────────────────────────────────────


class TestCalculateIntradayVwap:
    """calculate_intraday_vwap 헬퍼 단위 테스트."""

    @pytest.mark.asyncio
    async def test_normal_calculation(self) -> None:
        """정상 분봉 데이터로 VWAP 계산."""
        minutes = [
            MinutePrice(
                datetime="20260515093000",
                open=70000,
                high=71000,
                low=69500,
                close=70500,
                volume=10000,
            ),
            MinutePrice(
                datetime="20260515093500",
                open=70500,
                high=72000,
                low=70000,
                close=71500,
                volume=20000,
            ),
        ]

        client = AsyncMock()
        client.get_minute_price = AsyncMock(return_value=minutes)

        result = await calculate_intraday_vwap(client, "005930", date(2026, 5, 15))

        assert result is not None
        tp1 = (71000 + 69500 + 70500) / 3.0
        tp2 = (72000 + 70000 + 71500) / 3.0
        expected = (tp1 * 10000 + tp2 * 20000) / 30000
        assert abs(result - expected) < 1.0

    @pytest.mark.asyncio
    async def test_no_minute_data_returns_none(self) -> None:
        """분봉 데이터 없으면 None."""
        client = AsyncMock()
        client.get_minute_price = AsyncMock(return_value=[])

        result = await calculate_intraday_vwap(client, "005930", date(2026, 5, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_zero_volume_returns_none(self) -> None:
        """누적 거래량 0이면 None."""
        minutes = [
            MinutePrice(
                datetime="20260515093000",
                open=70000,
                high=71000,
                low=69500,
                close=70500,
                volume=0,
            ),
        ]

        client = AsyncMock()
        client.get_minute_price = AsyncMock(return_value=minutes)

        result = await calculate_intraday_vwap(client, "005930", date(2026, 5, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_none(self) -> None:
        """분봉 조회 실패 시 None."""
        client = AsyncMock()
        client.get_minute_price = AsyncMock(side_effect=Exception("네트워크 에러"))

        result = await calculate_intraday_vwap(client, "005930", date(2026, 5, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_no_get_minute_price_method_returns_none(self) -> None:
        """get_minute_price 메서드 없으면 None."""
        client = AsyncMock(spec=[])  # 빈 spec → hasattr 실패

        result = await calculate_intraday_vwap(client, "005930", date(2026, 5, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_filters_today_only(self) -> None:
        """당일 분봉만 필터링하여 계산."""
        minutes = [
            MinutePrice(  # 당일
                datetime="20260515093000",
                open=70000,
                high=71000,
                low=69500,
                close=70500,
                volume=10000,
            ),
            MinutePrice(  # 전일 — 제외
                datetime="20260514150000",
                open=68000,
                high=69000,
                low=67000,
                close=68500,
                volume=50000,
            ),
        ]

        client = AsyncMock()
        client.get_minute_price = AsyncMock(return_value=minutes)

        result = await calculate_intraday_vwap(client, "005930", date(2026, 5, 15))

        assert result is not None
        # 당일 1건만 사용
        expected = (71000 + 69500 + 70500) / 3.0
        assert abs(result - expected) < 1.0


# ── 진입 신호: prev_day_high 테스트 ──────────────────────────────────────────


class TestPrevDayHighMissing:
    """prev_day_high NULL이면 진입 신호 미발동."""

    @pytest.mark.asyncio
    async def test_null_prev_day_high_skips(self, db: AsyncSession) -> None:
        _make_candidate(db, close=70000, prev_day_high=None)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "prev_day_high_missing" for s in result.skipped)


class TestPrevDayHighBreakout:
    """prev_day_high 돌파 + VWAP 위이면 진입 신호 통과."""

    @pytest.mark.asyncio
    async def test_breakout_passes(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        # prev_day_high=70500, 현재가 72000 > 70500 → 돌파
        _make_candidate(db, close=70000, prev_day_high=70500)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
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

    @pytest.mark.asyncio
    async def test_no_breakout_skips(self, db: AsyncSession) -> None:
        """현재가 <= prev_day_high → 미돌파."""
        # prev_day_high=73000, 현재가 72000 → 미돌파
        _make_candidate(db, close=70000, prev_day_high=73000)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "no_entry_signal" for s in result.skipped)


# ── 진입 신호: VWAP 테스트 ──────────────────────────────────────────────────


class TestVwapUnavailable:
    """VWAP fetch 실패 시 진입 신호 미발동."""

    @pytest.mark.asyncio
    async def test_vwap_none_skips(self, db: AsyncSession) -> None:
        _make_candidate(db, close=70000, prev_day_high=70500)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "vwap_unavailable" for s in result.skipped)


class TestVwapAbovePrice:
    """현재가 < VWAP이면 진입 신호 미충족."""

    @pytest.mark.asyncio
    async def test_price_below_vwap_skips(self, db: AsyncSession) -> None:
        # prev_day_high=70500, 현재가=72000 > prev_day_high → 돌파 OK
        # 하지만 VWAP=73000 > 현재가 → 미충족
        _make_candidate(db, close=70000, prev_day_high=70500)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=73000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(db, client, user_id=_TEST_USER_ID, now=_ENTRY_TIME)

        assert result.ordered == 0
        assert any(s.get("reason") == "no_entry_signal" for s in result.skipped)


# ── dry_run 진입 테스트 ──────────────────────────────────────────────────────


class TestDryRunEntry:
    """dry_run=True 시 주문 없이 would_order 반환."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_would_order(self, db: AsyncSession, test_user: object) -> None:
        user_id = test_user.id  # type: ignore[attr-defined]

        _make_candidate(db, symbol="005930", name="삼성전자", close=70000, prev_day_high=70500)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(
                db, client, user_id=user_id, now=_ENTRY_TIME, dry_run=True
            )

        # place_order 미호출
        client.place_order.assert_not_called()

        # ordered는 0 (실제 주문 없음), would_order에 결과
        assert result.ordered == 0
        assert len(result.would_order) == 1
        wo = result.would_order[0]
        assert wo["symbol"] == "005930"
        assert wo["price"] == 72000
        assert wo["quantity"] > 0

    @pytest.mark.asyncio
    async def test_dry_run_no_position_created(self, db: AsyncSession, test_user: object) -> None:
        """dry_run=True 시 position row 생성 안 함."""
        user_id = test_user.id  # type: ignore[attr-defined]

        _make_candidate(db, symbol="005930", name="삼성전자", close=70000, prev_day_high=70500)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            await run_entry_check(db, client, user_id=user_id, now=_ENTRY_TIME, dry_run=True)

        # position 없어야 함
        pos_result = await db.execute(
            sa_select(ShortSwingPosition).where(ShortSwingPosition.symbol == "005930")
        )
        assert pos_result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_dry_run_false_regression(self, db: AsyncSession, test_user: object) -> None:
        """dry_run=False 시 기존 동작 유지 (실제 주문 생성)."""
        user_id = test_user.id  # type: ignore[attr-defined]

        _make_candidate(db, symbol="005930", name="삼성전자", close=70000, prev_day_high=70500)
        await db.commit()

        quote = _make_quote(price=72000, prev_close=70000, open_price=70500)
        client = _mock_client(quote=quote)

        with (
            patch("src.trading.short_swing.get_active_strategy", return_value="short_swing"),
            patch("src.trading.short_swing.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
            patch(
                "src.trading.short_swing.calculate_intraday_vwap",
                new_callable=AsyncMock,
                return_value=71000.0,
            ),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_entry_check(
                db, client, user_id=user_id, now=_ENTRY_TIME, dry_run=False
            )

        assert result.ordered == 1
        assert len(result.would_order) == 0
        client.place_order.assert_called_once()


# ── dry_run 청산 테스트 ──────────────────────────────────────────────────────


class TestDryRunExit:
    """dry_run=True 시 SELL 주문 없이 would_exit 반환."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_would_exit(self, db: AsyncSession, test_user: object) -> None:
        import math

        user_id = test_user.id  # type: ignore[attr-defined]

        # stop_loss 발동 조건 생성
        pos = ShortSwingPosition(
            user_id=user_id,
            symbol="005930",
            name="삼성전자",
            entry_date=date(2026, 5, 14),
            entry_time=datetime(2026, 5, 14, 10, 0, 0, tzinfo=KST),
            entry_price=70000,
            quantity=10,
            highest_price_since_entry=70000,
            stop_price=math.floor(70000 * (1 + (-0.02))),
            take_profit_price=math.floor(70000 * (1 + 0.04)),
            trailing_armed=False,
            max_holding_until=date(2026, 5, 23),
            status=PositionStatus.OPEN,
        )
        db.add(pos)
        await db.commit()

        # 현재가 68000 < stop_price 68600
        quote = _make_quote(price=68000, prev_close=70000)
        client = AsyncMock()
        client._is_mock = True
        client.get_quote.return_value = quote

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(
                db, client, user_id=user_id, now=_ENTRY_TIME, dry_run=True
            )

        # place_order 미호출
        client.place_order.assert_not_called()

        # would_exit에 결과
        assert len(result.would_exit) == 1
        we = result.would_exit[0]
        assert we["symbol"] == "005930"
        assert we["reason"] == "stop_loss"
        assert we["quantity"] == 10
        assert we["current_price"] == 68000

        # 포지션 status 변경 없어야 함
        await db.refresh(pos)
        assert pos.status == PositionStatus.OPEN

    @pytest.mark.asyncio
    async def test_dry_run_false_exit_regression(self, db: AsyncSession, test_user: object) -> None:
        """dry_run=False 시 기존 동작 유지 (실제 SELL 주문)."""
        import math

        user_id = test_user.id  # type: ignore[attr-defined]

        pos = ShortSwingPosition(
            user_id=user_id,
            symbol="005930",
            name="삼성전자",
            entry_date=date(2026, 5, 14),
            entry_time=datetime(2026, 5, 14, 10, 0, 0, tzinfo=KST),
            entry_price=70000,
            quantity=10,
            highest_price_since_entry=70000,
            stop_price=math.floor(70000 * (1 + (-0.02))),
            take_profit_price=math.floor(70000 * (1 + 0.04)),
            trailing_armed=False,
            max_holding_until=date(2026, 5, 23),
            status=PositionStatus.OPEN,
        )
        db.add(pos)
        await db.commit()

        quote = _make_quote(price=68000, prev_close=70000)

        holdings = [
            Holding(
                symbol="005930",
                name="삼성전자",
                quantity=10,
                avg_price=70000,
                current_price=68000,
                eval_amount=680000,
                profit=-20000,
                profit_pct=-2.86,
            ),
        ]
        client = AsyncMock()
        client._is_mock = True
        client.get_quote.return_value = quote
        client.get_holdings.return_value = holdings
        client.place_order.return_value = BrokerOrderResponse(
            order_no="T00001",
            symbol="005930",
            side="sell",
            price=68000,
            quantity=10,
            status="submitted",
            message="주문 접수",
        )

        with (
            patch(
                "src.trading.short_swing_exit.get_active_strategy",
                return_value="short_swing",
            ),
            patch("src.trading.short_swing_exit.ks") as mock_ks,
            patch("src.trading.drawdown_guard.run_all_checks", new_callable=AsyncMock),
        ):
            mock_ks.get_status.return_value = KillSwitchStatus.NORMAL
            result = await run_exit_check(
                db, client, user_id=user_id, now=_ENTRY_TIME, dry_run=False
            )

        assert result.closed == 1
        assert len(result.would_exit) == 0
        client.place_order.assert_called_once()
