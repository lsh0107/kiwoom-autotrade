"""데이터 수집기 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.ai.data.cache import TTLCache
from src.ai.data.market_collector import get_cached_quote
from src.broker.schemas import Quote


class TestMarketCollector:
    """시세 데이터 수집기 테스트."""

    async def test_get_cached_quote_cache_miss(self) -> None:
        """캐시 미스 시 KiwoomClient에서 조회."""
        mock_client = AsyncMock()
        expected_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=70000,
            change=1000,
            change_pct=1.45,
            volume=10_000_000,
            high=71000,
            low=69000,
            open=69500,
            prev_close=69000,
        )
        mock_client.get_quote.return_value = expected_quote

        # 캐시 초기화 (비우기)
        with patch("src.ai.data.market_collector._quote_cache", TTLCache(default_ttl=30)):
            result = await get_cached_quote(mock_client, "005930")

        assert result == expected_quote
        mock_client.get_quote.assert_called_once_with("005930")

    async def test_get_cached_quote_cache_hit(self) -> None:
        """캐시 히트 시 KiwoomClient 호출 안 함."""
        mock_client = AsyncMock()
        cached_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=70000,
            change=1000,
            change_pct=1.45,
            volume=10_000_000,
            high=71000,
            low=69000,
            open=69500,
            prev_close=69000,
        )

        cache = TTLCache(default_ttl=30)
        cache.set("quote:005930", cached_quote)

        with patch("src.ai.data.market_collector._quote_cache", cache):
            result = await get_cached_quote(mock_client, "005930")

        assert result == cached_quote
        mock_client.get_quote.assert_not_called()


class TestDisclosureCollector:
    """DART 공시 수집기 테스트."""

    async def test_get_recent_disclosures_no_api_key(self) -> None:
        """DART API 키 없으면 빈 목록 반환."""
        mock_settings = MagicMock()
        mock_settings.dart_api_key = ""

        with patch("src.ai.data.disclosure_collector.get_settings", return_value=mock_settings):
            from src.ai.data.disclosure_collector import get_recent_disclosures

            # 캐시 초기화
            cache = TTLCache(default_ttl=600)
            with patch("src.ai.data.disclosure_collector._disclosure_cache", cache):
                result = await get_recent_disclosures(stock_code="005930")

        assert result == []

    async def test_get_recent_disclosures_success(self) -> None:
        """정상 공시 데이터 조회 (httpx 모킹)."""
        import httpx
        import respx

        mock_settings = MagicMock()
        mock_settings.dart_api_key = "test-dart-key"

        dart_response = {
            "status": "000",
            "list": [
                {
                    "corp_name": "삼성전자",
                    "report_nm": "주요사항보고서",
                    "rcept_dt": "20260301",
                    "flr_nm": "삼성전자",
                    "rcept_no": "20260301000001",
                    "stock_code": "005930",
                },
                {
                    "corp_name": "SK하이닉스",
                    "report_nm": "사업보고서",
                    "rcept_dt": "20260301",
                    "flr_nm": "SK하이닉스",
                    "rcept_no": "20260301000002",
                    "stock_code": "000660",
                },
            ],
        }

        with (
            patch("src.ai.data.disclosure_collector.get_settings", return_value=mock_settings),
            patch("src.ai.data.disclosure_collector._disclosure_cache", TTLCache(default_ttl=600)),
            respx.mock,
        ):
            respx.get("https://opendart.fss.or.kr/api/list.json").mock(
                return_value=httpx.Response(200, json=dart_response)
            )

            from src.ai.data.disclosure_collector import get_recent_disclosures

            result = await get_recent_disclosures(stock_code="005930")

        # stock_code 필터로 삼성전자만 포함
        assert len(result) == 1
        assert result[0].corp_name == "삼성전자"
        assert result[0].report_nm == "주요사항보고서"

    async def test_get_recent_disclosures_api_error(self) -> None:
        """API 호출 실패 시 빈 목록 반환."""
        import httpx
        import respx

        mock_settings = MagicMock()
        mock_settings.dart_api_key = "test-dart-key"

        with (
            patch("src.ai.data.disclosure_collector.get_settings", return_value=mock_settings),
            patch("src.ai.data.disclosure_collector._disclosure_cache", TTLCache(default_ttl=600)),
            respx.mock,
        ):
            respx.get("https://opendart.fss.or.kr/api/list.json").mock(
                return_value=httpx.Response(500)
            )

            from src.ai.data.disclosure_collector import get_recent_disclosures

            result = await get_recent_disclosures(stock_code="005930")

        assert result == []

    async def test_get_recent_disclosures_non_success_status(self) -> None:
        """API 응답 status가 000이 아니면 빈 목록."""
        import httpx
        import respx

        mock_settings = MagicMock()
        mock_settings.dart_api_key = "test-dart-key"

        with (
            patch("src.ai.data.disclosure_collector.get_settings", return_value=mock_settings),
            patch("src.ai.data.disclosure_collector._disclosure_cache", TTLCache(default_ttl=600)),
            respx.mock,
        ):
            error_json = {"status": "013", "message": "조회 데이터 없음"}
            respx.get("https://opendart.fss.or.kr/api/list.json").mock(
                return_value=httpx.Response(200, json=error_json)
            )

            from src.ai.data.disclosure_collector import get_recent_disclosures

            result = await get_recent_disclosures(stock_code="005930")

        assert result == []


class TestFuturesCollector:
    """해외 선물/지수 수집기 테스트."""

    async def test_get_overseas_indices_success(self) -> None:
        """yfinance 모킹을 통한 해외 지수 조회."""
        mock_fast_info = MagicMock()
        mock_fast_info.last_price = 5000.0
        mock_fast_info.previous_close = 4950.0

        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_fast_info

        with patch("src.ai.data.futures_collector._futures_cache", TTLCache(default_ttl=300)):
            # yfinance를 이미 import된 것처럼 처리
            # futures_collector는 함수 내부에서 import하므로 그 부분을 패치
            mock_yf = MagicMock()
            mock_yf.Ticker.return_value = mock_ticker

            with patch.dict("sys.modules", {"yfinance": mock_yf}):
                from importlib import reload

                import src.ai.data.futures_collector as fc

                # 캐시 초기화
                fc._futures_cache = TTLCache(default_ttl=300)
                reload(fc)
                fc._futures_cache = TTLCache(default_ttl=300)

                result = await fc.get_overseas_indices()

        # OVERSEAS_SYMBOLS 5개 지수 모두 반환해야 함
        assert len(result) == 5
        for idx in result:
            assert idx.price == 5000.0
            assert idx.change_pct > 0

    async def test_get_overseas_indices_cache_hit(self) -> None:
        """캐시 히트 시 yfinance 호출 안 함."""
        from src.ai.data.futures_collector import OverseasIndex

        cached_data = [
            OverseasIndex(name="S&P500", symbol="^GSPC", price=5000.0, change_pct=1.01),
        ]

        cache = TTLCache(default_ttl=300)
        cache.set("overseas_indices", cached_data)

        with patch("src.ai.data.futures_collector._futures_cache", cache):
            from src.ai.data.futures_collector import get_overseas_indices

            result = await get_overseas_indices()

        assert len(result) == 1
        assert result[0].name == "S&P500"

    async def test_get_overseas_indices_error(self) -> None:
        """yfinance 오류 시 빈 목록 반환."""
        with (
            patch("src.ai.data.futures_collector._futures_cache", TTLCache(default_ttl=300)),
            patch.dict("sys.modules", {"yfinance": None}),
        ):
            # yfinance import 실패하도록 설정
            from src.ai.data.futures_collector import get_overseas_indices

            # _futures_cache를 새로 만들어야 캐시 히트 방지
            with patch("src.ai.data.futures_collector._futures_cache", TTLCache(default_ttl=300)):
                result = await get_overseas_indices()

        assert result == []


class TestAggregator:
    """데이터 통합기 테스트."""

    async def test_aggregate_symbol_data(self) -> None:
        """모든 수집기 모킹하여 통합 데이터 생성."""
        from src.ai.data.aggregator import aggregate_symbol_data
        from src.ai.data.disclosure_collector import Disclosure
        from src.ai.data.futures_collector import OverseasIndex
        from src.ai.data.market_collector import DailyPrice

        mock_client = AsyncMock()

        mock_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=70000,
            change=1000,
            change_pct=1.45,
            volume=10_000_000,
            high=71000,
            low=69000,
            open=69500,
            prev_close=69000,
        )

        mock_daily = [
            DailyPrice(
                date="20260303",
                open=69000,
                high=71000,
                low=68500,
                close=70000,
                volume=10_000_000,
                change_pct=1.45,
            ),
        ]

        mock_disclosures = [
            Disclosure(
                corp_name="삼성전자",
                report_nm="주요사항보고서",
                rcept_dt="20260301",
                flr_nm="삼성전자",
                rcept_no="20260301000001",
            ),
        ]

        mock_overseas = [
            OverseasIndex(name="S&P500", symbol="^GSPC", price=5000.0, change_pct=0.5),
        ]

        with (
            patch(
                "src.ai.data.aggregator.get_cached_quote",
                AsyncMock(return_value=mock_quote),
            ),
            patch(
                "src.ai.data.aggregator.get_daily_prices",
                AsyncMock(return_value=mock_daily),
            ),
            patch(
                "src.ai.data.aggregator.get_recent_disclosures",
                AsyncMock(return_value=mock_disclosures),
            ),
            patch(
                "src.ai.data.aggregator.get_overseas_indices",
                AsyncMock(return_value=mock_overseas),
            ),
        ):
            result = await aggregate_symbol_data(mock_client, "005930")

        assert result.symbol == "005930"
        assert result.quote == mock_quote
        assert len(result.daily_prices) == 1
        assert len(result.disclosures) == 1
        assert len(result.overseas_indices) == 1

    async def test_aggregate_partial_failure(self) -> None:
        """일부 수집기 실패 시에도 나머지 데이터 반환."""
        from src.ai.data.aggregator import aggregate_symbol_data

        mock_client = AsyncMock()

        mock_quote = Quote(
            symbol="005930",
            name="삼성전자",
            price=70000,
            change=1000,
            change_pct=1.45,
            volume=10_000_000,
            high=71000,
            low=69000,
            open=69500,
            prev_close=69000,
        )

        with (
            patch(
                "src.ai.data.aggregator.get_cached_quote",
                AsyncMock(return_value=mock_quote),
            ),
            patch(
                "src.ai.data.aggregator.get_daily_prices",
                AsyncMock(side_effect=RuntimeError("일봉 조회 실패")),
            ),
            patch(
                "src.ai.data.aggregator.get_recent_disclosures",
                AsyncMock(side_effect=RuntimeError("공시 조회 실패")),
            ),
            patch(
                "src.ai.data.aggregator.get_overseas_indices",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await aggregate_symbol_data(mock_client, "005930")

        # quote는 성공, 나머지는 빈 목록
        assert result.quote == mock_quote
        assert result.daily_prices == []
        assert result.disclosures == []
        assert result.overseas_indices == []

    def test_format_for_llm(self) -> None:
        """LLM 입력 포맷팅 검증."""
        from src.ai.data.aggregator import AggregatedData, format_for_llm
        from src.ai.data.disclosure_collector import Disclosure
        from src.ai.data.futures_collector import OverseasIndex
        from src.ai.data.market_collector import DailyPrice

        data = AggregatedData(
            symbol="005930",
            quote=Quote(
                symbol="005930",
                name="삼성전자",
                price=70000,
                change=1000,
                change_pct=1.45,
                volume=10_000_000,
                high=71000,
                low=69000,
                open=69500,
                prev_close=69000,
            ),
            daily_prices=[
                DailyPrice(
                    date="20260303",
                    open=69000,
                    high=71000,
                    low=68500,
                    close=70000,
                    volume=10_000_000,
                    change_pct=1.45,
                ),
            ],
            disclosures=[
                Disclosure(
                    corp_name="삼성전자",
                    report_nm="주요사항보고서",
                    rcept_dt="20260301",
                    flr_nm="삼성전자",
                    rcept_no="20260301000001",
                ),
            ],
            overseas_indices=[
                OverseasIndex(name="S&P500", symbol="^GSPC", price=5000.0, change_pct=0.5),
            ],
        )

        formatted = format_for_llm(data)

        assert formatted["symbol"] == "005930"
        assert formatted["name"] == "삼성전자"
        assert formatted["price"] == 70000
        assert formatted["change"] == 1000
        assert formatted["volume"] == 10_000_000
        assert "20260303" in formatted["daily_prices"]
        assert "주요사항보고서" in formatted["disclosures"]
        assert "S&P500" in formatted["overseas_data"]
