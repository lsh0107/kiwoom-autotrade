"""키움증권 REST API 클라이언트."""

from datetime import UTC, datetime, timedelta

import httpx
import structlog
from aiolimiter import AsyncLimiter

from src.broker.constants import (
    ENDPOINTS,
    MOCK_RATE_LIMIT,
    MOCK_TR_IDS,
    ORDER_TYPE_CODES,
    REAL_RATE_LIMIT,
    REAL_TR_IDS,
    TOKEN_REFRESH_BUFFER_SECONDS,
)
from src.broker.schemas import (
    AccountBalance,
    CancelRequest,
    CancelResponse,
    Holding,
    Orderbook,
    OrderRequest,
    OrderResponse,
    PriceLevel,
    Quote,
    TokenInfo,
)
from src.utils.exceptions import BrokerAuthError, BrokerError, BrokerRateLimitError

logger = structlog.get_logger("broker.kiwoom")


def _mask(value: str, visible: int = 4) -> str:
    """민감 정보 마스킹."""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


class KiwoomClient:
    """키움증권 REST API 클라이언트.

    httpx.AsyncClient 기반, 토큰 자동 갱신, 레이트 리밋 적용.
    """

    def __init__(
        self,
        *,
        base_url: str,
        app_key: str,
        app_secret: str,
        account_no: str,
        account_product_code: str = "01",
        is_mock: bool = True,
    ) -> None:
        """클라이언트 초기화.

        Args:
            base_url: 키움 API 베이스 URL
            app_key: 앱 키
            app_secret: 앱 시크릿
            account_no: 계좌번호
            account_product_code: 계좌 상품코드 (기본 "01")
            is_mock: 모의투자 여부
        """
        self._base_url = base_url
        self._app_key = app_key
        self._app_secret = app_secret
        self._account_no = account_no
        self._account_product_code = account_product_code
        self._is_mock = is_mock

        # 토큰 관리
        self._token: TokenInfo | None = None

        # tr_id 매핑 (모의 vs 실거래)
        self._tr_ids = MOCK_TR_IDS if is_mock else REAL_TR_IDS

        # 레이트 리밋 (모의: 5/s, 실거래: 20/s)
        rate = MOCK_RATE_LIMIT if is_mock else REAL_RATE_LIMIT
        self._limiter = AsyncLimiter(rate, 1.0)

        # httpx 비동기 클라이언트
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

        logger.info(
            "키움 클라이언트 초기화",
            base_url=base_url,
            app_key=_mask(app_key),
            account_no=_mask(account_no),
            is_mock=is_mock,
            rate_limit=rate,
        )

    async def close(self) -> None:
        """HTTP 클라이언트를 닫는다."""
        await self._client.aclose()

    # ── 인증 ──────────────────────────────────────────

    async def authenticate(self) -> TokenInfo:
        """토큰 발급 (POST /oauth2/tokenP).

        Returns:
            TokenInfo: 발급된 토큰 정보
        """
        url = ENDPOINTS["token"]
        body = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }

        logger.info("토큰 발급 요청", url=url, app_key=_mask(self._app_key))

        response = await self._client.post(url, json=body)
        data = response.json()

        if response.status_code != 200:
            msg = data.get("error_description", data.get("msg1", "토큰 발급 실패"))
            logger.error("토큰 발급 실패", status=response.status_code, error=msg)
            raise BrokerAuthError(f"토큰 발급 실패: {msg}")

        expires_in = int(data.get("expires_in", 86400))
        token_info = TokenInfo(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        self._token = token_info

        logger.info(
            "토큰 발급 성공",
            expires_at=token_info.expires_at.isoformat(),
            token_prefix=_mask(token_info.access_token, 8),
        )

        return token_info

    async def _ensure_token(self) -> str:
        """유효한 토큰을 보장한다. 만료 5분 전이면 자동 갱신.

        Returns:
            str: 액세스 토큰
        """
        if self._token is None:
            await self.authenticate()
            assert self._token is not None
            return self._token.access_token

        buffer = timedelta(seconds=TOKEN_REFRESH_BUFFER_SECONDS)
        if datetime.now(UTC) >= self._token.expires_at - buffer:
            logger.info("토큰 만료 임박, 갱신 시작")
            await self.authenticate()

        assert self._token is not None
        return self._token.access_token

    def _common_headers(self, tr_id: str, token: str) -> dict[str, str]:
        """공통 요청 헤더를 생성한다."""
        return {
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "custtype": "P",
            "content-type": "application/json; charset=utf-8",
        }

    async def _request(
        self,
        method: str,
        url: str,
        tr_id: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """공통 API 요청 처리 (레이트 리밋 + 에러 핸들링).

        Args:
            method: HTTP 메서드 (GET, POST)
            url: API 경로
            tr_id: 거래 ID
            params: 쿼리 파라미터
            json_body: JSON 바디

        Returns:
            dict: 응답 JSON
        """
        token = await self._ensure_token()
        headers = self._common_headers(tr_id, token)

        async with self._limiter:
            logger.debug(
                "API 요청",
                method=method,
                url=url,
                tr_id=tr_id,
            )

            if method.upper() == "GET":
                response = await self._client.get(url, headers=headers, params=params)
            else:
                response = await self._client.post(url, headers=headers, json=json_body)

        data = response.json()

        # 레이트 리밋 응답 체크
        if response.status_code == 429:
            logger.warning("레이트 리밋 초과", url=url, tr_id=tr_id)
            raise BrokerRateLimitError

        # 키움 API 에러 체크 (rt_cd != "0")
        rt_cd = data.get("rt_cd", "")
        if rt_cd != "0":
            msg = data.get("msg1", "알 수 없는 오류")
            msg_cd = data.get("msg_cd", "")
            logger.error(
                "API 오류 응답",
                url=url,
                tr_id=tr_id,
                rt_cd=rt_cd,
                msg_cd=msg_cd,
                msg=msg,
            )
            raise BrokerError(f"[{msg_cd}] {msg}")

        return data

    # ── 시세 조회 ────────────────────────────────────

    async def get_quote(self, symbol: str) -> Quote:
        """종목 현재가 조회.

        Args:
            symbol: 종목코드 (6자리)

        Returns:
            Quote: 현재가 정보
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
        }

        data = await self._request(
            "GET",
            ENDPOINTS["quote"],
            self._tr_ids["quote"],
            params=params,
        )

        output = data.get("output", {})

        return Quote(
            symbol=symbol,
            name=output.get("hts_kor_isnm", ""),
            price=int(output.get("stck_prpr", 0)),
            change=int(output.get("prdy_vrss", 0)),
            change_pct=float(output.get("prdy_ctrt", 0)),
            volume=int(output.get("acml_vol", 0)),
            high=int(output.get("stck_hgpr", 0)),
            low=int(output.get("stck_lwpr", 0)),
            open=int(output.get("stck_oprc", 0)),
            prev_close=int(output.get("stck_sdpr", 0)),
        )

    async def get_orderbook(self, symbol: str) -> Orderbook:
        """종목 호가 조회.

        Args:
            symbol: 종목코드

        Returns:
            Orderbook: 호가 정보 (매도 10단계, 매수 10단계)
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
        }

        data = await self._request(
            "GET",
            ENDPOINTS["orderbook"],
            self._tr_ids["orderbook"],
            params=params,
        )

        output = data.get("output1", {})

        # 매도호가 (askp1~askp10, askp_rsqn1~askp_rsqn10) - 가격 오름차순
        asks: list[PriceLevel] = []
        for i in range(1, 11):
            price = int(output.get(f"askp{i}", 0))
            qty = int(output.get(f"askp_rsqn{i}", 0))
            if price > 0:
                asks.append(PriceLevel(price=price, quantity=qty))

        # 매수호가 (bidp1~bidp10, bidp_rsqn1~bidp_rsqn10) - 가격 내림차순
        bids: list[PriceLevel] = []
        for i in range(1, 11):
            price = int(output.get(f"bidp{i}", 0))
            qty = int(output.get(f"bidp_rsqn{i}", 0))
            if price > 0:
                bids.append(PriceLevel(price=price, quantity=qty))

        return Orderbook(symbol=symbol, asks=asks, bids=bids)

    # ── 주문 ─────────────────────────────────────────

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """주문 실행 (매수/매도).

        Args:
            order: 주문 요청

        Returns:
            OrderResponse: 주문 결과
        """
        # tr_id 선택 (매수/매도)
        tr_key = "buy" if order.side.value == "BUY" else "sell"
        tr_id = self._tr_ids[tr_key]

        # 주문 유형 코드
        ord_dvsn = ORDER_TYPE_CODES.get(order.order_type.value, "00")

        body = {
            "CANO": self._account_no[:8],
            "ACNT_PRDT_CD": self._account_product_code,
            "PDNO": order.symbol,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(order.quantity),
            "ORD_UNPR": str(order.price),
        }

        logger.info(
            "주문 요청",
            symbol=order.symbol,
            side=order.side.value,
            price=order.price,
            quantity=order.quantity,
            order_type=order.order_type.value,
            tr_id=tr_id,
        )

        data = await self._request(
            "POST",
            ENDPOINTS["order"],
            tr_id,
            json_body=body,
        )

        output = data.get("output", {})
        order_no = output.get("ODNO", output.get("KRX_FWDG_ORD_ORGNO", ""))

        result = OrderResponse(
            order_no=order_no,
            symbol=order.symbol,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            status="submitted",
            message=data.get("msg1", ""),
        )

        logger.info(
            "주문 접수 완료",
            order_no=order_no,
            symbol=order.symbol,
            side=order.side.value,
        )

        return result

    async def cancel_order(self, cancel: CancelRequest) -> CancelResponse:
        """주문 취소.

        Args:
            cancel: 취소 요청

        Returns:
            CancelResponse: 취소 결과
        """
        tr_id = self._tr_ids["cancel"]

        body = {
            "CANO": self._account_no[:8],
            "ACNT_PRDT_CD": self._account_product_code,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": cancel.order_no,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",  # 02: 취소
            "ORD_QTY": str(cancel.quantity),
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "N",
        }

        logger.info(
            "주문 취소 요청",
            original_order_no=cancel.order_no,
            symbol=cancel.symbol,
            quantity=cancel.quantity,
        )

        data = await self._request(
            "POST",
            ENDPOINTS["cancel"],
            tr_id,
            json_body=body,
        )

        output = data.get("output", {})
        cancel_order_no = output.get("ODNO", "")

        result = CancelResponse(
            order_no=cancel_order_no,
            original_order_no=cancel.order_no,
            status="cancelled",
            message=data.get("msg1", ""),
        )

        logger.info(
            "주문 취소 완료",
            cancel_order_no=cancel_order_no,
            original_order_no=cancel.order_no,
        )

        return result

    # ── 잔고 조회 ────────────────────────────────────

    async def get_balance(self) -> AccountBalance:
        """계좌 잔고 및 보유종목 조회.

        Returns:
            AccountBalance: 계좌 잔고 + 보유종목
        """
        params = {
            "CANO": self._account_no[:8],
            "ACNT_PRDT_CD": self._account_product_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        data = await self._request(
            "GET",
            ENDPOINTS["balance"],
            self._tr_ids["balance"],
            params=params,
        )

        # 보유종목 파싱
        holdings: list[Holding] = []
        output1_list = data.get("output1", [])
        for item in output1_list:
            qty = int(item.get("hldg_qty", 0))
            if qty <= 0:
                continue

            avg_price = int(float(item.get("pchs_avg_pric", 0)))
            current_price = int(item.get("prpr", 0))
            eval_amount = int(item.get("evlu_amt", 0))
            profit = int(item.get("evlu_pfls_amt", 0))
            profit_pct = float(item.get("evlu_pfls_rt", 0))

            holdings.append(
                Holding(
                    symbol=item.get("pdno", ""),
                    name=item.get("prdt_name", ""),
                    quantity=qty,
                    avg_price=avg_price,
                    current_price=current_price,
                    eval_amount=eval_amount,
                    profit=profit,
                    profit_pct=profit_pct,
                )
            )

        # 계좌 요약
        output2_list = data.get("output2", [])
        summary = output2_list[0] if output2_list else {}

        total_eval = int(summary.get("tot_evlu_amt", 0))
        total_profit = int(summary.get("evlu_pfls_smtl_amt", 0))
        available_cash = int(summary.get("dnca_tot_amt", 0))

        # 총 수익률 계산
        purchase_total = int(summary.get("pchs_amt_smtl_amt", 0))
        total_profit_pct = 0.0
        if purchase_total > 0:
            total_profit_pct = round((total_profit / purchase_total) * 100, 2)

        balance = AccountBalance(
            total_eval=total_eval,
            total_profit=total_profit,
            total_profit_pct=total_profit_pct,
            available_cash=available_cash,
            holdings=holdings,
        )

        logger.info(
            "잔고 조회 완료",
            total_eval=total_eval,
            holdings_count=len(holdings),
            available_cash=available_cash,
        )

        return balance

    async def get_holdings(self) -> list[Holding]:
        """보유종목만 조회.

        Returns:
            list[Holding]: 보유종목 리스트
        """
        balance = await self.get_balance()
        return balance.holdings

    async def get_daily_price(self, symbol: str) -> list[dict]:
        """종목 일봉 조회.

        Args:
            symbol: 종목코드

        Returns:
            list[dict]: 일봉 데이터 리스트
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": "",
            "FID_INPUT_DATE_2": "",
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        }

        data = await self._request(
            "GET",
            ENDPOINTS["daily_price"],
            self._tr_ids["daily_price"],
            params=params,
        )

        return data.get("output2", [])
