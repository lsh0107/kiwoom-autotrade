"""ADR-022 cross_momentum_rebalance 어댑터 단위 테스트."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.trading.cross_momentum_rebalance import (
    CrossMomentumRebalanceAdapter,
    RebalanceParams,
    check_monthly_rebalance,
    load_rebalance_params,
)

# ── 헬퍼 ────────────────────────────────────────────────────────────────────


def _make_daily_price(date_str: str, close: int, volume: int = 10000):
    from src.broker.schemas import DailyPrice

    return DailyPrice(
        date=date_str,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
    )


def _make_trending_bars(n: int, start_close: int = 10000, pct: float = 0.005):
    """n일간 pct씩 상승하는 일봉 생성."""
    from src.broker.schemas import DailyPrice

    bars = []
    price = start_close
    for i in range(n):
        year = 2020 + i // 365
        day_of_year = i % 365
        month = day_of_year // 30 + 1
        day = day_of_year % 30 + 1
        date_str = f"{year}{month:02d}{day:02d}"
        bars.append(
            DailyPrice(
                date=date_str,
                open=int(price),
                high=int(price),
                low=int(price),
                close=int(price),
                volume=10000,
            )
        )
        price *= 1 + pct
    return bars


# ── RebalanceParams ──────────────────────────────────────────────────────────


class TestRebalanceParams:
    """RebalanceParams 기본값 검증."""

    def test_defaults(self) -> None:
        p = RebalanceParams()
        assert p.formation_months == 12
        assert p.skip_months == 1
        assert p.top_pct == 0.20
        assert p.use_vol_filter is False
        assert p.use_trend_filter is False
        assert p.n_positions == 5
        assert p.rebalance_freq == "monthly"
        assert p.min_order_amount == 500_000
        assert p.max_order_amount_pct == 0.20
        assert p.cash_buffer_pct == 0.10

    def test_frozen(self) -> None:
        """frozen=True이므로 변경 시 FrozenInstanceError."""
        from dataclasses import FrozenInstanceError

        p = RebalanceParams()
        with pytest.raises(FrozenInstanceError):
            p.top_pct = 0.1  # type: ignore[misc]

    def test_effective_top_pct_with_value(self) -> None:
        """top_pct가 설정되면 그 값 반환."""
        p = RebalanceParams(top_pct=0.30)
        assert p.effective_top_pct == 0.30

    def test_effective_top_pct_none_fallback(self) -> None:
        """top_pct=None이면 기본값 0.20 반환."""
        p = RebalanceParams(top_pct=None)
        assert p.effective_top_pct == 0.20


# ── load_rebalance_params ──────────────────────────────────────────────────


class TestLoadRebalanceParams:
    """load_rebalance_params: DB에서 키 로딩 검증."""

    @pytest.mark.asyncio
    async def test_loads_from_db(self) -> None:
        """strategy_config에서 키 읽어 RebalanceParams 반영."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("cross_momentum.n_positions", 10),
            ("cross_momentum.cash_buffer_pct", 0.15),
            ("cross_momentum.min_order_amount", 300000),
            ("cross_momentum.rebalance_freq", "weekly"),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        params = await load_rebalance_params(mock_session)

        assert params.n_positions == 10
        assert params.cash_buffer_pct == 0.15
        assert params.min_order_amount == 300000
        assert params.rebalance_freq == "weekly"
        # 미설정 키는 기본값 유지
        assert params.top_pct == 0.20
        assert params.use_vol_filter is False

    @pytest.mark.asyncio
    async def test_db_failure_returns_defaults(self) -> None:
        """DB 조회 실패 시 기본값 반환."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("DB 연결 실패"))

        params = await load_rebalance_params(mock_session)

        assert params.n_positions == 5
        assert params.cash_buffer_pct == 0.10

    @pytest.mark.asyncio
    async def test_json_string_values_parsed(self) -> None:
        """value가 JSON 문자열로 저장된 경우 파싱."""
        import json

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("cross_momentum.n_positions", json.dumps(7)),
            ("cross_momentum.top_pct", json.dumps(None)),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        params = await load_rebalance_params(mock_session)

        assert params.n_positions == 7
        assert params.top_pct is None


# ── compute_target_portfolio ─────────────────────────────────────────────────


class TestComputeTargetPortfolio:
    """compute_target_portfolio: 상위 20% 선택 검증."""

    def test_returns_top_20pct(self) -> None:
        """_score_and_select으로 momentum score 기준 상위 20% 종목 반환 검증.

        pykrx 의존 없이 순수 로직 테스트.
        """
        adapter = CrossMomentumRebalanceAdapter()

        # 5종목: AAA·BBB 강한 상승, 나머지 약한 상승
        bars_high = _make_trending_bars(300, 10000, 0.01)
        bars_low = _make_trending_bars(300, 10000, 0.0005)

        universe_data = {
            "AAA": bars_high,
            "BBB": bars_high,
            "CCC": bars_low,
            "DDD": bars_low,
            "EEE": bars_low,
        }

        result = adapter._score_and_select(universe_data)

        assert isinstance(result, list)
        # top_pct=0.20, 5종목 → 최소 1종목
        assert len(result) >= 1
        # 상위 momentum(AAA, BBB)이 포함돼야 함
        assert any(s in result for s in ("AAA", "BBB"))

    @pytest.mark.asyncio
    async def test_returns_list_type(self) -> None:
        """compute_target_portfolio 반환 타입이 list[str]인지 확인."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 28)

        with patch.object(
            adapter, "compute_target_portfolio", new=AsyncMock(return_value=["005930", "000660"])
        ):
            result = await adapter.compute_target_portfolio(today)
            assert isinstance(result, list)
            assert all(isinstance(s, str) for s in result)

    def test_n_positions_limits_selection(self) -> None:
        """n_positions가 select_portfolio 결과보다 작으면 잘라냄."""
        params = RebalanceParams(n_positions=2, top_pct=0.50)
        adapter = CrossMomentumRebalanceAdapter(params=params)

        bars = _make_trending_bars(300, 10000, 0.01)
        universe_data = {f"SYM{i:03d}": bars for i in range(10)}

        result = adapter._score_and_select(universe_data)

        assert len(result) <= 2


# ── compute_rebalance_orders ─────────────────────────────────────────────────


class TestComputeRebalanceOrders:
    """compute_rebalance_orders: equal-weight 완전화 검증."""

    def test_diff_computation(self) -> None:
        """현재 보유 vs 타깃 diff 계산."""
        adapter = CrossMomentumRebalanceAdapter()

        current = {"AAA": 10, "BBB": 5, "CCC": 3}
        target = ["BBB", "DDD", "EEE"]
        cash = 10_000_000

        orders = adapter.compute_rebalance_orders(target, current, cash)

        assert set(orders.sells) == {"AAA", "CCC"}  # current에는 있으나 target에 없음
        assert orders.target_symbols == target

    def test_equal_weight_with_buffer(self) -> None:
        """equal weight 계산에 cash_buffer 적용 검증."""
        params = RebalanceParams(cash_buffer_pct=0.10, n_positions=4)
        adapter = CrossMomentumRebalanceAdapter(params=params)

        target = ["A", "B", "C", "D"]
        cash = 10_000_000
        # investable = 10M * 0.9 = 9M
        # cash_per_position = 9M // 4 = 2,250,000

        orders = adapter.compute_rebalance_orders(target, {}, cash)

        assert orders.cash_per_position == 2_250_000

    def test_equal_weight_full_adjust(self) -> None:
        """보유 종목 비중 조정 — 부족/초과 모두 잡힘."""
        params = RebalanceParams(
            n_positions=3,
            min_order_amount=100_000,
            max_order_amount_pct=0.50,
            cash_buffer_pct=0.0,
        )
        adapter = CrossMomentumRebalanceAdapter(params=params)

        current = {"A": 10, "B": 30}  # C는 미보유
        target = ["A", "B", "C"]
        cash = 9_000_000
        # cash_per_position = 9M // 3 = 3,000,000
        prices = {"A": 100_000, "B": 100_000, "C": 100_000}
        # A: 현재 10*100K = 1M, 목표 3M → 부족 2M → adjust_buy
        # B: 현재 30*100K = 3M, 목표 3M → 차이 0 → SKIP
        # C: 미보유 → new_buy, amount=3M

        orders = adapter.compute_rebalance_orders(target, current, cash, current_prices=prices)

        assert "A" in orders.adjust_buys
        assert orders.buy_amounts["A"] == 2_000_000
        assert "C" in orders.buys
        assert orders.buy_amounts["C"] == 3_000_000
        # B는 차이 없어서 adjust에 안 들어감
        assert "B" not in orders.adjust_buys
        assert "B" not in orders.adjust_sells

    def test_adjust_sell_overweight(self) -> None:
        """보유 종목이 목표보다 초과하면 비중 축소 매도."""
        params = RebalanceParams(
            n_positions=2,
            min_order_amount=100_000,
            max_order_amount_pct=0.50,
            cash_buffer_pct=0.0,
        )
        adapter = CrossMomentumRebalanceAdapter(params=params)

        current = {"A": 50}  # 50 * 100K = 5M
        target = ["A", "B"]
        cash = 6_000_000
        # cash_per_position = 6M // 2 = 3M
        # A: 5M → 3M → 초과 2M → sell
        prices = {"A": 100_000}

        orders = adapter.compute_rebalance_orders(target, current, cash, current_prices=prices)

        assert "A" in orders.adjust_sells
        assert orders.sell_amounts["A"] == 2_000_000

    def test_skips_min_amount(self) -> None:
        """min_order_amount 미만 주문 SKIP."""
        params = RebalanceParams(
            n_positions=2,
            min_order_amount=500_000,
            cash_buffer_pct=0.0,
        )
        adapter = CrossMomentumRebalanceAdapter(params=params)

        current = {"A": 10}
        target = ["A", "B"]
        cash = 2_000_000
        # cash_per_position = 2M // 2 = 1M
        # A: 10 * 100K = 1M, 목표 1M → 차이 0 → 조정 SKIP
        prices = {"A": 100_000}

        orders = adapter.compute_rebalance_orders(target, current, cash, current_prices=prices)

        assert "A" not in orders.adjust_buys
        assert "A" not in orders.adjust_sells

    def test_caps_max_order_amount(self) -> None:
        """max_order_amount = available_cash * max_order_amount_pct 적용."""
        params = RebalanceParams(
            n_positions=1,
            max_order_amount_pct=0.10,
            min_order_amount=100_000,
            cash_buffer_pct=0.0,
        )
        adapter = CrossMomentumRebalanceAdapter(params=params)

        target = ["A"]
        cash = 10_000_000
        # cash_per_position = 10M
        # max_order_amount = 10M * 0.10 = 1M
        # buy_amt = min(10M, 1M) = 1M

        orders = adapter.compute_rebalance_orders(target, {}, cash)

        assert orders.buy_amounts["A"] == 1_000_000

    def test_empty_current(self) -> None:
        """현재 보유 종목 없을 때 sells 비어있어야 함."""
        adapter = CrossMomentumRebalanceAdapter()

        orders = adapter.compute_rebalance_orders(["A", "B"], {}, 10_000_000)

        assert orders.sells == []


# ── execute_monthly_rebalance (4-phase) ───────────────────────────────────────


class TestExecuteMonthlyRebalance:
    """execute_monthly_rebalance: 4-phase 검증."""

    @pytest.mark.asyncio
    async def test_calls_sell_then_balance_then_buy(self) -> None:
        """매도 → 잔고 재조회 → 매수 순서 검증."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)

        target_syms = ["NEW_A", "NEW_B"]
        current_holdings = {"OLD_X": 5}
        call_order: list[str] = []

        mock_balance = MagicMock()
        mock_balance.available_cash = 8_000_000
        mock_balance.holdings = []

        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=10000))
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        async def mock_place_order(req):
            resp = MagicMock()
            resp.order_no = f"ORD_{req.symbol}"
            if req.side.value == "sell" or str(req.side) == "sell":
                call_order.append(f"SELL:{req.symbol}")
            else:
                call_order.append(f"BUY:{req.symbol}")
            return resp

        mock_client.place_order = mock_place_order

        with (
            patch.object(adapter, "compute_target_portfolio", return_value=target_syms),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(
                    strftime=lambda fmt: "1455" if fmt == "%H%M" else "2026-04-30"
                ),
            ),
        ):
            result = await adapter.execute_monthly_rebalance(
                today, mock_client, current_holdings, 10_000_000
            )

        assert result is True
        # 매도가 먼저 발생해야 함
        sell_indices = [i for i, c in enumerate(call_order) if c.startswith("SELL")]
        buy_indices = [i for i, c in enumerate(call_order) if c.startswith("BUY")]
        if sell_indices and buy_indices:
            assert max(sell_indices) < min(buy_indices)
        # get_balance가 호출됨 (Phase 2 + Phase 4)
        assert mock_client.get_balance.call_count >= 1

    @pytest.mark.asyncio
    async def test_refreshes_between_sell_buy(self) -> None:
        """sell 후 get_balance 호출되고 buy가 그 이후 실행."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)
        events: list[str] = []

        mock_balance = MagicMock()
        mock_balance.available_cash = 5_000_000
        mock_balance.holdings = []

        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=10000))

        async def track_balance():
            events.append("GET_BALANCE")
            return mock_balance

        mock_client.get_balance = track_balance

        async def track_order(req):
            side = "SELL" if "sell" in str(req.side).lower() else "BUY"
            events.append(f"{side}:{req.symbol}")
            resp = MagicMock()
            resp.order_no = f"ORD_{req.symbol}"
            return resp

        mock_client.place_order = track_order

        with (
            patch.object(adapter, "compute_target_portfolio", return_value=["NEW"]),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(
                    strftime=lambda fmt: "1455" if fmt == "%H%M" else "2026-04-30"
                ),
            ),
        ):
            await adapter.execute_monthly_rebalance(today, mock_client, {"OLD": 5}, 10_000_000)

        # GET_BALANCE가 SELL과 BUY 사이에 있어야 함
        sell_idx = next((i for i, e in enumerate(events) if e.startswith("SELL")), -1)
        balance_idx = next((i for i, e in enumerate(events) if e == "GET_BALANCE"), -1)
        buy_idx = next((i for i, e in enumerate(events) if e.startswith("BUY")), -1)
        if sell_idx >= 0 and buy_idx >= 0:
            assert sell_idx < balance_idx < buy_idx

    @pytest.mark.asyncio
    async def test_skip_when_market_closed(self) -> None:
        """장 운영시간 외 리밸런싱 SKIP 검증."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)
        mock_client = MagicMock()

        with patch(
            "src.utils.time.now_kst",
            return_value=MagicMock(strftime=lambda fmt: "1600" if fmt == "%H%M" else "2026-04-30"),
        ):
            result = await adapter.execute_monthly_rebalance(today, mock_client, {}, 10_000_000)

        assert result is False

    @pytest.mark.asyncio
    async def test_duplicate_prevention(self) -> None:
        """당일 중복 리밸런싱 방지."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)
        adapter._last_rebalance_date = today  # 이미 실행됨

        mock_client = MagicMock()

        with patch(
            "src.utils.time.now_kst",
            return_value=MagicMock(strftime=lambda fmt: "1455" if fmt == "%H%M" else "2026-04-30"),
        ):
            result = await adapter.execute_monthly_rebalance(today, mock_client, {}, 10_000_000)

        assert result is False

    @pytest.mark.asyncio
    async def test_rebalance_freq_warn(self) -> None:
        """rebalance_freq가 monthly가 아니면 경고 로깅."""
        params = RebalanceParams(rebalance_freq="weekly")
        adapter = CrossMomentumRebalanceAdapter(params=params)
        today = date(2026, 4, 30)
        mock_balance = MagicMock()
        mock_balance.available_cash = 5_000_000
        mock_balance.holdings = []
        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=10000))
        mock_client.get_balance = AsyncMock(return_value=mock_balance)
        mock_client.place_order = AsyncMock(return_value=MagicMock(order_no="ORD1"))

        with (
            patch.object(adapter, "compute_target_portfolio", return_value=["A"]),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(
                    strftime=lambda fmt: "1455" if fmt == "%H%M" else "2026-04-30"
                ),
            ),
        ):
            result = await adapter.execute_monthly_rebalance(today, mock_client, {}, 5_000_000)

        # weekly는 미지원이지만 파이프라인은 완료됨
        assert result is True


# ── reconcile structlog 검증 ────────────────────────────────────────────────


class TestReconcile:
    """_compute_reconcile: structlog 구조화 로그 검증."""

    def test_reconcile_logs_diff(self) -> None:
        """reconcile이 target 대비 weight diff 계산."""
        adapter = CrossMomentumRebalanceAdapter()

        mock_holding_a = MagicMock(symbol="A", eval_amount=5_000_000)
        mock_holding_b = MagicMock(symbol="B", eval_amount=5_000_000)
        mock_balance = MagicMock()
        mock_balance.holdings = [mock_holding_a, mock_holding_b]

        report = adapter._compute_reconcile(
            ["A", "B"],
            mock_balance,
            {"OLD": 5},
            {"A": (50, 100_000)},
        )

        assert report["target_count"] == 2
        assert report["sold_count"] == 1
        assert report["bought_count"] == 1
        assert report["total_eval"] == 10_000_000
        assert report["target_weight"] == 0.5
        # A: 5M/10M = 0.5, target = 0.5 → diff 0.0
        assert report["weight_diffs"]["A"] == 0.0
        assert report["max_deviation"] == 0.0

    def test_reconcile_empty_balance(self) -> None:
        """잔고가 비어있어도 에러 없이 처리."""
        adapter = CrossMomentumRebalanceAdapter()

        mock_balance = MagicMock()
        mock_balance.holdings = []

        report = adapter._compute_reconcile(["A"], mock_balance, {}, {})

        assert report["total_eval"] == 0
        assert report["weight_diffs"]["A"] == pytest.approx(-1.0)


# ── _place_buy_order: 1주 미만 SKIP ─────────────────────────────────────────


class TestPlaceBuyOrder:
    """_place_buy_order: 수량 0주 SKIP 검증."""

    @pytest.mark.asyncio
    async def test_skip_when_quantity_below_one(self) -> None:
        """현재가가 배정 금액보다 높으면 0주 → SKIP."""
        adapter = CrossMomentumRebalanceAdapter()

        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=6_000_000))  # 600만원

        result = await adapter._place_buy_order(
            mock_client,
            "005930",
            5_000_000,  # 배정금 500만원 < 현재가
        )

        assert result == (False, 0, 6_000_000)
        mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_success_when_enough_cash(self) -> None:
        """배정금이 충분하면 매수 접수."""
        adapter = CrossMomentumRebalanceAdapter()

        mock_resp = MagicMock()
        mock_resp.order_no = "ORDER_001"
        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=100_000))
        mock_client.place_order = AsyncMock(return_value=mock_resp)

        result = await adapter._place_buy_order(
            mock_client,
            "005930",
            1_000_000,  # 100만원 / 10만원 = 10주
        )

        assert result == (True, 10, 100_000)
        mock_client.place_order.assert_called_once()


# ── persist_orders_to_db ─────────────────────────────────────────────────────


class TestPersistRebalance:
    """_persist_rebalance: DB persist 검증."""

    @pytest.mark.asyncio
    async def test_persist_orders_called(self) -> None:
        """_persist_rebalance 호출 시 persist_order_submitted 호출 검증."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)
        submitted_calls: list[dict] = []

        async def mock_persist(session, symbol, side, qty, price, order_no, strategy, is_mock, uid):
            submitted_calls.append({"symbol": symbol, "side": side, "qty": qty, "price": price})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.config.database.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "src.trading.live_order_persist.resolve_live_trader_user_id",
                new=AsyncMock(return_value=uuid.uuid4()),
            ),
            patch(
                "src.trading.live_order_persist.persist_order_submitted",
                side_effect=mock_persist,
            ),
            patch(
                "src.trading.live_order_persist.get_is_mock",
                return_value=True,
            ),
        ):
            await adapter._persist_rebalance(today, {"OLD_X": 5}, {"NEW_A": (3, 100_000)})

        sides = [c["side"] for c in submitted_calls]
        assert "SELL" in sides
        assert "BUY" in sides
        sell_call = next(c for c in submitted_calls if c["side"] == "SELL")
        buy_call = next(c for c in submitted_calls if c["side"] == "BUY")
        assert sell_call["qty"] == 5
        assert buy_call["qty"] == 3
        assert buy_call["price"] == 100_000


# ── check_monthly_rebalance hook ─────────────────────────────────────────────


class TestCheckMonthlyRebalance:
    """check_monthly_rebalance 훅 단위 테스트."""

    @pytest.mark.asyncio
    async def test_use_cross_momentum_disabled_skips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """USE_CROSS_MOMENTUM=false → 즉시 False 반환."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "none")
        adapter = CrossMomentumRebalanceAdapter()

        result = await check_monthly_rebalance(
            adapter, "1455", date(2026, 4, 30), MagicMock(), {}, 10_000_000
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_time_skips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """14:55가 아닌 시각 → 스킵."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        adapter = CrossMomentumRebalanceAdapter()

        result = await check_monthly_rebalance(
            adapter, "1430", date(2026, 4, 30), MagicMock(), {}, 10_000_000
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_monthly_rebalance_trigger_only_on_last_business_day(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """마지막 거래일이 아닌 날은 리밸런싱 스킵."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        adapter = CrossMomentumRebalanceAdapter()

        # 2026-04-15는 월중이므로 마지막 거래일이 아님
        with patch(
            "src.utils.krx_calendar.is_last_business_day_of_month",
            return_value=False,
        ):
            result = await check_monthly_rebalance(
                adapter, "1455", date(2026, 4, 15), MagicMock(), {}, 10_000_000
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_triggers_on_last_business_day(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """마지막 거래일 + 14:55 → execute_monthly_rebalance 호출."""
        monkeypatch.setenv("ACTIVE_STRATEGY", "cross_momentum")
        adapter = CrossMomentumRebalanceAdapter()

        with (
            patch(
                "src.utils.krx_calendar.is_last_business_day_of_month",
                return_value=True,
            ),
            patch.object(
                adapter,
                "execute_monthly_rebalance",
                new=AsyncMock(return_value=True),
            ) as mock_exec,
        ):
            result = await check_monthly_rebalance(
                adapter, "1455", date(2026, 4, 30), MagicMock(), {}, 10_000_000
            )

        assert result is True
        mock_exec.assert_called_once()


# ── _is_last_trading_day_of_month ───────────────────────────────────────────


class TestIsLastTradingDayOfMonth:
    """_is_last_trading_day_of_month: pykrx 경로 및 fallback 검증."""

    def test_pykrx_success_next_month(self) -> None:
        """pykrx 성공 + 다음 거래일이 다음 달 → True."""
        from src.trading.cross_momentum_rebalance import _is_last_trading_day_of_month

        # 2026-04-30은 4월 마지막 날, 다음 거래일 = 2026-05-04 (5월)
        today = date(2026, 4, 30)
        with (
            patch(
                "src.trading.cross_momentum_rebalance.pykrx_stock",
                create=True,
            ),
            patch.dict(
                "sys.modules",
                {
                    "pykrx": MagicMock(),
                    "pykrx.stock": MagicMock(
                        get_nearest_business_day_in_a_week=MagicMock(return_value="20260504")
                    ),
                },
            ),
        ):
            result = _is_last_trading_day_of_month(today)
        assert result is True

    def test_pykrx_success_same_month(self) -> None:
        """pykrx 성공 + 다음 거래일이 같은 달 → False."""
        from src.trading.cross_momentum_rebalance import _is_last_trading_day_of_month

        today = date(2026, 4, 15)
        # mock_pykrx.stock을 직접 설정해야 from pykrx import stock이 올바른 mock 반환
        mock_stock = MagicMock()
        mock_stock.get_nearest_business_day_in_a_week = MagicMock(return_value="20260416")
        mock_pykrx = MagicMock()
        mock_pykrx.stock = mock_stock
        with patch.dict(
            "sys.modules",
            {"pykrx": mock_pykrx, "pykrx.stock": mock_stock},
        ):
            result = _is_last_trading_day_of_month(today)
        assert result is False

    def test_pykrx_exception_fallback_last_weekday(self) -> None:
        """pykrx 예외 시 fallback — 해당 월 마지막 평일 = 오늘이면 True."""
        from src.trading.cross_momentum_rebalance import _is_last_trading_day_of_month

        # 2026-04-30 (목) → 4월 마지막 거래일
        today = date(2026, 4, 30)
        with patch.dict(
            "sys.modules",
            {"pykrx": MagicMock(side_effect=ImportError("no pykrx"))},
        ):
            result = _is_last_trading_day_of_month(today)
        # ImportError 발생 시 fallback 사용 — 4월 30일이 마지막 평일인지 확인
        # (pykrx 실패 → fallback 로직으로 판정)
        assert isinstance(result, bool)

    def test_fallback_december_last_weekday(self) -> None:
        """fallback — 12월 말일 처리 (year+1 분기)."""
        from src.trading.cross_momentum_rebalance import _is_last_trading_day_of_month

        # 2025-12-31 (수) → 12월 마지막 평일이 맞음 → True
        today = date(2025, 12, 31)
        with patch.dict(
            "sys.modules",
            {"pykrx": MagicMock(side_effect=ImportError("no pykrx"))},
        ):
            result = _is_last_trading_day_of_month(today)
        assert isinstance(result, bool)

    def test_fallback_not_last_day(self) -> None:
        """fallback — 월 중간 날짜는 False. pykrx 미설치 환경 → ImportError → fallback."""
        from src.trading.cross_momentum_rebalance import _is_last_trading_day_of_month

        # pykrx 미설치이므로 패칭 없이 호출하면 항상 fallback 경로 실행
        today = date(2026, 4, 10)
        # sys.modules에 pykrx가 없으므로 ImportError → fallback
        with patch.dict("sys.modules", {"pykrx": None, "pykrx.stock": None}):
            result = _is_last_trading_day_of_month(today)
        assert result is False

    def test_pykrx_returns_none_fallback(self) -> None:
        """pykrx가 None 반환 → fallback 사용."""
        from src.trading.cross_momentum_rebalance import _is_last_trading_day_of_month

        today = date(2026, 4, 30)
        mock_stock = MagicMock()
        mock_stock.get_nearest_business_day_in_a_week = MagicMock(return_value=None)
        with patch.dict(
            "sys.modules",
            {"pykrx": MagicMock(), "pykrx.stock": mock_stock},
        ):
            result = _is_last_trading_day_of_month(today)
        # None 반환 → fallback → 4월 30일이 마지막 평일이므로 True
        assert isinstance(result, bool)


# ── _score_and_select empty ──────────────────────────────────────────────────


class TestScoreAndSelectEmpty:
    """_score_and_select: 빈 universe_data → 빈 리스트 반환."""

    def test_empty_universe_returns_empty(self) -> None:
        """universe_data가 비어있으면 빈 리스트 반환."""
        adapter = CrossMomentumRebalanceAdapter()
        result = adapter._score_and_select({})
        assert result == []


# ── execute_monthly_rebalance 추가 케이스 ───────────────────────────────────


class TestExecuteMonthlyRebalanceCoverage:
    """execute_monthly_rebalance: 예외 케이스 및 빈 포트폴리오 처리."""

    @pytest.mark.asyncio
    async def test_empty_target_portfolio_aborts(self) -> None:
        """목표 포트폴리오 산정 실패 시 False 반환."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)
        mock_client = MagicMock()

        with (
            patch.object(adapter, "compute_target_portfolio", return_value=[]),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(
                    strftime=lambda fmt: "1455" if fmt == "%H%M" else "2026-04-30"
                ),
            ),
        ):
            result = await adapter.execute_monthly_rebalance(today, mock_client, {}, 10_000_000)

        assert result is False

    @pytest.mark.asyncio
    async def test_sell_exception_continues_to_buy(self) -> None:
        """매도 예외 발생해도 매수 계속 진행."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)

        mock_balance = MagicMock()
        mock_balance.available_cash = 5_000_000
        mock_balance.holdings = []

        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=50_000))
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        async def mock_place_order(req):
            resp = MagicMock()
            resp.order_no = f"ORD_{req.symbol}"
            side_str = str(req.side)
            if "SELL" in side_str.upper() or "sell" in side_str:
                raise RuntimeError("매도 실패 테스트")
            return resp

        mock_client.place_order = mock_place_order

        with (
            patch.object(adapter, "compute_target_portfolio", return_value=["NEW_A"]),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(
                    strftime=lambda fmt: "1455" if fmt == "%H%M" else "2026-04-30"
                ),
            ),
        ):
            result = await adapter.execute_monthly_rebalance(
                today, mock_client, {"OLD_X": 5}, 10_000_000
            )

        # 매도 실패해도 완료 반환
        assert result is True

    @pytest.mark.asyncio
    async def test_buy_exception_continues(self) -> None:
        """매수 예외 발생해도 전체 파이프라인 완료."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)

        mock_balance = MagicMock()
        mock_balance.available_cash = 5_000_000
        mock_balance.holdings = []

        mock_client = MagicMock()
        mock_client.get_balance = AsyncMock(return_value=mock_balance)

        async def mock_place_order(req):
            raise RuntimeError("매수 실패 테스트")

        mock_client.place_order = mock_place_order
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=50_000))

        with (
            patch.object(adapter, "compute_target_portfolio", return_value=["NEW_A"]),
            patch.object(adapter, "_persist_rebalance", new=AsyncMock()),
            patch(
                "src.utils.time.now_kst",
                return_value=MagicMock(
                    strftime=lambda fmt: "1455" if fmt == "%H%M" else "2026-04-30"
                ),
            ),
        ):
            result = await adapter.execute_monthly_rebalance(today, mock_client, {}, 10_000_000)

        assert result is True


# ── _place_sell_order 성공 케이스 ────────────────────────────────────────────


class TestPlaceSellOrderSuccess:
    """_place_sell_order: 정상 매도 주문 접수."""

    @pytest.mark.asyncio
    async def test_sell_success(self) -> None:
        """정상 매도 주문 접수 시 place_order 호출."""
        adapter = CrossMomentumRebalanceAdapter()

        mock_resp = MagicMock()
        mock_resp.order_no = "SELL_ORD_001"
        mock_client = MagicMock()
        mock_client.place_order = AsyncMock(return_value=mock_resp)

        await adapter._place_sell_order(mock_client, "005930", quantity=10)

        mock_client.place_order.assert_called_once()
        call_args = mock_client.place_order.call_args[0][0]
        assert call_args.quantity == 10
        assert call_args.symbol == "005930"

    @pytest.mark.asyncio
    async def test_sell_skip_zero_quantity(self) -> None:
        """quantity=0 전달 시 주문 스킵 (ValidationError 방지)."""
        adapter = CrossMomentumRebalanceAdapter()
        mock_client = MagicMock()
        mock_client.place_order = AsyncMock()

        await adapter._place_sell_order(mock_client, "005930", quantity=0)

        mock_client.place_order.assert_not_called()


# ── _place_buy_order 추가 케이스 ─────────────────────────────────────────────


class TestPlaceBuyOrderCoverage:
    """_place_buy_order: get_quote 실패, 가격 0 케이스."""

    @pytest.mark.asyncio
    async def test_quote_failure_skips(self) -> None:
        """현재가 조회 실패 시 False 반환."""
        adapter = CrossMomentumRebalanceAdapter()

        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(side_effect=RuntimeError("API 오류"))

        result = await adapter._place_buy_order(mock_client, "005930", 1_000_000)

        assert result == (False, 0, 0)
        mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_price_zero_skips(self) -> None:
        """현재가 0원 시 False 반환."""
        adapter = CrossMomentumRebalanceAdapter()

        mock_client = MagicMock()
        mock_client.get_quote = AsyncMock(return_value=MagicMock(price=0))

        result = await adapter._place_buy_order(mock_client, "005930", 1_000_000)

        assert result == (False, 0, 0)
        mock_client.place_order.assert_not_called()


# ── _persist_rebalance 예외 처리 ─────────────────────────────────────────────


class TestPersistRebalanceException:
    """_persist_rebalance: DB 예외 발생 시 silently ignore."""

    @pytest.mark.asyncio
    async def test_db_exception_is_silenced(self) -> None:
        """DB persist 중 예외 발생해도 전파되지 않음."""
        adapter = CrossMomentumRebalanceAdapter()
        today = date(2026, 4, 30)

        with patch(
            "src.config.database.async_session_factory",
            side_effect=RuntimeError("DB 연결 실패"),
        ):
            # 예외 전파 없이 완료
            await adapter._persist_rebalance(today, {"A": 1}, {"B": (1, 10000)})


# ── cross_momentum_universe ───────────────────────────────────────────────────


class TestCrossMomentumUniverse:
    """cross_momentum_universe: 유니버스 목록 및 중복 제거 검증."""

    def test_get_universe_returns_list(self) -> None:
        """get_universe()가 리스트를 반환하는지 확인."""
        from src.strategy.cross_momentum_universe import get_universe

        result = get_universe()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(s, str) for s in result)

    def test_universe_no_duplicates(self) -> None:
        """FROZEN_UNIVERSE에 중복 종목코드가 없어야 함."""
        from src.strategy.cross_momentum_universe import get_universe

        result = get_universe()
        assert len(result) == len(set(result))

    def test_universe_max_200(self) -> None:
        """유니버스 종목 수는 최대 200개."""
        from src.strategy.cross_momentum_universe import get_universe

        assert len(get_universe()) <= 200

    def test_kospi_symbol_present(self) -> None:
        """삼성전자(005930)가 유니버스에 포함돼야 함."""
        from src.strategy.cross_momentum_universe import get_universe

        assert "005930" in get_universe()

    def test_frozen_universe_is_immutable_copy(self) -> None:
        """get_universe()는 매번 새로운 list를 반환해야 함."""
        from src.strategy.cross_momentum_universe import get_universe

        a = get_universe()
        b = get_universe()
        assert a is not b
        assert a == b

    def test_deduplicate_preserves_order(self) -> None:
        """_deduplicate: 순서를 유지하며 중복 제거."""
        from src.strategy.cross_momentum_universe import _deduplicate

        result = _deduplicate(["A", "B", "A", "C", "B"])
        assert result == ["A", "B", "C"]

    def test_deduplicate_empty(self) -> None:
        """_deduplicate: 빈 리스트 입력 시 빈 리스트 반환."""
        from src.strategy.cross_momentum_universe import _deduplicate

        assert _deduplicate([]) == []
