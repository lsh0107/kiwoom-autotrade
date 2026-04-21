"""collectors.candles 단위 테스트.

pykrx/psycopg2 호출을 monkeypatch로 전부 mock.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest


def _install_fake_pykrx(
    monkeypatch: pytest.MonkeyPatch,
    df_by_call: Any,
) -> None:
    """pykrx.stock.get_market_ohlcv_by_ticker 를 mock."""
    fake_stock = types.SimpleNamespace(
        get_market_ohlcv_by_ticker=df_by_call,
    )
    fake_pkg = types.ModuleType("pykrx")
    fake_pkg.stock = fake_stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pkg)
    # collectors.candles가 이미 import된 경우 stock 심볼을 덮어씀
    if "collectors.candles" in sys.modules:
        import collectors.candles as mod  # type: ignore[import-not-found]

        mod.stock = fake_stock  # type: ignore[attr-defined]


class TestCollectDailyOhlcv:
    """collect_daily_ohlcv 테스트."""

    def test_normal_response_returns_records(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 응답 시 정규화된 레코드 반환."""
        import pandas as pd

        fake_df = pd.DataFrame(
            [
                {
                    "티커": "005930",
                    "시가": 70000,
                    "고가": 71500,
                    "저가": 69800,
                    "종가": 71000,
                    "거래량": 12345678,
                },
                {
                    "티커": "000660",
                    "시가": 135000,
                    "고가": 136500,
                    "저가": 134200,
                    "종가": 136000,
                    "거래량": 3_000_000,
                },
            ]
        )
        _install_fake_pykrx(monkeypatch, MagicMock(return_value=fake_df))
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

        from collectors.candles import collect_daily_ohlcv

        result = collect_daily_ohlcv("20260421", market="KOSPI")
        assert len(result) == 2
        r0 = result[0]
        assert r0["symbol"] == "005930"
        assert r0["date"] == "20260421"
        assert r0["close"] == 71000
        assert r0["volume"] == 12_345_678

    def test_empty_df_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """빈 DataFrame → 빈 리스트."""
        import pandas as pd

        _install_fake_pykrx(monkeypatch, MagicMock(return_value=pd.DataFrame()))
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

        from collectors.candles import collect_daily_ohlcv

        assert collect_daily_ohlcv("20260421", market="KOSDAQ") == []

    def test_keyerror_handled_gracefully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KRX 미제공 날짜 (KeyError/ValueError) → 빈 리스트."""
        _install_fake_pykrx(
            monkeypatch,
            MagicMock(side_effect=KeyError("no data")),
        )
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

        from collectors.candles import collect_daily_ohlcv

        assert collect_daily_ohlcv("20260101", market="KOSPI") == []

    def test_zero_padding_for_short_ticker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """int 5자리 티커도 6자리 zero-padding."""
        import pandas as pd

        fake_df = pd.DataFrame(
            [
                {
                    "티커": 5930,
                    "시가": 70000,
                    "고가": 71000,
                    "저가": 69000,
                    "종가": 70500,
                    "거래량": 1000,
                }
            ]
        )
        _install_fake_pykrx(monkeypatch, MagicMock(return_value=fake_df))
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

        from collectors.candles import collect_daily_ohlcv

        result = collect_daily_ohlcv("20260421")
        assert result[0]["symbol"] == "005930"

    def test_pykrx_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """pykrx 미설치 상태(stock=None) 시 ImportError 명시."""
        import collectors.candles as mod  # type: ignore[import-not-found]

        monkeypatch.setattr(mod, "stock", None)
        with pytest.raises(ImportError, match="pykrx"):
            mod.collect_daily_ohlcv("20260421")


class TestUpsertDailyCandles:
    """upsert_daily_candles 테스트 (psycopg2 mock)."""

    def test_empty_records_returns_zero(self) -> None:
        """빈 리스트는 0 반환 + DB 호출 없음."""
        from collectors.candles import upsert_daily_candles

        assert upsert_daily_candles([]) == 0

    def test_happy_path_upserts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 업서트 호출 검증."""
        fake_cursor = MagicMock()
        fake_cursor.__enter__ = MagicMock(return_value=fake_cursor)
        fake_cursor.__exit__ = MagicMock(return_value=False)
        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor

        import collectors.candles as candles_mod  # type: ignore[import-not-found]

        monkeypatch.setattr(candles_mod, "_get_db_conn", lambda: fake_conn)

        from collectors.candles import upsert_daily_candles

        recs = [
            {
                "symbol": "005930",
                "date": "20260421",
                "open": 70000,
                "high": 71000,
                "low": 69000,
                "close": 70500,
                "volume": 1_000_000,
            },
            {
                "symbol": "000660",
                "date": "20260421",
                "open": 135000,
                "high": 136000,
                "low": 134000,
                "close": 135500,
                "volume": 2_000_000,
            },
        ]
        count = upsert_daily_candles(recs, source="pykrx")
        assert count == 2
        assert fake_cursor.execute.call_count == 2
        fake_conn.commit.assert_called_once()
        fake_conn.close.assert_called_once()

    def test_db_error_raises_runtime_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB 예외 발생 시 RuntimeError로 래핑."""

        def _broken_conn() -> Any:
            raise RuntimeError("connection refused")

        import collectors.candles as candles_mod  # type: ignore[import-not-found]

        monkeypatch.setattr(candles_mod, "_get_db_conn", _broken_conn)

        from collectors.candles import upsert_daily_candles

        with pytest.raises(RuntimeError, match="업서트 실패"):
            upsert_daily_candles(
                [
                    {
                        "symbol": "005930",
                        "date": "20260421",
                        "open": 1,
                        "high": 1,
                        "low": 1,
                        "close": 1,
                        "volume": 1,
                    }
                ]
            )

    def test_get_db_conn_missing_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """환경변수 미설정 시 ValueError."""
        monkeypatch.delenv("AIRFLOW_CONN_KIWOOM_DB", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        from collectors.candles import _get_db_conn

        with pytest.raises(ValueError, match="미설정"):
            _get_db_conn()
