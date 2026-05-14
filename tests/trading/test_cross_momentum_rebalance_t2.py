"""ADR-023 견고화 — T+2 cash flow + pykrx backoff 단위 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.trading.cross_momentum_rebalance import (
    CrossMomentumRebalanceAdapter,
    RebalanceParams,
    T2PendingSettlement,
    _fetch_pykrx_with_backoff,
    check_monthly_rebalance,
)

# ── T2PendingSettlement ──────────────────────────────────────────────────────


class TestT2PendingSettlement:
    """T2PendingSettlement 데이터클래스 기본 검증."""

    def test_fields(self) -> None:
        """필드가 올바르게 저장되는지 확인."""
        from src.utils.krx_calendar import add_business_days

        sell_date = date(2026, 4, 28)
        settle_date = add_business_days(sell_date, 2)

        item = T2PendingSettlement(
            symbol="005930",
            sell_amount=1_000_000,
            sell_date=sell_date,
            settle_date=settle_date,
        )

        assert item.symbol == "005930"
        assert item.sell_amount == 1_000_000
        assert item.sell_date == sell_date
        assert item.settle_date == date(2026, 4, 30)


# ── RebalanceParams t2_settlement ───────────────────────────────────────────


class TestRebalanceParamsT2:
    """RebalanceParams.t2_settlement 기본값 검증."""

    def test_t2_settlement_default_false(self) -> None:
        """t2_settlement 기본값은 False (모의 모드)."""
        p = RebalanceParams()
        assert p.t2_settlement is False

    def test_t2_settlement_can_be_true(self) -> None:
        """실전 모드에서 t2_settlement=True 설정 가능."""
        p = RebalanceParams(t2_settlement=True)
        assert p.t2_settlement is True


# ── compute_rebalance_orders T2 ──────────────────────────────────────────────


class TestComputeRebalanceOrdersT2:
    """T+2 결제 현금흐름 시뮬레이션 검증."""

    def test_t2_settlement_false_uses_immediate_cash(self) -> None:
        """t2_settlement=False(모의): T2 pending 있어도 total_cash 전액 사용."""
        adapter = CrossMomentumRebalanceAdapter(
            params=RebalanceParams(
                t2_settlement=False, cash_buffer_pct=0.0, n_positions=4, max_order_amount_pct=1.0
            )
        )
        target = ["A", "B", "C", "D"]
        pending = [
            T2PendingSettlement(
                symbol="OLD1",
                sell_amount=2_000_000,
                sell_date=date(2026, 4, 26),
                settle_date=date(2026, 4, 28),
            )
        ]

        orders = adapter.compute_rebalance_orders(target, {}, 8_000_000, pending)

        # t2_settlement=False → T2 잠금 없음 → 8_000_000 // 4 = 2_000_000
        assert orders.cash_per_position == 2_000_000

    def test_t2_settlement_true_locks_cash_until_settle(self) -> None:
        """t2_settlement=True(실전): T2 pending 금액만큼 가용현금 차감."""
        adapter = CrossMomentumRebalanceAdapter(
            params=RebalanceParams(
                t2_settlement=True, cash_buffer_pct=0.0, n_positions=4, max_order_amount_pct=1.0
            )
        )
        target = ["A", "B", "C", "D"]
        pending = [
            T2PendingSettlement(
                symbol="OLD1",
                sell_amount=4_000_000,
                sell_date=date(2026, 4, 26),
                settle_date=date(2026, 4, 28),
            )
        ]

        orders = adapter.compute_rebalance_orders(target, {}, 8_000_000, pending)

        # t2_settlement=True → 8_000_000 - 4_000_000 = 4_000_000 → 4_000_000 // 4 = 1_000_000
        assert orders.cash_per_position == 1_000_000

    def test_t2_settlement_true_no_pending_uses_full_cash(self) -> None:
        """t2_settlement=True이지만 pending 없으면 전액 사용."""
        adapter = CrossMomentumRebalanceAdapter(
            params=RebalanceParams(
                t2_settlement=True, cash_buffer_pct=0.0, n_positions=2, max_order_amount_pct=1.0
            )
        )
        target = ["A", "B"]

        orders = adapter.compute_rebalance_orders(target, {}, 6_000_000, [])

        assert orders.cash_per_position == 3_000_000

    def test_t2_settlement_true_multiple_pending(self) -> None:
        """여러 T2 항목의 합산 잠금 검증."""
        adapter = CrossMomentumRebalanceAdapter(
            params=RebalanceParams(t2_settlement=True, cash_buffer_pct=0.0, n_positions=1)
        )
        target = ["A"]
        pending = [
            T2PendingSettlement("X", 1_000_000, date(2026, 4, 25), date(2026, 4, 28)),
            T2PendingSettlement("Y", 2_000_000, date(2026, 4, 26), date(2026, 4, 29)),
        ]

        orders = adapter.compute_rebalance_orders(target, {}, 10_000_000, pending)

        # 10_000_000 - 3_000_000 = 7_000_000 → 1종목 → 7_000_000 (cap 디폴트 unlimited)
        assert orders.cash_per_position == 7_000_000

    def test_t2_settlement_true_all_cash_locked_uses_zero(self) -> None:
        """T2 잠금 > total_cash → 가용현금 0."""
        adapter = CrossMomentumRebalanceAdapter(params=RebalanceParams(t2_settlement=True))
        target = ["A"]
        pending = [
            T2PendingSettlement("X", 20_000_000, date(2026, 4, 25), date(2026, 4, 28)),
        ]

        orders = adapter.compute_rebalance_orders(target, {}, 5_000_000, pending)

        assert orders.cash_per_position == 0


# ── execute_monthly_rebalance T2 큐 적재 ────────────────────────────────────


class TestExecuteMonthlyRebalanceT2Enqueue:
    """execute_monthly_rebalance: T2 큐 적재 (실전 모드) 검증."""

    @pytest.mark.asyncio
    async def test_t2_enqueue_on_sell_when_settlement_true(self) -> None:
        """t2_settlement=True + 매도 성공 → t2_pending 큐에 항목 추가."""
        params = RebalanceParams(t2_settlement=True)
        adapter = CrossMomentumRebalanceAdapter(params=params)
        today = date(2026, 4, 30)
        t2_pending: list[T2PendingSettlement] = []

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.order_no = "ORD_001"
        mock_client.place_order = AsyncMock(return_value=mock_resp)
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=50_000))

        with (
            patch.object(
                adapter, "compute_target_portfolio", new=AsyncMock(return_value=["NEW_A"])
            ),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(strftime=lambda fmt: "1455" if fmt == "%H%M" else ""),
            ),
        ):
            result = await adapter.execute_monthly_rebalance(
                today,
                mock_client,
                {"OLD_X": 10},
                10_000_000,
                t2_pending,
            )

        assert result is True
        # 매도 후 T2 큐에 항목 1개 추가
        assert len(t2_pending) == 1
        assert t2_pending[0].symbol == "OLD_X"
        assert t2_pending[0].sell_amount == 50_000 * 10  # 현재가 x 수량
        assert t2_pending[0].sell_date == today

    @pytest.mark.asyncio
    async def test_no_t2_enqueue_when_settlement_false(self) -> None:
        """t2_settlement=False(모의) → 매도 후 T2 큐 변화 없음."""
        adapter = CrossMomentumRebalanceAdapter(params=RebalanceParams(t2_settlement=False))
        today = date(2026, 4, 30)
        t2_pending: list[T2PendingSettlement] = []

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.order_no = "ORD_001"
        mock_client.place_order = AsyncMock(return_value=mock_resp)
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=50_000))

        with (
            patch.object(
                adapter, "compute_target_portfolio", new=AsyncMock(return_value=["NEW_A"])
            ),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(strftime=lambda fmt: "1455" if fmt == "%H%M" else ""),
            ),
        ):
            await adapter.execute_monthly_rebalance(
                today,
                mock_client,
                {"OLD_X": 10},
                10_000_000,
                t2_pending,
            )

        # t2_settlement=False → T2 큐 적재 없음
        assert len(t2_pending) == 0

    @pytest.mark.asyncio
    async def test_t2_enqueue_settle_date_is_t_plus_2(self) -> None:
        """T+2 결제일 계산 검증."""
        from src.utils.krx_calendar import add_business_days

        params = RebalanceParams(t2_settlement=True)
        adapter = CrossMomentumRebalanceAdapter(params=params)
        today = date(2026, 4, 28)  # 화요일
        t2_pending: list[T2PendingSettlement] = []

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.order_no = "ORD_001"
        mock_client.place_order = AsyncMock(return_value=mock_resp)
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=100_000))

        with (
            patch.object(
                adapter, "compute_target_portfolio", new=AsyncMock(return_value=["NEW_A"])
            ),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(strftime=lambda fmt: "1455" if fmt == "%H%M" else ""),
            ),
        ):
            await adapter.execute_monthly_rebalance(
                today,
                mock_client,
                {"OLD_X": 5},
                10_000_000,
                t2_pending,
            )

        expected_settle = add_business_days(today, 2)
        assert len(t2_pending) == 1
        assert t2_pending[0].settle_date == expected_settle


# ── _fetch_pykrx_with_backoff ────────────────────────────────────────────────


class TestFetchPykrxWithBackoff:
    """pykrx backoff 재시도 래퍼 검증."""

    @pytest.mark.asyncio
    async def test_pykrx_backoff_retries_on_failure(self) -> None:
        """pykrx 실패 시 재시도 후 성공 검증."""
        mock_df = MagicMock()
        mock_df.empty = False

        call_count = 0

        def flaky_pykrx(start, end, symbol):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("rate limit")
            return mock_df

        mock_stock = MagicMock()
        mock_stock.get_market_ohlcv_by_date = flaky_pykrx
        mock_pykrx = MagicMock()
        mock_pykrx.stock = mock_stock

        with patch.dict("sys.modules", {"pykrx": mock_pykrx, "pykrx.stock": mock_stock}):
            result = await _fetch_pykrx_with_backoff("005930", "20260101", "20260430")

        assert result is mock_df
        assert call_count == 3  # 2번 실패 후 3번째 성공

    @pytest.mark.asyncio
    async def test_pykrx_backoff_raises_after_max_retries(self) -> None:
        """재시도 횟수 소진 시 예외 전파."""

        def always_fail(start, end, symbol):
            raise ConnectionError("persistent rate limit")

        mock_stock = MagicMock()
        mock_stock.get_market_ohlcv_by_date = always_fail
        mock_pykrx = MagicMock()
        mock_pykrx.stock = mock_stock

        with (
            patch.dict("sys.modules", {"pykrx": mock_pykrx, "pykrx.stock": mock_stock}),
            pytest.raises(ConnectionError, match="persistent rate limit"),
        ):
            await _fetch_pykrx_with_backoff("005930", "20260101", "20260430", retries=2)

    @pytest.mark.asyncio
    async def test_pykrx_backoff_success_on_first_try(self) -> None:
        """첫 번째 시도에 성공 → sleep 없이 즉시 반환."""
        mock_df = MagicMock()
        mock_stock = MagicMock()
        mock_stock.get_market_ohlcv_by_date = MagicMock(return_value=mock_df)
        mock_pykrx = MagicMock()
        mock_pykrx.stock = mock_stock

        with patch.dict("sys.modules", {"pykrx": mock_pykrx, "pykrx.stock": mock_stock}):
            result = await _fetch_pykrx_with_backoff("005930", "20260101", "20260430")

        assert result is mock_df
        mock_stock.get_market_ohlcv_by_date.assert_called_once_with(
            "20260101", "20260430", "005930"
        )

    @pytest.mark.asyncio
    async def test_pykrx_backoff_sleep_delay_exponential(self) -> None:
        """backoff sleep delay가 0.5 x 2^attempt 지수 패턴인지 검증."""
        call_count = 0

        def flaky_pykrx(start, end, symbol):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("rate limit")
            return MagicMock()

        mock_stock = MagicMock()
        mock_stock.get_market_ohlcv_by_date = flaky_pykrx
        mock_pykrx = MagicMock()
        mock_pykrx.stock = mock_stock

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with (
            patch.dict("sys.modules", {"pykrx": mock_pykrx, "pykrx.stock": mock_stock}),
            patch("src.trading.cross_momentum_rebalance.asyncio.sleep", side_effect=mock_sleep),
        ):
            await _fetch_pykrx_with_backoff("005930", "20260101", "20260430")

        # 2번 실패 → 2번 sleep: 0.5 x 2^0=0.5, 0.5 x 2^1=1.0
        assert sleep_calls == [0.5, 1.0]


# ── check_monthly_rebalance krx_calendar ────────────────────────────────────


class TestCheckMonthlyRebalanceKrxCalendar:
    """check_monthly_rebalance: krx_calendar 기반 마지막 영업일 판정."""

    @pytest.mark.asyncio
    async def test_skips_when_not_last_business_day(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """마지막 영업일이 아닌 날 → 스킵."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        adapter = CrossMomentumRebalanceAdapter()

        with patch("src.utils.krx_calendar.is_last_business_day_of_month", return_value=False):
            result = await check_monthly_rebalance(
                adapter, "1455", date(2026, 4, 15), MagicMock(), {}, 10_000_000
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_triggers_on_last_business_day(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """마지막 영업일 + 14:55 → execute_monthly_rebalance 호출."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        adapter = CrossMomentumRebalanceAdapter()

        with (
            patch("src.utils.krx_calendar.is_last_business_day_of_month", return_value=True),
            patch.object(
                adapter, "execute_monthly_rebalance", new=AsyncMock(return_value=True)
            ) as mock_exec,
        ):
            result = await check_monthly_rebalance(
                adapter, "1455", date(2026, 4, 30), MagicMock(), {}, 10_000_000
            )

        assert result is True
        mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_t2_pending_passed_to_execute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """t2_pending이 execute_monthly_rebalance에 전달되는지 검증."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        adapter = CrossMomentumRebalanceAdapter()
        t2_pending: list[T2PendingSettlement] = [
            T2PendingSettlement("X", 1_000_000, date(2026, 4, 26), date(2026, 4, 29))
        ]

        with (
            patch("src.utils.krx_calendar.is_last_business_day_of_month", return_value=True),
            patch.object(
                adapter, "execute_monthly_rebalance", new=AsyncMock(return_value=True)
            ) as mock_exec,
        ):
            await check_monthly_rebalance(
                adapter, "1455", date(2026, 4, 30), MagicMock(), {}, 10_000_000, t2_pending
            )

        _, _kwargs = mock_exec.call_args
        # positional args: (today, client, holdings, cash, t2_pending)
        call_args = mock_exec.call_args[0]
        assert call_args[-1] is t2_pending
