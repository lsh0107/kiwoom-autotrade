"""해외지수 수집기 단위 테스트."""

from __future__ import annotations

import datetime
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestOverseasCollector:
    """해외지수 수집기 테스트."""

    def _make_hist(self, closes: list[float]) -> pd.DataFrame:
        """히스토리 DataFrame 생성 헬퍼."""
        dates = [datetime.date(2025, 1, i + 1) for i in range(len(closes))]
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates], tz="UTC")
        return pd.DataFrame({"Close": closes}, index=idx)

    def _make_yf_mock(self, hist: pd.DataFrame) -> MagicMock:
        """yfinance mock 생성 헬퍼."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker
        return mock_yf

    def test_collect_indices_returns_dict(self) -> None:
        """정상 응답 시 지수별 dict를 반환해야 한다."""
        mock_yf = self._make_yf_mock(self._make_hist([5000.0, 5100.0]))

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            sys.modules.pop("collectors.overseas", None)
            from collectors.overseas import collect_indices

            result = collect_indices()

        assert isinstance(result, dict)
        assert "SP500" in result
        assert result["SP500"]["close"] == 5100.0
        assert result["SP500"]["change_pct"] == pytest.approx(2.0, rel=0.01)

    def test_collect_indices_single_row_change_pct_zero(self) -> None:
        """1행 데이터 시 change_pct는 0.0이어야 한다."""
        mock_yf = self._make_yf_mock(self._make_hist([5000.0]))

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            sys.modules.pop("collectors.overseas", None)
            from collectors.overseas import collect_indices

            result = collect_indices()

        assert result["SP500"]["change_pct"] == 0.0
        assert result["SP500"]["close"] == 5000.0

    def test_collect_indices_empty_history_returns_error(self) -> None:
        """빈 히스토리 시 error=True를 반환해야 한다."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            sys.modules.pop("collectors.overseas", None)
            from collectors.overseas import collect_indices

            result = collect_indices()

        assert result["SP500"]["close"] is None
        assert result["SP500"]["change_pct"] is None
        assert result["SP500"]["error"] is True

    def test_collect_indices_exception_returns_error(self) -> None:
        """예외 발생 시 error=True를 반환하고 다른 지수 수집을 계속해야 한다."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = RuntimeError("네트워크 오류")
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            sys.modules.pop("collectors.overseas", None)
            from collectors.overseas import collect_indices

            result = collect_indices()

        assert len(result) == 6
        for v in result.values():
            assert v["error"] is True

    def test_collect_indices_all_tickers_present(self) -> None:
        """모든 티커 키가 결과에 포함되어야 한다."""
        mock_yf = self._make_yf_mock(self._make_hist([100.0, 101.0]))

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            sys.modules.pop("collectors.overseas", None)
            from collectors.overseas import collect_indices

            result = collect_indices()

        expected_keys = {"SP500", "NASDAQ", "NIKKEI", "HSI", "VIX", "USDKRW"}
        assert set(result.keys()) == expected_keys
