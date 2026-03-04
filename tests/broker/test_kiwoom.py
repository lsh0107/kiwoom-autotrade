"""키움증권 REST API 클라이언트 테스트 (respx mock)."""

from datetime import UTC, datetime, timedelta

import pytest
import respx
from httpx import Response
from src.broker.constants import API_IDS, ENDPOINTS, TOKEN_REFRESH_BUFFER_SECONDS
from src.broker.kiwoom import KiwoomClient, _mask, _parse_expires_dt
from src.broker.schemas import (
    CancelRequest,
    OrderRequest,
    OrderSideEnum,
    OrderTypeEnum,
    TokenInfo,
    from_kiwoom_symbol,
    to_kiwoom_symbol,
)
from src.utils.exceptions import BrokerAuthError, BrokerError, BrokerRateLimitError

MOCK_BASE_URL = "https://mockapi.kiwoom.com"


@pytest.fixture
def kiwoom_client() -> KiwoomClient:
    """테스트용 키움 클라이언트."""
    return KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key="test_app_key",
        app_secret="test_app_secret",
        is_mock=True,
    )


def _mock_token() -> respx.Route:
    """토큰 발급 mock 헬퍼."""
    return respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
        return_value=Response(
            200,
            json={
                "token": "test_access_token",
                "token_type": "Bearer",
                "expires_dt": "20260306000000",
            },
        )
    )


class TestParseExpiresDt:
    """_parse_expires_dt 유틸 테스트."""

    def test_parse_full_datetime(self) -> None:
        """14자리 YYYYMMDDHHMMSS 파싱."""
        result = _parse_expires_dt("20260306120000")
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 6
        assert result.hour == 12

    def test_parse_date_only(self) -> None:
        """8자리 YYYYMMDD 파싱."""
        result = _parse_expires_dt("20260306")
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 6
        assert result.hour == 0


class TestSymbolConversion:
    """종목코드 변환 유틸 테스트."""

    def test_to_kiwoom_symbol_plain(self) -> None:
        """6자리 → KRX:005930."""
        assert to_kiwoom_symbol("005930") == "KRX:005930"

    def test_to_kiwoom_symbol_already_formatted(self) -> None:
        """이미 키움 형식이면 그대로."""
        assert to_kiwoom_symbol("KRX:005930") == "KRX:005930"

    def test_to_kiwoom_symbol_custom_exchange(self) -> None:
        """커스텀 거래소."""
        assert to_kiwoom_symbol("005930", "KOSDAQ") == "KOSDAQ:005930"

    def test_from_kiwoom_symbol(self) -> None:
        """KRX:005930 → 005930."""
        assert from_kiwoom_symbol("KRX:005930") == "005930"

    def test_from_kiwoom_symbol_plain(self) -> None:
        """6자리 그대로."""
        assert from_kiwoom_symbol("005930") == "005930"


class TestAuthenticate:
    """토큰 발급 테스트."""

    @respx.mock
    async def test_authenticate_success(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 발급 성공."""
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "token": "test_access_token_abc123",
                    "token_type": "Bearer",
                    "expires_dt": "20260306120000",
                },
            )
        )

        token_info = await kiwoom_client.authenticate()

        assert token_info.access_token == "test_access_token_abc123"
        assert token_info.token_type == "Bearer"
        assert token_info.expires_at.year == 2026

        await kiwoom_client.close()

    @respx.mock
    async def test_authenticate_with_expires_in_fallback(self, kiwoom_client: KiwoomClient) -> None:
        """expires_dt 없이 expires_in으로 폴백."""
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        token_info = await kiwoom_client.authenticate()
        assert token_info.access_token == "test_token"
        assert token_info.expires_at > datetime.now(UTC)

        await kiwoom_client.close()

    @respx.mock
    async def test_authenticate_failure(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 발급 실패 (401)."""
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                401,
                json={
                    "error_message": "Invalid appkey or secretkey",
                },
            )
        )

        with pytest.raises(BrokerAuthError, match="토큰 발급 실패"):
            await kiwoom_client.authenticate()

        await kiwoom_client.close()

    @respx.mock
    async def test_authenticate_request_headers(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 요청에 api-id 헤더 포함 확인."""
        route = respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "token": "test_token",
                    "token_type": "Bearer",
                    "expires_dt": "20260306000000",
                },
            )
        )

        await kiwoom_client.authenticate()

        assert route.called
        request = route.calls[0].request
        assert request.headers["api-id"] == API_IDS["token"]

        await kiwoom_client.close()

    @respx.mock
    async def test_authenticate_request_body(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 요청 바디에 secretkey 포함 확인."""
        import json

        route = respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "token": "test_token",
                    "token_type": "Bearer",
                    "expires_dt": "20260306000000",
                },
            )
        )

        await kiwoom_client.authenticate()

        request = route.calls[0].request
        body = json.loads(request.content)
        assert body["secretkey"] == "test_app_secret"
        assert body["appkey"] == "test_app_key"
        assert "appsecret" not in body

        await kiwoom_client.close()


class TestGetQuote:
    """시세 조회 테스트."""

    @respx.mock
    async def test_get_quote_success(self, kiwoom_client: KiwoomClient) -> None:
        """현재가 정상 조회."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={
                    "stk_nm": "삼성전자",
                    "cur_prc": "70000",
                    "pred_close_pric": "69000",
                },
            )
        )

        quote = await kiwoom_client.get_quote("005930")

        assert quote.symbol == "005930"
        assert quote.name == "삼성전자"
        assert quote.price == 70000
        assert quote.prev_close == 69000
        assert quote.change == 1000
        assert quote.change_pct == pytest.approx(1.45, abs=0.01)
        # ka10007에 없는 필드들은 0
        assert quote.volume == 0
        assert quote.high == 0
        assert quote.low == 0
        assert quote.open == 0

        await kiwoom_client.close()

    @respx.mock
    async def test_get_quote_request_format(self, kiwoom_client: KiwoomClient) -> None:
        """시세 조회가 POST + api-id 헤더로 요청되는지 확인."""
        _mock_token()

        import json

        route = respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={
                    "stk_nm": "삼성전자",
                    "cur_prc": "70000",
                    "pred_close_pric": "69000",
                },
            )
        )

        await kiwoom_client.get_quote("005930")

        request = route.calls[0].request
        assert request.headers["api-id"] == API_IDS["quote"]
        assert "Bearer" in request.headers["authorization"]
        body = json.loads(request.content)
        assert body["stk_cd"] == "KRX:005930"
        # KIS 헤더가 없는지 확인
        assert "appkey" not in request.headers
        assert "appsecret" not in request.headers
        assert "tr_id" not in request.headers

        await kiwoom_client.close()


class TestGetOrderbook:
    """호가 조회 테스트."""

    @respx.mock
    async def test_get_orderbook_success(self, kiwoom_client: KiwoomClient) -> None:
        """호가 정상 조회."""
        _mock_token()

        orderbook_data = {
            "sel_1st_pre_bid": "70100",
            "sel_1st_pre_req": "500",
            "sel_2nd_pre_bid": "70200",
            "sel_2nd_pre_req": "300",
            "buy_1st_pre_bid": "70000",
            "buy_1st_pre_req": "1000",
            "buy_2nd_pre_bid": "69900",
            "buy_2nd_pre_req": "800",
        }

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(200, json=orderbook_data)
        )

        orderbook = await kiwoom_client.get_orderbook("005930")

        assert orderbook.symbol == "005930"
        assert len(orderbook.asks) == 2
        assert orderbook.asks[0].price == 70100
        assert orderbook.asks[0].quantity == 500
        assert orderbook.asks[1].price == 70200
        assert len(orderbook.bids) == 2
        assert orderbook.bids[0].price == 70000
        assert orderbook.bids[0].quantity == 1000

        await kiwoom_client.close()


class TestPlaceOrder:
    """주문 실행 테스트."""

    @respx.mock
    async def test_place_order_buy(self, kiwoom_client: KiwoomClient) -> None:
        """매수 주문 정상 접수."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['order']}").mock(
            return_value=Response(
                200,
                json={
                    "ord_no": "0000012345",
                    "dmst_stex_tp": "KRX",
                },
            )
        )

        order_req = OrderRequest(
            symbol="005930",
            side=OrderSideEnum.BUY,
            price=70000,
            quantity=10,
            order_type=OrderTypeEnum.LIMIT,
        )

        result = await kiwoom_client.place_order(order_req)

        assert result.order_no == "0000012345"
        assert result.symbol == "005930"
        assert result.side == OrderSideEnum.BUY
        assert result.status == "submitted"

        await kiwoom_client.close()

    @respx.mock
    async def test_place_order_sell(self, kiwoom_client: KiwoomClient) -> None:
        """매도 주문 정상 접수."""
        _mock_token()

        import json

        route = respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['order']}").mock(
            return_value=Response(
                200,
                json={
                    "ord_no": "0000012346",
                    "dmst_stex_tp": "KRX",
                },
            )
        )

        order_req = OrderRequest(
            symbol="005930",
            side=OrderSideEnum.SELL,
            price=71000,
            quantity=5,
            order_type=OrderTypeEnum.LIMIT,
        )

        result = await kiwoom_client.place_order(order_req)

        assert result.order_no == "0000012346"
        assert result.side == OrderSideEnum.SELL

        # api-id가 매도용인지 확인
        request = route.calls[0].request
        assert request.headers["api-id"] == API_IDS["sell"]
        body = json.loads(request.content)
        assert body["stk_cd"] == "KRX:005930"
        assert body["trde_tp"] == "sell"
        # KIS 필드 없음 확인
        assert "CANO" not in body
        assert "ACNT_PRDT_CD" not in body

        await kiwoom_client.close()

    @respx.mock
    async def test_place_order_market(self, kiwoom_client: KiwoomClient) -> None:
        """시장가 주문 시 cond_uv=3."""
        _mock_token()

        import json

        route = respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['order']}").mock(
            return_value=Response(
                200,
                json={"ord_no": "0000012347", "dmst_stex_tp": "KRX"},
            )
        )

        order_req = OrderRequest(
            symbol="005930",
            side=OrderSideEnum.BUY,
            price=0,
            quantity=10,
            order_type=OrderTypeEnum.MARKET,
        )

        await kiwoom_client.place_order(order_req)

        body = json.loads(route.calls[0].request.content)
        assert body["cond_uv"] == "3"

        await kiwoom_client.close()


class TestCancelOrder:
    """주문 취소 테스트."""

    @respx.mock
    async def test_cancel_order(self, kiwoom_client: KiwoomClient) -> None:
        """주문 취소 정상 처리."""
        _mock_token()

        import json

        route = respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['order']}").mock(
            return_value=Response(
                200,
                json={
                    "ord_no": "0000098765",
                    "base_orig_ord_no": "0000012345",
                    "cncl_qty": "5",
                },
            )
        )

        cancel_req = CancelRequest(
            order_no="0000012345",
            symbol="005930",
            quantity=5,
        )

        result = await kiwoom_client.cancel_order(cancel_req)

        assert result.order_no == "0000098765"
        assert result.original_order_no == "0000012345"
        assert result.status == "cancelled"

        # 요청 바디 검증
        body = json.loads(route.calls[0].request.content)
        assert body["orig_ord_no"] == "0000012345"
        assert body["stk_cd"] == "KRX:005930"
        assert body["cncl_qty"] == "5"
        assert route.calls[0].request.headers["api-id"] == API_IDS["cancel"]

        await kiwoom_client.close()


class TestGetBalance:
    """잔고 조회 테스트."""

    @respx.mock
    async def test_get_balance_success(self, kiwoom_client: KiwoomClient) -> None:
        """잔고 정상 조회 (ka10085 + kt00005 조합)."""
        _mock_token()

        # 2개의 POST 요청을 순서대로 mock (ka10085 → kt00005)
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['account']}").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "stocks": [
                            {
                                "stk_cd": "KRX:005930",
                                "stk_nm": "삼성전자",
                                "cur_prc": "70000",
                                "pur_pric": "65000",
                                "rmnd_qty": "10",
                                "pur_amt": "650000",
                            }
                        ]
                    },
                ),
                Response(
                    200,
                    json={
                        "ord_alowa": "5000000",
                    },
                ),
            ]
        )

        balance = await kiwoom_client.get_balance()

        assert len(balance.holdings) == 1
        assert balance.holdings[0].symbol == "005930"
        assert balance.holdings[0].name == "삼성전자"
        assert balance.holdings[0].quantity == 10
        assert balance.holdings[0].avg_price == 65000
        assert balance.holdings[0].current_price == 70000
        assert balance.holdings[0].eval_amount == 700000
        assert balance.holdings[0].profit == 50000
        assert balance.available_cash == 5000000

        await kiwoom_client.close()

    @respx.mock
    async def test_get_balance_empty(self, kiwoom_client: KiwoomClient) -> None:
        """보유종목 없는 경우."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['account']}").mock(
            side_effect=[
                Response(200, json={"stocks": []}),
                Response(200, json={"ord_alowa": "10000000"}),
            ]
        )

        balance = await kiwoom_client.get_balance()

        assert len(balance.holdings) == 0
        assert balance.available_cash == 10000000

        await kiwoom_client.close()

    @respx.mock
    async def test_get_holdings(self, kiwoom_client: KiwoomClient) -> None:
        """get_holdings는 get_balance의 holdings만 반환."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['account']}").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "stocks": [
                            {
                                "stk_cd": "KRX:005930",
                                "stk_nm": "삼성전자",
                                "cur_prc": "70000",
                                "pur_pric": "65000",
                                "rmnd_qty": "10",
                                "pur_amt": "650000",
                            }
                        ]
                    },
                ),
                Response(200, json={"ord_alowa": "5000000"}),
            ]
        )

        holdings = await kiwoom_client.get_holdings()

        assert len(holdings) == 1
        assert holdings[0].symbol == "005930"

        await kiwoom_client.close()


class TestGetDailyPrice:
    """일봉 데이터 조회 테스트."""

    @respx.mock
    async def test_get_daily_price(self, kiwoom_client: KiwoomClient) -> None:
        """일봉 데이터 정상 조회."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={
                    "daly_stkpc": [
                        {
                            "date": "20260303",
                            "open_pric": "69500",
                            "high_pric": "71000",
                            "low_pric": "69000",
                            "close_pric": "70000",
                            "trde_qty": "10000000",
                            "flu_rt": "1.45",
                        },
                        {
                            "date": "20260302",
                            "open_pric": "68000",
                            "high_pric": "69500",
                            "low_pric": "67500",
                            "close_pric": "69000",
                            "trde_qty": "8000000",
                            "flu_rt": "-0.72",
                        },
                    ]
                },
            )
        )

        result = await kiwoom_client.get_daily_price("005930")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["date"] == "20260303"
        assert result[0]["close_pric"] == "70000"
        assert result[1]["date"] == "20260302"

        await kiwoom_client.close()

    @respx.mock
    async def test_get_daily_price_request_body(self, kiwoom_client: KiwoomClient) -> None:
        """일봉 요청 바디에 stk_cd가 키움 형식인지 확인."""
        _mock_token()

        import json

        route = respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(200, json={"daly_stkpc": []})
        )

        await kiwoom_client.get_daily_price("005930")

        body = json.loads(route.calls[0].request.content)
        assert body["stk_cd"] == "KRX:005930"
        assert route.calls[0].request.headers["api-id"] == API_IDS["daily_price"]

        await kiwoom_client.close()


class TestTokenRefresh:
    """토큰 만료 시 자동 갱신 테스트."""

    @respx.mock
    async def test_token_refresh(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 만료 임박 시 자동 갱신."""
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "token": "old_token",
                        "token_type": "Bearer",
                        "expires_dt": "20260306000000",
                    },
                ),
                Response(
                    200,
                    json={
                        "token": "new_token",
                        "token_type": "Bearer",
                        "expires_dt": "20260307000000",
                    },
                ),
            ]
        )

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={
                    "stk_nm": "삼성전자",
                    "cur_prc": "70000",
                    "pred_close_pric": "69000",
                },
            )
        )

        # 첫 인증
        await kiwoom_client.authenticate()
        assert kiwoom_client._token is not None
        assert kiwoom_client._token.access_token == "old_token"

        # 토큰 만료 시간을 임박하게 설정
        kiwoom_client._token = TokenInfo(
            access_token="old_token",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(seconds=TOKEN_REFRESH_BUFFER_SECONDS - 10),
        )

        # API 호출 시 자동 갱신
        await kiwoom_client.get_quote("005930")

        assert kiwoom_client._token.access_token == "new_token"

        await kiwoom_client.close()

    @respx.mock
    async def test_token_no_refresh_when_valid(self, kiwoom_client: KiwoomClient) -> None:
        """토큰이 유효할 때 갱신하지 않음."""
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "token": "valid_token",
                    "token_type": "Bearer",
                    "expires_dt": "20260306000000",
                },
            )
        )

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={
                    "stk_nm": "삼성전자",
                    "cur_prc": "70000",
                    "pred_close_pric": "70000",
                },
            )
        )

        # 유효한 토큰 수동 설정
        kiwoom_client._token = TokenInfo(
            access_token="valid_token",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(hours=23),
        )

        await kiwoom_client.get_quote("005930")

        assert kiwoom_client._token.access_token == "valid_token"

        await kiwoom_client.close()


class TestErrorHandling:
    """에러 처리 테스트."""

    @respx.mock
    async def test_rate_limit_http_429(self, kiwoom_client: KiwoomClient) -> None:
        """HTTP 429 응답 시 BrokerRateLimitError 발생."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                429,
                json={"error_code": "1700", "error_message": "요청 한도 초과"},
            )
        )

        with pytest.raises(BrokerRateLimitError):
            await kiwoom_client.get_quote("005930")

        await kiwoom_client.close()

    @respx.mock
    async def test_rate_limit_error_code(self, kiwoom_client: KiwoomClient) -> None:
        """에러 코드 1700 시 BrokerRateLimitError 발생."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={"error_code": "1700", "error_message": "초당 거래 건수를 초과하였습니다"},
            )
        )

        with pytest.raises(BrokerRateLimitError):
            await kiwoom_client.get_quote("005930")

        await kiwoom_client.close()

    @respx.mock
    async def test_invalid_token_error(self, kiwoom_client: KiwoomClient) -> None:
        """에러 코드 8005 시 BrokerAuthError 발생."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={"error_code": "8005", "error_message": "유효하지 않은 토큰"},
            )
        )

        with pytest.raises(BrokerAuthError, match="토큰 오류"):
            await kiwoom_client.get_quote("005930")

        await kiwoom_client.close()

    @respx.mock
    async def test_generic_api_error(self, kiwoom_client: KiwoomClient) -> None:
        """일반 에러 코드 시 BrokerError 발생."""
        _mock_token()

        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['market']}").mock(
            return_value=Response(
                200,
                json={"error_code": "9999", "error_message": "유효하지 않은 종목코드"},
            )
        )

        with pytest.raises(BrokerError, match="유효하지 않은 종목코드"):
            await kiwoom_client.get_quote("INVALID")

        await kiwoom_client.close()


class TestMaskFunction:
    """_mask 유틸 함수 테스트."""

    def test_mask_long_string(self) -> None:
        """긴 문자열 마스킹."""
        result = _mask("test_app_key_12345")
        assert result == "test**************"

    def test_mask_short_string(self) -> None:
        """짧은 문자열 전체 마스킹."""
        result = _mask("abc")
        assert result == "***"

    def test_mask_exact_visible(self) -> None:
        """visible 길이와 같은 문자열."""
        result = _mask("abcd")
        assert result == "****"
