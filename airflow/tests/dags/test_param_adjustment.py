"""mark_telegram_sent 함수 테스트."""

from unittest.mock import MagicMock, patch


class TestMarkTelegramSent:
    """mark_telegram_sent DB 업데이트 테스트."""

    def test_updates_db_on_success(self) -> None:
        """전송된 키에 대해 telegram_sent_at 업데이트."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None

        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn

        with (
            patch.dict("os.environ", {"DATABASE_URL": "postgresql://test:test@localhost/test"}),
            patch.dict("sys.modules", {"psycopg2": mock_psycopg2}),
        ):
            from analysis.param_tuner import mark_telegram_sent

            result = mark_telegram_sent(["atr_stop_mult", "volume_ratio"])

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "telegram_sent_at" in sql
        assert "strategy_config_suggestions" in sql
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()
        assert result == 2

    def test_skips_when_no_keys(self) -> None:
        """빈 키 목록이면 DB 호출 없음."""
        from analysis.param_tuner import mark_telegram_sent

        result = mark_telegram_sent([])
        assert result == 0

    def test_skips_when_no_db_url(self) -> None:
        """DB URL 미설정이면 스킵."""
        from analysis.param_tuner import mark_telegram_sent

        with patch.dict("os.environ", {}, clear=True):
            result = mark_telegram_sent(["atr_stop_mult"])

        assert result == 0
