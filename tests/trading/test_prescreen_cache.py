"""src/trading/prescreen_cache 테스트 (Design 012 PR 4).

SQLite 파일 DB를 임시 생성해 동기/비동기 양쪽이 같은 테이블을 볼 수 있도록 구성.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.daily_screening_cache import DailyScreeningCache
from src.trading.prescreen_cache import (
    is_prescreen_cache_enabled,
    load_screened_rows,
    load_screened_symbols_from_db,
    write_screened_json_from_db,
)


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    """파일 기반 SQLite URL — 동기 접근용."""
    return f"sqlite:///{tmp_path / 'prescreen.db'}"


@pytest.fixture
def seeded_url(sqlite_url: str) -> str:
    """스키마 생성 + 샘플 데이터 주입된 sqlite URL."""
    engine = create_engine(sqlite_url, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    rows: list[dict[str, Any]] = [
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
            "run_id": "run_A",
        },
        {
            "date": dt.date(2026, 4, 21),
            "profile": "momentum_breakout",
            "symbol": "000660",
            "name": "SK하이닉스",
            "sector": "반도체",
            "hint": "BO",
            "rank": 2,
            "passed": True,
            "price_ratio": 0.93,
            "vol_ratio": 2.1,
            "bonus_score": 1,
            "close": 135000,
            "high_52w": 145000,
            "volume": 800_000,
            "avg_volume": 380_000,
            "threshold": 0.75,
            "volume_ratio_param": 0.8,
            "min_stocks_param": 10,
            "run_id": "run_A",
        },
        # 미통과(조회 제외 대상)
        {
            "date": dt.date(2026, 4, 21),
            "profile": "momentum_breakout",
            "symbol": "035720",
            "name": "카카오",
            "sector": "IT플랫폼",
            "hint": "BO",
            "rank": 0,
            "passed": False,
            "price_ratio": 0.62,
            "vol_ratio": 0.5,
            "bonus_score": 0,
            "close": 40000,
            "high_52w": 65000,
            "volume": 200_000,
            "avg_volume": 350_000,
            "threshold": 0.75,
            "volume_ratio_param": 0.8,
            "min_stocks_param": 10,
            "run_id": "run_A",
        },
    ]
    with factory() as session:
        for r in rows:
            session.add(DailyScreeningCache(**r))
        session.commit()
    return sqlite_url


class TestIsPrescreenCacheEnabled:
    def test_default_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USE_PRESCREEN_CACHE", raising=False)
        assert is_prescreen_cache_enabled() is False

    @pytest.mark.parametrize("val", ["true", "1", "YES", "on", "True"])
    def test_truthy(self, monkeypatch: pytest.MonkeyPatch, val: str) -> None:
        monkeypatch.setenv("USE_PRESCREEN_CACHE", val)
        assert is_prescreen_cache_enabled() is True

    @pytest.mark.parametrize("val", ["false", "0", "", "no"])
    def test_falsy(self, monkeypatch: pytest.MonkeyPatch, val: str) -> None:
        monkeypatch.setenv("USE_PRESCREEN_CACHE", val)
        assert is_prescreen_cache_enabled() is False


class TestLoadScreenedRows:
    def test_returns_passed_rows_only_ordered_by_rank(self, seeded_url: str) -> None:
        rows = load_screened_rows(
            dt.date(2026, 4, 21),
            database_url=seeded_url,
        )
        assert [r.symbol for r in rows] == ["005930", "000660"]

    def test_missing_date_returns_empty(self, seeded_url: str) -> None:
        rows = load_screened_rows(
            dt.date(2026, 4, 20),
            database_url=seeded_url,
        )
        assert rows == []

    def test_no_database_url_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        rows = load_screened_rows(dt.date(2026, 4, 21), database_url=None)
        assert rows == []

    def test_invalid_url_logs_and_returns_empty(self) -> None:
        rows = load_screened_rows(
            dt.date(2026, 4, 21),
            database_url="sqlite:////nonexistent/readonly.db",
        )
        # 파일 없으면 스키마 없음 → exception 캐치 후 빈 리스트
        assert isinstance(rows, list)


class TestLoadScreenedSymbolsFromDb:
    def test_returns_symbols(self, seeded_url: str) -> None:
        syms = load_screened_symbols_from_db(
            dt.date(2026, 4, 21),
            database_url=seeded_url,
        )
        assert syms == ["005930", "000660"]


class TestWriteScreenedJsonFromDb:
    def test_creates_screened_json(
        self,
        seeded_url: str,
        tmp_path: Path,
    ) -> None:
        out_dir = tmp_path / "results"
        path = write_screened_json_from_db(
            dt.date(2026, 4, 21),
            out_dir,
            database_url=seeded_url,
        )
        assert path is not None
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["source"] == "prescreen_cache"
        assert data["passed_count"] == 2
        assert data["symbols"] == ["005930", "000660"]
        assert data["threshold"] == pytest.approx(0.75)
        assert len(data["details"]) == 2
        assert data["details"][0]["rank"] == 1

    def test_returns_none_when_empty(
        self,
        seeded_url: str,
        tmp_path: Path,
    ) -> None:
        out_dir = tmp_path / "results"
        path = write_screened_json_from_db(
            dt.date(2026, 4, 20),  # 없는 날짜
            out_dir,
            database_url=seeded_url,
        )
        assert path is None
