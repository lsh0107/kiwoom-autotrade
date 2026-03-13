"""파라미터 튜너 단위 테스트.

범위 검증, 필터링, 제안 생성, DB 저장 테스트.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# 테스트용 가상 DB URL (실제 자격증명 없음)
_SCHEME = "postgresql"
_TEST_DB_URL = f"{_SCHEME}://nouser:nopass@testhost/testdb"

# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

SAMPLE_REVIEW = {
    "summary": "당일 반도체 섹터 중심 상승",
    "performance_analysis": "외국인 순매수 유입으로 강세",
    "risk_assessment": "금리 불확실성 유의",
    "suggestions": [
        {
            "key": "atr_stop_mult",
            "current_value": 2.0,
            "suggested_value": 1.5,
            "reason": "변동성 감소로 손절 강화",
            "confidence": 0.8,
        },
        {
            "key": "volume_ratio",
            "current_value": 1.5,
            "suggested_value": 2.0,
            "reason": "거래량 증가 포착 필요",
            "confidence": 0.75,
        },
    ],
}

SAMPLE_TRADES = [
    {"ticker": "005930", "side": "BUY", "quantity": 10, "price": 70000, "pnl": 50000},
    {"ticker": "000660", "side": "SELL", "quantity": 5, "price": 130000, "pnl": -20000},
    {"ticker": "035420", "side": "BUY", "quantity": 3, "price": 200000, "pnl": 30000},
]


def _make_psycopg2_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    """psycopg2 mock 삼총사 반환."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg2 = MagicMock()
    mock_psycopg2.connect.return_value = mock_conn
    return mock_psycopg2, mock_conn, mock_cursor


# ── _clamp_numeric ────────────────────────────────────────────────────────────


class TestClampNumeric:
    """숫자 파라미터 클램핑 테스트."""

    def test_atr_stop_mult_clamps_to_bounds(self) -> None:
        """atr_stop_mult가 1.0~3.0 범위로 클램핑되어야 한다."""
        from analysis.param_tuner import _clamp_numeric

        assert _clamp_numeric("atr_stop_mult", 0.5) == pytest.approx(1.0)
        assert _clamp_numeric("atr_stop_mult", 5.0) == pytest.approx(3.0)
        assert _clamp_numeric("atr_stop_mult", 2.0) == pytest.approx(2.0)

    def test_atr_tp_mult_clamps_to_bounds(self) -> None:
        """atr_tp_mult가 2.0~5.0 범위로 클램핑되어야 한다."""
        from analysis.param_tuner import _clamp_numeric

        assert _clamp_numeric("atr_tp_mult", 1.0) == pytest.approx(2.0)
        assert _clamp_numeric("atr_tp_mult", 6.0) == pytest.approx(5.0)

    def test_volume_ratio_clamps_to_bounds(self) -> None:
        """volume_ratio가 1.0~3.0 범위로 클램핑되어야 한다."""
        from analysis.param_tuner import _clamp_numeric

        assert _clamp_numeric("volume_ratio", 0.1) == pytest.approx(1.0)
        assert _clamp_numeric("volume_ratio", 10.0) == pytest.approx(3.0)

    def test_max_positions_rounds_and_clamps(self) -> None:
        """max_positions가 정수로 반올림되고 1~5 범위로 클램핑되어야 한다."""
        from analysis.param_tuner import _clamp_numeric

        assert _clamp_numeric("max_positions", 0) == 1
        assert _clamp_numeric("max_positions", 7) == 5
        assert _clamp_numeric("max_positions", 2.7) == 3

    def test_unknown_key_returns_original(self) -> None:
        """범위 정의 없는 키는 원본 값을 반환해야 한다."""
        from analysis.param_tuner import _clamp_numeric

        assert _clamp_numeric("unknown_param", 99.9) == 99.9


# ── _validate_time ───────────────────────────────────────────────────────────


class TestValidateTime:
    """시간 파라미터 검증 테스트."""

    def test_valid_time_within_range(self) -> None:
        """09:00~15:00 범위의 HH:MM 시간은 유효해야 한다."""
        from analysis.param_tuner import _validate_time

        assert _validate_time("09:00") is True
        assert _validate_time("12:30") is True
        assert _validate_time("15:00") is True

    def test_time_before_range_invalid(self) -> None:
        """09:00 이전 시간은 유효하지 않아야 한다."""
        from analysis.param_tuner import _validate_time

        assert _validate_time("08:59") is False
        assert _validate_time("00:00") is False

    def test_time_after_range_invalid(self) -> None:
        """15:00 이후 시간은 유효하지 않아야 한다."""
        from analysis.param_tuner import _validate_time

        assert _validate_time("15:01") is False
        assert _validate_time("18:00") is False

    def test_invalid_format_returns_false(self) -> None:
        """HH:MM 형식이 아닌 값은 유효하지 않아야 한다."""
        from analysis.param_tuner import _validate_time

        assert _validate_time("9시") is False
        assert _validate_time("") is False
        assert _validate_time(900) is False  # type: ignore[arg-type]
        assert _validate_time("12:30:00") is False


# ── _compute_trade_stats ──────────────────────────────────────────────────────


class TestComputeTradeStats:
    """매매 통계 계산 테스트."""

    def test_empty_trades_returns_defaults(self) -> None:
        """빈 매매 기록이면 기본값을 반환해야 한다."""
        from analysis.param_tuner import _compute_trade_stats

        stats = _compute_trade_stats([])

        assert stats["win_rate"] == pytest.approx(0.5)
        assert stats["total_trades"] == 0

    def test_win_rate_calculated_correctly(self) -> None:
        """승률이 올바르게 계산되어야 한다."""
        from analysis.param_tuner import _compute_trade_stats

        trades = [{"pnl": 1000}, {"pnl": -500}, {"pnl": 2000}, {"pnl": -300}]
        stats = _compute_trade_stats(trades)

        assert stats["win_rate"] == pytest.approx(0.5)
        assert stats["total_trades"] == 4
        assert stats["profitable_trades"] == 2

    def test_trades_without_pnl_use_defaults(self) -> None:
        """pnl 없는 매매 기록은 기본값을 사용해야 한다."""
        from analysis.param_tuner import _compute_trade_stats

        trades = [{"ticker": "005930", "side": "BUY"}]
        stats = _compute_trade_stats(trades)

        assert stats["win_rate"] == pytest.approx(0.5)
        assert stats["total_trades"] == 1

    def test_avg_pnl_calculated(self) -> None:
        """평균 손익이 올바르게 계산되어야 한다."""
        from analysis.param_tuner import _compute_trade_stats

        trades = [{"pnl": 1000}, {"pnl": -500}, {"pnl": 750}]
        stats = _compute_trade_stats(trades)

        assert stats["avg_pnl"] == pytest.approx((1000 - 500 + 750) / 3)


# ── analyze_and_suggest ───────────────────────────────────────────────────────


class TestAnalyzeAndSuggest:
    """analyze_and_suggest 함수 테스트."""

    def test_success_returns_suggestions(self) -> None:
        """정상 입력 시 ParamSuggestion 목록을 반환해야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        result = analyze_and_suggest(SAMPLE_REVIEW, SAMPLE_TRADES)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_high_confidence_suggestions_included(self) -> None:
        """confidence 0.7 이상인 제안은 포함되어야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        result = analyze_and_suggest(SAMPLE_REVIEW, SAMPLE_TRADES)

        for s in result:
            assert s.confidence >= 0.7

    def test_low_confidence_suggestions_excluded(self) -> None:
        """confidence 0.7 미만인 제안은 제외되어야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        review = {
            "suggestions": [
                {
                    "key": "atr_stop_mult",
                    "current_value": 2.0,
                    "suggested_value": 1.5,
                    "reason": "테스트",
                    "confidence": 0.5,
                }
            ]
        }
        result = analyze_and_suggest(review, SAMPLE_TRADES)

        assert result == []

    def test_out_of_bounds_numeric_clamped(self) -> None:
        """범위 초과 숫자 파라미터는 클램핑되어야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        review = {
            "suggestions": [
                {
                    "key": "atr_stop_mult",
                    "current_value": 2.0,
                    "suggested_value": 10.0,  # 범위 3.0 초과
                    "reason": "테스트",
                    "confidence": 0.9,
                }
            ]
        }
        result = analyze_and_suggest(review, SAMPLE_TRADES)

        assert len(result) == 1
        assert result[0].suggested_value == pytest.approx(3.0)

    def test_out_of_bounds_time_param_excluded(self) -> None:
        """범위 초과 시간 파라미터는 제외되어야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        review = {
            "suggestions": [
                {
                    "key": "entry_start_time",
                    "current_value": "09:00",
                    "suggested_value": "07:30",
                    "reason": "테스트",
                    "confidence": 0.9,
                }
            ]
        }
        result = analyze_and_suggest(review, SAMPLE_TRADES)

        assert result == []

    def test_valid_time_param_included(self) -> None:
        """유효 범위 시간 파라미터는 포함되어야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        review = {
            "suggestions": [
                {
                    "key": "entry_start_time",
                    "current_value": "09:00",
                    "suggested_value": "09:30",
                    "reason": "테스트",
                    "confidence": 0.85,
                }
            ]
        }
        result = analyze_and_suggest(review, SAMPLE_TRADES)

        assert len(result) == 1
        assert result[0].suggested_value == "09:30"

    def test_empty_review_returns_empty(self) -> None:
        """빈 리뷰이면 빈 목록을 반환해야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        result = analyze_and_suggest({}, SAMPLE_TRADES)

        assert result == []

    def test_source_is_param_tuner(self) -> None:
        """생성된 제안의 source가 'param_tuner'여야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        result = analyze_and_suggest(SAMPLE_REVIEW, SAMPLE_TRADES)

        for s in result:
            assert s.source == "param_tuner"

    def test_low_win_rate_boosts_confidence(self) -> None:
        """승률이 40% 미만이면 confidence가 소폭 상향되어야 한다."""
        from analysis.param_tuner import analyze_and_suggest

        # 0.66: 정상적으로는 필터되지만 승률 부스트로 0.71 → 통과
        review = {
            "suggestions": [
                {
                    "key": "atr_stop_mult",
                    "current_value": 2.0,
                    "suggested_value": 1.5,
                    "reason": "테스트",
                    "confidence": 0.66,
                }
            ]
        }
        low_win_trades = [{"pnl": -100}, {"pnl": -200}, {"pnl": -300}]

        result = analyze_and_suggest(review, low_win_trades)

        assert len(result) == 1


# ── save_suggestions ──────────────────────────────────────────────────────────


class TestSaveSuggestions:
    """save_suggestions 함수 테스트."""

    def test_empty_suggestions_returns_zero(self) -> None:
        """빈 제안 목록이면 0을 반환해야 한다."""
        from analysis.param_tuner import save_suggestions

        result = save_suggestions([])

        assert result == 0

    def test_no_db_conn_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB 연결 정보 없으면 0을 반환해야 한다."""
        monkeypatch.delenv("AIRFLOW_CONN_KIWOOM_DB", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        from analysis.param_tuner import ParamSuggestion, save_suggestions

        suggestions = [
            ParamSuggestion(
                key="atr_stop_mult",
                current_value=2.0,
                suggested_value=1.5,
                reason="테스트",
                confidence=0.8,
            )
        ]
        result = save_suggestions(suggestions)

        assert result == 0

    def test_saves_to_db_with_pending_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """제안이 status='pending'으로 DB에 저장되어야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2, mock_conn, mock_cursor = _make_psycopg2_mock()

        from analysis.param_tuner import ParamSuggestion, save_suggestions

        suggestions = [
            ParamSuggestion(
                key="atr_stop_mult",
                current_value=2.0,
                suggested_value=1.5,
                reason="변동성 감소",
                confidence=0.8,
            ),
            ParamSuggestion(
                key="volume_ratio",
                current_value=1.5,
                suggested_value=2.0,
                reason="거래량 증가",
                confidence=0.75,
            ),
        ]

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            result = save_suggestions(suggestions)

        assert result == 2
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    def test_sql_contains_pending_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """INSERT SQL에 'pending' status가 포함되어야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2, _, mock_cursor = _make_psycopg2_mock()

        from analysis.param_tuner import ParamSuggestion, save_suggestions

        suggestions = [
            ParamSuggestion(
                key="atr_stop_mult",
                current_value=2.0,
                suggested_value=1.5,
                reason="테스트",
                confidence=0.8,
            )
        ]

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            save_suggestions(suggestions)

        sql = mock_cursor.execute.call_args[0][0]
        assert "pending" in sql.lower()

    def test_db_failure_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB 오류 시 예외 없이 0을 반환해야 한다."""
        monkeypatch.setenv("AIRFLOW_CONN_KIWOOM_DB", _TEST_DB_URL)

        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = Exception("DB 연결 실패")

        from analysis.param_tuner import ParamSuggestion, save_suggestions

        suggestions = [
            ParamSuggestion(
                key="atr_stop_mult",
                current_value=2.0,
                suggested_value=1.5,
                reason="테스트",
                confidence=0.8,
            )
        ]

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            result = save_suggestions(suggestions)

        assert result == 0
