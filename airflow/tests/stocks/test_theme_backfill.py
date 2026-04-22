"""stocks.theme 백필 로직 테스트.

순수 Python (Airflow 의존 없음). psycopg2를 MagicMock으로 대체한다.
"""

# ruff: noqa: N802

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# plugins 경로 추가 (Airflow 미실행 환경에서 import 가능하도록)
_PLUGINS_DIR = str(Path(__file__).parent.parent.parent / "plugins")
if _PLUGINS_DIR not in sys.path:
    sys.path.insert(0, _PLUGINS_DIR)

from stocks.theme_backfill import BackfillResult, run_theme_backfill  # noqa: E402

# ── 헬퍼 ──────────────────────────────────────────────────────────


def _make_mock_conn(
    universe_rowcount: int = 0,
    null_symbols: list[str] | None = None,
    final_null_cnt: int = 0,
    final_total: int = 0,
) -> MagicMock:
    """psycopg2.connect() 반환값 MagicMock 생성.

    Args:
        universe_rowcount: 1단계 UPDATE rowcount.
        null_symbols: 2단계에서 fetchall()이 반환할 NULL symbol 목록.
        final_null_cnt: 최종 집계 NULL 건수.
        final_total: 최종 집계 전체 건수.

    Returns:
        conn MagicMock.
    """
    null_symbols = null_symbols or []

    cur = MagicMock()
    cur.__enter__ = lambda self: self
    cur.__exit__ = MagicMock(return_value=False)

    # execute 호출 순서에 따라 rowcount / fetchall / fetchone 결과 제어
    execute_call_count = 0

    def fake_execute(_sql: str, _params: tuple = ()) -> None:
        nonlocal execute_call_count
        execute_call_count += 1
        # 1번 execute: 1단계 UPDATE
        if execute_call_count == 1:
            cur.rowcount = universe_rowcount
        # 2번 execute: NULL symbol SELECT (rowcount 무관)
        # 3번+ execute: 2단계 개별 UPDATE (rowcount=1로 설정)
        elif execute_call_count >= 3:
            cur.rowcount = 1

    cur.execute.side_effect = fake_execute
    cur.fetchall.return_value = [(s,) for s in null_symbols]
    cur.fetchone.return_value = (final_null_cnt, final_total)

    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


# ── 테스트 ──────────────────────────────────────────────────────────


class TestRunThemeBackfill:
    """run_theme_backfill 단위 테스트."""

    DUMMY_URI = "postgresql://dummy/dummy"

    def test_universe_복제_정상(self) -> None:
        """stock_universe.sector가 stocks.theme에 복제되는지 검증."""
        conn = _make_mock_conn(
            universe_rowcount=2,
            null_symbols=[],
            final_null_cnt=0,
            final_total=2,
        )
        with patch("psycopg2.connect", return_value=conn):
            result = run_theme_backfill(self.DUMMY_URI, sector_map={}, dry_run=False)

        assert result.updated_from_universe == 2
        assert result.updated_from_sector_map == 0
        assert result.remaining_null == 0
        conn.commit.assert_called_once()

    def test_기존_theme_보존_멱등(self) -> None:
        """theme 이미 채워진 행은 UPDATE WHERE theme IS NULL 조건으로 보호됨."""
        conn = _make_mock_conn(
            universe_rowcount=1,  # NULL인 행 1개만 업데이트
            null_symbols=[],
            final_null_cnt=0,
            final_total=2,
        )
        with patch("psycopg2.connect", return_value=conn):
            result = run_theme_backfill(self.DUMMY_URI, sector_map={}, dry_run=False)

        # universe에서 1건만 업데이트 → 나머지 1건은 기존 theme 유지
        assert result.updated_from_universe == 1
        assert result.remaining_null == 0

    def test_sector_map_fallback(self) -> None:
        """stock_universe에 없는 종목은 SECTOR_MAP fallback으로 채워진다."""
        conn = _make_mock_conn(
            universe_rowcount=1,
            null_symbols=["UNKNOWN"],  # 2단계에서 NULL로 남은 심볼
            final_null_cnt=0,
            final_total=2,
        )
        sector_map = {"UNKNOWN": "AI로봇"}

        with patch("psycopg2.connect", return_value=conn):
            result = run_theme_backfill(self.DUMMY_URI, sector_map=sector_map, dry_run=False)

        assert result.updated_from_universe == 1
        assert result.updated_from_sector_map == 1
        assert result.remaining_null == 0

    def test_universe_없고_sector_map_없으면_null_유지(self) -> None:
        """universe·SECTOR_MAP 모두 없으면 NULL 건 잔존."""
        conn = _make_mock_conn(
            universe_rowcount=0,
            null_symbols=["NOTHEME"],
            final_null_cnt=1,
            final_total=1,
        )
        with patch("psycopg2.connect", return_value=conn):
            result = run_theme_backfill(self.DUMMY_URI, sector_map={}, dry_run=False)

        assert result.remaining_null == 1
        assert result.null_pct == 100.0

    def test_dry_run_롤백(self) -> None:
        """dry_run=True 시 rollback 호출, commit 미호출."""
        conn = _make_mock_conn(
            universe_rowcount=1,
            null_symbols=[],
            final_null_cnt=0,
            final_total=1,
        )
        with patch("psycopg2.connect", return_value=conn):
            run_theme_backfill(self.DUMMY_URI, sector_map={}, dry_run=True)

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_sector_map_없는_심볼은_fallback_적용_안됨(self) -> None:
        """SECTOR_MAP에 없는 심볼은 업데이트되지 않는다."""
        conn = _make_mock_conn(
            universe_rowcount=0,
            null_symbols=["NOMAP"],
            final_null_cnt=1,
            final_total=1,
        )
        # SECTOR_MAP에 NOMAP 없음
        sector_map = {"OTHER": "반도체"}

        with patch("psycopg2.connect", return_value=conn):
            result = run_theme_backfill(self.DUMMY_URI, sector_map=sector_map, dry_run=False)

        assert result.updated_from_sector_map == 0
        assert result.remaining_null == 1

    def test_conn_close_항상_호출(self) -> None:
        """성공/예외 여부와 무관하게 conn.close() 호출 보장."""
        conn = _make_mock_conn(
            universe_rowcount=0,
            null_symbols=[],
            final_null_cnt=0,
            final_total=0,
        )
        with patch("psycopg2.connect", return_value=conn):
            run_theme_backfill(self.DUMMY_URI, sector_map={}, dry_run=False)

        conn.close.assert_called_once()


class TestBackfillResult:
    """BackfillResult 속성 단위 테스트."""

    def test_null_pct_정상(self) -> None:
        """null_pct 계산 정확성."""
        r = BackfillResult(
            updated_from_universe=3,
            updated_from_sector_map=1,
            remaining_null=5,
            total=10,
        )
        assert r.null_pct == 50.0

    def test_null_pct_total_zero(self) -> None:
        """total=0일 때 null_pct가 0.0 (ZeroDivisionError 없음)."""
        r = BackfillResult(
            updated_from_universe=0,
            updated_from_sector_map=0,
            remaining_null=0,
            total=0,
        )
        assert r.null_pct == 0.0

    def test_null_pct_전부_null(self) -> None:
        """remaining_null == total 이면 100.0."""
        r = BackfillResult(
            updated_from_universe=0,
            updated_from_sector_map=0,
            remaining_null=55,
            total=55,
        )
        assert r.null_pct == 100.0
