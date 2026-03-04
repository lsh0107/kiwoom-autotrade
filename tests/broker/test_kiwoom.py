"""키움증권 REST API 클라이언트 테스트 (respx mock)."""

from datetime import UTC, datetime, timedelta

import pytest
import respx
from httpx import Response
from src.broker.constants import ENDPOINTS, TOKEN_REFRESH_BUFFER_SECONDS
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import (
    CancelRequest,
    OrderRequest,
    OrderSideEnum,
    OrderTypeEnum,
    TokenInfo,
)
from src.utils.exceptions import BrokerAuthError, BrokerError, BrokerRateLimitError

MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"


@pytest.fixture
def kiwoom_client() -> KiwoomClient:
    """테스트용 키움 클라이언트."""
    return KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key="test_app_key",
        app_secret="test_app_secret",
        account_no="1234567890",
        is_mock=True,
    )


class TestAuthenticate:
    """토큰 발급 테스트."""

    @respx.mock
    async def test_authenticate_success(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 발급 성공."""
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_access_token_abc123",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        token_info = await kiwoom_client.authenticate()

        assert token_info.access_token == "test_access_token_abc123"
        assert token_info.token_type == "Bearer"
        assert token_info.expires_at is not None

        await kiwoom_client.close()

    @respx.mock
    async def test_authenticate_failure(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 발급 실패 (401)."""
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                401,
                json={
                    "error_description": "Invalid appkey or appsecret",
                },
            )
        )

        with pytest.raises(BrokerAuthError, match="토큰 발급 실패"):
            await kiwoom_client.authenticate()

        await kiwoom_client.close()


class TestGetQuote:
    """시세 조회 테스트."""

    @respx.mock
    async def test_get_quote_success(self, kiwoom_client: KiwoomClient) -> None:
        """현재가 정상 조회."""
        # 토큰 먼저 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        # 시세 조회 mock
        respx.get(f"{MOCK_BASE_URL}{ENDPOINTS['quote']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상",
                    "output": {
                        "hts_kor_isnm": "삼성전자",
                        "stck_prpr": "70000",
                        "prdy_vrss": "1000",
                        "prdy_ctrt": "1.45",
                        "acml_vol": "10000000",
                        "stck_hgpr": "71000",
                        "stck_lwpr": "69000",
                        "stck_oprc": "69500",
                        "stck_sdpr": "69000",
                    },
                },
            )
        )

        quote = await kiwoom_client.get_quote("005930")

        assert quote.symbol == "005930"
        assert quote.name == "삼성전자"
        assert quote.price == 70000
        assert quote.change == 1000
        assert quote.change_pct == 1.45
        assert quote.volume == 10000000
        assert quote.prev_close == 69000

        await kiwoom_client.close()


class TestPlaceOrder:
    """주문 실행 테스트."""

    @respx.mock
    async def test_place_order_success(self, kiwoom_client: KiwoomClient) -> None:
        """주문 정상 접수."""
        # 토큰 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        # 주문 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['order']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "주문 접수 완료",
                    "output": {
                        "ODNO": "0000012345",
                        "KRX_FWDG_ORD_ORGNO": "",
                    },
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


class TestGetBalance:
    """잔고 조회 테스트."""

    @respx.mock
    async def test_get_balance_success(self, kiwoom_client: KiwoomClient) -> None:
        """잔고 정상 조회."""
        # 토큰 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        # 잔고 mock
        respx.get(f"{MOCK_BASE_URL}{ENDPOINTS['balance']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상",
                    "output1": [
                        {
                            "pdno": "005930",
                            "prdt_name": "삼성전자",
                            "hldg_qty": "10",
                            "pchs_avg_pric": "65000.00",
                            "prpr": "70000",
                            "evlu_amt": "700000",
                            "evlu_pfls_amt": "50000",
                            "evlu_pfls_rt": "7.69",
                        }
                    ],
                    "output2": [
                        {
                            "tot_evlu_amt": "10000000",
                            "evlu_pfls_smtl_amt": "500000",
                            "dnca_tot_amt": "5000000",
                            "pchs_amt_smtl_amt": "9500000",
                        }
                    ],
                },
            )
        )

        balance = await kiwoom_client.get_balance()

        assert balance.total_eval == 10000000
        assert balance.total_profit == 500000
        assert balance.available_cash == 5000000
        assert len(balance.holdings) == 1
        assert balance.holdings[0].symbol == "005930"
        assert balance.holdings[0].name == "삼성전자"
        assert balance.holdings[0].quantity == 10
        assert balance.holdings[0].avg_price == 65000
        assert balance.holdings[0].current_price == 70000

        await kiwoom_client.close()


class TestTokenRefresh:
    """토큰 만료 시 자동 갱신 테스트."""

    @respx.mock
    async def test_token_refresh(self, kiwoom_client: KiwoomClient) -> None:
        """토큰 만료 임박 시 자동 갱신."""
        # 첫 번째 토큰 (곧 만료)
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "access_token": "old_token",
                        "token_type": "Bearer",
                        "expires_in": 86400,
                    },
                ),
                Response(
                    200,
                    json={
                        "access_token": "new_token",
                        "token_type": "Bearer",
                        "expires_in": 86400,
                    },
                ),
            ]
        )

        # 시세 조회 mock
        respx.get(f"{MOCK_BASE_URL}{ENDPOINTS['quote']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상",
                    "output": {
                        "hts_kor_isnm": "삼성전자",
                        "stck_prpr": "70000",
                        "prdy_vrss": "1000",
                        "prdy_ctrt": "1.45",
                        "acml_vol": "10000000",
                        "stck_hgpr": "71000",
                        "stck_lwpr": "69000",
                        "stck_oprc": "69500",
                        "stck_sdpr": "69000",
                    },
                },
            )
        )

        # 첫 번째 인증 (토큰 없을 때)
        await kiwoom_client.authenticate()
        assert kiwoom_client._token is not None
        assert kiwoom_client._token.access_token == "old_token"

        # 토큰 만료 시간을 임박하게 설정 (버퍼 이내)
        kiwoom_client._token = TokenInfo(
            access_token="old_token",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(seconds=TOKEN_REFRESH_BUFFER_SECONDS - 10),
        )

        # API 호출 시 자동 갱신
        await kiwoom_client.get_quote("005930")

        # 토큰이 갱신되었는지 확인
        assert kiwoom_client._token.access_token == "new_token"

        await kiwoom_client.close()

    @respx.mock
    async def test_token_no_refresh_when_valid(self, kiwoom_client: KiwoomClient) -> None:
        """토큰이 유효할 때 갱신하지 않음."""
        # 토큰 발급 1회만 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "valid_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        respx.get(f"{MOCK_BASE_URL}{ENDPOINTS['quote']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상",
                    "output": {
                        "hts_kor_isnm": "삼성전자",
                        "stck_prpr": "70000",
                        "prdy_vrss": "0",
                        "prdy_ctrt": "0",
                        "acml_vol": "0",
                        "stck_hgpr": "70000",
                        "stck_lwpr": "70000",
                        "stck_oprc": "70000",
                        "stck_sdpr": "70000",
                    },
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

        # 토큰이 변경되지 않았는지 확인
        assert kiwoom_client._token.access_token == "valid_token"

        await kiwoom_client.close()


class TestGetDailyPrice:
    """일봉 데이터 조회 테스트."""

    @respx.mock
    async def test_get_daily_price(self, kiwoom_client: KiwoomClient) -> None:
        """일봉 데이터 정상 조회."""
        # 토큰 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        # 일봉 mock
        respx.get(f"{MOCK_BASE_URL}{ENDPOINTS['daily_price']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상",
                    "output2": [
                        {
                            "stck_bsop_date": "20260303",
                            "stck_oprc": "69500",
                            "stck_hgpr": "71000",
                            "stck_lwpr": "69000",
                            "stck_clpr": "70000",
                            "acml_vol": "10000000",
                        },
                        {
                            "stck_bsop_date": "20260302",
                            "stck_oprc": "68000",
                            "stck_hgpr": "69500",
                            "stck_lwpr": "67500",
                            "stck_clpr": "69000",
                            "acml_vol": "8000000",
                        },
                    ],
                },
            )
        )

        result = await kiwoom_client.get_daily_price("005930")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["stck_bsop_date"] == "20260303"
        assert result[0]["stck_clpr"] == "70000"
        assert result[1]["stck_bsop_date"] == "20260302"

        await kiwoom_client.close()


class TestCancelOrder:
    """주문 취소 테스트."""

    @respx.mock
    async def test_cancel_order(self, kiwoom_client: KiwoomClient) -> None:
        """주문 취소 정상 처리."""
        # 토큰 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        # 취소 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['cancel']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "주문 취소 완료",
                    "output": {
                        "ODNO": "0000098765",
                    },
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

        await kiwoom_client.close()


class TestRateLimit:
    """레이트 리밋 동작 테스트."""

    @respx.mock
    async def test_rate_limit_429(self, kiwoom_client: KiwoomClient) -> None:
        """429 응답 시 BrokerRateLimitError 발생."""
        # 토큰 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        # 시세 조회 429 응답
        respx.get(f"{MOCK_BASE_URL}{ENDPOINTS['quote']}").mock(
            return_value=Response(
                429,
                json={
                    "rt_cd": "1",
                    "msg1": "요청 한도 초과",
                },
            )
        )

        with pytest.raises(BrokerRateLimitError):
            await kiwoom_client.get_quote("005930")

        await kiwoom_client.close()

    @respx.mock
    async def test_api_error_response(self, kiwoom_client: KiwoomClient) -> None:
        """rt_cd != '0' 시 BrokerError 발생."""
        # 토큰 mock
        respx.post(f"{MOCK_BASE_URL}{ENDPOINTS['token']}").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        )

        # 에러 응답
        respx.get(f"{MOCK_BASE_URL}{ENDPOINTS['quote']}").mock(
            return_value=Response(
                200,
                json={
                    "rt_cd": "1",
                    "msg_cd": "EGW00123",
                    "msg1": "유효하지 않은 종목코드",
                },
            )
        )

        with pytest.raises(BrokerError, match="유효하지 않은 종목코드"):
            await kiwoom_client.get_quote("INVALID")

        await kiwoom_client.close()


class TestMaskFunction:
    """_mask 유틸 함수 테스트."""

    def test_mask_long_string(self) -> None:
        """긴 문자열 마스킹."""
        from src.broker.kiwoom import _mask

        result = _mask("test_app_key_12345")
        assert result == "test**************"

    def test_mask_short_string(self) -> None:
        """짧은 문자열 전체 마스킹."""
        from src.broker.kiwoom import _mask

        result = _mask("abc")
        assert result == "***"

    def test_mask_exact_visible(self) -> None:
        """visible 길이와 같은 문자열."""
        from src.broker.kiwoom import _mask

        result = _mask("abcd")
        assert result == "****"
