"""collectors.screening 단위 테스트 (Design 012 PR 3).

DB 연결(psycopg2)과 스크리닝 엔진을 각각 monkeypatch로 대체하고
`compute_screening`/`upsert_screening_rows` 의 흐름을 검증한다.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

# ── load_screening_params ────────────────────────────


class TestLoadScreeningParams:
    """환경변수 기반 파라미터 로드."""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SCREEN_THRESHOLD", raising=False)
        monkeypatch.delenv("SCREEN_VOLUME_RATIO", raising=False)
        monkeypatch.delenv("SCREEN_MIN_STOCKS", raising=False)

        from collectors.screening import load_screening_params  # type: ignore[import-not-found]

        p = load_screening_params()
        assert p["profile"] == "momentum_breakout"
        assert p["threshold"] == pytest.approx(0.75)
        assert p["volume_ratio"] == pytest.approx(0.8)
        assert p["min_stocks"] == 10

    def test_overrides_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCREEN_THRESHOLD", "0.90")
        monkeypatch.setenv("SCREEN_VOLUME_RATIO", "1.5")
        monkeypatch.setenv("SCREEN_MIN_STOCKS", "7")

        from collectors.screening import load_screening_params  # type: ignore[import-not-found]

        p = load_screening_params(profile="custom")
        assert p["profile"] == "custom"
        assert p["threshold"] == pytest.approx(0.90)
        assert p["volume_ratio"] == pytest.approx(1.5)
        assert p["min_stocks"] == 7


# ── compute_screening (DB/엔진 mock) ────────────────


class _FakeCursor:
    """DB-API 2.0 cursor 최소 흉내."""

    def __init__(self, rows_by_symbol: dict[str, list[tuple]]) -> None:
        self._rows_by_symbol = rows_by_symbol
        self._last: list[tuple] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, _sql: str, params: tuple[Any, ...]) -> None:
        """params = (symbol, start, end) — symbol 기준 시계열 반환."""
        symbol = params[0]
        self._last = self._rows_by_symbol.get(symbol, [])

    def fetchall(self) -> list[tuple]:
        return self._last


class _FakeConn:
    def __init__(self, rows_by_symbol: dict[str, list[tuple]]) -> None:
        self._rows_by_symbol = rows_by_symbol

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows_by_symbol)

    def close(self) -> None:
        return None

    def commit(self) -> None:
        return None


def _make_rows(
    n_days: int,
    close_start: int = 60_000,
    volume: int = 1_000_000,
) -> list[tuple]:
    """n_days 만큼 dummy 일봉 튜플 (date, open, high, low, close, volume)."""
    out: list[tuple] = []
    for i in range(n_days):
        day = dt.date(2026, 1, 1) + dt.timedelta(days=i)
        close = close_start + i * 10
        out.append(
            (day, close - 50, close + 100, close - 200, close, volume),
        )
    return out


class TestComputeScreening:
    """compute_screening 흐름 테스트 (DB/엔진 injection)."""

    def test_insufficient_bars_are_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """20 bars 미만은 check_screen_condition이 None → 스킵."""
        from collectors import screening as mod

        # 10 bars만 제공 → engine이 None 반환
        conn = _FakeConn({"005930": _make_rows(10)})
        monkeypatch.setattr(mod, "_get_db_conn", lambda: conn)

        rows = mod.compute_screening(
            {
                "profile": "momentum_breakout",
                "threshold": 0.1,
                "volume_ratio": 0.1,
                "min_stocks": 0,
            },
            on_date=dt.date(2026, 4, 21),
            universe=[("005930", "삼성전자")],
            get_sector=lambda _s: "반도체",
            get_hint=lambda _s: "BO",
            run_id="test_run",
        )
        assert rows == []

    def test_passed_rows_include_params_and_run_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """통과 종목 행에 파라미터/ run_id/ rank가 포함된다."""
        from collectors import screening as mod

        # 250일치 상승 일봉 — 52주 고가에 근접, 거래량 충분
        series = _make_rows(250, close_start=60_000, volume=2_000_000)
        conn = _FakeConn({"005930": series, "000660": series})
        monkeypatch.setattr(mod, "_get_db_conn", lambda: conn)

        rows = mod.compute_screening(
            {
                "profile": "momentum_breakout",
                "threshold": 0.50,
                "volume_ratio": 0.5,
                "min_stocks": 2,
            },
            on_date=dt.date(2026, 4, 21),
            universe=[("005930", "삼성전자"), ("000660", "SK하이닉스")],
            get_sector=lambda _s: "반도체",
            get_hint=lambda _s: "BO",
            run_id="airflow_test",
        )
        assert len(rows) == 2
        for r in rows:
            assert r["profile"] == "momentum_breakout"
            assert r["threshold"] == pytest.approx(0.50)
            assert r["volume_ratio_param"] == pytest.approx(0.5)
            assert r["min_stocks_param"] == 2
            assert r["run_id"] == "airflow_test"
            assert r["date"] == dt.date(2026, 4, 21)
            assert r["sector"] == "반도체"
        # rank 1/2 가 있어야 한다
        ranks = sorted(r["rank"] for r in rows)
        assert ranks == [1, 2]


# ── upsert_screening_rows ────────────────────────────


class _RecordingCursor(_FakeCursor):
    """execute 인자를 저장."""

    def __init__(self) -> None:
        super().__init__({})
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:  # type: ignore[override]
        """상위 execute 시그니처와 호환 — 호출 인자를 저장."""
        self.calls.append((sql, params))


class _RecordingConn:
    def __init__(self) -> None:
        self.cur = _RecordingCursor()
        self.committed = False
        self.closed = False

    def cursor(self) -> _RecordingCursor:
        return self.cur

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


class TestUpsertScreeningRows:
    def test_empty_rows_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from collectors import screening as mod

        called: list[bool] = []
        monkeypatch.setattr(mod, "_get_db_conn", lambda: called.append(True) or None)
        assert mod.upsert_screening_rows([]) == 0
        assert called == []  # 빈 입력 시 DB 접근 없음

    def test_commits_and_closes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from collectors import screening as mod

        rec = _RecordingConn()
        monkeypatch.setattr(mod, "_get_db_conn", lambda: rec)
        n = mod.upsert_screening_rows(
            [
                {
                    "date": dt.date(2026, 4, 21),
                    "profile": "momentum_breakout",
                    "symbol": "005930",
                    "name": "삼성전자",
                    "sector": "반도체",
                    "hint": "BO",
                    "rank": 1,
                    "passed": True,
                    "price_ratio": 0.97,
                    "vol_ratio": 3.0,
                    "bonus_score": 2,
                    "close": 70000,
                    "high_52w": 72000,
                    "volume": 1_000_000,
                    "avg_volume": 330_000,
                    "threshold": 0.75,
                    "volume_ratio_param": 0.8,
                    "min_stocks_param": 10,
                    "run_id": "run_X",
                }
            ]
        )
        assert n == 1
        assert rec.committed is True
        assert rec.closed is True
        assert len(rec.cur.calls) == 1
