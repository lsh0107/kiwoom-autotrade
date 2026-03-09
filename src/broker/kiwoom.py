"""키움증권 REST API 클라이언트."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import structlog
from aiolimiter import AsyncLimiter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.broker.schemas import DailyPrice, MinutePrice

from src.broker.constants import (
    API_IDS,
    DEFAULT_EXCHANGE,
    ENDPOINTS,
    ERROR_INVALID_TOKEN,
    ERROR_RATE_LIMIT,
    MOCK_RATE_LIMIT,
    ORDER_COND_CODES,
    REAL_RATE_LIMIT,
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
    from_kiwoom_symbol,
    to_kiwoom_symbol,
)
from src.utils.exceptions import BrokerAuthError, BrokerError, BrokerRateLimitError

logger = structlog.get_logger("broker.kiwoom")


def _mask(value: str, visible: int = 4) -> str:
    """민감 정보 마스킹."""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


def _safe_int(value: str | int, default: int = 0) -> int:
    """빈 문자열·None도 안전하게 int 변환."""
    if isinstance(value, int):
        return value
    if not value or not value.strip():
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_price(value: str | int, default: int = 0) -> int:
    """가격 파싱 (부호 접두사 제거).

    키움 API는 가격 앞에 +/- 부호로 전일대비 등락 방향을 표시한다.
    예: '-173500' → 173500 (실제 현재가)
    """
    return abs(_safe_int(value, default))


def _parse_expires_dt(expires_dt: str) -> datetime:
    """키움 토큰 만료 시각 파싱.

    키움 API는 expires_dt를 "YYYYMMDD" 또는 "YYYYMMDDHHMMSS" 형식으로 반환한다.
    어느 형식이든 파싱하여 datetime(UTC)으로 반환.

    Args:
        expires_dt: 만료 시각 문자열

    Returns:
        datetime: 만료 시각 (UTC)
    """
    if len(expires_dt) >= 14:
        return datetime.strptime(expires_dt[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    return datetime.strptime(expires_dt[:8], "%Y%m%d").replace(tzinfo=UTC)


class KiwoomClient:
    """키움증권 REST API 클라이언트.

    httpx.AsyncClient 기반, 토큰 자동 갱신, 레이트 리밋 적용.
    키움 REST API는 모든 요청이 POST. 모의/실거래는 URL만 다르고 api-id는 동일.
    """

    def __init__(
        self,
        *,
        base_url: str,
        app_key: str,
        app_secret: str,
        is_mock: bool = True,
        db: AsyncSession | None = None,
        credential_id: uuid.UUID | None = None,
    ) -> None:
        """클라이언트 초기화.

        Args:
            base_url: 키움 API 베이스 URL
            app_key: 앱 키
            app_secret: 앱 시크릿 (secretkey)
            is_mock: 모의투자 여부
            db: DB 세션 (토큰 캐시 사용 시 필수)
            credential_id: 브로커 자격증명 ID (토큰 캐시 사용 시 필수)
        """
        self._base_url = base_url
        self._app_key = app_key
        self._app_secret = app_secret
        self._is_mock = is_mock
        self._db = db
        self._credential_id = credential_id

        # 토큰 관리
        self._token: TokenInfo | None = None

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
            is_mock=is_mock,
            rate_limit=rate,
        )

    async def close(self) -> None:
        """HTTP 클라이언트를 닫는다."""
        await self._client.aclose()

    # ── 인증 ──────────────────────────────────────────

    async def authenticate(self) -> TokenInfo:
        """토큰 발급 (POST /oauth2/token).

        Returns:
            TokenInfo: 발급된 토큰 정보
        """
        url = ENDPOINTS["token"]
        headers = {
            "api-id": API_IDS["token"],
            "content-type": "application/json;charset=UTF-8",
        }
        body = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "secretkey": self._app_secret,
        }

        logger.info("토큰 발급 요청", url=url, app_key=_mask(self._app_key))

        response = await self._client.post(url, headers=headers, json=body)
        data = response.json()

        if response.status_code != 200:
            msg = data.get("error_message", data.get("error_description", "토큰 발급 실패"))
            logger.error("토큰 발급 실패", status=response.status_code, error=msg)
            raise BrokerAuthError(f"토큰 발급 실패: {msg}")

        # 키움: token + expires_dt 형식
        access_token = data.get("token", data.get("access_token", ""))
        token_type = data.get("token_type", "Bearer")

        # expires_dt (문자열) 또는 expires_in (초) 파싱
        expires_dt = data.get("expires_dt", "")
        if expires_dt:
            expires_at = _parse_expires_dt(expires_dt)
        else:
            expires_in = _safe_int(data.get("expires_in", 86400), default=86400)
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        token_info = TokenInfo(
            access_token=access_token,
            token_type=token_type,
            expires_at=expires_at,
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

        DB 캐시가 설정되어 있으면 token_store를 통해 토큰을 관리한다.
        없으면 기존 인메모리 방식으로 동작한다 (하위 호환).

        Returns:
            str: 액세스 토큰
        """
        # DB 캐시 경로
        if self._db is not None and self._credential_id is not None:
            from src.broker.token_store import get_or_refresh_token

            return await get_or_refresh_token(
                self._credential_id,
                self._db,
                self.authenticate,
            )

        # 기존 인메모리 경로 (하위 호환)
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

    def _common_headers(self, api_id: str, token: str) -> dict[str, str]:
        """공통 요청 헤더를 생성한다.

        키움 REST API는 api-id와 authorization 2개만 필요.
        """
        return {
            "api-id": api_id,
            "authorization": f"Bearer {token}",
            "content-type": "application/json;charset=UTF-8",
        }

    async def _request(
        self,
        url: str,
        api_id: str,
        *,
        json_body: dict | None = None,
    ) -> dict:
        """공통 API 요청 처리 (전부 POST, 레이트 리밋 + 에러 핸들링).

        Args:
            url: API 경로
            api_id: 키움 API ID (예: ka10007)
            json_body: JSON 바디

        Returns:
            dict: 응답 JSON
        """
        token = await self._ensure_token()
        headers = self._common_headers(api_id, token)

        async with self._limiter:
            logger.debug("API 요청", url=url, api_id=api_id)
            response = await self._client.post(url, headers=headers, json=json_body or {})

        data = response.json()

        # HTTP 429 체크
        if response.status_code == 429:
            logger.warning("레이트 리밋 초과 (HTTP 429)", url=url, api_id=api_id)
            raise BrokerRateLimitError

        # 키움 에러 응답 체크 (error_code 존재 시)
        error_code = data.get("error_code", "")
        if error_code:
            error_message = data.get("error_message", "알 수 없는 오류")
            logger.error(
                "API 오류 응답",
                url=url,
                api_id=api_id,
                error_code=error_code,
                error_message=error_message,
            )

            if error_code == ERROR_RATE_LIMIT:
                raise BrokerRateLimitError

            if error_code == ERROR_INVALID_TOKEN:
                raise BrokerAuthError(f"토큰 오류: {error_message}")

            raise BrokerError(f"[{error_code}] {error_message}")

        return data

    # ── 시세 조회 ────────────────────────────────────

    async def get_quote(self, symbol: str) -> Quote:
        """종목 현재가 조회 (ka10007 — 시세표성정보).

        Args:
            symbol: 종목코드 (6자리 또는 KRX:005930 형식)

        Returns:
            Quote: 현재가 정보
        """
        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)

        data = await self._request(
            ENDPOINTS["market"],
            API_IDS["quote"],
            json_body={"stk_cd": stk_cd},
        )

        cur_prc = _safe_price(data.get("cur_prc", 0))
        prev_close = _safe_price(data.get("pred_close_pric", 0))
        change = cur_prc - prev_close
        change_pct = round((change / prev_close) * 100, 2) if prev_close != 0 else 0.0

        return Quote(
            symbol=from_kiwoom_symbol(stk_cd),
            name=data.get("stk_nm", ""),
            price=cur_prc,
            change=change,
            change_pct=change_pct,
            volume=_safe_int(data.get("trde_qty", 0)),
            high=_safe_price(data.get("high_pric", 0)),
            low=_safe_price(data.get("low_pric", 0)),
            open=_safe_price(data.get("open_pric", 0)),
            prev_close=prev_close,
        )

    async def get_orderbook(self, symbol: str) -> Orderbook:
        """종목 호가 조회 (ka10004 — 주식호가).

        Args:
            symbol: 종목코드

        Returns:
            Orderbook: 호가 정보 (매도 10단계, 매수 10단계)
        """
        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)

        data = await self._request(
            ENDPOINTS["market"],
            API_IDS["orderbook"],
            json_body={"stk_cd": stk_cd},
        )

        # 매도호가: 최우선(fpr) + 2th~10th
        asks: list[PriceLevel] = []
        price = _safe_price(data.get("sel_fpr_bid", 0))
        qty = _safe_int(data.get("sel_fpr_req", 0))
        if price > 0:
            asks.append(PriceLevel(price=price, quantity=qty))
        for n in range(2, 11):
            price = _safe_price(data.get(f"sel_{n}th_pre_bid", 0))
            qty = _safe_int(data.get(f"sel_{n}th_pre_req", 0))
            if price > 0:
                asks.append(PriceLevel(price=price, quantity=qty))

        # 매수호가: 최우선(fpr) + 2th~10th
        bids: list[PriceLevel] = []
        price = _safe_price(data.get("buy_fpr_bid", 0))
        qty = _safe_int(data.get("buy_fpr_req", 0))
        if price > 0:
            bids.append(PriceLevel(price=price, quantity=qty))
        for n in range(2, 11):
            price = _safe_price(data.get(f"buy_{n}th_pre_bid", 0))
            qty = _safe_int(data.get(f"buy_{n}th_pre_req", 0))
            if price > 0:
                bids.append(PriceLevel(price=price, quantity=qty))

        return Orderbook(
            symbol=from_kiwoom_symbol(stk_cd),
            asks=asks,
            bids=bids,
        )

    # ── 주문 ─────────────────────────────────────────

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """주문 실행 (매수/매도).

        키움: 매수 kt10000, 매도 kt10001. 전부 POST /api/dostk/ordr.

        Args:
            order: 주문 요청

        Returns:
            OrderResponse: 주문 결과
        """
        api_id = API_IDS["buy"] if order.side.value == "BUY" else API_IDS["sell"]
        stk_cd = to_kiwoom_symbol(order.symbol, DEFAULT_EXCHANGE)
        cond_uv = ORDER_COND_CODES.get(order.order_type.value, "0")

        body = {
            "dmst_stex_tp": DEFAULT_EXCHANGE,
            "stk_cd": stk_cd,
            "ord_qty": str(order.quantity),
            "ord_uv": str(order.price),
            "trde_tp": "sell" if order.side.value == "SELL" else "buy",
            "cond_uv": cond_uv,
        }

        logger.info(
            "주문 요청",
            symbol=order.symbol,
            side=order.side.value,
            price=order.price,
            quantity=order.quantity,
            order_type=order.order_type.value,
            api_id=api_id,
        )

        data = await self._request(
            ENDPOINTS["order"],
            api_id,
            json_body=body,
        )

        order_no = data.get("ord_no", "")

        result = OrderResponse(
            order_no=order_no,
            symbol=from_kiwoom_symbol(stk_cd),
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            status="submitted",
            message=data.get("message", ""),
        )

        logger.info(
            "주문 접수 완료",
            order_no=order_no,
            symbol=order.symbol,
            side=order.side.value,
        )

        return result

    async def cancel_order(self, cancel: CancelRequest) -> CancelResponse:
        """주문 취소 (kt10003).

        Args:
            cancel: 취소 요청

        Returns:
            CancelResponse: 취소 결과
        """
        stk_cd = to_kiwoom_symbol(cancel.symbol, DEFAULT_EXCHANGE)

        body = {
            "dmst_stex_tp": DEFAULT_EXCHANGE,
            "orig_ord_no": cancel.order_no,
            "stk_cd": stk_cd,
            "cncl_qty": str(cancel.quantity),
        }

        logger.info(
            "주문 취소 요청",
            original_order_no=cancel.order_no,
            symbol=cancel.symbol,
            quantity=cancel.quantity,
        )

        data = await self._request(
            ENDPOINTS["order"],
            API_IDS["cancel"],
            json_body=body,
        )

        cancel_order_no = data.get("ord_no", "")

        result = CancelResponse(
            order_no=cancel_order_no,
            original_order_no=cancel.order_no,
            status="cancelled",
            message=data.get("message", ""),
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

        1차 호출: ka10085 (계좌수익률) → 보유종목 리스트
        2차 호출: kt00005 (체결잔고) → 주문가능현금

        Returns:
            AccountBalance: 계좌 잔고 + 보유종목
        """
        # 1차: 보유종목 상세 (ka10085) — stex_tp 필수
        holdings_data = await self._request(
            ENDPOINTS["account"],
            API_IDS["balance"],
            json_body={"stex_tp": "0"},
        )

        holdings: list[Holding] = []
        total_eval = 0
        total_purchase = 0

        items = holdings_data.get("acnt_prft_rt", [])
        if isinstance(items, list):
            for item in items:
                qty = _safe_int(item.get("rmnd_qty", 0))
                if qty <= 0:
                    continue

                cur_price = _safe_int(item.get("cur_prc", 0))
                pur_price = _safe_int(item.get("pur_pric", 0))
                eval_amount = cur_price * qty
                pur_amount = _safe_int(item.get("pur_amt", pur_price * qty))
                profit = eval_amount - pur_amount
                profit_pct = round((profit / pur_amount) * 100, 2) if pur_amount > 0 else 0.0

                raw_symbol = item.get("stk_cd", "")
                holdings.append(
                    Holding(
                        symbol=from_kiwoom_symbol(raw_symbol),
                        name=item.get("stk_nm", ""),
                        quantity=qty,
                        avg_price=pur_price,
                        current_price=cur_price,
                        eval_amount=eval_amount,
                        profit=profit,
                        profit_pct=profit_pct,
                    )
                )

                total_eval += eval_amount
                total_purchase += pur_amount

        # 2차: 예수금상세현황 (kt00001) — 모의/실거래 모두 지원
        deposit_data = await self._request(
            ENDPOINTS["account"],
            API_IDS["deposit"],
            json_body={"qry_tp": "0"},
        )

        available_cash = _safe_int(deposit_data.get("ord_alow_amt", 0))
        total_eval += available_cash
        total_profit = total_eval - total_purchase - available_cash
        if total_purchase > 0:
            total_profit_pct = round((total_profit / total_purchase) * 100, 2)
        else:
            total_profit_pct = 0.0

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
        """종목 일봉 조회 (ka10086 — 일별주가).

        Args:
            symbol: 종목코드

        Returns:
            list[dict]: 일봉 데이터 리스트
        """
        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)

        data = await self._request(
            ENDPOINTS["market"],
            API_IDS["daily_price"],
            json_body={
                "stk_cd": stk_cd,
                "qry_dt": "",
                "indc_tp": "0",
            },
        )

        return data.get("daly_stkpc", [])

    # ── 차트 조회 ────────────────────────────────────

    async def get_minute_price(
        self, symbol: str, interval: int = 5, *, base_dt: str = ""
    ) -> list[MinutePrice]:
        """종목 분봉 차트 조회 (ka10080).

        Args:
            symbol: 종목코드 (6자리)
            interval: 분봉 간격 (1, 3, 5, 10, 15, 30, 45, 60)
            base_dt: 기준일자 YYYYMMDD (빈 문자열이면 당일)

        Returns:
            list[MinutePrice]: 분봉 데이터 리스트 (시간 역순)
        """
        from src.broker.schemas import MinutePrice as _MinutePrice

        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)

        body: dict[str, str] = {
            "stk_cd": stk_cd,
            "tic_scope": str(interval),
            "upd_stkpc_tp": "1",
        }
        if base_dt:
            body["base_dt"] = base_dt

        data = await self._request(
            ENDPOINTS["chart"],
            API_IDS["minute_chart"],
            json_body=body,
        )

        items = data.get("stk_min_pole_chart_qry", [])
        results: list[MinutePrice] = []
        for item in items:
            results.append(
                _MinutePrice(
                    datetime=item.get("cntr_tm", ""),
                    open=_safe_price(item.get("open_pric", 0)),
                    high=_safe_price(item.get("high_pric", 0)),
                    low=_safe_price(item.get("low_pric", 0)),
                    close=_safe_price(item.get("cur_prc", 0)),
                    volume=_safe_int(item.get("trde_qty", 0)),
                )
            )

        logger.info(
            "분봉 조회 완료",
            symbol=symbol,
            interval=interval,
            count=len(results),
        )

        return results

    async def get_daily_chart(self, symbol: str, *, base_dt: str = "") -> list[DailyPrice]:
        """종목 일봉 차트 조회 (ka10081).

        Args:
            symbol: 종목코드 (6자리)
            base_dt: 기준일자 YYYYMMDD (빈 문자열이면 최근)

        Returns:
            list[DailyPrice]: 일봉 데이터 리스트 (날짜 역순)
        """
        from src.broker.schemas import DailyPrice as _DailyPrice

        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)

        body: dict[str, str] = {
            "stk_cd": stk_cd,
            "base_dt": base_dt or "",
            "upd_stkpc_tp": "1",
        }

        data = await self._request(
            ENDPOINTS["chart"],
            API_IDS["daily_chart"],
            json_body=body,
        )

        items = data.get("stk_dt_pole_chart_qry", [])
        results: list[DailyPrice] = []
        for item in items:
            results.append(
                _DailyPrice(
                    date=item.get("dt", ""),
                    open=_safe_price(item.get("open_pric", 0)),
                    high=_safe_price(item.get("high_pric", 0)),
                    low=_safe_price(item.get("low_pric", 0)),
                    close=_safe_price(item.get("cur_prc", 0)),
                    volume=_safe_int(item.get("trde_qty", 0)),
                )
            )

        logger.info(
            "일봉 차트 조회 완료",
            symbol=symbol,
            count=len(results),
        )

        return results
