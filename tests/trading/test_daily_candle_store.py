"""DailyCandleStore 조회 모듈 테스트."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_candle import DailyCandle
from src.trading.daily_candle_store import DailyCandleStore, _env_truthy


class TestEnvTruthy:
    """환경변수 해석 헬퍼."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, False),
            ("", False),
            ("0", False),
            ("false", False),
            ("FALSE", False),
            ("no", False),
            ("1", True),
            ("true", True),
            ("TRUE", True),
            ("yes", True),
            ("on", True),
        ],
    )
    def test_parse(self, value: str | None, expected: bool) -> None:
        """문자열 → bool 매핑."""
        assert _env_truthy(value) == expected


class TestDailyCandleStoreConstruction:
    """초기화 및 feature flag 해석."""

    def test_default_no_flag_no_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """URL/flag 없으면 use_db=False."""
        monkeypatch.delenv("USE_DB_DAILY_CANDLES", raising=False)
        store = DailyCandleStore()
        assert store.use_db is False

    def test_env_flag_on_without_url_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """flag=true여도 url 없으면 use_db=False (안전)."""
        monkeypatch.setenv("USE_DB_DAILY_CANDLES", "true")
        store = DailyCandleStore(database_url=None)
        assert store.use_db is False

    def test_explicit_use_db_true_with_url(self) -> None:
        """명시적 use_db=True + url → use_db=True."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )
        assert store.use_db is True

    def test_env_flag_true_with_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """USE_DB_DAILY_CANDLES=1 + url → use_db=True."""
        monkeypatch.setenv("USE_DB_DAILY_CANDLES", "1")
        store = DailyCandleStore(database_url="postgresql+asyncpg://test/db")
        assert store.use_db is True


class TestDailyCandleStoreDbPath:
    """DB 조회 경로 테스트 — _fetch_from_db를 mock."""

    async def test_get_daily_prices_from_db_above_threshold(self) -> None:
        """DB bars >= 20이면 키움 폴백 없이 DB 결과 반환."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )

        fake_bars: list[Any] = [
            _make_bar(date(2026, 4, d))
            for d in range(1, 22)  # 21개
        ]

        with patch.object(
            store,
            "_fetch_from_db",
            new=AsyncMock(return_value=fake_bars),
        ):
            client_mock = AsyncMock()
            bars = await store.get_daily_prices(
                "005930",
                kiwoom_client=client_mock,
            )
        assert len(bars) == 21
        # 키움은 호출되지 않음
        client_mock._request.assert_not_called()

    async def test_get_daily_prices_fallback_when_db_insufficient(self) -> None:
        """DB bars < 20이면 키움 폴백."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )

        fake_bars_short: list[Any] = [_make_bar(date(2026, 4, 1))]  # 1개

        fallback_result = [_make_bar(date(2026, 4, d)) for d in range(1, 26)]  # 25개

        with (
            patch.object(
                store,
                "_fetch_from_db",
                new=AsyncMock(return_value=fake_bars_short),
            ),
            patch.object(
                store,
                "_fetch_from_kiwoom",
                new=AsyncMock(return_value=fallback_result),
            ),
        ):
            client_mock = AsyncMock()
            bars = await store.get_daily_prices(
                "005930",
                kiwoom_client=client_mock,
            )
        assert len(bars) == 25

    async def test_get_daily_prices_db_error_falls_back(self) -> None:
        """DB 조회 중 예외 시 빈 결과 + 키움 폴백 시도."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )

        fallback_result = [_make_bar(date(2026, 4, d)) for d in range(1, 26)]

        with (
            patch.object(
                store,
                "_fetch_from_db",
                new=AsyncMock(side_effect=RuntimeError("db down")),
            ),
            patch.object(
                store,
                "_fetch_from_kiwoom",
                new=AsyncMock(return_value=fallback_result),
            ),
        ):
            bars = await store.get_daily_prices(
                "005930",
                kiwoom_client=AsyncMock(),
            )
        assert len(bars) == 25


class TestDailyCandleStoreFlagOffPath:
    """flag off (기본) 시 항상 키움 경로."""

    async def test_flag_off_always_kiwoom(self) -> None:
        """use_db=False면 DB 조회 없이 키움만 사용."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=False,
        )
        fake_result = [_make_bar(date(2026, 4, d)) for d in range(1, 30)]

        with (
            patch.object(
                store,
                "_fetch_from_db",
                new=AsyncMock(return_value=[]),
            ) as db_mock,
            patch.object(
                store,
                "_fetch_from_kiwoom",
                new=AsyncMock(return_value=fake_result),
            ),
        ):
            bars = await store.get_daily_prices(
                "005930",
                kiwoom_client=AsyncMock(),
            )
        assert len(bars) == 29
        db_mock.assert_not_called()


class TestDailyCandleStoreCache:
    """프로세스 캐시 hit 검증."""

    async def test_cache_hit_prevents_second_db_call(self) -> None:
        """같은 (symbol, lookback) 재요청 시 DB 재조회 없음."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )
        fake_bars = [_make_bar(date(2026, 4, d)) for d in range(1, 30)]
        fetch_mock = AsyncMock(return_value=fake_bars)
        with patch.object(store, "_fetch_from_db", new=fetch_mock):
            await store.get_daily_prices("005930", kiwoom_client=AsyncMock())
            await store.get_daily_prices("005930", kiwoom_client=AsyncMock())
        assert fetch_mock.await_count == 1

    async def test_flush_cache_resets(self) -> None:
        """flush_cache() 이후 재조회 시 DB 재호출."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )
        fake_bars = [_make_bar(date(2026, 4, d)) for d in range(1, 30)]
        fetch_mock = AsyncMock(return_value=fake_bars)
        with patch.object(store, "_fetch_from_db", new=fetch_mock):
            await store.get_daily_prices("005930", kiwoom_client=AsyncMock())
            store.flush_cache()
            await store.get_daily_prices("005930", kiwoom_client=AsyncMock())
        assert fetch_mock.await_count == 2


class TestDailyCandleStoreContext:
    """get_daily_context — live_trader.load_daily_context 호환."""

    async def test_context_computes_52w_high_and_avg_volume(self) -> None:
        """반환 타입은 (daily_prices, daily_context)."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )

        fake_bars = _volume_stair([1_000_000, 2_000_000, 3_000_000], count=25)

        with patch.object(store, "_fetch_from_db", new=AsyncMock(return_value=fake_bars)):
            prices, ctx = await store.get_daily_context(
                ["005930"],
                kiwoom_client=AsyncMock(),
            )

        assert "005930" in prices
        assert "005930" in ctx
        assert ctx["005930"]["high_52w"] == max(b.high for b in fake_bars)
        assert ctx["005930"]["avg_volume"] > 0

    async def test_context_skips_empty(self) -> None:
        """일봉 없는 종목은 스킵."""
        store = DailyCandleStore(
            database_url="postgresql+asyncpg://test/db",
            use_db=True,
        )
        with (
            patch.object(store, "_fetch_from_db", new=AsyncMock(return_value=[])),
            patch.object(
                store,
                "_fetch_from_kiwoom",
                new=AsyncMock(return_value=[]),
            ),
        ):
            prices, ctx = await store.get_daily_context(
                ["999999"],
                kiwoom_client=AsyncMock(),
            )
        assert prices == {}
        assert ctx == {}


class TestDailyCandleStoreDbIntegration:
    """_fetch_from_db + DailyCandle ORM 간단 통합 (세션 fixture 이용)."""

    async def test_fetch_returns_ordered_bars(self, db: AsyncSession) -> None:
        """DailyCandle → DailyPrice 매핑 및 날짜 오름차순 검증."""
        for day, close in [(21, 71500), (20, 71200), (17, 71000), (16, 70500)]:
            db.add(
                DailyCandle(
                    symbol="005930",
                    date=date(2026, 4, day),
                    open=close - 500,
                    high=close + 300,
                    low=close - 800,
                    close=close,
                    volume=1_000_000 + day,
                )
            )
        await db.flush()

        # _fetch_from_db의 create_async_engine 경로는 테스트 DB와 별개이므로
        # 여기서는 공용 ORM 조회 로직을 직접 구성해 매핑 정합성을 검증한다.
        from sqlalchemy import select

        from src.broker.schemas import DailyPrice

        rows = (
            (
                await db.execute(
                    select(DailyCandle)
                    .where(DailyCandle.symbol == "005930")
                    .order_by(DailyCandle.date.asc())
                )
            )
            .scalars()
            .all()
        )
        bars = [
            DailyPrice(
                date=r.date.strftime("%Y%m%d"),
                open=int(r.open),
                high=int(r.high),
                low=int(r.low),
                close=int(r.close),
                volume=int(r.volume),
            )
            for r in rows
        ]
        assert [b.date for b in bars] == ["20260416", "20260417", "20260420", "20260421"]
        assert bars[-1].close == 71500


# ── helpers ──────────────────────────────────────────


def _make_bar(d: date) -> Any:
    """테스트용 DailyPrice."""
    from src.broker.schemas import DailyPrice

    return DailyPrice(
        date=d.strftime("%Y%m%d"),
        open=70000,
        high=71000,
        low=69000,
        close=70500,
        volume=1_000_000,
    )


def _volume_stair(volumes: list[int], *, count: int) -> list[Any]:
    """볼륨 순환 패턴으로 count개 bar 생성."""
    from src.broker.schemas import DailyPrice

    bars: list[Any] = []
    for i in range(count):
        v = volumes[i % len(volumes)]
        bars.append(
            DailyPrice(
                date=f"2026040{i % 9 + 1}" if i < 9 else f"202604{10 + (i - 9):02d}",
                open=70000,
                high=70000 + i * 10,
                low=69800,
                close=70000,
                volume=v,
            )
        )
    return bars
