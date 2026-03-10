"""live_trader.py 핵심 매매 로직 테스트.

mock 기반으로 KiwoomClient 호출을 대체하여
진입/청산 판단, 주문 실행, 폴링 사이클, 강제 청산을 검증한다.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from scripts.live_trader import (
    LivePosition,
    TradingState,
    _safe_int,
    build_strategies,
    execute_buy,
    execute_sell,
    force_close_all,
    load_daily_context,
    now_hhmm,
    poll_cycle,
    save_results,
)
from src.backtest.strategy import MomentumParams
from src.broker.schemas import DailyPrice, OrderResponse, OrderSideEnum, Quote

# ── fixture ─────────────────────────────────────────


@pytest.fixture
def params() -> MomentumParams:
    """기본 전략 파라미터."""
    return MomentumParams()


@pytest.fixture
def state() -> TradingState:
    """빈 트레이딩 상태."""
    return TradingState()


@pytest.fixture
def mock_client() -> AsyncMock:
    """모의 KiwoomClient."""
    client = AsyncMock()
    client.place_order.return_value = OrderResponse(
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

        mock_client.place_order.return_value = OrderResponse(
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
        expected_pnl = (10100 - 10000) / 10000 - (0.00015 * 2 + 0.0018)
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

        mock_client.place_order.return_value = OrderResponse(
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
        expected_pnl = (9950 - 10000) / 10000 - (0.00015 * 2 + 0.0018)
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
        sample_daily: list[DailyPrice],
    ) -> None:
        """52주 고가 대비 미달 시 매수 안 함."""
        mock_client.get_quote.return_value = sample_quote
        # 현재가 70000, high_52w 100000 → 70% < 80% threshold
        state.daily_context["005930"] = {"high_52w": 100000, "avg_volume": 10000}
        state.daily_prices["005930"] = sample_daily

        strategies = build_strategies("momentum", params)
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

        mock_client.place_order.return_value = OrderResponse(
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

    @patch("scripts.live_trader.now_hhmm", return_value="1430")
    async def test_force_close_at_1430(
        self,
        _mock_hhmm: AsyncMock,
        mock_client: AsyncMock,
        params: MomentumParams,
        state: TradingState,
        sample_daily: list[DailyPrice],
    ) -> None:
        """14:30 시각에 보유 포지션 강제 청산."""
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

        mock_client.place_order.return_value = OrderResponse(
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
        mock_client.place_order.return_value = OrderResponse(
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
        mock_client.place_order.return_value = OrderResponse(
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
