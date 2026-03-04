"""키움증권 REST API 클라이언트 테스트 (respx mock)."""

import pytest
import respx
from httpx import Response
from src.broker.constants import ENDPOINTS
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import OrderRequest, OrderSideEnum, OrderTypeEnum
from src.utils.exceptions import BrokerAuthError

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
