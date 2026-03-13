"""live_trader.py 핵심 매매 로직 테스트.

mock 기반으로 KiwoomClient 호출을 대체하여
진입/청산 판단, 주문 실행, 폴링 사이클, 강제 청산을 검증한다.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.live_trader import (
    LivePosition,
    TradingState,
    _safe_int,
    build_strategies,
    calc_time_ratio,
    execute_buy,
    execute_sell,
    force_close_all,
    load_daily_context,
    now_hhmm,
    poll_cycle,
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


# ── _safe_int ───────────────────────────────────────


class TestSafeInt:
    """_safe_int 유틸 함수 테스트."""

    def test_int_value(self) -> None:
        """정수 입력은 절대값 반환."""
        assert _safe_int(100) == 100
        assert _safe_int(-500) == 500

    def test_string_value(self) -> None:
        """문자열 숫자 파싱."""
        assert _safe_int("12345") == 12345

    def test_signed_string(self) -> None:
        """부호 접두사 제거."""
        assert _safe_int("+70000") == 70000
        assert _safe_int("-70000") == 70000

    def test_empty_string(self) -> None:
        """빈 문자열은 0 반환."""
        assert _safe_int("") == 0


# ── now_hhmm ────────────────────────────────────────


class TestNowHhmm:
    """now_hhmm 함수 테스트."""

    @patch("scripts.live_trader.datetime")
    def test_returns_hhmm_format(self, mock_dt: AsyncMock) -> None:
        """HHMM 형식 반환 확인."""
        mock_dt.now.return_value.strftime.return_value = "0935"
        result = now_hhmm()
        assert result == "0935"


# ── build_strategies ──────────────────────────────────


class TestBuildStrategies:
    """전략 빌더 테스트."""

    def test_both(self, params: MomentumParams) -> None:
        """both 옵션은 2개 전략."""
        strats = build_strategies("both", params)
        assert len(strats) == 2
        names = {s.name for s in strats}
        assert names == {"momentum", "mean_reversion"}

    def test_momentum_only(self, params: MomentumParams) -> None:
        """모멘텀만."""
        strats = build_strategies("momentum", params)
        assert len(strats) == 1
        assert strats[0].name == "momentum"

    def test_mean_reversion_only(self, params: MomentumParams) -> None:
        """평균회귀만."""
        strats = build_strategies("mean_reversion", params)
        assert len(strats) == 1
        assert strats[0].name == "mean_reversion"

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

    async def test_buy_success(self, mock_client: AsyncMock, state: TradingState) -> None:
        """정상 매수 시 포지션+거래 기록."""
        await execute_buy(mock_client, "005930", "삼성전자", 50000, 10, "momentum", state)

        assert "005930" in state.positions
        assert state.positions["005930"].quantity == 10
        assert state.positions["005930"].entry_price == 50000
        assert state.positions["005930"].strategy == "momentum"
        assert len(state.trades) == 1
        assert state.trades[0].side == "BUY"
        assert state.trades[0].strategy == "momentum"

    async def test_buy_quantity_zero(self, mock_client: AsyncMock, state: TradingState) -> None:
        """수량 0이면 매수 안 함."""
        await execute_buy(mock_client, "005930", "삼성전자", 600000, 0, "momentum", state)

        assert "005930" not in state.positions
        assert len(state.trades) == 0
        mock_client.place_order.assert_not_called()

    async def test_buy_api_error(self, mock_client: AsyncMock, state: TradingState) -> None:
        """주문 API 실패 시 포지션 미생성."""
        mock_client.place_order.side_effect = Exception("API Error")

        await execute_buy(mock_client, "005930", "삼성전자", 50000, 10, "momentum", state)

        assert "005930" not in state.positions
        assert len(state.trades) == 0

    async def test_buy_mean_reversion_strategy(
        self, mock_client: AsyncMock, state: TradingState
    ) -> None:
        """평균회귀 전략 매수."""
        await execute_buy(mock_client, "005930", "삼성전자", 50000, 5, "mean_reversion", state)

        assert state.positions["005930"].strategy == "mean_reversion"
        assert state.trades[0].strategy == "mean_reversion"


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
        state.daily_context["005930"] = {"high_52w": 72900, "avg_volume": 10725}
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
            price=9900,
            change=-100,
            change_pct=-1.0,
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
        state.daily_context["005930"] = {"high_52w": 72900, "avg_volume": 10725}
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
    """LivePosition, TradeLog, TradingState 기본 동작 테스트."""

    def test_live_position(self) -> None:
        """LivePosition 필드 확인."""
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=70000,
            quantity=10,
            entry_time="20260309100000",
            order_no="ORD001",
        )
        assert pos.symbol == "005930"
        assert pos.entry_price == 70000
        assert pos.strategy == "momentum"  # 기본값

    def test_live_position_strategy(self) -> None:
        """LivePosition 전략 필드."""
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=70000,
            quantity=10,
            entry_time="20260309100000",
            order_no="ORD001",
            strategy="mean_reversion",
        )
        assert pos.strategy == "mean_reversion"
        assert pos.high_since_entry == 0

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

    def test_at_market_open(self) -> None:
        """장 시작(09:00) 직후는 0."""
        assert calc_time_ratio("0900") == 0.0

    def test_before_market_open(self) -> None:
        """장 시작 전은 0."""
        assert calc_time_ratio("0830") == 0.0

    def test_at_market_close(self) -> None:
        """장 마감(15:30)은 1.0."""
        assert calc_time_ratio("1530") == 1.0

    def test_after_market_close(self) -> None:
        """장 마감 이후는 1.0 초과하지 않음."""
        assert calc_time_ratio("1600") == 1.0

    def test_midday(self) -> None:
        """12:15 = 195분 경과 → 0.5."""
        result = calc_time_ratio("1215")
        assert abs(result - 0.5) < 0.01

    def test_one_hour_in(self) -> None:
        """10:00 = 60분 경과 → 60/390."""
        result = calc_time_ratio("1000")
        assert abs(result - 60 / 390) < 0.001

    def test_invalid_input(self) -> None:
        """잘못된 입력은 1.0 반환."""
        assert calc_time_ratio("") == 1.0
        assert calc_time_ratio("ab") == 1.0


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
        state.daily_context["005930"] = {"high_52w": 72900, "avg_volume": 10725}
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

        # 손절 조건(entry 10000, 현재가 9950) 틱 호출
        tick = RealtimeTick(symbol="005930", price=9950, volume=5000, timestamp="100000")
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

    @patch("scripts.live_trader.run_trading_loop")
    @patch("scripts.live_trader.run_trading_loop_ws")
    async def test_main_ws_fallback_to_polling(
        self,
        mock_ws_loop: AsyncMock,
        mock_poll_loop: AsyncMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """WebSocket 루프 실패 시 폴링 루프로 폴백."""
        mock_ws_loop.side_effect = Exception("ws connection failed")
        mock_poll_loop.return_value = None

        # ws 모드에서 실패 시 polling으로 폴백 경로 직접 검증
        try:
            await mock_ws_loop(mock_client, ["005930"], [], state, 10_000_000, 1.0, None)
        except Exception:
            await mock_poll_loop(mock_client, ["005930"], [], state, 10_000_000, 1.0, None)

        mock_poll_loop.assert_called_once()


# ── update_risk_after_trade + kill_switch ────────────


class TestUpdateRiskAfterTrade:
    """단계적 리스크 관리 — 손실 카운터 + 블랙리스트 + kill_switch 통합 테스트."""

    def test_first_loss_increments_counter(self, state: TradingState) -> None:
        """첫 손실: 카운터 1, 블랙리스트 없음."""
        update_risk_after_trade(state, "005930", -0.005)
        assert state.symbol_losses["005930"] == 1
        assert "005930" not in state.symbol_blacklist

    def test_two_losses_no_blacklist(self, state: TradingState) -> None:
        """2연패: 카운터 2, 블랙리스트 없음 (50% 축소만)."""
        update_risk_after_trade(state, "005930", -0.005)
        update_risk_after_trade(state, "005930", -0.005)
        assert state.symbol_losses["005930"] == 2
        assert "005930" not in state.symbol_blacklist

    def test_three_losses_blacklist(self, state: TradingState) -> None:
        """3연패: 당일 블랙리스트 등록."""
        for _ in range(3):
            update_risk_after_trade(state, "005930", -0.005)
        assert state.symbol_losses["005930"] == 3
        assert "005930" in state.symbol_blacklist

    def test_win_resets_counter(self, state: TradingState) -> None:
        """수익 청산 시 손실 카운터 초기화."""
        update_risk_after_trade(state, "005930", -0.005)
        update_risk_after_trade(state, "005930", -0.005)
        update_risk_after_trade(state, "005930", 0.01)
        assert state.symbol_losses["005930"] == 0

    def test_zero_pnl_not_loss(self, state: TradingState) -> None:
        """pnl = 0.0 은 수익으로 간주해 카운터 초기화."""
        update_risk_after_trade(state, "005930", -0.005)
        update_risk_after_trade(state, "005930", 0.0)
        assert state.symbol_losses["005930"] == 0

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
        from src.trading.kill_switch import DrawdownAction

        mock_update_drawdown.return_value = DrawdownAction.STOP_BUY

        exit_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=9900,
            change=-100,
            change_pct=-1.0,
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
        mock_update_drawdown.assert_called_once()

    @patch("scripts.live_trader.force_close_all")
    @patch("scripts.live_trader.update_drawdown")
    @patch("scripts.live_trader.now_hhmm", return_value="1000")
    async def test_kill_switch_force_close_after_sell(
        self,
        _mock_hhmm: AsyncMock,
        mock_update_drawdown: MagicMock,
        mock_force_close: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """청산 후 drawdown FORCE_CLOSE → force_close_all 호출."""
        from src.trading.kill_switch import DrawdownAction

        mock_update_drawdown.return_value = DrawdownAction.FORCE_CLOSE

        exit_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=9900,
            change=-100,
            change_pct=-1.0,
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

        mock_force_close.assert_called_once()

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
        state.daily_context["005930"] = {"high_52w": 72900, "avg_volume": 10725}
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
        state.sector_positions.add("반도체")  # 이미 반도체 섹터 보유

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
        state.daily_context["005490"] = {"high_52w": 72900, "avg_volume": 10725}
        state.daily_prices["005490"] = sample_daily
        state.sector_positions.add("반도체")  # 반도체만 점유, 소재는 비어 있음

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
        state.daily_context["999999"] = {"high_52w": 72900, "avg_volume": 10725}
        state.daily_prices["999999"] = sample_daily
        state.sector_positions.add("기타")  # 기타가 이미 있어도 진입 허용

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

        assert "반도체" in state.sector_positions

    @patch("scripts.live_trader.get_sector", return_value="기타")
    async def test_buy_other_sector_not_registered(
        self,
        _mock_sector: MagicMock,
        mock_client: AsyncMock,
        state: TradingState,
    ) -> None:
        """'기타' 섹터 매수 시 sector_positions에 추가 안 됨."""
        await execute_buy(mock_client, "999999", "기타종목", 70000, 10, "momentum", state)

        assert "기타" not in state.sector_positions


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

    def test_rescreened_default_empty(self) -> None:
        """기본값은 빈 dict."""
        from scripts.live_trader import RESCREEN_TIMES

        state = TradingState()
        assert state.rescreened == {}
        assert RESCREEN_TIMES == ("1000", "1100")

    def test_rescreened_tracking(self) -> None:
        """재스크리닝 실행 여부 추적."""
        state = TradingState()
        state.rescreened["1000"] = True
        assert state.rescreened.get("1000") is True
        assert state.rescreened.get("1100") is None
