"""VKOSPI & KOSPI 레짐 수집기 단위 테스트.

외부 pykrx 호출은 monkeypatch로 mock 처리한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── VKOSPI 수집기 ─────────────────────────────────────────────────────────────


class TestCollectVkospi:
    """collect_vkospi 함수 테스트."""

    def _make_ticker_list_mock(
        self, ticker: str = "1045", name: str = "코스피 변동성지수"
    ) -> MagicMock:
        """pykrx stock 모듈 mock 생성 헬퍼."""
        mock_stock = MagicMock()
        mock_stock.get_index_ticker_list.return_value = [ticker, "1001", "1028"]
        mock_stock.get_index_ticker_name.side_effect = lambda t: {
            ticker: name,
            "1001": "코스피",
            "1028": "코스피 200",
        }.get(t, "알수없음")
        return mock_stock

    def _make_ohlcv_df(self, closes: list[float]) -> pd.DataFrame:
        """OHLCV 데이터프레임 생성 헬퍼."""
        return pd.DataFrame({"종가": closes, "시가": closes, "고가": closes, "저가": closes})

    def test_정상_응답_시_딕셔너리_반환(self) -> None:
        """정상 pykrx 응답 시 value/change/change_pct 포함 딕셔너리를 반환해야 한다."""
        mock_stock = self._make_ticker_list_mock()
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_ohlcv_df([20.0, 21.5])

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_vkospi

            result = collect_vkospi(date="20250101")

        assert result["available"] is True
        assert result["value"] == 21.5
        assert result["change"] == pytest.approx(1.5, abs=0.01)
        assert result["change_pct"] == pytest.approx(7.5, abs=0.01)
        assert result["date"] == "20250101"

    def test_전일_데이터_없을_때_change_none(self) -> None:
        """단일 데이터 포인트이면 change/change_pct가 None이어야 한다."""
        mock_stock = self._make_ticker_list_mock()
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_ohlcv_df([18.0])

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_vkospi

            result = collect_vkospi(date="20250101")

        assert result["available"] is True
        assert result["value"] == 18.0
        assert result["change"] is None
        assert result["change_pct"] is None

    def test_티커_탐색_실패_시_available_false(self) -> None:
        """변동성 티커를 찾지 못하면 available=False를 반환해야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_index_ticker_list.return_value = ["1001", "1028"]
        mock_stock.get_index_ticker_name.side_effect = lambda t: {
            "1001": "코스피",
            "1028": "코스피 200",
        }.get(t, "알수없음")

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_vkospi

            result = collect_vkospi(date="20250101")

        assert result["available"] is False
        assert result["reason"] == "ticker_not_found"
        assert result["value"] is None

    def test_빈_데이터프레임_시_available_false(self) -> None:
        """pykrx가 빈 DataFrame을 반환하면 available=False를 반환해야 한다."""
        mock_stock = self._make_ticker_list_mock()
        mock_stock.get_index_ohlcv_by_date.return_value = pd.DataFrame()

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_vkospi

            result = collect_vkospi(date="20250101")

        assert result["available"] is False
        assert result["reason"] == "no_data"

    def test_pykrx_예외_시_available_false(self) -> None:
        """pykrx 호출 중 예외 발생 시 available=False를 반환해야 한다."""
        mock_stock = self._make_ticker_list_mock()
        mock_stock.get_index_ohlcv_by_date.side_effect = ValueError("KRX 응답 오류")

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_vkospi

            result = collect_vkospi(date="20250101")

        assert result["available"] is False
        assert "KRX 응답 오류" in result["reason"]

    def test_pykrx_미설치_시_ImportError(self) -> None:
        """pykrx 미설치 시 ImportError를 발생시켜야 한다."""
        with patch("collectors.vkospi.stock", None):
            from collectors.vkospi import collect_vkospi

            with pytest.raises(ImportError, match="pykrx"):
                collect_vkospi(date="20250101")

    def test_Close_컬럼명_영문_지원(self) -> None:
        """pykrx가 영문 컬럼(Close)을 반환해도 정상 파싱해야 한다."""
        mock_stock = self._make_ticker_list_mock()
        df = pd.DataFrame({"Close": [15.0, 16.0], "Open": [15.0, 16.0]})
        mock_stock.get_index_ohlcv_by_date.return_value = df

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_vkospi

            result = collect_vkospi(date="20250101")

        assert result["available"] is True
        assert result["value"] == 16.0


# ── KOSPI 레짐 수집기 ─────────────────────────────────────────────────────────


class TestCollectKospiRegime:
    """collect_kospi_regime 함수 테스트."""

    def _make_kospi_df(self, closes: list[float]) -> pd.DataFrame:
        """KOSPI OHLCV 데이터프레임 생성 헬퍼."""
        return pd.DataFrame({"종가": closes, "시가": closes, "고가": closes, "저가": closes})

    def test_MA12_위일_때_above_ma12_true(self) -> None:
        """현재 종가가 MA12보다 높으면 above_ma12=True여야 한다."""
        # 251개 = 2500, 마지막 1개 = 3000 → MA12 < 3000
        closes = [2500.0] * 251 + [3000.0]
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_kospi_df(closes)

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        assert result["available"] is True
        assert result["above_ma12"] is True
        assert result["kospi_close"] == 3000.0
        assert result["ma12"] < 3000.0

    def test_MA12_아래일_때_above_ma12_false(self) -> None:
        """현재 종가가 MA12보다 낮으면 above_ma12=False여야 한다."""
        closes = [3000.0] * 251 + [2500.0]
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_kospi_df(closes)

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        assert result["available"] is True
        assert result["above_ma12"] is False
        assert result["kospi_close"] == 2500.0

    def test_데이터_252일_미만_시_있는_만큼_사용(self) -> None:
        """데이터가 252거래일 미만이어도 있는 만큼 MA를 계산해야 한다."""
        closes = [2700.0] * 100
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_kospi_df(closes)

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        assert result["available"] is True
        assert result["data_points"] == 100
        assert result["ma12"] == pytest.approx(2700.0, abs=0.01)

    def test_MA12_정확도_검증(self) -> None:
        """252거래일 MA12가 올바르게 계산되어야 한다."""
        # 252개 모두 동일한 값 → MA12 = 해당 값
        closes = [2600.0] * 252
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = self._make_kospi_df(closes)

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        assert result["ma12"] == pytest.approx(2600.0, abs=0.01)
        assert result["data_points"] == 252

    def test_빈_데이터프레임_시_available_false(self) -> None:
        """pykrx가 빈 DataFrame을 반환하면 available=False를 반환해야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = pd.DataFrame()

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        assert result["available"] is False
        assert result["reason"] == "no_data"

    def test_pykrx_예외_시_available_false(self) -> None:
        """pykrx 호출 중 예외 발생 시 available=False를 반환해야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.side_effect = ConnectionError("네트워크 오류")

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        assert result["available"] is False
        assert "네트워크 오류" in result["reason"]

    def test_pykrx_미설치_시_ImportError(self) -> None:
        """pykrx 미설치 시 ImportError를 발생시켜야 한다."""
        with patch("collectors.vkospi.stock", None):
            from collectors.vkospi import collect_kospi_regime

            with pytest.raises(ImportError, match="pykrx"):
                collect_kospi_regime(date="20250101")

    def test_Close_컬럼명_영문_지원(self) -> None:
        """pykrx가 영문 컬럼(Close)을 반환해도 정상 파싱해야 한다."""
        closes = [2700.0] * 50
        df = pd.DataFrame({"Close": closes, "Open": closes})
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = df

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        assert result["available"] is True
        assert result["kospi_close"] == 2700.0


# ── 모듈 임포트 검증 ──────────────────────────────────────────────────────────


class TestVkospiModuleImport:
    """vkospi 모듈 임포트 및 공개 인터페이스 검증."""

    def test_모듈_임포트_가능(self) -> None:
        """vkospi 모듈이 임포트 가능해야 한다."""
        from collectors.vkospi import collect_kospi_regime, collect_vkospi

        assert callable(collect_vkospi)
        assert callable(collect_kospi_regime)

    def test_반환_딕셔너리_필수_키_존재(self) -> None:
        """collect_vkospi 반환 딕셔너리에 필수 키가 있어야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_index_ticker_list.return_value = ["1001"]
        mock_stock.get_index_ticker_name.return_value = "코스피"

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_vkospi

            result = collect_vkospi(date="20250101")

        # 티커 탐색 실패 케이스지만 키는 항상 존재해야 한다
        required_keys = {"value", "change", "change_pct", "date", "available"}
        assert required_keys.issubset(result.keys())

    def test_레짐_딕셔너리_필수_키_존재(self) -> None:
        """collect_kospi_regime 반환 딕셔너리에 필수 키가 있어야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_index_ohlcv_by_date.return_value = pd.DataFrame()

        with (
            patch("collectors.vkospi.stock", mock_stock),
            patch("collectors.vkospi.time.sleep"),
        ):
            from collectors.vkospi import collect_kospi_regime

            result = collect_kospi_regime(date="20250101")

        required_keys = {"kospi_close", "ma12", "above_ma12", "date", "available"}
        assert required_keys.issubset(result.keys())
