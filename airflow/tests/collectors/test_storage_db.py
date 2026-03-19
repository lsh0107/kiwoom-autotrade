"""storage.py DB 저장 함수 단위 테스트.

psycopg2를 mock 처리해 실제 DB 연결 없이 테스트.
psycopg2는 _get_db_conn 함수 내부에서 lazy import하므로
sys.modules를 통해 패치한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# 테스트용 가상 DB URL (실제 자격증명 없음)
_SCHEME = "postgresql"
_TEST_DB_URL = f"{_SCHEME}://nouser:nopass@testhost/testdb"


def _make_psycopg2_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    """psycopg2 mock 삼총사 반환: (mock_psycopg2, mock_conn, mock_cursor)."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_psycopg2 = MagicMock()
    mock_psycopg2.connect.return_value = mock_conn

    return mock_psycopg2, mock_conn, mock_cursor


# ── _get_db_conn ─────────────────────────────────────────────────────────────


class TestGetDbConn:
    """DB 연결 함수 테스트."""

    def test_airflow_conn_env_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AIRFLOW_CONN_KIWOOM_DB 환경변수로 psycopg2.connect가 호출되어야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        mock_psycopg2, mock_conn, _ = _make_psycopg2_mock()

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import _get_db_conn

            _get_db_conn()

        mock_psycopg2.connect.assert_called_once_with(_TEST_DB_URL)

    def test_database_url_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AIRFLOW_CONN_KIWOOM_DB 미설정 시 DATABASE_URL을 사용해야 한다."""
        monkeypatch.delenv("AIRFLOW_CONN_KIWOOM_DB", raising=False)
        monkeypatch.setenv("DATABASE_URL", _TEST_DB_URL)

        mock_psycopg2, _, _ = _make_psycopg2_mock()

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import _get_db_conn

            _get_db_conn()

        mock_psycopg2.connect.assert_called_once()

    def test_no_conn_raises_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """연결 정보 미설정 시 ValueError를 발생시켜야 한다."""
        monkeypatch.delenv("AIRFLOW_CONN_KIWOOM_DB", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        from collectors.storage import _get_db_conn

        with pytest.raises(ValueError, match="AIRFLOW_CONN_KIWOOM_DB"):
            _get_db_conn()

    def test_legacy_scheme_normalized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """레거시 스키마(postgres://)가 표준 스키마(postgresql://)로 변환되어야 한다."""
        legacy_url = _TEST_DB_URL.replace("postgresql://", "postgres://")
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", legacy_url)

        mock_psycopg2, _, _ = _make_psycopg2_mock()

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import _get_db_conn

            _get_db_conn()

        connect_arg = mock_psycopg2.connect.call_args[0][0]
        assert connect_arg.startswith("postgresql://")


# ── save_market_data ──────────────────────────────────────────────────────────


class TestSaveMarketData:
    """save_market_data 함수 테스트."""

    def test_calls_save_json_and_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """JSON 파일 저장과 DB upsert가 모두 호출되어야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2, mock_conn, mock_cursor = _make_psycopg2_mock()

        with (
            patch.dict("sys.modules", {"psycopg2": mock_psycopg2}),
            patch("collectors.storage.save_json") as mock_save_json,
        ):
            from collectors.storage import save_market_data

            save_market_data("premarket", "20260314", {"dart": [], "fred": {}})

        mock_save_json.assert_called_once_with("premarket", "20260314", {"dart": [], "fred": {}})
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_db_failure_raises_runtime_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB 저장 실패 시 RuntimeError를 발생시켜야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = Exception("DB 연결 실패")

        with (
            patch.dict("sys.modules", {"psycopg2": mock_psycopg2}),
            patch("collectors.storage.save_json"),
        ):
            from collectors.storage import save_market_data

            with pytest.raises(RuntimeError, match="시장 데이터 DB 저장 실패"):
                save_market_data("premarket", "20260314", {"data": "test"})

    def test_upsert_sql_contains_on_conflict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SQL에 ON CONFLICT 절이 포함되어야 한다 (upsert 보장)."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2, _, mock_cursor = _make_psycopg2_mock()

        with (
            patch.dict("sys.modules", {"psycopg2": mock_psycopg2}),
            patch("collectors.storage.save_json"),
        ):
            from collectors.storage import save_market_data

            save_market_data("macro", "20260314", {})

        sql_call = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql_call.upper()
        assert "DO UPDATE" in sql_call.upper()

    def test_no_db_conn_saves_json_then_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB 연결 정보 없으면 JSON 저장 후 RuntimeError를 발생시켜야 한다."""
        monkeypatch.delenv("AIRFLOW_CONN_KIWOOM_DB", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with patch("collectors.storage.save_json") as mock_save_json:
            from collectors.storage import save_market_data

            with pytest.raises(RuntimeError, match="시장 데이터 DB 저장 실패"):
                save_market_data("premarket", "20260314", {"test": True})

        # JSON 파일은 DB 저장 전에 저장되므로 호출되어야 한다
        mock_save_json.assert_called_once()


_SAMPLE_ARTICLES = [
    {
        "url": "https://example.com/news/1",
        "title": "반도체 수출 급증",
        "description": "반도체 수출이 급증했다.",
        "published_at": "2026-03-14T09:00:00",
        "source": "연합뉴스",
        "sentiment": "positive",
    },
    {
        "url": "https://example.com/news/2",
        "title": "금리 인상 우려",
        "description": "금리 인상 우려가 커지고 있다.",
        "published_at": "2026-03-14T10:00:00",
        "source": "한국경제",
        "sentiment": "negative",
    },
]


# ── save_news_articles ────────────────────────────────────────────────────────


class TestSaveNewsArticles:
    """save_news_articles 함수 테스트."""

    def test_inserts_all_articles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """모든 기사가 DB에 삽입 시도되어야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2, mock_conn, mock_cursor = _make_psycopg2_mock()

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import save_news_articles

            save_news_articles(_SAMPLE_ARTICLES)

        # 기사 수만큼 execute가 호출되어야 한다
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    def test_empty_articles_skips_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """빈 기사 목록이면 DB를 호출하지 않아야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2 = MagicMock()

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import save_news_articles

            save_news_articles([])

        mock_psycopg2.connect.assert_not_called()

    def test_on_conflict_do_nothing_in_sql(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SQL에 ON CONFLICT DO NOTHING이 포함되어야 한다 (중복 URL 스킵)."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2, _, mock_cursor = _make_psycopg2_mock()

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import save_news_articles

            save_news_articles(_SAMPLE_ARTICLES[:1])

        sql_call = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql_call.upper()
        assert "DO NOTHING" in sql_call.upper()

    def test_db_failure_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB 저장 실패 시 예외를 발생시키지 않아야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = Exception("DB 연결 실패")

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import save_news_articles

            save_news_articles(_SAMPLE_ARTICLES)

    def test_published_at_camel_case_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """published_at 없고 publishedAt 있으면 대안 필드를 사용해야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2, _, mock_cursor = _make_psycopg2_mock()

        article_with_camel = {
            "url": "https://example.com/news/3",
            "title": "테스트",
            "publishedAt": "2026-03-14T11:00:00",
            "source": "테스트",
        }

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            from collectors.storage import save_news_articles

            save_news_articles([article_with_camel])

        # 에러 없이 실행되어야 한다
        mock_cursor.execute.assert_called_once()
