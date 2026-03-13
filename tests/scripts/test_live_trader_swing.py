# ruff: noqa: DTZ005
"""스윙 인프라 테스트 — overnight 포지션 저장/복원, 갭 리스크, 보유 기간 제한."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from scripts.live_trader import (
    MAX_HOLDING_DAYS,
    LivePosition,
    TradingState,
    _count_business_days,
    check_gap_risk,
    check_holding_limit,
    force_close_all,
    load_overnight_positions,
    save_overnight_positions,
)

# ── 헬퍼 ──────────────────────────────────────────────


def _make_position(
    symbol: str = "005930",
    name: str = "삼성전자",
    entry_price: int = 70000,
    quantity: int = 10,
    strategy: str = "momentum",
    entry_date: str = "2026-03-10",
) -> LivePosition:
    """LivePosition 간편 생성."""
    return LivePosition(
        symbol=symbol,
        name=name,
        entry_price=entry_price,
        quantity=quantity,
        entry_time="093000",
        order_no="ORD001",
        strategy=strategy,
        entry_date=entry_date,
    )


def _make_state(positions: dict[str, LivePosition] | None = None) -> TradingState:
    """TradingState 간편 생성."""
    state = TradingState()
    if positions:
        state.positions = positions
    return state


# ── save_overnight_positions ──────────────────────────


class TestSaveOvernightPositions:
    """overnight 포지션 JSON 저장 테스트."""

    def test_save_overnight_positions(self, tmp_path: object) -> None:
        """포지션 → JSON 저장, 파일 내용 검증."""
        path = str(tmp_path / "overnight.json")  # type: ignore[operator]
        pos = _make_position(strategy="mean_reversion")
        state = _make_state({"005930": pos})

        save_overnight_positions(state, path=path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["symbol"] == "005930"
        assert data[0]["name"] == "삼성전자"
        assert data[0]["entry_price"] == 70000
        assert data[0]["quantity"] == 10
        assert data[0]["strategy"] == "mean_reversion"
        assert data[0]["entry_date"] == "2026-03-10"

    def test_save_overnight_positions_empty(self, tmp_path: object) -> None:
        """빈 포지션 시 빈 리스트 저장."""
        path = str(tmp_path / "overnight.json")  # type: ignore[operator]
        state = _make_state()

        save_overnight_positions(state, path=path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert data == []


# ── load_overnight_positions ──────────────────────────


class TestLoadOvernightPositions:
    """overnight 포지션 JSON 복원 테스트."""

    def test_load_overnight_positions(self, tmp_path: object) -> None:
        """JSON → LivePosition 복원, 필드 일치 검증."""
        path = str(tmp_path / "overnight.json")  # type: ignore[operator]
        data = [
            {
                "symbol": "005930",
                "name": "삼성전자",
                "entry_price": 70000,
                "quantity": 10,
                "entry_time": "093000",
                "order_no": "ORD001",
                "strategy": "mean_reversion",
                "high_since_entry": 72000,
                "dynamic_stop": -0.024,
                "dynamic_tp": 0.048,
                "entry_date": "2026-03-10",
            }
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        positions = load_overnight_positions(path=path)

        assert len(positions) == 1
        pos = positions[0]
        assert pos.symbol == "005930"
        assert pos.name == "삼성전자"
        assert pos.entry_price == 70000
        assert pos.quantity == 10
        assert pos.strategy == "mean_reversion"
        assert pos.high_since_entry == 72000
        assert pos.dynamic_stop == pytest.approx(-0.024)
        assert pos.dynamic_tp == pytest.approx(0.048)
        assert pos.entry_date == "2026-03-10"

    def test_load_overnight_positions_no_file(self, tmp_path: object) -> None:
        """파일 없을 때 빈 리스트 반환."""
        path = str(tmp_path / "no_such_file.json")  # type: ignore[operator]
        positions = load_overnight_positions(path=path)
        assert positions == []

    def test_load_overnight_positions_backup(self, tmp_path: object) -> None:
        """로드 후 .bak rename 확인."""
        path = str(tmp_path / "overnight.json")  # type: ignore[operator]
        bak_path = path + ".bak"
        data = [
            {
                "symbol": "005930",
                "name": "삼성전자",
                "entry_price": 70000,
                "quantity": 10,
                "entry_time": "093000",
                "order_no": "ORD001",
            }
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        load_overnight_positions(path=path)

        import os

        assert not os.path.exists(path)
        assert os.path.exists(bak_path)


# ── check_gap_risk ────────────────────────────────────


class TestCheckGapRisk:
    """갭 하락 리스크 체크 테스트."""

    @pytest.mark.asyncio
    async def test_gap_risk_triggers_sell(self) -> None:
        """-3% 이하 갭다운 시 손절 실행."""
        pos = _make_position(
            entry_price=10000,
            strategy="mean_reversion",
            entry_date="2026-03-10",
        )
        state = _make_state({"005930": pos})

        broker = AsyncMock()
        # 현재가 9600 → 갭 -4% (< -3% threshold)
        broker.get_quote.return_value = AsyncMock(price=9600)

        with patch("scripts.live_trader.execute_sell", new_callable=AsyncMock) as mock_sell:
            closed = await check_gap_risk(state, broker)

        assert "005930" in closed
        mock_sell.assert_called_once()
        call_args = mock_sell.call_args
        assert call_args[0][2] == 9600  # price
        assert call_args[0][3] == "gap_risk"  # reason

    @pytest.mark.asyncio
    async def test_gap_risk_normal(self) -> None:
        """정상 범위 시 포지션 유지."""
        pos = _make_position(
            entry_price=10000,
            strategy="mean_reversion",
            entry_date="2026-03-10",
        )
        state = _make_state({"005930": pos})

        broker = AsyncMock()
        # 현재가 9800 → 갭 -2% (> -3% threshold, 정상)
        broker.get_quote.return_value = AsyncMock(price=9800)

        with patch("scripts.live_trader.execute_sell", new_callable=AsyncMock) as mock_sell:
            closed = await check_gap_risk(state, broker)

        assert closed == []
        mock_sell.assert_not_called()


# ── check_holding_limit ───────────────────────────────


class TestCheckHoldingLimit:
    """보유 기간 초과 청산 테스트."""

    @pytest.mark.asyncio
    async def test_holding_limit_exceeded(self) -> None:
        """5거래일 초과 시 청산."""
        # 오늘로부터 8일 전(주말 포함) → 6거래일 > MAX_HOLDING_DAYS(5)
        today = datetime.now()
        # 8 calendar days ago = 6 business days (Mon-Fri)
        entry = today - timedelta(days=10)
        entry_date = entry.strftime("%Y-%m-%d")

        # _count_business_days가 > 5 되도록 보장
        bdays = _count_business_days(entry_date, today.strftime("%Y-%m-%d"))
        if bdays <= MAX_HOLDING_DAYS:
            # 충분히 과거로 설정
            entry = today - timedelta(days=14)
            entry_date = entry.strftime("%Y-%m-%d")

        pos = _make_position(
            entry_price=10000,
            strategy="mean_reversion",
            entry_date=entry_date,
        )
        state = _make_state({"005930": pos})

        broker = AsyncMock()
        broker.get_quote.return_value = AsyncMock(price=9500)

        with patch("scripts.live_trader.execute_sell", new_callable=AsyncMock) as mock_sell:
            closed = await check_holding_limit(state, broker)

        assert "005930" in closed
        mock_sell.assert_called_once()

    @pytest.mark.asyncio
    async def test_holding_limit_within(self) -> None:
        """5거래일 이내 유지."""
        # 어제 진입 → 1거래일 ≤ 5
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        # 주말이면 금요일로 조정
        while yesterday.weekday() >= 5:
            yesterday -= timedelta(days=1)
        entry_date = yesterday.strftime("%Y-%m-%d")

        pos = _make_position(
            entry_price=10000,
            strategy="mean_reversion",
            entry_date=entry_date,
        )
        state = _make_state({"005930": pos})

        broker = AsyncMock()
        broker.get_quote.return_value = AsyncMock(price=10200)

        with patch("scripts.live_trader.execute_sell", new_callable=AsyncMock) as mock_sell:
            closed = await check_holding_limit(state, broker)

        assert closed == []
        mock_sell.assert_not_called()


# ── force_close_all ───────────────────────────────────


class TestForceCloseAll:
    """force_close_all 스윙 포지션 제외 테스트."""

    @pytest.mark.asyncio
    async def test_force_close_all_skips_swing(self) -> None:
        """force_all=False 시 swing(mean_reversion) 포지션 제외, momentum만 청산."""
        momentum_pos = _make_position(symbol="005930", strategy="momentum")
        swing_pos = _make_position(symbol="000660", strategy="mean_reversion")
        state = _make_state({"005930": momentum_pos, "000660": swing_pos})

        broker = AsyncMock()
        broker.get_quote.return_value = AsyncMock(price=70000)

        with patch("scripts.live_trader.execute_sell", new_callable=AsyncMock) as mock_sell:
            await force_close_all(broker, state, force_all=False)

        # momentum만 청산, mean_reversion은 유지
        assert mock_sell.call_count == 1
        sold_pos = mock_sell.call_args[0][1]
        assert sold_pos.strategy == "momentum"
        assert sold_pos.symbol == "005930"

    @pytest.mark.asyncio
    async def test_force_close_killswitch_includes_swing(self) -> None:
        """force_all=True(kill_switch) 시 스윙 포함 전량 청산."""
        momentum_pos = _make_position(symbol="005930", strategy="momentum")
        swing_pos = _make_position(symbol="000660", strategy="mean_reversion")
        state = _make_state({"005930": momentum_pos, "000660": swing_pos})

        broker = AsyncMock()
        broker.get_quote.return_value = AsyncMock(price=70000)

        with patch("scripts.live_trader.execute_sell", new_callable=AsyncMock) as mock_sell:
            await force_close_all(broker, state, force_all=True)

        # 전량 청산: momentum + mean_reversion 모두
        assert mock_sell.call_count == 2
        sold_symbols = {call.args[1].symbol for call in mock_sell.call_args_list}
        assert sold_symbols == {"005930", "000660"}

    @pytest.mark.asyncio
    async def test_momentum_still_force_closed(self) -> None:
        """모멘텀 포지션은 15:15 강제청산(force_all=False)에서 청산."""
        pos = _make_position(symbol="005930", strategy="momentum")
        state = _make_state({"005930": pos})

        broker = AsyncMock()
        broker.get_quote.return_value = AsyncMock(price=70000)

        with patch("scripts.live_trader.execute_sell", new_callable=AsyncMock) as mock_sell:
            await force_close_all(broker, state, force_all=False)

        mock_sell.assert_called_once()
        assert mock_sell.call_args[0][1].strategy == "momentum"


# ── LivePosition entry_date ───────────────────────────


class TestLivePositionEntryDate:
    """LivePosition entry_date 필드 테스트."""

    def test_entry_date_default(self) -> None:
        """LivePosition 생성 시 entry_date 미지정이면 빈 문자열."""
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=70000,
            quantity=10,
            entry_time="093000",
            order_no="ORD001",
        )
        assert pos.entry_date == ""

    def test_entry_date_set(self) -> None:
        """entry_date를 명시적으로 설정하면 해당 값 유지."""
        today = datetime.now().strftime("%Y-%m-%d")
        pos = LivePosition(
            symbol="005930",
            name="삼성전자",
            entry_price=70000,
            quantity=10,
            entry_time="093000",
            order_no="ORD001",
            entry_date=today,
        )
        assert pos.entry_date == today
