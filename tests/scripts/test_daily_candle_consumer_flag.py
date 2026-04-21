"""Design 011 PR 4: USE_DB_DAILY_CANDLES flag 분기 테스트.

- flag off (기본) → 기존 키움 경로
- flag on → DailyCandleStore.get_daily_context/get_daily_prices 위임
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from scripts.live_trader import load_daily_context as lt_load_daily_context
from scripts.screen_symbols import fetch_daily_pages
from src.broker.schemas import DailyPrice


def _bar(date_str: str, high: int = 71000, volume: int = 1_000_000) -> DailyPrice:
    return DailyPrice(
        date=date_str,
        open=70000,
        high=high,
        low=69000,
        close=70500,
        volume=volume,
    )


class TestLiveTraderLoadDailyContextFlag:
    """scripts.live_trader.load_daily_context 경로 분기."""

    async def test_flag_off_uses_kiwoom_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag off 시 DailyCandleStore 미사용 (기존 키움 경로)."""
        monkeypatch.delenv("USE_DB_DAILY_CANDLES", raising=False)

        mock_client = AsyncMock()
        # 키움 ka10086 응답: 1페이지에 최소한의 bar 1개 → 두번째 페이지 비어 break
        mock_client._request.side_effect = [
            {
                "daly_stkpc": [
                    {
                        "date": "20260421",
                        "open_pric": 70000,
                        "high_pric": 71000,
                        "low_pric": 69000,
                        "close_pric": 70500,
                        "trde_qty": 1_000_000,
                    }
                ]
            },
            {"daly_stkpc": []},
        ]

        with patch("src.trading.daily_candle_store.DailyCandleStore") as store_cls:
            prices, ctx = await lt_load_daily_context(mock_client, ["005930"])

        store_cls.assert_not_called()
        assert "005930" in prices
        assert ctx["005930"]["high_52w"] == 71000

    async def test_flag_on_uses_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag on 시 DailyCandleStore.get_daily_context로 위임."""
        monkeypatch.setenv("USE_DB_DAILY_CANDLES", "true")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test/db")

        fake_prices = {"005930": [_bar("20260420"), _bar("20260421", high=72000)]}
        fake_ctx = {"005930": {"high_52w": 72000, "avg_volume": 1_500_000}}

        with patch("src.trading.daily_candle_store.DailyCandleStore") as store_cls:
            store_instance = store_cls.return_value
            store_instance.get_daily_context = AsyncMock(return_value=(fake_prices, fake_ctx))
            prices, ctx = await lt_load_daily_context(AsyncMock(), ["005930"])

        store_cls.assert_called_once()
        _, kwargs = store_cls.call_args
        assert kwargs.get("use_db") is True
        assert prices == fake_prices
        assert ctx == fake_ctx


class TestScreenSymbolsFetchDailyPagesFlag:
    """scripts.screen_symbols.fetch_daily_pages 경로 분기."""

    async def test_flag_off_uses_kiwoom_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag off 시 DailyCandleStore 미사용."""
        monkeypatch.delenv("USE_DB_DAILY_CANDLES", raising=False)
        mock_client = AsyncMock()
        mock_client._request.side_effect = [
            {
                "daly_stkpc": [
                    {
                        "date": "20260421",
                        "open_pric": 70000,
                        "high_pric": 71000,
                        "low_pric": 69000,
                        "close_pric": 70500,
                        "trde_qty": 1_000_000,
                    }
                ]
            },
            {"daly_stkpc": []},
        ]

        with patch("src.trading.daily_candle_store.DailyCandleStore") as store_cls:
            bars = await fetch_daily_pages(mock_client, "005930", max_pages=2)

        store_cls.assert_not_called()
        assert len(bars) == 1

    async def test_flag_on_uses_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag on 시 DailyCandleStore.get_daily_prices로 위임."""
        monkeypatch.setenv("USE_DB_DAILY_CANDLES", "true")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test/db")

        fake_bars = [_bar("20260420"), _bar("20260421", high=72000)]

        with patch("src.trading.daily_candle_store.DailyCandleStore") as store_cls:
            store_instance = store_cls.return_value
            store_instance.get_daily_prices = AsyncMock(return_value=fake_bars)
            bars = await fetch_daily_pages(AsyncMock(), "005930", max_pages=13)

        store_cls.assert_called_once()
        _, kwargs = store_cls.call_args
        assert kwargs.get("use_db") is True
        assert bars == fake_bars
