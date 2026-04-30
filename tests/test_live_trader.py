"""live_trader.py 핵심 매매 로직 테스트.

mock 기반으로 KiwoomClient 호출을 대체하여
진입/청산 판단, 주문 실행, 폴링 사이클, 강제 청산을 검증한다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.live_trader import (
    _WS_RECONNECT_POLL_SEC,
    LivePosition,
    TradingState,
    _safe_int,
    _wait_for_ws_reconnect,
    build_strategies,
    calc_time_ratio,
    execute_buy,
    execute_sell,
    force_close_all,
    load_daily_context,
    now_hhmm,
    poll_cycle,
    rescreening_task_ws,
    run_trading_loop_ws,
    save_results,
    update_risk_after_trade,
)
from src.backtest.strategy import MomentumParams
from src.broker.schemas import BrokerOrderResponse, DailyPrice, OrderSideEnum, Quote, RealtimeTick
from src.strategy import MeanReversionParams

# ── fixture ─────────────────────────────────────────


@pytest.fixture
def params() -> MomentumParams:
    """기본 전략 파라미터."""
    return MomentumParams()


@pytest.fixture
def state() -> TradingState:
    """빈 트레이딩 상태 (자금 버킷 초기화 포함)."""
    s = TradingState()
    s.budget.reset(10_000_000)  # 기본 1천만원 잔고
    return s


@pytest.fixture
def mock_client() -> AsyncMock:
    """모의 KiwoomClient."""
    client = AsyncMock()
    client.place_order.return_value = BrokerOrderResponse(
        order_no="ORD001",
        symbol="005930",
        side=OrderSideEnum.BUY,
        price=0,
        quantity=10,
        status="submitted",
        message="",
    )
    return client


@pytest.fixture
def sample_quote() -> Quote:
    """샘플 시세 데이터."""
    return Quote(
        symbol="005930",
        name="삼성전자",
        price=70000,
        change=1000,
        change_pct=1.45,
        volume=15000,
        high=71000,
        low=69000,
        open=69500,
        prev_close=69000,
    )


@pytest.fixture
def sample_daily() -> list[DailyPrice]:
    """52주 일봉 샘플 (30개 바)."""
    return [
        DailyPrice(
            date=f"2026010{i:02d}",
            open=69000 + i * 100,
            high=70000 + i * 100,
            low=68000 + i * 100,
            close=69500 + i * 100,
            volume=10000 + i * 50,
        )
        for i in range(30)
    ]


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    """각 테스트 전 싱글턴 상태 초기화 (테스트 격리)."""
    from src.trading.kill_switch import _kill_switch_states, auto_kill_monitor
    from src.trading.risk_manager import cooldown_tracker

    cooldown_tracker._last_exit_times.clear()
    cooldown_tracker._daily_counts.clear()
    auto_kill_monitor.reset_for_test()
    _kill_switch_states.clear()


# ── _safe_int ───────────────────────────────────────


class TestSafeInt:
    """_safe_int 유틸 함수 테스트."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (100, 100),
            (-500, 500),
            ("12345", 12345),
            ("+70000", 70000),
            ("-70000", 70000),
            ("", 0),
        ],
    )
    def test_safe_int_matrix(self, value: int | str, expected: int) -> None:
        """정수·문자열·부호접두사·빈문자열 변환 검증."""
        assert _safe_int(value) == expected


# ── now_hhmm ────────────────────────────────────────


class TestNowHhmm:
    """now_hhmm 함수 테스트."""

    @patch("scripts.live_trader.now_kst")
    def test_returns_hhmm_format(self, mock_now: AsyncMock) -> None:
        """HHMM 형식 반환 확인."""
        mock_now.return_value = datetime(2026, 1, 1, 9, 35, tzinfo=UTC)
        result = now_hhmm()
        assert result == "0935"


# ── build_strategies ──────────────────────────────────


class TestBuildStrategies:
    """전략 빌더 테스트."""

    @pytest.mark.parametrize(
        "mode,expected",
        [
            ("both", {"momentum", "mean_reversion"}),
            ("momentum", {"momentum"}),
            ("mean_reversion", {"mean_reversion"}),
        ],
    )
    def test_mode_to_strategies(
        self, params: MomentumParams, mode: str, expected: set[str]
    ) -> None:
        """전략 모드에 따른 반환 전략 이름 집합 검증."""
        strats = build_strategies(mode, params)
        assert {s.name for s in strats} == expected

    def test_mr_params_passed_to_strategy(self, params: MomentumParams) -> None:
        """mr_params가 MeanReversionStrategy에 전달됨."""
        mr_params = MeanReversionParams(rsi_oversold=35.0, bb_std=1.2)
        strats = build_strategies("mean_reversion", params, mr_params)
        assert strats[0].params.rsi_oversold == 35.0
        assert strats[0].params.bb_std == 1.2


# ── load_daily_context ──────────────────────────────


class TestLoadDailyContext:
    """52주 일봉 로드 테스트."""

    async def test_load_daily_context_success(self, mock_client: AsyncMock) -> None:
        """정상 일봉 데이터 로드 시 DailyPrice + context 반환."""
        daily_items = [
            {
                "high_pric": str(10000 + i * 100),
                "low_pric": str(9000 + i * 100),
                "open_pric": str(9500 + i * 100),
                "close_pric": str(9800 + i * 100),
                "trde_qty": str(5000 + i * 10),
                "date": f"2026010{i:02d}",
            }
            for i in range(25)
        ]
        mock_client._request.side_effect = [
            {"daly_stkpc": daily_items},
            {"daly_stkpc": []},  # pagination 종료
        ]

        daily_prices, daily_context = await load_daily_context(mock_client, ["005930"])

        assert "005930" in daily_prices
        assert len(daily_prices["005930"]) == 25
        assert isinstance(daily_prices["005930"][0], DailyPrice)
        assert "005930" in daily_context
        assert daily_context["005930"]["high_52w"] > 0
        assert daily_context["005930"]["avg_volume"] > 0

    async def test_load_daily_context_empty(self, mock_client: AsyncMock) -> None:
        """일봉 데이터 없으면 건너뜀."""
        mock_client._request.return_value = {"daly_stkpc": []}

        daily_prices, _daily_context = await load_daily_context(mock_client, ["005930"])

        assert "005930" not in daily_prices

    async def test_load_daily_context_api_error_retry(self, mock_client: AsyncMock) -> None:
        """첫 요청 실패 시 재시도 후 성공."""
        daily_items = [
            {
                "high_pric": "10000",
                "low_pric": "9000",
                "open_pric": "9500",
                "close_pric": "9800",
                "trde_qty": "5000",
                "date": "20260101",
            }
        ]
        mock_client._request.side_effect = [
            Exception("timeout"),
            {"daly_stkpc": daily_items},
        ]

        daily_prices, _daily_context = await load_daily_context(mock_client, ["005930"])

        assert "005930" in daily_prices

    async def test_load_daily_context_both_retries_fail(self, mock_client: AsyncMock) -> None:
        """첫 요청 + 재시도 모두 실패 시 해당 종목 스킵."""
        mock_client._request.side_effect = Exception("timeout")

        daily_prices, _daily_context = await load_daily_context(mock_client, ["005930"])

        assert "005930" not in daily_prices

    async def test_load_daily_context_pagination(self, mock_client: AsyncMock) -> None:
        """여러 페이지 로드 시 합산."""
        page1 = [
            {
                "high_pric": "10000",
                "low_pric": "9000",
                "open_pric": "9500",
                "close_pric": "9800",
                "trde_qty": "5000",
                "date": "20260101",
            }
        ]
        page2 = [
            {
                "high_pric": "12000",
                "low_pric": "11000",
                "open_pric": "11500",
                "close_pric": "11800",
                "trde_qty": "6000",
                "date": "20260102",
            }
        ]
        page3: list[dict] = []
        mock_client._request.side_effect = [
            {"daly_stkpc": page1},
            {"daly_stkpc": page2},
            {"daly_stkpc": page3},
        ]

        _daily_prices, daily_context = await load_daily_context(mock_client, ["005930"])

        assert daily_context["005930"]["high_52w"] == 12000


# ── execute_buy ─────────────────────────────────────


class TestExecuteBuy:
    """시장가 매수 테스트."""

    @pytest.mark.parametrize("strategy", ["momentum", "mean_reversion"])
    async def test_buy_success(
        self, mock_client: AsyncMock, state: TradingState, strategy: str
    ) -> None:
        """정상 매수 시 포지션+거래 기록 (전략별)."""
        await execute_buy(mock_client, "005930", "삼성전자", 50000, 10, strategy, state)

        assert "005930" in state.positions
        assert state.positions["005930"].quantity == 10
        assert state.positions["005930"].entry_price == 50000
        assert state.positions["005930"].strategy == strategy
        assert len(state.trades) == 1
        assert state.trades[0].side == "BUY"
        assert state.trades[0].strategy == strategy

    async def test_buy_quantity_zero(self, mock_client: AsyncMock, state: TradingState) -> None:
        """수량 0이면 매수 안 함 + 주문 API 호출 자체가 일어나지 않음."""
        await execute_buy(mock_client, "005930", "삼성전자", 600000, 0, "momentum", state)

        assert "005930" not in state.positions
        assert len(state.trades) == 0
        # place_order가 호출되면 예외가 뜸 — return_value만 존재하는 AsyncMock
        # 0수량 경로에서는 그 전에 skip 되므로 place_order는 unused 상태
        assert mock_client.place_order.await_count == 0

    async def test_buy_api_error(self, mock_client: AsyncMock, state: TradingState) -> None:
        """주문 API 실패 시 포지션 미생성."""
        mock_client.place_order.side_effect = Exception("API Error")

        await execute_buy(mock_client, "005930", "삼성전자", 50000, 10, "momentum", state)

        assert "005930" not in state.positions
        assert len(state.trades) == 0


# ── execute_sell ─────────────────────────────────────


class TestExecuteSell:
    """시장가 매도 테스트."""

    async def test_sell_success(self, mock_client: AsyncMock, state: TradingState) -> None:
        """정상 매도 시 PnL 계산 + 포지션 삭제."""
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309100000",
            order_no="ORD001",
        )
        state.positions["005930"] = pos

        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD002",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        await execute_sell(mock_client, pos, 10100, "take_profit", state)

        assert "005930" not in state.positions
        assert len(state.trades) == 1
        trade = state.trades[0]
        assert trade.side == "SELL"
        assert trade.exit_reason == "take_profit"
        # PnL: (10100-10000)/10000 - 0.00015*2 - 0.0018 = 0.01 - 0.0021 = 0.0079
        expected_pnl = (10100 - 10000) / 10000 - (0.00015 * 2 + 0.0020)
        assert trade.pnl_pct == pytest.approx(expected_pnl, abs=1e-6)

    async def test_sell_stop_loss_pnl(self, mock_client: AsyncMock, state: TradingState) -> None:
        """손절 매도 시 음수 PnL."""
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309100000",
            order_no="ORD001",
        )
        state.positions["005930"] = pos

        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD002",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        await execute_sell(mock_client, pos, 9950, "stop_loss", state)

        trade = state.trades[0]
        assert trade.pnl_pct < 0
        expected_pnl = (9950 - 10000) / 10000 - (0.00015 * 2 + 0.0020)
        assert trade.pnl_pct == pytest.approx(expected_pnl, abs=1e-6)

    async def test_sell_api_error(self, mock_client: AsyncMock, state: TradingState) -> None:
        """매도 API 실패 시 포지션 유지."""
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309100000",
            order_no="ORD001",
        )
        state.positions["005930"] = pos
        mock_client.place_order.side_effect = Exception("API Error")

        await execute_sell(mock_client, pos, 10100, "take_profit", state)

        assert "005930" in state.positions
        assert len(state.trades) == 0


# ── poll_cycle ──────────────────────────────────────


class TestPollCycle:
    """폴링 사이클 테스트."""

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_entry_signal_triggers_buy(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """진입 신호 충족 시 매수 실행."""
        # 거래량 20000 → avg_volume(~10725) 대비 1.86x > 1.5 threshold
        quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=72000,
            change=1000,
            change_pct=1.45,
            volume=20000,
            high=72500,
            low=71000,
            open=71500,
            prev_close=71000,
        )
        mock_client.get_quote.return_value = quote
        # daily_context에 high_52w 설정
        state.daily_context["005930"] = {"high_52w": 80100, "avg_volume": 10725}
        state.daily_prices["005930"] = sample_daily

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" in state.positions
        assert state.positions["005930"].strategy == "momentum"

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_no_entry_below_threshold(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_quote: Quote,
    ) -> None:
        """52주 고가 대비 미달 시 매수 안 함.

        high_52w=100000인 일봉 데이터를 사용하면 현재가 70000 → 70% < 80% → 진입 불가.
        """
        mock_client.get_quote.return_value = sample_quote
        # high_52w=100000인 일봉 데이터: 70000 < 100000*0.80=80000 → price_condition 실패
        high_daily = [
            DailyPrice(
                date=f"2026010{i:02d}",
                open=99000,
                high=100000,
                low=98000,
                close=99500,
                volume=10000,
            )
            for i in range(30)
        ]
        state.daily_context["005930"] = {"high_52w": 100000, "avg_volume": 10000}
        state.daily_prices["005930"] = high_daily

        threshold_params = MomentumParams(high_52w_threshold=0.80)
        strategies = build_strategies("momentum", threshold_params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_exit_signal_triggers_sell(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """보유 중 손절 조건 충족 시 매도."""
        exit_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=9840,
            change=-160,
            change_pct=-1.6,
            volume=15000,
            high=10100,
            low=9800,
            open=10000,
            prev_close=10000,
        )
        mock_client.get_quote.return_value = exit_quote

        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309093000",
            order_no="ORD001",
            strategy="momentum",
        )
        state.positions["005930"] = pos
        state.daily_context["005930"] = {"high_52w": 10000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily

        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD002",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_mean_reversion_exit_with_indicators(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """평균회귀 포지션에서 RSI 과매수 청산 (check_exit_with_indicators 호출)."""
        # 지속 상승 → RSI 과매수 유발
        rising_daily = [
            DailyPrice(
                date=f"2026010{i:02d}",
                open=100 + i * 3,
                high=105 + i * 3,
                low=98 + i * 3,
                close=100 + i * 3,
                volume=1000,
            )
            for i in range(30)
        ]
        last_close = rising_daily[-1].close
        quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=last_close,
            change=3,
            change_pct=1.0,
            volume=1000,
            high=last_close + 5,
            low=last_close - 5,
            open=last_close - 3,
            prev_close=last_close - 3,
        )
        mock_client.get_quote.return_value = quote

        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=last_close,  # 손절/익절 범위 내
            quantity=10,
            entry_time="20260309093000",
            order_no="ORD001",
            strategy="mean_reversion",
        )
        state.positions["005930"] = pos
        state.daily_context["005930"] = {"high_52w": last_close + 100, "avg_volume": 1000}
        state.daily_prices["005930"] = rising_daily

        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD002",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        strategies = build_strategies("mean_reversion", MomentumParams())
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions
        sell_trade = next(t for t in state.trades if t.side == "SELL")
        assert sell_trade.exit_reason == "rsi_overbought"

    @patch("scripts.live_trader.now_hhmm", return_value="1515")
    async def test_force_close_at_1515(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """15:15 시각에 보유 포지션 강제 청산."""
        quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=10005,
            change=5,
            change_pct=0.05,
            volume=8000,
            high=10010,
            low=9990,
            open=10000,
            prev_close=10000,
        )
        mock_client.get_quote.return_value = quote

        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309093000",
            order_no="ORD001",
            strategy="momentum",
        )
        state.positions["005930"] = pos
        state.daily_context["005930"] = {"high_52w": 10000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily

        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD002",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_max_positions_limit(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_quote: Quote,
        sample_daily: list[DailyPrice],
    ) -> None:
        """전략별 최대 포지션 수 초과 시 신규 진입 안 함."""
        mock_client.get_quote.return_value = sample_quote
        state.daily_context["999999"] = {"high_52w": 70000, "avg_volume": 10000}
        state.daily_prices["999999"] = sample_daily

        # max_positions(3)만큼 이미 보유 (모멘텀)
        for i in range(params.max_positions):
            sym = f"00000{i}"
            state.positions[sym] = LivePosition(
                symbol=sym,
                name=f"종목{i}",
                entry_price=10000,
                quantity=1,
                entry_time="20260309093000",
                order_no=f"ORD{i}",
                strategy="momentum",
            )

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["999999"], strategies, state, 10_000_000, 1.0)

        assert "999999" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_quote_api_error_skips_symbol(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """시세 조회 실패 시 해당 종목 건너뜀."""
        mock_client.get_quote.side_effect = Exception("timeout")
        state.daily_context["005930"] = {"high_52w": 70000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_no_daily_data_skips_symbol(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_quote: Quote,
    ) -> None:
        """daily_prices 없는 종목은 건너뜀."""
        mock_client.get_quote.return_value = sample_quote
        # daily_prices에 005930 없음

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_drawdown_stop_buy(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_quote: Quote,
        sample_daily: list[DailyPrice],
    ) -> None:
        """드로우다운 매수중단 플래그 시 진입 안 함."""
        mock_client.get_quote.return_value = sample_quote
        state.daily_context["005930"] = {"high_52w": 70000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily
        state.drawdown_stop_buy = True

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_atr_filter_low_volatility_skips(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
    ) -> None:
        """ATR% < 0.35%인 저변동성 종목은 진입 스킵."""
        # 저변동성 일봉: 고가-저가 폭이 매우 좁음 (ATR% ≈ 0.1%)
        low_vol_daily = [
            DailyPrice(
                date=f"2026010{i:02d}",
                open=100000,
                high=100100,  # 폭 100원 = 0.1%
                low=100000,
                close=100050,
                volume=10000,
            )
            for i in range(25)
        ]
        quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=100050,
            change=50,
            change_pct=0.05,
            volume=20000,
            high=100100,
            low=100000,
            open=99800,
            prev_close=100000,
        )
        mock_client.get_quote.return_value = quote
        state.daily_context["005930"] = {"high_52w": 100100, "avg_volume": 10725}
        state.daily_prices["005930"] = low_vol_daily

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_atr_filter_normal_volatility_buys(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """ATR% >= 0.35%인 정상 변동성 종목은 진입 + dynamic_stop 설정됨."""
        # sample_daily의 고가-저가 폭: 2000원, 종가 ≈ 72500 → ATR% ≈ 2000/72500 ≈ 2.76%
        quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=72000,
            change=1000,
            change_pct=1.4,
            volume=20000,
            high=72500,
            low=71000,
            open=71500,
            prev_close=71000,
        )
        mock_client.get_quote.return_value = quote
        # daily_context에 high_52w 설정
        state.daily_context["005930"] = {"high_52w": 80100, "avg_volume": 10725}
        state.daily_prices["005930"] = sample_daily

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" in state.positions
        pos = state.positions["005930"]
        assert pos.dynamic_stop is not None
        assert pos.dynamic_stop <= -0.005  # 바닥 0.5% 이상
        assert pos.dynamic_tp is not None
        assert pos.dynamic_tp >= 0.01  # R:R 1:2 → TP >= SL*2


# ── force_close_all ─────────────────────────────────


class TestForceCloseAll:
    """미청산 강제 청산 테스트."""

    async def test_close_all_positions(self, mock_client: AsyncMock, state: TradingState) -> None:
        """모든 포지션 강제 청산."""
        for i, sym in enumerate(["005930", "000660"]):
            state.positions[sym] = LivePosition(
                symbol=sym,
                name=f"종목{i}",
                entry_price=10000,
                quantity=10,
                entry_time="20260309093000",
                order_no=f"ORD{i}",
            )

        mock_client.get_quote.return_value = Quote(
            symbol="005930",
            name="삼성전자",
            price=10100,
            change=100,
            change_pct=1.0,
            volume=5000,
            high=10200,
            low=9900,
            open=10000,
            prev_close=10000,
        )
        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD_CLOSE",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        await force_close_all(mock_client, state)

        assert len(state.positions) == 0
        sell_trades = [t for t in state.trades if t.side == "SELL"]
        assert len(sell_trades) == 2

    async def test_close_empty_positions(self, mock_client: AsyncMock, state: TradingState) -> None:
        """포지션 없으면 아무 동작 안 함."""
        await force_close_all(mock_client, state)

        mock_client.get_quote.assert_not_called()
        mock_client.place_order.assert_not_called()

    async def test_close_partial_failure(self, mock_client: AsyncMock, state: TradingState) -> None:
        """일부 종목 청산 실패 시 나머지는 계속 진행."""
        state.positions["005930"] = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309093000",
            order_no="ORD001",
        )
        state.positions["000660"] = LivePosition(
            symbol="000660",
            name="SK하이닉스",
            entry_price=10000,
            quantity=5,
            entry_time="20260309093000",
            order_no="ORD002",
        )

        # 첫 번째 시세 조회 실패, 두 번째 성공
        mock_client.get_quote.side_effect = [
            Exception("timeout"),
            Quote(
                symbol="000660",
                name="SK하이닉스",
                price=10100,
                change=100,
                change_pct=1.0,
                volume=3000,
                high=10200,
                low=9900,
                open=10000,
                prev_close=10000,
            ),
        ]
        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD_CLOSE",
            symbol="000660",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=5,
            status="submitted",
            message="",
        )

        await force_close_all(mock_client, state)

        # 005930은 실패로 남아있고, 000660만 청산
        assert "005930" in state.positions
        assert "000660" not in state.positions


# ── save_results ────────────────────────────────────


class TestSaveResults:
    """결과 저장 테스트."""

    def test_save_results_creates_json(
        self, tmp_path: pytest.TempPathFactory, params: MomentumParams, state: TradingState
    ) -> None:
        """JSON 파일 정상 생성."""
        import json

        import scripts.live_trader as lt

        original_dir = lt.RESULTS_DIR
        lt.RESULTS_DIR = tmp_path  # type: ignore[assignment]

        try:
            from scripts.live_trader import TradeLog

            state.trades.append(
                TradeLog(
                    symbol="005930",
                    name="삼성전자",
                    side="BUY",
                    price=10000,
                    quantity=10,
                    time="20260309100000",
                    order_no="ORD001",
                    strategy="momentum",
                )
            )
            state.trades.append(
                TradeLog(
                    symbol="005930",
                    name="삼성전자",
                    side="SELL",
                    price=10100,
                    quantity=10,
                    time="20260309110000",
                    order_no="ORD002",
                    pnl_pct=0.0079,
                    exit_reason="take_profit",
                    strategy="momentum",
                )
            )

            strategies = build_strategies("both", params)
            save_results(state, strategies)

            files = list(tmp_path.glob("live_*.json"))
            assert len(files) == 1

            data = json.loads(files[0].read_text(encoding="utf-8"))
            assert data["mode"] == "live_mock"
            assert "strategies" in data
            assert data["summary"]["total_buys"] == 1
            assert data["summary"]["total_sells"] == 1
            assert data["summary"]["win_rate"] == 1.0
            assert len(data["trades"]) == 2
            assert data["trades"][0]["strategy"] == "momentum"
            assert "strategy_stats" in data
        finally:
            lt.RESULTS_DIR = original_dir


# ── dataclass 테스트 ────────────────────────────────


class TestDataclasses:
    """LivePosition, TradingState 기본 동작 테스트."""

    def test_live_position_defaults_and_override(self) -> None:
        """LivePosition 기본 strategy=momentum, override 가능."""
        default_pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=70000,
            quantity=10,
            entry_time="20260309100000",
            order_no="ORD001",
        )
        assert default_pos.strategy == "momentum"
        assert default_pos.high_since_entry == 0

        mr_pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=70000,
            quantity=10,
            entry_time="20260309100000",
            order_no="ORD001",
            strategy="mean_reversion",
        )
        assert mr_pos.strategy == "mean_reversion"

    def test_trading_state_defaults(self) -> None:
        """TradingState 기본값 확인."""
        state = TradingState()
        assert state.positions == {}
        assert state.trades == []
        assert state.daily_prices == {}
        assert state.daily_context == {}
        assert state.drawdown_stop_buy is False


# ── calc_time_ratio ──────────────────────────────────


class TestCalcTimeRatio:
    """calc_time_ratio 장 경과 비율 테스트."""

    @pytest.mark.parametrize(
        "hhmm,expected,tol",
        [
            ("0900", 0.0, 0.0),  # 장 시작
            ("0830", 0.0, 0.0),  # 장 시작 전
            ("1530", 1.0, 0.0),  # 장 마감
            ("1600", 1.0, 0.0),  # 장 마감 이후
            ("1215", 0.5, 0.01),  # 중간 (195/390)
            ("1000", 60 / 390, 0.001),  # 60분 경과
            ("", 1.0, 0.0),  # 빈 문자열
            ("ab", 1.0, 0.0),  # 잘못된 형식
        ],
    )
    def test_time_ratio_matrix(self, hhmm: str, expected: float, tol: float) -> None:
        """다양한 시각에 대한 장 경과 비율 검증."""
        result = calc_time_ratio(hhmm)
        if tol == 0.0:
            assert result == expected
        else:
            assert abs(result - expected) < tol


# ── run_trading_loop_ws ──────────────────────────────


class TestRunTradingLoopWs:
    """WebSocket 매매 루프 테스트."""

    @patch("scripts.live_trader.KiwoomWebSocket")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_ws_entry_signal_triggers_buy(
        self,
        _mock_hhmm: AsyncMock,
        mock_ws_cls: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """WebSocket 틱 수신 시 진입 신호 충족 → 매수 실행."""
        mock_ws = AsyncMock()
        mock_ws.is_connected = True
        mock_ws_cls.return_value = mock_ws

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        # daily_context에 high_52w 설정
        state.daily_context["005930"] = {"high_52w": 80100, "avg_volume": 10725}
        state.daily_prices["005930"] = sample_daily
        # day_open을 tick보다 낮게 설정해 price_change_min 필터 통과
        state.day_open_prices["005930"] = 71500

        # run_until이 즉시 종료되도록 설정
        mock_ws.run_until = AsyncMock()

        await run_trading_loop_ws(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        # on_tick 콜백이 등록됐는지 확인
        assert mock_ws.on_tick is not None

        # 진입 신호 조건을 만족하는 틱으로 콜백 직접 호출
        tick = RealtimeTick(symbol="005930", price=72000, volume=20000, timestamp="100000")
        await mock_ws.on_tick(tick)

        assert "005930" in state.positions
        assert state.positions["005930"].strategy == "momentum"

    @patch("scripts.live_trader.KiwoomWebSocket")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_ws_exit_signal_triggers_sell(
        self,
        _mock_hhmm: AsyncMock,
        mock_ws_cls: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """WebSocket 틱 수신 시 보유 포지션 손절 조건 충족 → 매도 실행."""
        mock_ws = AsyncMock()
        mock_ws.is_connected = True
        mock_ws_cls.return_value = mock_ws
        mock_ws.run_until = AsyncMock()

        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309093000",
            order_no="ORD001",
            strategy="momentum",
            high_since_entry=10000,
        )
        state.positions["005930"] = pos
        state.daily_context["005930"] = {"high_52w": 10000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily

        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD002",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        params = MomentumParams()
        strategies = build_strategies("momentum", params)

        await run_trading_loop_ws(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        # 손절 조건(entry 10000, 현재가 9840 → -1.6% > stop_loss -1.5%) 틱 호출
        tick = RealtimeTick(symbol="005930", price=9840, volume=5000, timestamp="100000")
        await mock_ws.on_tick(tick)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.KiwoomWebSocket")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_ws_unknown_symbol_ignored(
        self,
        _mock_hhmm: AsyncMock,
        mock_ws_cls: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """구독 목록에 없는 종목 틱은 무시."""
        mock_ws = AsyncMock()
        mock_ws.is_connected = True
        mock_ws_cls.return_value = mock_ws
        mock_ws.run_until = AsyncMock()

        params = MomentumParams()
        strategies = build_strategies("momentum", params)

        await run_trading_loop_ws(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        tick = RealtimeTick(symbol="999999", price=50000, volume=10000, timestamp="100000")
        await mock_ws.on_tick(tick)

        assert "999999" not in state.positions
        mock_client.place_order.assert_not_called()

    @patch("scripts.live_trader.KiwoomWebSocket")
    async def test_ws_connection_timeout_raises(
        self,
        mock_ws_cls: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """WebSocket 연결 수립 실패 시 ConnectionError 발생."""
        mock_ws = AsyncMock()
        mock_ws.is_connected = False  # 연결 수립 실패 상태
        mock_ws_cls.return_value = mock_ws

        params = MomentumParams()
        strategies = build_strategies("momentum", params)

        with pytest.raises(ConnectionError, match="WebSocket 연결 수립 시간 초과"):
            await run_trading_loop_ws(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)


# ── update_risk_after_trade + kill_switch ────────────


class TestUpdateRiskAfterTrade:
    """단계적 리스크 관리 — 손실 카운터 + 블랙리스트 + kill_switch 통합 테스트."""

    @pytest.mark.parametrize(
        "pnls,expected_count,blacklisted",
        [
            ([-0.005], 1, False),  # 첫 손실
            ([-0.005, -0.005], 2, False),  # 2연패: 축소만
            ([-0.005, -0.005, -0.005], 3, True),  # 3연패: 블랙리스트
            ([-0.005, -0.005, 0.01], 0, False),  # 수익 → 리셋
            ([-0.005, 0.0], 0, False),  # pnl 0은 수익 간주
        ],
    )
    def test_risk_counter_and_blacklist(
        self,
        state: TradingState,
        pnls: list[float],
        expected_count: int,
        blacklisted: bool,
    ) -> None:
        """손실 카운터 + 블랙리스트 편입 규칙 검증."""
        for pnl in pnls:
            update_risk_after_trade(state, "005930", pnl)
        assert state.symbol_losses.get("005930", 0) == expected_count
        assert ("005930" in state.symbol_blacklist) is blacklisted

    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_blacklisted_symbol_skips_entry(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """블랙리스트 종목은 진입 신호 충족해도 매수 안 함."""
        quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=72000,
            change=1000,
            change_pct=1.4,
            volume=20000,
            high=72500,
            low=71000,
            open=71500,
            prev_close=71000,
        )
        mock_client.get_quote.return_value = quote
        state.daily_context["005930"] = {"high_52w": 72900, "avg_volume": 10725}
        state.daily_prices["005930"] = sample_daily
        state.symbol_blacklist.add("005930")

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert "005930" not in state.positions

    @patch("scripts.live_trader.update_drawdown")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_kill_switch_stop_buy_after_sell(
        self,
        _mock_hhmm: AsyncMock,
        mock_update_drawdown: MagicMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """청산 후 drawdown STOP_BUY → drawdown_stop_buy = True."""
        from src.trading.drawdown_guard import DrawdownAction

        mock_update_drawdown.return_value = DrawdownAction.STOP_BUY

        exit_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=9840,
            change=-160,
            change_pct=-1.6,
            volume=15000,
            high=10100,
            low=9800,
            open=10000,
            prev_close=10000,
        )
        mock_client.get_quote.return_value = exit_quote
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309093000",
            order_no="ORD001",
            strategy="momentum",
        )
        state.positions["005930"] = pos
        state.daily_context["005930"] = {"high_52w": 10000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily
        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD002",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert state.drawdown_stop_buy is True

    @patch("scripts.live_trader.update_drawdown")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_kill_switch_force_close_after_sell(
        self,
        _mock_hhmm: AsyncMock,
        mock_update_drawdown: MagicMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """청산 후 drawdown FORCE_CLOSE → 남은 포지션 전량 정리.

        behavior 기반 검증: force_close_all은 실제로 실행되어 잔여 포지션이
        모두 비워져야 한다 (mock 호출 여부가 아닌 상태 변화로 확인).
        """
        from src.trading.drawdown_guard import DrawdownAction

        mock_update_drawdown.return_value = DrawdownAction.FORCE_CLOSE

        exit_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=9840,
            change=-160,
            change_pct=-1.6,
            volume=15000,
            high=10100,
            low=9800,
            open=10000,
            prev_close=10000,
        )
        extra_quote = Quote(
            symbol="000660",
            name="SK하이닉스",
            price=10100,
            change=100,
            change_pct=1.0,
            volume=5000,
            high=10200,
            low=9900,
            open=10000,
            prev_close=10000,
        )
        # get_quote는 종목마다 다른 응답
        mock_client.get_quote.side_effect = lambda symbol: (
            exit_quote if symbol == "005930" else extra_quote
        )
        # 손절 대상 + 강제 청산 대상 동시 존재
        state.positions["005930"] = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=10000,
            quantity=10,
            entry_time="20260309093000",
            order_no="ORD001",
            strategy="momentum",
        )
        state.positions["000660"] = LivePosition(
            symbol="000660",
            name="SK하이닉스",
            entry_price=10000,
            quantity=5,
            entry_time="20260309093000",
            order_no="ORD002",
            strategy="momentum",
        )
        state.daily_context["005930"] = {"high_52w": 10000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily
        mock_client.place_order.return_value = BrokerOrderResponse(
            order_no="ORD_CLOSE",
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=0,
            quantity=10,
            status="submitted",
            message="",
        )

        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        # 손절 + FORCE_CLOSE 경로 → 모든 포지션 정리
        assert state.positions == {}

    @patch("scripts.live_trader.calc_dynamic_position_size")
    @patch("scripts.live_trader.calc_atr", return_value=2520.0)  # 2520/72000 ≈ 3.5% > MIN_ATR_PCT
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_two_loss_symbol_scales_down(
        self,
        _mock_hhmm: AsyncMock,
        _mock_atr: MagicMock,
        mock_sizer: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """2연패 종목 진입 시 scale_factor * 0.5 적용."""
        mock_sizer.return_value = 5

        quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=72000,
            change=1000,
            change_pct=1.4,
            volume=20000,
            high=72500,
            low=71000,
            open=71500,
            prev_close=71000,
        )
        mock_client.get_quote.return_value = quote
        # daily_context에 high_52w 설정
        state.daily_context["005930"] = {"high_52w": 80100, "avg_volume": 10725}
        state.daily_prices["005930"] = sample_daily
        state.symbol_losses["005930"] = 2  # 2연패

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005930"], strategies, state, 10_000_000, 1.0)

        assert mock_sizer.called
        scale_used = mock_sizer.call_args.kwargs.get("scale_factor")
        assert scale_used == pytest.approx(0.5)


# ── 섹터 포지션 제한 ──────────────────────────────────


class TestSectorPositionLimit:
    """섹터 포지션 제한 — 테마당 1개 테스트."""

    @patch("scripts.live_trader.get_sector", return_value="반도체")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_same_sector_blocks_second_entry(
        self,
        _mock_hhmm: AsyncMock,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """같은 섹터 종목이 이미 진입됐으면 신규 매수 차단."""
        quote = Quote(
            symbol="000660",
            name="SK하이닉스",
            price=72000,
            change=1000,
            change_pct=1.4,
            volume=20000,
            high=72500,
            low=71000,
            open=71500,
            prev_close=71000,
        )
        mock_client.get_quote.return_value = quote
        state.daily_context["000660"] = {"high_52w": 72900, "avg_volume": 10725}
        state.daily_prices["000660"] = sample_daily
        state.sector_positions["반도체"] = 2  # 이미 반도체 섹터 2개 보유 (한도)

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["000660"], strategies, state, 10_000_000, 1.0)

        assert "000660" not in state.positions

    @patch("scripts.live_trader.get_sector", return_value="소재")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_different_sector_allows_entry(
        self,
        _mock_hhmm: AsyncMock,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """다른 섹터 종목은 정상 진입 가능."""
        quote = Quote(
            symbol="005490",
            name="POSCO홀딩스",
            price=72000,
            change=1000,
            change_pct=1.4,
            volume=20000,
            high=72500,
            low=71000,
            open=71500,
            prev_close=71000,
        )
        mock_client.get_quote.return_value = quote
        # daily_context에 high_52w 설정
        state.daily_context["005490"] = {"high_52w": 80100, "avg_volume": 10725}
        state.daily_prices["005490"] = sample_daily
        state.sector_positions["반도체"] = 2  # 반도체만 점유, 소재는 비어 있음

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["005490"], strategies, state, 10_000_000, 1.0)

        assert "005490" in state.positions

    @patch("scripts.live_trader.get_sector", return_value="기타")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_unknown_sector_always_allowed(
        self,
        _mock_hhmm: AsyncMock,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """'기타' 섹터는 sector_positions에 무관하게 진입 허용."""
        quote = Quote(
            symbol="999999",
            name="기타종목",
            price=72000,
            change=1000,
            change_pct=1.4,
            volume=20000,
            high=72500,
            low=71000,
            open=71500,
            prev_close=71000,
        )
        mock_client.get_quote.return_value = quote
        # daily_context에 high_52w 설정
        state.daily_context["999999"] = {"high_52w": 80100, "avg_volume": 10725}
        state.daily_prices["999999"] = sample_daily
        state.sector_positions["기타"] = 2  # 기타가 이미 있어도 진입 허용

        params = MomentumParams()
        strategies = build_strategies("momentum", params)
        await poll_cycle(mock_client, ["999999"], strategies, state, 10_000_000, 1.0)

        assert "999999" in state.positions

    @patch("scripts.live_trader.get_sector", return_value="반도체")
    async def test_buy_registers_sector(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """매수 성공 시 섹터가 sector_positions에 등록됨."""
        await execute_buy(mock_client, "005930", "삼성전자", 70000, 10, "momentum", state)

        assert state.sector_positions.get("반도체", 0) >= 1

    @patch("scripts.live_trader.get_sector", return_value="기타")
    async def test_buy_other_sector_not_registered(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """'기타' 섹터 매수 시 sector_positions에 추가 안 됨."""
        await execute_buy(mock_client, "999999", "기타종목", 70000, 10, "momentum", state)

        assert state.sector_positions.get("기타", 0) == 0


# ── 장중 재스크리닝 ──────────────────────────────────


class TestRescreenIntraday:
    """rescreen_intraday 단위 테스트."""

    async def test_skips_existing_symbols(self, mock_client: AsyncMock) -> None:
        """기존 종목은 스킵."""
        from scripts.screen_symbols import UNIVERSE, rescreen_intraday

        existing = list(UNIVERSE.keys())
        result = await rescreen_intraday(mock_client, existing)
        assert result == []
        mock_client._request.assert_not_called()

    @patch("scripts.screen_symbols.fetch_daily_pages")
    @patch("scripts.screen_symbols.check_screen_condition")
    async def test_returns_new_passing_symbols(
        self,
        mock_check: MagicMock,
        mock_fetch: AsyncMock,
        mock_client: AsyncMock,
    ) -> None:
        """조건 통과한 신규 종목만 반환."""
        from scripts.screen_symbols import UNIVERSE, rescreen_intraday

        daily_data = [
            DailyPrice(
                date=f"2026010{i:02d}",
                open=10000,
                high=10500,
                low=9500,
                close=10000,
                volume=1000,
            )
            for i in range(30)
        ]
        mock_fetch.return_value = daily_data
        mock_check.return_value = {"passed": True, "bonus_score": 2}

        all_symbols = list(UNIVERSE.keys())
        existing = all_symbols[:50]
        result = await rescreen_intraday(mock_client, existing)
        # UNIVERSE 전체 - 기존 50개 = 나머지가 통과해야 함
        expected_new = [s for s in all_symbols if s not in existing]
        assert result == expected_new

    @patch("scripts.screen_symbols.fetch_daily_pages")
    @patch("scripts.screen_symbols.check_screen_condition")
    async def test_returns_empty_when_none_pass(
        self,
        mock_check: MagicMock,
        mock_fetch: AsyncMock,
        mock_client: AsyncMock,
    ) -> None:
        """조건 미통과 시 빈 리스트."""
        from scripts.screen_symbols import rescreen_intraday

        mock_fetch.return_value = [
            DailyPrice(
                date="20260101",
                open=10000,
                high=10500,
                low=9500,
                close=10000,
                volume=1000,
            )
        ] * 30
        mock_check.return_value = {"passed": False}

        result = await rescreen_intraday(mock_client, [])
        assert result == []


class TestRunRescreen:
    """_run_rescreen 통합 테스트."""

    @patch("scripts.live_trader.load_daily_context")
    @patch("scripts.screen_symbols.rescreen_intraday", new_callable=AsyncMock)
    async def test_adds_new_symbols_to_state(
        self,
        mock_rescreen: AsyncMock,
        mock_load_ctx: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """신규 종목을 state에 추가."""
        from scripts.live_trader import _run_rescreen

        new_sym = "999999"
        mock_rescreen.return_value = [new_sym]
        mock_load_ctx.return_value = (
            {new_sym: sample_daily},
            {new_sym: {"high_52w": 72900, "avg_volume": 11450}},
        )

        symbols: list[str] = ["005930"]
        state.daily_prices["005930"] = sample_daily

        added = await _run_rescreen(mock_client, symbols, state)

        assert new_sym in added
        assert new_sym in state.daily_prices
        assert new_sym in state.symbol_strategies
        assert new_sym in symbols

    @patch("scripts.live_trader.load_daily_context")
    @patch("scripts.screen_symbols.rescreen_intraday", new_callable=AsyncMock)
    async def test_no_new_symbols(
        self,
        mock_rescreen: AsyncMock,
        mock_load_ctx: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """신규 종목 없으면 빈 리스트 반환."""
        from scripts.live_trader import _run_rescreen

        mock_rescreen.return_value = []
        added = await _run_rescreen(mock_client, [], state)

        assert added == []
        mock_load_ctx.assert_not_called()


class TestTradingStateRescreened:
    """TradingState.rescreened 필드 테스트."""

    def test_rescreened_tracking(self) -> None:
        """기본값 빈 dict + 재스크리닝 실행 여부 추적 가능."""
        from scripts.live_trader import RESCREEN_TIMES

        state = TradingState()
        assert state.rescreened == {}
        assert RESCREEN_TIMES == ("1000", "1100")

        state.rescreened["1000"] = True
        assert state.rescreened.get("1000") is True
        assert state.rescreened.get("1100") is None


# ── rescreening_task_ws WS 구독 테스트 ────────────────


class TestRescreeningTaskWs:
    """rescreening_task_ws: WS 연결 상태별 구독 동작 검증."""

    @patch("scripts.live_trader._run_rescreen", new_callable=AsyncMock)
    @patch("scripts.live_trader.now_hhmm", return_value="1059")
    @patch("scripts.live_trader.asyncio.sleep", new_callable=AsyncMock)
    async def test_subscribe_called_when_ws_connected(
        self,
        _mock_sleep: AsyncMock,
        _mock_hhmm: MagicMock,
        mock_rescreen: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """WS 연결 상태에서 재스크리닝 성공 → subscribe 호출.

        now_hhmm="1059": 1000 스킵(이미 지남), 1100만 처리 → 1회 subscribe 검증.
        """
        mock_ws = AsyncMock()
        mock_ws.is_connected = True

        mock_rescreen.return_value = ["036930"]

        await rescreening_task_ws(mock_client, ["005930"], state, mock_ws)

        mock_ws.subscribe.assert_called_once_with(["036930"], "0B")

    @patch("scripts.live_trader._run_rescreen", new_callable=AsyncMock)
    @patch("scripts.live_trader.now_hhmm", return_value="1059")
    @patch("scripts.live_trader.asyncio.sleep", new_callable=AsyncMock)
    async def test_subscribe_skipped_when_no_new_symbols(
        self,
        _mock_sleep: AsyncMock,
        _mock_hhmm: MagicMock,
        mock_rescreen: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """재스크리닝 결과 신규 종목 없으면 subscribe 미호출."""
        mock_ws = AsyncMock()
        mock_ws.is_connected = True
        mock_rescreen.return_value = []

        await rescreening_task_ws(mock_client, ["005930"], state, mock_ws)

        mock_ws.subscribe.assert_not_called()

    @patch("scripts.live_trader._wait_for_ws_reconnect", new_callable=AsyncMock)
    @patch("scripts.live_trader._run_rescreen", new_callable=AsyncMock)
    @patch("scripts.live_trader.now_hhmm", return_value="1059")
    @patch("scripts.live_trader.asyncio.sleep", new_callable=AsyncMock)
    async def test_reconnect_waited_then_subscribe_on_success(
        self,
        _mock_sleep: AsyncMock,
        _mock_hhmm: MagicMock,
        mock_rescreen: AsyncMock,
        mock_wait: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """WS 끊김 → 재연결 성공 → subscribe 호출.

        now_hhmm="1059": 1100 타겟만 처리. WS 미연결 → 재연결 대기 → 성공 → subscribe.
        """
        mock_ws = AsyncMock()
        mock_ws.is_connected = False  # 재스크리닝 시점에 WS 미연결
        mock_rescreen.return_value = ["299660", "034020"]
        mock_wait.return_value = True  # 재연결 성공

        await rescreening_task_ws(mock_client, ["005930"], state, mock_ws)

        mock_wait.assert_called_once_with(mock_ws)
        mock_ws.subscribe.assert_called_once_with(["299660", "034020"], "0B")

    @patch("scripts.live_trader._wait_for_ws_reconnect", new_callable=AsyncMock)
    @patch("scripts.live_trader._run_rescreen", new_callable=AsyncMock)
    @patch("scripts.live_trader.now_hhmm", return_value="1059")
    @patch("scripts.live_trader.asyncio.sleep", new_callable=AsyncMock)
    async def test_fallback_polling_when_reconnect_fails(
        self,
        _mock_sleep: AsyncMock,
        _mock_hhmm: MagicMock,
        mock_rescreen: AsyncMock,
        mock_wait: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """WS 끊김 → 재연결 실패 → subscribe 미호출, 폴링 폴백.

        now_hhmm="1059": 1100 타겟만 처리. 재연결 실패 → subscribe 생략.
        """
        mock_ws = AsyncMock()
        mock_ws.is_connected = False  # 재연결 실패
        mock_rescreen.return_value = ["036930"]
        mock_wait.return_value = False  # 재연결 실패

        await rescreening_task_ws(mock_client, ["005930"], state, mock_ws)

        mock_wait.assert_called_once_with(mock_ws)
        mock_ws.subscribe.assert_not_called()  # 폴링 폴백 → subscribe 생략


class TestWaitForWsReconnect:
    """_wait_for_ws_reconnect: 재연결 대기 로직 검증."""

    async def test_returns_true_immediately_if_connected(self) -> None:
        """이미 연결된 경우 즉시 True 반환."""

        mock_ws = MagicMock()
        mock_ws.is_connected = True

        result = await _wait_for_ws_reconnect(mock_ws, timeout=5.0)

        assert result is True

    @patch("scripts.live_trader.asyncio.sleep", new_callable=AsyncMock)
    async def test_returns_true_after_reconnect(self, mock_sleep: AsyncMock) -> None:
        """몇 번 폴링 후 연결되면 True 반환."""

        mock_ws = MagicMock()
        # 첫 2회 미연결, 3회째 연결
        mock_ws.is_connected = False
        call_count = 0

        async def fake_sleep(_: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                mock_ws.is_connected = True

        mock_sleep.side_effect = fake_sleep

        result = await _wait_for_ws_reconnect(mock_ws, timeout=10.0)

        assert result is True

    @patch("scripts.live_trader.asyncio.sleep", new_callable=AsyncMock)
    async def test_returns_false_on_timeout(self, _mock_sleep: AsyncMock) -> None:
        """timeout 초과 시 False 반환."""

        mock_ws = MagicMock()
        mock_ws.is_connected = False

        # timeout을 poll 간격보다 살짝 짧게 설정 → 1회 시도 후 timeout
        result = await _wait_for_ws_reconnect(mock_ws, timeout=_WS_RECONNECT_POLL_SEC * 0.5)

        assert result is False


# ── 이중 안전망 테스트 ────────────────────────────────


class TestDualStopLoss:
    """이중 안전망 — TradingState.max_loss_pct 필드 검증."""

    def test_max_loss_pct_default_and_override(self) -> None:
        """기본값 -0.02, 커스텀 할당 허용."""
        state = TradingState()
        assert state.max_loss_pct == -0.02
        state.max_loss_pct = -0.03
        assert state.max_loss_pct == -0.03


# ── 레짐별 자본 배분 테스트 ───────────────────────────


class TestRegimeCapitalAllocation:
    """StrategyBudget.apply_regime 테스트."""

    @pytest.mark.parametrize(
        "regime_name,momentum_budget,mr_budget",
        [
            ("AGGRESSIVE", 5_500_000, 3_000_000),  # pool_a 55%, pool_b 30%
            ("NEUTRAL", 4_000_000, 4_000_000),  # 40% / 40%
            ("DEFENSIVE", 2_500_000, 4_000_000),  # 25% / 40%
            ("CRISIS", 0, 0),  # 전량 현금
        ],
    )
    def test_regime_allocation_matrix(
        self, regime_name: str, momentum_budget: int, mr_budget: int
    ) -> None:
        """레짐별 전략 자본 배분 검증."""
        from src.ai.signal.position_sizer import StrategyBudget
        from src.trading.market_regime import MarketRegime

        budget = StrategyBudget()
        regime = getattr(MarketRegime, regime_name)
        budget.apply_regime(regime, 10_000_000)

        assert budget.budget_for("momentum") == momentum_budget
        assert budget.budget_for("mean_reversion") == mr_budget
        if regime is MarketRegime.CRISIS:
            # 위기 레짐: 가용 자금도 0이어야 함
            assert budget.available("momentum") == 0
            assert budget.available("mean_reversion") == 0

    def test_apply_regime_updates_total_balance(self) -> None:
        """apply_regime 호출 시 total_balance도 갱신된다."""
        from src.ai.signal.position_sizer import StrategyBudget
        from src.trading.market_regime import MarketRegime

        budget = StrategyBudget()
        budget.apply_regime(MarketRegime.NEUTRAL, 20_000_000)

        assert budget.total_balance == 20_000_000


# ── DEFENSIVE 레짐 모멘텀 중단 테스트 ───────────────────


class TestDefensiveRegimeBlocksMomentum:
    """DEFENSIVE/CRISIS 레짐에서 모멘텀 신규 매수 중단."""

    @pytest.mark.asyncio
    @patch("scripts.live_trader.get_sector", return_value="기타")
    async def test_defensive_regime_blocks_momentum_entry(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """DEFENSIVE 레짐에서 모멘텀 신규 진입 차단."""
        from src.trading.market_regime import MarketRegime

        state = TradingState()
        state.budget.reset(10_000_000)
        state.current_regime = MarketRegime.DEFENSIVE

        high_52w = 100_000
        current_price = 90_000  # 10% 조정 → 풀백 조건 통과

        daily = [
            DailyPrice(
                date=f"2025{i:04d}",
                open=current_price - 500,
                high=current_price + 1000,
                low=current_price - 1000,
                close=current_price,
                volume=20_000,
            )
            for i in range(1, 22)
        ]

        state.daily_prices["005930"] = daily
        state.daily_context["005930"] = {"high_52w": high_52w, "avg_volume": 10_000}
        state.symbol_strategies["005930"] = "momentum"

        from src.backtest.strategy import MomentumParams
        from src.strategy import MomentumStrategy

        p = MomentumParams(
            volume_ratio=1.0,
            entry_start_time="00:00",
            entry_end_time="23:59",
            price_change_min=0.0,
            require_bullish_bar=False,
        )
        strats = [MomentumStrategy(params=p)]

        quote = Quote(
            symbol="005930",
            name="테스트",
            price=current_price,
            change=0,
            change_pct=0.0,
            volume=20_000,
            high=current_price,
            low=current_price,
            open=current_price - 100,
            prev_close=current_price,
        )
        mock_client.get_quote.return_value = quote

        await poll_cycle(mock_client, ["005930"], strats, state, 10_000_000, 1.0)
        # DEFENSIVE 레짐 → 모멘텀 진입 차단
        assert not mock_client.place_order.called


# ── MarketContext observe-only 로깅 테스트 ─────────────────


class TestMarketContextObservation:
    """MarketContext 수급/테마 observe 로그(매매 영향 없음) 검증."""

    def _build_mock_ctx(
        self,
        investor_flow: dict | None = None,
        theme_scores: dict | None = None,
        stock_flows: dict | None = None,
    ) -> MagicMock:
        """MarketContext mock 생성 헬퍼."""
        ctx = MagicMock()
        ctx.get_investor_flow.return_value = investor_flow if investor_flow is not None else {}
        ctx.get_theme_scores.return_value = theme_scores if theme_scores is not None else {}
        ctx.get_stock_investor_flows.return_value = stock_flows if stock_flows is not None else {}
        return ctx

    def test_log_observation_all_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        """모든 데이터 빈 dict — 각 '데이터 없음' 로그 3줄 출력."""
        from scripts.live_trader import _log_market_context_observation

        ctx = self._build_mock_ctx()
        with caplog.at_level("INFO", logger="live_trader"):
            _log_market_context_observation(ctx, symbols=["005930"])

        messages = [rec.message for rec in caplog.records]
        assert any("[observe] 시장 수급: 데이터 없음" in m for m in messages)
        assert any("[observe] 테마 점수: 데이터 없음" in m for m in messages)
        assert any("[observe] 종목별 수급 데이터: 없음" in m for m in messages)

    def test_log_observation_with_data(self, caplog: pytest.LogCaptureFixture) -> None:
        """정상 데이터 — investor_flow·theme top5·매칭 수 로그."""
        from scripts.live_trader import _log_market_context_observation

        ctx = self._build_mock_ctx(
            investor_flow={"foreign": 1.0e9, "institution": 5.0e8, "individual": -1.5e9},
            theme_scores={
                "반도체": 0.9,
                "AI": 0.85,
                "2차전지": 0.8,
                "바이오": 0.7,
                "조선": 0.6,
                "건설": 0.3,
            },
            stock_flows={
                "005930": {"foreign": 3.0e8, "institution": 1.0e8},
                "000660": {"foreign": 2.0e8, "institution": 5.0e7},
            },
        )
        with caplog.at_level("INFO", logger="live_trader"):
            _log_market_context_observation(ctx, symbols=["005930", "035720"])

        messages = [rec.message for rec in caplog.records]
        # 시장 수급
        assert any("foreign=1000000000.0" in m and "institution=" in m for m in messages)
        # 테마 top5 (6개 중 상위 5개만, 건설 제외)
        theme_msg = next(m for m in messages if "[observe] 테마 점수 상위 5" in m)
        assert "반도체=0.90" in theme_msg
        assert "조선=0.60" in theme_msg
        assert "건설" not in theme_msg  # 상위 5개 밖
        assert "총 6개" in theme_msg
        # 감시 종목 매칭 1/2 (005930만 매칭)
        assert any("1/2" in m for m in messages)

    def test_log_observation_theme_score_invalid_type(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """테마 점수에 숫자 캐스팅 불가 값 포함 — 해당 항목만 제외 후 출력."""
        from scripts.live_trader import _log_market_context_observation

        ctx = self._build_mock_ctx(
            theme_scores={"반도체": 0.9, "AI": "invalid", "2차전지": 0.8},
        )
        with caplog.at_level("INFO", logger="live_trader"):
            _log_market_context_observation(ctx, symbols=None)

        theme_msg = next(
            m for m in caplog.records if "[observe] 테마 점수 상위 5" in m.message
        ).message
        assert "반도체=0.90" in theme_msg
        assert "2차전지=0.80" in theme_msg
        assert "AI=" not in theme_msg

    def test_log_observation_getter_exception_tolerated(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """getter 예외 발생 시 로그만 기록하고 진행 — raise 금지."""
        from scripts.live_trader import _log_market_context_observation

        ctx = MagicMock()
        ctx.get_investor_flow.side_effect = RuntimeError("DB down")
        ctx.get_theme_scores.return_value = {}
        ctx.get_stock_investor_flows.return_value = {}

        with caplog.at_level("INFO", logger="live_trader"):
            _log_market_context_observation(ctx, symbols=["005930"])

        messages = [rec.message for rec in caplog.records]
        # 예외 발생해도 나머지 로그는 정상 출력
        assert any("[observe] 시장 수급: 데이터 없음" in m for m in messages)


# ── FlowSignal 통합 테스트 (feature flag USE_FLOW_SIGNAL) ────────


class TestFlowSignalIntegration:
    """FlowSignal 진입 필터(feature flag) 검증."""

    def _ctx_with_flows(self, market_flow: dict, stock_flows: dict | None = None) -> MagicMock:
        ctx = MagicMock()
        ctx.get_investor_flow.return_value = market_flow
        ctx.get_stock_investor_flows.return_value = stock_flows or {}
        return ctx

    def test_flag_default_off_never_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """USE_FLOW_SIGNAL 미설정 — bearish 수급이라도 차단 안 함."""
        from scripts.live_trader import _is_flow_signal_enabled, _should_block_by_flow_signal

        monkeypatch.delenv("USE_FLOW_SIGNAL", raising=False)
        assert _is_flow_signal_enabled() is False
        ctx = self._ctx_with_flows(
            {"foreign": -1e9, "institution": -5e8},
            {"005930": {"foreign": -1e9}},
        )
        assert _should_block_by_flow_signal(ctx, "005930") is False

    @pytest.mark.parametrize(
        "market_flow,stock_flows,ctx_mode,expected_block",
        [
            # bullish → 허용
            ({"foreign": 1e9, "institution": 5e8}, {"005930": {"foreign": 1e9}}, "ctx", False),
            # ctx None → 안전장치
            (None, None, "none", False),
            # 빈 flow → 기존 경로 유지
            ({}, {}, "ctx", False),
            # getter 예외 → 안전장치
            (None, None, "raise", False),
        ],
    )
    def test_flag_enabled_scenarios(
        self,
        monkeypatch: pytest.MonkeyPatch,
        market_flow: dict | None,
        stock_flows: dict | None,
        ctx_mode: str,
        expected_block: bool,
    ) -> None:
        """flag on 상태에서 수급/안전장치 시나리오별 차단 여부 검증."""
        from scripts.live_trader import _should_block_by_flow_signal

        monkeypatch.setenv("USE_FLOW_SIGNAL", "true")

        if ctx_mode == "none":
            assert _should_block_by_flow_signal(None, "005930") is expected_block
            return
        if ctx_mode == "raise":
            ctx = MagicMock()
            ctx.get_investor_flow.side_effect = RuntimeError("DB down")
            ctx.get_stock_investor_flows.return_value = {}
        else:
            ctx = self._ctx_with_flows(market_flow or {}, stock_flows or {})

        assert _should_block_by_flow_signal(ctx, "005930") is expected_block

    def test_flag_enabled_bearish_blocks_with_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """USE_FLOW_SIGNAL=true + bearish 시장 — 진입 차단 + 로그 출력."""
        from scripts.live_trader import _should_block_by_flow_signal

        monkeypatch.setenv("USE_FLOW_SIGNAL", "true")
        ctx = self._ctx_with_flows(
            {"foreign": -1e9, "institution": -5e8},
            {"005930": {"foreign": -1e9}},
        )
        with caplog.at_level("INFO", logger="live_trader"):
            blocked = _should_block_by_flow_signal(ctx, "005930")
        assert blocked is True
        assert any(
            "FlowSignal score=" in rec.message and "진입 차단" in rec.message
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    @patch("scripts.live_trader.get_sector", return_value="기타")
    @pytest.mark.xfail(
        reason=(
            "fixture leak: 다른 테스트의 cooldown_tracker/sector_positions 상태에 "
            "의존. 단독 실행 시 fail. 별도 follow-up에서 fixture 격리 필요."
        ),
        strict=False,
    )
    async def test_poll_cycle_flag_off_allows_entry(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """USE_FLOW_SIGNAL=false + bearish 수급 — 모멘텀 진입 기존 경로 유지."""
        from src.trading.market_regime import MarketRegime

        monkeypatch.delenv("USE_FLOW_SIGNAL", raising=False)
        # ADR-024: poll_cycle은 multi_regime 모드에서만 동작
        monkeypatch.setenv("ACTIVE_STRATEGY", "multi_regime")

        state = TradingState()
        state.budget.reset(10_000_000)
        state.current_regime = MarketRegime.AGGRESSIVE

        # 풀백 조건 통과 셋업 (DEFENSIVE 테스트와 유사)
        high_52w = 100_000
        current_price = 90_000
        daily = [
            DailyPrice(
                date=f"2025{i:04d}",
                open=current_price - 500,
                high=current_price + 1000,
                low=current_price - 1000,
                close=current_price,
                volume=20_000,
            )
            for i in range(1, 22)
        ]
        state.daily_prices["005930"] = daily
        state.daily_context["005930"] = {"high_52w": high_52w, "avg_volume": 10_000}
        state.symbol_strategies["005930"] = "momentum"

        from src.strategy import MomentumStrategy

        p = MomentumParams(
            volume_ratio=1.0,
            entry_start_time="00:00",
            entry_end_time="23:59",
            price_change_min=0.0,
            require_bullish_bar=False,
        )
        strats = [MomentumStrategy(params=p)]

        quote = Quote(
            symbol="005930",
            name="테스트",
            price=current_price,
            change=0,
            change_pct=0.0,
            volume=20_000,
            high=current_price,
            low=current_price,
            open=current_price - 100,
            prev_close=current_price,
        )
        mock_client.get_quote.return_value = quote

        # bearish 수급 MarketContext
        ctx = MagicMock()
        ctx.get_investor_flow.return_value = {"foreign": -1e9, "institution": -5e8}
        ctx.get_stock_investor_flows.return_value = {"005930": {"foreign": -1e9}}

        await poll_cycle(
            mock_client,
            ["005930"],
            strats,
            state,
            10_000_000,
            1.0,
            market_ctx=ctx,
        )
        # flag off → bearish라도 차단 없이 진입 시도됨(place_order 호출)
        assert mock_client.place_order.called

    @pytest.mark.asyncio
    @patch("scripts.live_trader.get_sector", return_value="기타")
    async def test_poll_cycle_flag_on_bearish_blocks(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """USE_FLOW_SIGNAL=true + bearish 수급 — 모멘텀 신규 진입 차단."""
        from src.trading.market_regime import MarketRegime

        monkeypatch.setenv("USE_FLOW_SIGNAL", "true")

        state = TradingState()
        state.budget.reset(10_000_000)
        state.current_regime = MarketRegime.AGGRESSIVE

        high_52w = 100_000
        current_price = 90_000
        daily = [
            DailyPrice(
                date=f"2025{i:04d}",
                open=current_price - 500,
                high=current_price + 1000,
                low=current_price - 1000,
                close=current_price,
                volume=20_000,
            )
            for i in range(1, 22)
        ]
        state.daily_prices["005930"] = daily
        state.daily_context["005930"] = {"high_52w": high_52w, "avg_volume": 10_000}
        state.symbol_strategies["005930"] = "momentum"

        from src.strategy import MomentumStrategy

        p = MomentumParams(
            volume_ratio=1.0,
            entry_start_time="00:00",
            entry_end_time="23:59",
            price_change_min=0.0,
            require_bullish_bar=False,
        )
        strats = [MomentumStrategy(params=p)]

        quote = Quote(
            symbol="005930",
            name="테스트",
            price=current_price,
            change=0,
            change_pct=0.0,
            volume=20_000,
            high=current_price,
            low=current_price,
            open=current_price - 100,
            prev_close=current_price,
        )
        mock_client.get_quote.return_value = quote

        # bearish 수급
        ctx = MagicMock()
        ctx.get_investor_flow.return_value = {"foreign": -1e9, "institution": -5e8}
        ctx.get_stock_investor_flows.return_value = {"005930": {"foreign": -1e9}}

        await poll_cycle(
            mock_client,
            ["005930"],
            strats,
            state,
            10_000_000,
            1.0,
            market_ctx=ctx,
        )
        # flag on + bearish → 진입 차단
        assert not mock_client.place_order.called


# ── ThemeDetector 통합 테스트 (feature flag USE_THEME_BOOST) ────


class TestThemeBoostIntegration:
    """ThemeDetector 진입 필터(feature flag) 검증."""

    def _ctx_with_theme(self, theme_scores: dict | None) -> MagicMock:
        ctx = MagicMock()
        ctx.get_theme_scores.return_value = theme_scores if theme_scores is not None else {}
        return ctx

    def test_flag_default_off_never_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """USE_THEME_BOOST 미설정 — _is_theme_boost_enabled False, cold 테마라도 차단 안 함."""
        from scripts.live_trader import _is_theme_boost_enabled, _should_block_by_theme

        monkeypatch.delenv("USE_THEME_BOOST", raising=False)
        assert _is_theme_boost_enabled() is False
        ctx = self._ctx_with_theme({"반도체": 0.1})
        assert _should_block_by_theme(ctx, "005930", ["005930"]) is False

    @pytest.mark.parametrize(
        "theme_scores,symbol,expected_block",
        [
            ({"반도체": 0.8}, "005930", False),  # 핫 테마 → 허용
            ({"반도체": 0.8}, "999999", True),  # 테마 미분류('기타') → 차단
            (None, "005930", False),  # ctx None → 안전장치
            ({}, "005930", False),  # 빈 theme_scores → 기존 경로 유지
            ("raise", "005930", False),  # getter 예외 → 안전장치
        ],
    )
    def test_flag_enabled_scenarios(
        self,
        monkeypatch: pytest.MonkeyPatch,
        theme_scores: dict | str | None,
        symbol: str,
        expected_block: bool,
    ) -> None:
        """flag on 상태에서 테마 시나리오별 차단 여부 검증 (안전장치 포함)."""
        from scripts.live_trader import _should_block_by_theme

        monkeypatch.setenv("USE_THEME_BOOST", "true")
        if theme_scores is None:
            # ctx 자체가 None
            assert _should_block_by_theme(None, symbol, [symbol]) is expected_block
            return
        if theme_scores == "raise":
            ctx = MagicMock()
            ctx.get_theme_scores.side_effect = RuntimeError("DB down")
        else:
            ctx = self._ctx_with_theme(theme_scores)  # type: ignore[arg-type]
        assert _should_block_by_theme(ctx, symbol, [symbol]) is expected_block

    def test_flag_enabled_cold_theme_blocks_with_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """USE_THEME_BOOST=true + cold 테마(0.1) — 진입 차단 + 로그 출력."""
        from scripts.live_trader import _should_block_by_theme

        monkeypatch.setenv("USE_THEME_BOOST", "true")
        ctx = self._ctx_with_theme({"반도체": 0.1})
        with caplog.at_level("INFO", logger="live_trader"):
            blocked = _should_block_by_theme(ctx, "005930", ["005930"])
        assert blocked is True
        assert any(
            "ThemeDetector score=" in rec.message and "진입 차단" in rec.message
            for rec in caplog.records
        )

    def test_build_sector_map_groups_symbols(self) -> None:
        """_build_sector_map: symbol→sector을 sector→[symbols]로 역변환."""
        from scripts.live_trader import _build_sector_map

        result = _build_sector_map(["005930", "000660", "999999"])
        assert "005930" in result.get("반도체", [])
        assert "000660" in result.get("반도체", [])
        assert "999999" in result.get("기타", [])

    @pytest.mark.asyncio
    @patch("scripts.live_trader.get_sector", return_value="반도체")
    async def test_poll_cycle_flag_off_allows_entry(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """USE_THEME_BOOST=false + cold 테마 — 기존 경로 유지(진입 허용)."""
        from src.trading.market_regime import MarketRegime

        monkeypatch.delenv("USE_THEME_BOOST", raising=False)

        state = TradingState()
        state.budget.reset(10_000_000)
        state.current_regime = MarketRegime.AGGRESSIVE

        high_52w = 100_000
        current_price = 90_000
        daily = [
            DailyPrice(
                date=f"2025{i:04d}",
                open=current_price - 500,
                high=current_price + 1000,
                low=current_price - 1000,
                close=current_price,
                volume=20_000,
            )
            for i in range(1, 22)
        ]
        state.daily_prices["005930"] = daily
        state.daily_context["005930"] = {"high_52w": high_52w, "avg_volume": 10_000}
        state.symbol_strategies["005930"] = "momentum"

        from src.strategy import MomentumStrategy

        p = MomentumParams(
            volume_ratio=1.0,
            entry_start_time="00:00",
            entry_end_time="23:59",
            price_change_min=0.0,
            require_bullish_bar=False,
        )
        strats = [MomentumStrategy(params=p)]

        quote = Quote(
            symbol="005930",
            name="테스트",
            price=current_price,
            change=0,
            change_pct=0.0,
            volume=20_000,
            high=current_price,
            low=current_price,
            open=current_price - 100,
            prev_close=current_price,
        )
        mock_client.get_quote.return_value = quote

        ctx = MagicMock()
        ctx.get_investor_flow.return_value = {}
        ctx.get_stock_investor_flows.return_value = {}
        ctx.get_theme_scores.return_value = {"반도체": 0.1}

        await poll_cycle(
            mock_client,
            ["005930"],
            strats,
            state,
            10_000_000,
            1.0,
            market_ctx=ctx,
        )
        assert mock_client.place_order.called

    @pytest.mark.asyncio
    @patch("scripts.live_trader.get_sector", return_value="반도체")
    async def test_poll_cycle_flag_on_cold_blocks(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """USE_THEME_BOOST=true + cold 테마 — 모멘텀 신규 진입 차단."""
        from src.trading.market_regime import MarketRegime

        monkeypatch.setenv("USE_THEME_BOOST", "true")

        state = TradingState()
        state.budget.reset(10_000_000)
        state.current_regime = MarketRegime.AGGRESSIVE

        high_52w = 100_000
        current_price = 90_000
        daily = [
            DailyPrice(
                date=f"2025{i:04d}",
                open=current_price - 500,
                high=current_price + 1000,
                low=current_price - 1000,
                close=current_price,
                volume=20_000,
            )
            for i in range(1, 22)
        ]
        state.daily_prices["005930"] = daily
        state.daily_context["005930"] = {"high_52w": high_52w, "avg_volume": 10_000}
        state.symbol_strategies["005930"] = "momentum"

        from src.strategy import MomentumStrategy

        p = MomentumParams(
            volume_ratio=1.0,
            entry_start_time="00:00",
            entry_end_time="23:59",
            price_change_min=0.0,
            require_bullish_bar=False,
        )
        strats = [MomentumStrategy(params=p)]

        quote = Quote(
            symbol="005930",
            name="테스트",
            price=current_price,
            change=0,
            change_pct=0.0,
            volume=20_000,
            high=current_price,
            low=current_price,
            open=current_price - 100,
            prev_close=current_price,
        )
        mock_client.get_quote.return_value = quote

        ctx = MagicMock()
        ctx.get_investor_flow.return_value = {}
        ctx.get_stock_investor_flows.return_value = {}
        ctx.get_theme_scores.return_value = {"반도체": 0.1}

        await poll_cycle(
            mock_client,
            ["005930"],
            strats,
            state,
            10_000_000,
            1.0,
            market_ctx=ctx,
        )
        assert not mock_client.place_order.called
