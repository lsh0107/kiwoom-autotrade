"""종목별 수급 수집기 단위 테스트.

외부 pykrx 호출 및 DB 연결은 mock 처리한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── load_watch_symbols ────────────────────────────────────────────────────────


class TestLoadWatchSymbols:
    """load_watch_symbols 함수 테스트."""

    def test_DB_성공_시_종목코드_목록_반환(self) -> None:
        """DB 조회 성공 시 종목코드 리스트를 반환해야 한다."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [("005930",), ("000660",), ("035420",)]
        mock_conn.cursor.return_value = mock_cursor

        with patch("collectors.storage._get_db_conn", return_value=mock_conn):
            from collectors.investor_flow import load_watch_symbols

            result = load_watch_symbols()

        assert result == ["005930", "000660", "035420"]

    def test_DB_빈_결과_시_빈_리스트(self) -> None:
        """DB 조회 결과가 없으면 빈 리스트를 반환해야 한다."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        with patch("collectors.storage._get_db_conn", return_value=mock_conn):
            from collectors.investor_flow import load_watch_symbols

            result = load_watch_symbols()

        assert result == []

    def test_DB_실패_시_JSON_fallback(self, tmp_path: pytest.TempPathFactory) -> None:
        """DB 연결 실패 시 screened_*.json 파일에서 fallback 로드해야 한다."""
        import json

        screened_data = [
            {"symbol": "005930", "name": "삼성전자"},
            {"symbol": "000660", "name": "SK하이닉스"},
        ]
        screened_file = tmp_path / "screened_20250101.json"
        screened_file.write_text(json.dumps(screened_data), encoding="utf-8")

        with (
            patch("collectors.storage._get_db_conn", side_effect=ValueError("DB 연결 실패")),
            patch("collectors.storage.DATA_DIR", tmp_path),
        ):
            from collectors.investor_flow import load_watch_symbols

            result = load_watch_symbols()

        assert result == ["005930", "000660"]

    def test_DB_실패_JSON_dict_형식_지원(self, tmp_path: pytest.TempPathFactory) -> None:
        """screened.json이 {"symbols": [...]} 형식이어도 파싱해야 한다."""
        import json

        screened_data = {"symbols": ["005930", "000660", "035420"]}
        screened_file = tmp_path / "screened_20250101.json"
        screened_file.write_text(json.dumps(screened_data), encoding="utf-8")

        with (
            patch("collectors.storage._get_db_conn", side_effect=ValueError("DB 연결 실패")),
            patch("collectors.storage.DATA_DIR", tmp_path),
        ):
            from collectors.investor_flow import load_watch_symbols

            result = load_watch_symbols()

        assert result == ["005930", "000660", "035420"]

    def test_DB_실패_JSON_없을_때_빈_리스트(self, tmp_path: pytest.TempPathFactory) -> None:
        """DB 실패 + JSON 파일 없을 때 빈 리스트를 반환해야 한다."""
        with (
            patch("collectors.storage._get_db_conn", side_effect=ValueError("DB 연결 실패")),
            patch("collectors.storage.DATA_DIR", tmp_path),
        ):
            from collectors.investor_flow import load_watch_symbols

            result = load_watch_symbols()

        assert result == []


# ── collect_stock_investor_flow ───────────────────────────────────────────────


class TestCollectStockInvestorFlow:
    """collect_stock_investor_flow 함수 테스트."""

    def _make_trading_df(
        self,
        institution_net: int = 1_000_000_000,
        foreign_net: int = -500_000_000,
        individual_net: int = -500_000_000,
    ) -> pd.DataFrame:
        """pykrx 투자자별 매매 DataFrame 생성 헬퍼."""
        return pd.DataFrame(
            [
                {
                    "기관합계": institution_net,
                    "기타법인": 0,
                    "개인": individual_net,
                    "외국인합계": foreign_net,
                    "전체": institution_net + foreign_net + individual_net,
                }
            ]
        )

    def test_정상_수집_시_종목별_순매수_반환(self) -> None:
        """정상 응답 시 종목별 외국인/기관/개인 순매수를 반환해야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_market_trading_value_by_date.return_value = self._make_trading_df(
            institution_net=2_000_000_000,
            foreign_net=-1_000_000_000,
            individual_net=-1_000_000_000,
        )

        with (
            patch("collectors.investor_flow.stock", mock_stock),
            patch("collectors.investor_flow.time.sleep"),
        ):
            from collectors.investor_flow import collect_stock_investor_flow

            result = collect_stock_investor_flow(date="20250101", symbols=["005930"])

        assert result["available"] is True
        assert result["date"] == "20250101"
        assert result["total"] == 1
        assert result["success"] == 1
        stock_data = result["stocks"]["005930"]
        assert stock_data["available"] is True
        assert stock_data["institution_net"] == 2_000_000_000
        assert stock_data["foreign_net"] == -1_000_000_000
        assert stock_data["individual_net"] == -1_000_000_000

    def test_복수_종목_수집(self) -> None:
        """여러 종목을 순차적으로 수집해야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_market_trading_value_by_date.return_value = self._make_trading_df()

        with (
            patch("collectors.investor_flow.stock", mock_stock),
            patch("collectors.investor_flow.time.sleep"),
        ):
            from collectors.investor_flow import collect_stock_investor_flow

            result = collect_stock_investor_flow(
                date="20250101", symbols=["005930", "000660", "035420"]
            )

        assert result["total"] == 3
        assert result["success"] == 3
        assert len(result["stocks"]) == 3
        # pykrx 호출 횟수 검증
        assert mock_stock.get_market_trading_value_by_date.call_count == 3

    def test_빈_종목_목록_시_available_false(self) -> None:
        """종목 목록이 비어있으면 available=False를 반환해야 한다."""
        mock_stock = MagicMock()

        with patch("collectors.investor_flow.stock", mock_stock):
            from collectors.investor_flow import collect_stock_investor_flow

            result = collect_stock_investor_flow(date="20250101", symbols=[])

        assert result["available"] is False
        assert result["reason"] == "empty_symbols"
        assert result["stocks"] == {}
        mock_stock.get_market_trading_value_by_date.assert_not_called()

    def test_개별_종목_수집_실패_시_graceful_degradation(self) -> None:
        """일부 종목 수집 실패 시 해당 종목만 available=False, 나머지는 정상 반환."""

        def side_effect(fromdate: str, todate: str, ticker: str) -> pd.DataFrame:
            if ticker == "000660":
                raise ConnectionError("KRX 응답 오류")
            return self._make_trading_df()

        mock_stock = MagicMock()
        mock_stock.get_market_trading_value_by_date.side_effect = side_effect

        with (
            patch("collectors.investor_flow.stock", mock_stock),
            patch("collectors.investor_flow.time.sleep"),
        ):
            from collectors.investor_flow import collect_stock_investor_flow

            result = collect_stock_investor_flow(date="20250101", symbols=["005930", "000660"])

        assert result["available"] is True
        assert result["total"] == 2
        assert result["success"] == 1
        assert result["stocks"]["005930"]["available"] is True
        assert result["stocks"]["000660"]["available"] is False
        assert "KRX 응답 오류" in result["stocks"]["000660"]["reason"]

    def test_빈_데이터프레임_시_available_false(self) -> None:
        """pykrx가 빈 DataFrame을 반환하면 해당 종목 available=False여야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_market_trading_value_by_date.return_value = pd.DataFrame()

        with (
            patch("collectors.investor_flow.stock", mock_stock),
            patch("collectors.investor_flow.time.sleep"),
        ):
            from collectors.investor_flow import collect_stock_investor_flow

            result = collect_stock_investor_flow(date="20250101", symbols=["005930"])

        assert result["stocks"]["005930"]["available"] is False
        assert result["stocks"]["005930"]["reason"] == "no_data"
        assert result["success"] == 0

    def test_pykrx_미설치_시_ImportError(self) -> None:
        """pykrx 미설치 시 ImportError를 발생시켜야 한다."""
        with patch("collectors.investor_flow.stock", None):
            from collectors.investor_flow import collect_stock_investor_flow

            with pytest.raises(ImportError, match="pykrx"):
                collect_stock_investor_flow(date="20250101", symbols=["005930"])

    def test_rate_limit_sleep_호출(self) -> None:
        """종목별 수집마다 sleep을 호출해야 한다 (rate limit 준수)."""
        mock_stock = MagicMock()
        mock_stock.get_market_trading_value_by_date.return_value = self._make_trading_df()

        with (
            patch("collectors.investor_flow.stock", mock_stock),
            patch("collectors.investor_flow.time.sleep") as mock_sleep,
        ):
            from collectors.investor_flow import collect_stock_investor_flow

            collect_stock_investor_flow(date="20250101", symbols=["005930", "000660", "035420"])

        # 3종목 → sleep 3회
        assert mock_sleep.call_count == 3

    def test_반환_딕셔너리_필수_키_존재(self) -> None:
        """반환 딕셔너리에 필수 키가 항상 존재해야 한다."""
        mock_stock = MagicMock()
        mock_stock.get_market_trading_value_by_date.return_value = self._make_trading_df()

        with (
            patch("collectors.investor_flow.stock", mock_stock),
            patch("collectors.investor_flow.time.sleep"),
        ):
            from collectors.investor_flow import collect_stock_investor_flow

            result = collect_stock_investor_flow(date="20250101", symbols=["005930"])

        required_keys = {"date", "available", "total", "success", "stocks"}
        assert required_keys.issubset(result.keys())

        stock_required_keys = {"available", "institution_net", "foreign_net", "individual_net"}
        assert stock_required_keys.issubset(result["stocks"]["005930"].keys())


# ── 모듈 임포트 검증 ──────────────────────────────────────────────────────────


class TestInvestorFlowModuleImport:
    """investor_flow 모듈 임포트 및 공개 인터페이스 검증."""

    def test_모듈_임포트_가능(self) -> None:
        """investor_flow 모듈이 임포트 가능해야 한다."""
        from collectors.investor_flow import collect_stock_investor_flow, load_watch_symbols

        assert callable(collect_stock_investor_flow)
        assert callable(load_watch_symbols)
