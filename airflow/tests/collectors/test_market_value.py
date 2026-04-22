"""시장 전체 거래대금 수집기 테스트 (Design 013).

pykrx 호출을 monkeypatch로 mock 처리한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestCollectMarketValue:
    """collect_market_value 함수 테스트."""

    def _make_df(self, values: list[float]) -> pd.DataFrame:
        """거래대금 컬럼을 포함한 DataFrame 생성."""
        return pd.DataFrame(
            {
                "종가": [2500.0 for _ in values],
                "거래대금": values,
            }
        )

    def test_normal_response_returns_dict(self) -> None:
        """정상 응답 시 value_today/avg/ratio 포함 딕셔너리 반환."""
        mock_stock = MagicMock()
        values = [10e12, 11e12, 12e12, 10e12, 9e12]  # 5일치
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_df(values)

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            result = collect_market_value(date="20260421", market="KOSPI")

        assert result["available"] is True
        assert result["value_today"] == pytest.approx(9e12)
        # 5일 평균 = (10+11+12+10+9)/5 * 1e12 = 10.4e12
        assert result["value_avg_5d"] == pytest.approx(10.4e12)
        # ratio 대략 9 / 10.4
        assert result["ratio"] == pytest.approx(0.8654, abs=0.01)
        assert result["market"] == "KOSPI"
        assert result["date"] == "20260421"
        assert result["data_points"] == 5

    def test_empty_dataframe_returns_unavailable(self) -> None:
        """빈 DataFrame → available=False, reason=no_data."""
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = pd.DataFrame()

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            result = collect_market_value(date="20260421")

        assert result["available"] is False
        assert result["reason"] == "no_data"
        assert result["value_today"] is None

    def test_missing_column_returns_unavailable(self) -> None:
        """거래대금 컬럼이 없으면 available=False."""
        mock_stock = MagicMock()
        df = pd.DataFrame({"종가": [2500.0, 2510.0]})
        mock_stock.get_index_ohlcv_by_date.return_value = df

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            result = collect_market_value(date="20260421")

        assert result["available"] is False
        assert result["reason"] == "column_missing"

    def test_pykrx_exception_returns_unavailable(self) -> None:
        """pykrx 예외 시 available=False + reason."""
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.side_effect = RuntimeError("네트워크 오류")

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            result = collect_market_value(date="20260421")

        assert result["available"] is False
        assert "네트워크" in result["reason"]

    def test_less_than_5_days_uses_available_data(self) -> None:
        """5거래일 미만 데이터라도 있는 만큼 사용."""
        mock_stock = MagicMock()
        values = [8e12, 9e12, 10e12]
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_df(values)

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            result = collect_market_value(date="20260421")

        assert result["available"] is True
        assert result["value_today"] == pytest.approx(10e12)
        assert result["value_avg_5d"] == pytest.approx(9e12)  # (8+9+10)/3
        assert result["data_points"] == 3

    def test_english_column_name(self) -> None:
        """영문 컬럼명(Trading Value) 대응."""
        mock_stock = MagicMock()
        df = pd.DataFrame({"Close": [2500.0], "Trading Value": [9e12]})
        mock_stock.get_index_ohlcv_by_date.return_value = df

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            result = collect_market_value(date="20260421")

        assert result["available"] is True
        assert result["value_today"] == pytest.approx(9e12)

    def test_kosdaq_uses_different_ticker(self) -> None:
        """market=KOSDAQ → ticker 2001 전달."""
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_df([10e12])

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            collect_market_value(date="20260421", market="KOSDAQ")

        call_kwargs = mock_stock.get_index_ohlcv_by_date.call_args.kwargs
        assert call_kwargs["ticker"] == "2001"

    def test_pykrx_missing_raises_importerror(self) -> None:
        """pykrx 미설치 환경 → ImportError."""
        with patch("collectors.market_value.stock", None):
            from collectors.market_value import collect_market_value

            with pytest.raises(ImportError, match="pykrx"):
                collect_market_value(date="20260421")

    def test_ratio_rounded(self) -> None:
        """ratio는 4자리 반올림."""
        mock_stock = MagicMock()
        # today=3, avg=(1+2+3)/3=2 → ratio=1.5
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_df([1e12, 2e12, 3e12])

        with (
            patch("collectors.market_value.stock", mock_stock),
            patch("collectors.market_value.time.sleep"),
        ):
            from collectors.market_value import collect_market_value

            result = collect_market_value(date="20260421")

        assert result["ratio"] == pytest.approx(1.5)
