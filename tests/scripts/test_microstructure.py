"""마이크로구조 개선 (ADR-015) 단위 테스트.

검증 대상:
- is_entry_blocked: 점심 시간대 + 시초가 변동성 구간 차단
- execute_buy: 지정가 주문 우선 → 호가 조회 실패 시 시장가 fallback
- execute_sell: 긴급 사유 → 시장가 / 목표 사유 → 지정가
- apply_dynamic_filters: 거래대금·스프레드·변동폭 필터
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import live_trader
from scripts.live_trader import (
    LivePosition,
    TradingState,
    is_entry_blocked,
)
from scripts.screen_symbols import apply_dynamic_filters
from src.broker.schemas import DailyPrice, Orderbook, PriceLevel, Quote

# ── is_entry_blocked ────────────────────────────────────


class TestIsEntryBlocked:
    """시간대 진입 차단 로직 검증."""

    def test_noon_window_blocked(self) -> None:
        """기본 점심 차단 구간(11:30~13:00) 내부는 차단된다."""
        assert is_entry_blocked("1130") is True
        assert is_entry_blocked("1200") is True
        assert is_entry_blocked("1259") is True

    def test_noon_window_boundary_end_not_blocked(self) -> None:
        """13:00 이후는 차단 해제된다."""
        assert is_entry_blocked("1300") is False
        assert is_entry_blocked("1301") is False

    def test_before_noon_not_blocked(self) -> None:
        """11:30 이전은 차단되지 않는다."""
        assert is_entry_blocked("1000") is False
        assert is_entry_blocked("1129") is False

    def test_afternoon_not_blocked(self) -> None:
        """오후 정상 시간대는 차단되지 않는다."""
        assert is_entry_blocked("1400") is False
        assert is_entry_blocked("1459") is False

    def test_open_volatility_disabled_by_default(self) -> None:
        """BLOCK_OPEN_VOLATILITY 기본 False이면 09:00~09:30도 차단 안 됨."""
        with patch.object(live_trader, "BLOCK_OPEN_VOLATILITY", False):
            assert is_entry_blocked("0910") is False
            assert is_entry_blocked("0929") is False

    def test_open_volatility_enabled(self) -> None:
        """BLOCK_OPEN_VOLATILITY=True이면 09:00~09:30 차단된다."""
        with patch.object(live_trader, "BLOCK_OPEN_VOLATILITY", True):
            assert is_entry_blocked("0900") is True
            assert is_entry_blocked("0920") is True
            assert is_entry_blocked("0930") is False  # 09:30은 포함 안 됨

    def test_custom_blocked_window(self) -> None:
        """ENTRY_BLOCKED_WINDOWS를 변경하면 해당 구간이 차단된다."""
        with patch.object(live_trader, "ENTRY_BLOCKED_WINDOWS", [("1400", "1500")]):
            assert is_entry_blocked("1400") is True
            assert is_entry_blocked("1430") is True
            assert is_entry_blocked("1500") is False
            assert is_entry_blocked("1200") is False  # 점심 구간 제거됨


# ── execute_buy 지정가 로직 ─────────────────────────────


class TestExecuteBuyLimitOrder:
    """execute_buy 지정가 우선 / 시장가 fallback 검증."""

    def _make_state(self) -> TradingState:
        from src.ai.signal.position_sizer import StrategyBudget

        state = TradingState()
        state.budget = StrategyBudget()
        return state

    @pytest.mark.asyncio
    async def test_limit_order_uses_ask1_price(self) -> None:
        """호가 조회 성공 시 매도1호가(ask1)로 지정가 매수가 요청된다."""
        client = AsyncMock()
        client.get_orderbook.return_value = Orderbook(
            symbol="KRX:005930",
            asks=[PriceLevel(price=50100, quantity=100)],
            bids=[PriceLevel(price=50000, quantity=200)],
        )
        captured: list = []

        async def _fake_place_order(req):
            captured.append(req)
            resp = MagicMock()
            resp.order_no = "ORD001"
            return resp

        client.place_order.side_effect = _fake_place_order

        state = self._make_state()

        with (
            patch("scripts.live_trader.async_session_factory") as mock_sf,
            patch("scripts.live_trader.resolve_live_trader_user_id", new_callable=AsyncMock),
            patch("scripts.live_trader.persist_order_submitted", new_callable=AsyncMock),
            patch("scripts.live_trader.get_is_mock", return_value=True),
            patch("scripts.live_trader.asyncio.create_task"),
        ):
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            await live_trader.execute_buy(
                client, "005930", "삼성전자", 50000, 10, "momentum", state
            )

        assert len(captured) == 1
        req = captured[0]
        from src.broker.schemas import OrderTypeEnum

        assert req.order_type == OrderTypeEnum.LIMIT
        assert req.price == 50100  # 매도1호가

    @pytest.mark.asyncio
    async def test_market_fallback_when_orderbook_fails(self) -> None:
        """호가 조회 실패 시 시장가로 fallback된다."""
        client = AsyncMock()
        client.get_orderbook.side_effect = Exception("호가 조회 오류")
        captured: list = []

        async def _fake_place_order(req):
            captured.append(req)
            resp = MagicMock()
            resp.order_no = "ORD002"
            return resp

        client.place_order.side_effect = _fake_place_order

        state = self._make_state()

        with (
            patch("scripts.live_trader.async_session_factory") as mock_sf,
            patch("scripts.live_trader.resolve_live_trader_user_id", new_callable=AsyncMock),
            patch("scripts.live_trader.persist_order_submitted", new_callable=AsyncMock),
            patch("scripts.live_trader.get_is_mock", return_value=True),
        ):
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            await live_trader.execute_buy(
                client, "005930", "삼성전자", 50000, 10, "momentum", state
            )

        assert len(captured) == 1
        req = captured[0]
        from src.broker.schemas import OrderTypeEnum

        assert req.order_type == OrderTypeEnum.MARKET
        assert req.price == 0


# ── execute_sell 지정가/시장가 구분 ─────────────────────


class TestExecuteSellOrderType:
    """execute_sell: 긴급 사유 → 시장가, 목표 사유 → 지정가 검증."""

    def _make_pos(self, symbol: str = "005930") -> LivePosition:
        return LivePosition(
            symbol=symbol,
            name="삼성전자",
            entry_price=50000,
            quantity=10,
            entry_time="20260424093000",
            order_no="ORD000",
        )

    def _make_state(self) -> TradingState:
        from src.ai.signal.position_sizer import StrategyBudget

        state = TradingState()
        state.budget = StrategyBudget()
        state.budget.allocate("momentum", 500_000)
        return state

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "reason",
        ["stop_loss", "force_close", "gap_risk", "holding_limit", "kill_switch", "end_of_day"],
    )
    async def test_emergency_reasons_use_market_order(self, reason: str) -> None:
        """긴급 사유는 호가 조회 없이 시장가로 즉시 청산한다."""
        client = AsyncMock()
        captured: list = []

        async def _fake_place_order(req):
            captured.append(req)
            resp = MagicMock()
            resp.order_no = "SELL001"
            return resp

        client.place_order.side_effect = _fake_place_order

        pos = self._make_pos()
        state = self._make_state()
        state.positions[pos.symbol] = pos

        with (
            patch("scripts.live_trader.async_session_factory") as mock_sf,
            patch("scripts.live_trader.resolve_live_trader_user_id", new_callable=AsyncMock),
            patch("scripts.live_trader.persist_order_submitted", new_callable=AsyncMock),
            patch("scripts.live_trader.get_is_mock", return_value=True),
        ):
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            await live_trader.execute_sell(client, pos, 49000, reason, state)

        # 호가 조회 호출 없음
        client.get_orderbook.assert_not_called()
        from src.broker.schemas import OrderTypeEnum

        assert captured[0].order_type == OrderTypeEnum.MARKET

    @pytest.mark.asyncio
    async def test_target_exit_uses_limit_order(self) -> None:
        """take_profit 사유는 매수1호가로 지정가 매도한다."""
        client = AsyncMock()
        client.get_orderbook.return_value = Orderbook(
            symbol="KRX:005930",
            asks=[PriceLevel(price=51000, quantity=50)],
            bids=[PriceLevel(price=50900, quantity=80)],
        )
        captured: list = []

        async def _fake_place_order(req):
            captured.append(req)
            resp = MagicMock()
            resp.order_no = "SELL002"
            return resp

        client.place_order.side_effect = _fake_place_order

        pos = self._make_pos()
        state = self._make_state()
        state.positions[pos.symbol] = pos

        with (
            patch("scripts.live_trader.async_session_factory") as mock_sf,
            patch("scripts.live_trader.resolve_live_trader_user_id", new_callable=AsyncMock),
            patch("scripts.live_trader.persist_order_submitted", new_callable=AsyncMock),
            patch("scripts.live_trader.get_is_mock", return_value=True),
        ):
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            await live_trader.execute_sell(client, pos, 51000, "take_profit", state)

        from src.broker.schemas import OrderTypeEnum

        req = captured[0]
        assert req.order_type == OrderTypeEnum.LIMIT
        assert req.price == 50900  # 매수1호가


# ── apply_dynamic_filters ───────────────────────────────


class TestApplyDynamicFilters:
    """screen_symbols.apply_dynamic_filters 검증."""

    def _make_daily(
        self, high: int = 52000, low: int = 50000, close: int = 51000
    ) -> list[DailyPrice]:
        """전일 일봉 1개 생성."""
        return [
            DailyPrice(
                date="20260423",
                open=50500,
                high=high,
                low=low,
                close=close,
                volume=1_000_000,
            )
        ]

    def _make_candidate(self, symbol: str = "005930") -> dict:
        return {
            "symbol": symbol,
            "name": "삼성전자",
            "close": 51000,
            "avg_volume": 1_000_000,
            "high_52w": 60000,
            "sector": "반도체",
            "hint": "swing",
            "passed": True,
            "price_ratio": 0.85,
            "vol_ratio": 1.2,
            "bonus_score": 0,
        }

    @pytest.mark.asyncio
    async def test_passes_when_all_conditions_met(self) -> None:
        """모든 조건 충족 시 종목이 통과한다."""
        client = AsyncMock()
        client.get_quote.return_value = Quote(
            symbol="KRX:005930",
            name="삼성전자",
            price=51000,
            change=0,
            change_pct=0.0,
            volume=600_000,  # 전일 평균(1M) x 0.5 이상
            high=52000,
            low=50000,
            open=50500,
            prev_close=50000,
        )
        client.get_orderbook.return_value = Orderbook(
            symbol="KRX:005930",
            asks=[PriceLevel(price=51010, quantity=100)],
            bids=[PriceLevel(price=51000, quantity=200)],
        )

        daily = self._make_daily(high=52000, low=50000, close=51000)  # 변동폭 3.9% → 통과
        candidate = self._make_candidate()

        result = await apply_dynamic_filters(client, [candidate], {"005930": daily})
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_blocked_by_low_volume(self) -> None:
        """거래대금 부족 종목은 제외된다."""
        client = AsyncMock()
        client.get_quote.return_value = Quote(
            symbol="KRX:005930",
            name="삼성전자",
            price=51000,
            change=0,
            change_pct=0.0,
            volume=100,  # 전일 평균(1M) x 0.5 = 500M원 >> 100 x 51000 = 5.1M원
            high=52000,
            low=50000,
            open=50500,
            prev_close=50000,
        )
        client.get_orderbook.return_value = Orderbook(
            symbol="KRX:005930",
            asks=[PriceLevel(price=51010, quantity=100)],
            bids=[PriceLevel(price=51000, quantity=200)],
        )

        daily = self._make_daily()
        candidate = self._make_candidate()

        result = await apply_dynamic_filters(client, [candidate], {"005930": daily})
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_blocked_by_wide_spread(self) -> None:
        """스프레드 과대 종목(> 0.15%)은 제외된다."""
        client = AsyncMock()
        client.get_quote.return_value = Quote(
            symbol="KRX:005930",
            name="삼성전자",
            price=51000,
            change=0,
            change_pct=0.0,
            volume=600_000,
            high=52000,
            low=50000,
            open=50500,
            prev_close=50000,
        )
        # 스프레드 = (52000 - 50000) / 50000 = 4% >> 0.15%
        client.get_orderbook.return_value = Orderbook(
            symbol="KRX:005930",
            asks=[PriceLevel(price=52000, quantity=10)],
            bids=[PriceLevel(price=50000, quantity=10)],
        )

        daily = self._make_daily()
        candidate = self._make_candidate()

        result = await apply_dynamic_filters(client, [candidate], {"005930": daily})
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_blocked_by_low_range(self) -> None:
        """전일 변동폭 부족(< 1.5%) 종목은 제외된다."""
        client = AsyncMock()
        client.get_quote.return_value = Quote(
            symbol="KRX:005930",
            name="삼성전자",
            price=51000,
            change=0,
            change_pct=0.0,
            volume=600_000,
            high=52000,
            low=50000,
            open=50500,
            prev_close=50000,
        )
        client.get_orderbook.return_value = Orderbook(
            symbol="KRX:005930",
            asks=[PriceLevel(price=51010, quantity=100)],
            bids=[PriceLevel(price=51000, quantity=200)],
        )

        # 변동폭 = (51100 - 51000) / 51000 ≈ 0.2% < 1.5%
        daily = self._make_daily(high=51100, low=51000, close=51000)
        candidate = self._make_candidate()

        result = await apply_dynamic_filters(client, [candidate], {"005930": daily})
        assert len(result) == 0
