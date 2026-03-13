"""Tier 1 수집기 단위 테스트.

외부 API를 호출하지 않고 monkeypatch로 mock 처리한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── DART ──────────────────────────────────────────────────────────────────────


class TestDartCollector:
    """DART 수집기 테스트."""

    def test_collect_disclosures_returns_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 응답 시 list[dict]를 반환해야 한다."""
        import pandas as pd

        fake_df = pd.DataFrame(
            [
                {
                    "rcept_no": "20250101000001",
                    "corp_name": "삼성전자",
                    "report_nm": "주요사항보고서",
                },
                {
                    "rcept_no": "20250101000002",
                    "corp_name": "SK하이닉스",
                    "report_nm": "단일판매·공급계약",
                },
            ]
        )

        mock_api = MagicMock()
        mock_api.list.return_value = fake_df

        monkeypatch.setenv("DART_API_KEY", "test-key")

        with (
            patch("include.collectors.dart.odr") as mock_odr,
            patch("include.collectors.dart.time.sleep"),
        ):
            mock_odr.OpenDartReader.return_value = mock_api
            from include.collectors.dart import collect_disclosures

            result = collect_disclosures(days=1)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["corp_name"] == "삼성전자"

    def test_collect_disclosures_empty_returns_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """응답이 없을 때 빈 리스트를 반환해야 한다."""
        import pandas as pd

        mock_api = MagicMock()
        mock_api.list.return_value = pd.DataFrame()

        monkeypatch.setenv("DART_API_KEY", "test-key")

        with (
            patch("include.collectors.dart.odr") as mock_odr,
            patch("include.collectors.dart.time.sleep"),
        ):
            mock_odr.OpenDartReader.return_value = mock_api
            from include.collectors.dart import collect_disclosures

            result = collect_disclosures(days=1)

        assert result == []

    def test_collect_disclosures_no_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 키 미설정 시 ValueError를 발생시켜야 한다."""
        monkeypatch.delenv("DART_API_KEY", raising=False)

        from include.collectors.dart import collect_disclosures

        with pytest.raises(ValueError, match="DART_API_KEY"):
            collect_disclosures()


# ── KRX ───────────────────────────────────────────────────────────────────────


class TestKrxCollector:
    """KRX 수집기 테스트."""

    def test_collect_ohlcv_returns_list(self) -> None:
        """정상 응답 시 list[dict]를 반환해야 한다."""
        import pandas as pd

        fake_df = pd.DataFrame(
            [
                {
                    "티커": "005930",
                    "시가": 70000,
                    "고가": 71000,
                    "저가": 69000,
                    "종가": 70500,
                    "거래량": 1000000,
                },
                {
                    "티커": "000660",
                    "시가": 130000,
                    "고가": 132000,
                    "저가": 129000,
                    "종가": 131000,
                    "거래량": 500000,
                },
            ]
        )

        with (
            patch("include.collectors.krx.stock") as mock_stock,
            patch("include.collectors.krx.time.sleep"),
        ):
            mock_stock.get_market_ohlcv.return_value = fake_df
            from include.collectors.krx import collect_ohlcv

            result = collect_ohlcv(date="20250101", market="KOSPI")

        assert isinstance(result, list)
        assert len(result) == 2

    def test_collect_ohlcv_empty_returns_empty_list(self) -> None:
        """응답이 없을 때 빈 리스트를 반환해야 한다."""
        import pandas as pd

        with (
            patch("include.collectors.krx.stock") as mock_stock,
            patch("include.collectors.krx.time.sleep"),
        ):
            mock_stock.get_market_ohlcv.return_value = pd.DataFrame()
            from include.collectors.krx import collect_ohlcv

            result = collect_ohlcv(date="20250101")

        assert result == []

    def test_collect_investor_trading_returns_list(self) -> None:
        """투자자 매매 데이터를 list[dict]로 반환해야 한다."""
        import pandas as pd

        fake_df = pd.DataFrame(
            [
                {"투자자": "개인", "매수": 100000000, "매도": 90000000, "순매수": 10000000},
                {"투자자": "외국인", "매수": 200000000, "매도": 210000000, "순매수": -10000000},
            ]
        )

        with (
            patch("include.collectors.krx.stock") as mock_stock,
            patch("include.collectors.krx.time.sleep"),
        ):
            mock_stock.get_market_trading_value_by_investor.return_value = fake_df
            from include.collectors.krx import collect_investor_trading

            result = collect_investor_trading(date="20250101")

        assert isinstance(result, list)
        assert len(result) == 2


# ── FRED ──────────────────────────────────────────────────────────────────────


class TestFredCollector:
    """FRED 수집기 테스트."""

    def test_collect_macro_returns_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 응답 시 dict를 반환해야 한다."""
        import pandas as pd

        monkeypatch.setenv("FRED_API_KEY", "test-key")

        fake_series = pd.Series([18.5, 19.0, 17.8], name="VIXCLS")

        mock_fred = MagicMock()
        mock_fred.get_series.return_value = fake_series

        with patch("include.collectors.fred.Fred") as mock_fred_cls:
            mock_fred_cls.return_value = mock_fred
            from include.collectors.fred import collect_macro

            result = collect_macro(days=5)

        assert isinstance(result, dict)
        # 모든 시리즈 키가 존재해야 한다
        assert "vix" in result
        assert "us_rate_10y" in result
        assert "usd_krw" in result
        assert "wti" in result

    def test_collect_macro_api_failure_returns_none_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """API 호출 실패 시 해당 지표를 None으로 반환해야 한다."""
        monkeypatch.setenv("FRED_API_KEY", "test-key")

        mock_fred = MagicMock()
        mock_fred.get_series.side_effect = Exception("API 오류")

        with patch("include.collectors.fred.Fred") as mock_fred_cls:
            mock_fred_cls.return_value = mock_fred
            from include.collectors.fred import collect_macro

            result = collect_macro(days=5)

        assert isinstance(result, dict)
        for value in result.values():
            assert value is None

    def test_collect_macro_no_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 키 미설정 시 ValueError를 발생시켜야 한다."""
        monkeypatch.delenv("FRED_API_KEY", raising=False)

        from include.collectors.fred import collect_macro

        with pytest.raises(ValueError, match="FRED_API_KEY"):
            collect_macro()


# ── ECOS ──────────────────────────────────────────────────────────────────────


class TestEcosCollector:
    """ECOS 수집기 테스트."""

    def test_collect_base_rate_returns_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """정상 응답 시 기준금리 딕셔너리를 반환해야 한다."""
        monkeypatch.setenv("ECOS_API_KEY", "test-key")

        fake_response = {
            "StatisticSearch": {
                "row": [
                    {"TIME": "202412", "DATA_VALUE": "3.00"},
                    {"TIME": "202501", "DATA_VALUE": "3.00"},
                ]
            }
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status.return_value = None

        with patch("include.collectors.ecos.requests.get") as mock_get:
            mock_get.return_value = mock_resp
            from include.collectors.ecos import collect_base_rate

            result = collect_base_rate(months=3)

        assert isinstance(result, dict)
        assert result["base_rate"] == 3.0
        assert result["period"] == "202501"
        assert "collected_at" in result

    def test_collect_base_rate_empty_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """빈 응답 시 None 값의 딕셔너리를 반환해야 한다."""
        monkeypatch.setenv("ECOS_API_KEY", "test-key")

        fake_response = {"StatisticSearch": {"row": []}}

        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status.return_value = None

        with patch("include.collectors.ecos.requests.get") as mock_get:
            mock_get.return_value = mock_resp
            from include.collectors.ecos import collect_base_rate

            result = collect_base_rate()

        assert result["base_rate"] is None
        assert result["period"] is None

    def test_collect_base_rate_no_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 키 미설정 시 ValueError를 발생시켜야 한다."""
        monkeypatch.delenv("ECOS_API_KEY", raising=False)

        from include.collectors.ecos import collect_base_rate

        with pytest.raises(ValueError, match="ECOS_API_KEY"):
            collect_base_rate()
