"""브로커 관련 Pydantic 스키마."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ── 종목코드 변환 유틸 ──────────────────────────────


def to_kiwoom_symbol(symbol: str, exchange: str = "KRX") -> str:  # noqa: ARG001
    """6자리 종목코드 반환 (KRX: 접두사 제거).

    키움 REST API의 stk_cd 파라미터는 6자리 코드만 허용.
    거래소 구분은 dmst_stex_tp 파라미터로 별도 전송.
    exchange 파라미터는 호환성 유지 목적으로 남겨둠.

    Args:
        symbol: 종목코드 (예: "005930" 또는 "KRX:005930")
        exchange: 사용 안 함 (호환성 유지 목적)

    Returns:
        6자리 종목코드 (예: "005930")
    """
    if ":" in symbol:
        return symbol.split(":")[-1]
    return symbol


def from_kiwoom_symbol(kiwoom_symbol: str) -> str:
    """키움 형식 종목코드를 6자리로 변환.

    Args:
        kiwoom_symbol: 키움 형식 종목코드 (예: "KRX:005930")

    Returns:
        6자리 종목코드 (예: "005930")
    """
    if ":" in kiwoom_symbol:
        return kiwoom_symbol.split(":")[-1]
    return kiwoom_symbol


# ── 공통 Enum ────────────────────────────────────────


class OrderSideEnum(StrEnum):
    """주문 방향."""

    BUY = "BUY"
    SELL = "SELL"


class OrderTypeEnum(StrEnum):
    """주문 유형."""

    LIMIT = "limit"
    MARKET = "market"


# ── 주문 ─────────────────────────────────────────────


class OrderRequest(BaseModel):
    """주문 요청."""

    symbol: str = Field(description="종목코드 (6자리 또는 KRX:005930 형식)", max_length=20)
    side: OrderSideEnum = Field(description="매수/매도")
    price: int = Field(description="주문가격 (시장가 시 0)", ge=0)
    quantity: int = Field(description="주문수량", gt=0)
    order_type: OrderTypeEnum = Field(
        default=OrderTypeEnum.LIMIT,
        description="주문유형 (limit: 지정가, market: 시장가)",
    )


class BrokerOrderResponse(BaseModel):
    """브로커 주문 응답 (키움 API 응답 파싱용)."""

    order_no: str = Field(description="주문번호")
    symbol: str = Field(description="종목코드")
    side: OrderSideEnum = Field(description="매수/매도")
    price: int = Field(description="주문가격")
    quantity: int = Field(description="주문수량")
    status: str = Field(description="주문 상태 (submitted, filled, rejected 등)")
    message: str = Field(default="", description="응답 메시지")


class CancelRequest(BaseModel):
    """주문 취소 요청."""

    order_no: str = Field(description="원주문번호")
    symbol: str = Field(description="종목코드 (6자리 또는 KRX:005930 형식)", max_length=20)
    quantity: int = Field(description="취소 수량", gt=0)


class CancelResponse(BaseModel):
    """주문 취소 응답."""

    order_no: str = Field(description="취소 주문번호")
    original_order_no: str = Field(description="원주문번호")
    status: str = Field(description="취소 상태")
    message: str = Field(default="", description="응답 메시지")


# ── 시세 ─────────────────────────────────────────────


class Quote(BaseModel):
    """현재가 정보."""

    symbol: str = Field(description="종목코드")
    name: str = Field(description="종목명")
    price: int = Field(description="현재가")
    change: int = Field(description="전일 대비 변동")
    change_pct: float = Field(description="전일 대비 변동률 (%)")
    volume: int = Field(description="거래량")
    high: int = Field(description="고가")
    low: int = Field(description="저가")
    open: int = Field(description="시가")
    prev_close: int = Field(description="전일 종가")


class PriceLevel(BaseModel):
    """호가 한 단계."""

    price: int = Field(description="가격")
    quantity: int = Field(description="수량")


class Orderbook(BaseModel):
    """호가 정보."""

    symbol: str = Field(description="종목코드")
    asks: list[PriceLevel] = Field(description="매도호가 (가격 오름차순)")
    bids: list[PriceLevel] = Field(description="매수호가 (가격 내림차순)")


# ── 잔고 ─────────────────────────────────────────────


class Holding(BaseModel):
    """보유종목 정보."""

    symbol: str = Field(description="종목코드")
    name: str = Field(description="종목명")
    quantity: int = Field(description="보유수량")
    avg_price: int = Field(description="평균매입가")
    current_price: int = Field(description="현재가")
    eval_amount: int = Field(description="평가금액")
    profit: int = Field(description="손익금액")
    profit_pct: float = Field(description="손익률 (%)")


class AccountBalance(BaseModel):
    """계좌 잔고 정보."""

    total_eval: int = Field(description="총 평가금액")
    total_profit: int = Field(description="총 손익금액")
    total_profit_pct: float = Field(description="총 손익률 (%)")
    available_cash: int = Field(description="주문 가능 현금")
    holdings: list[Holding] = Field(default_factory=list, description="보유종목 리스트")


# ── 차트 ─────────────────────────────────────────


class MinutePrice(BaseModel):
    """분봉 가격 데이터."""

    datetime: str = Field(description="체결시간 (YYYYMMDDHHMMSS)")
    open: int = Field(description="시가")
    high: int = Field(description="고가")
    low: int = Field(description="저가")
    close: int = Field(description="종가(현재가)")
    volume: int = Field(description="거래량")


class DailyPrice(BaseModel):
    """일봉 가격 데이터."""

    date: str = Field(description="일자 (YYYYMMDD)")
    open: int = Field(description="시가")
    high: int = Field(description="고가")
    low: int = Field(description="저가")
    close: int = Field(description="종가(현재가)")
    volume: int = Field(description="거래량")


# ── 인증 ─────────────────────────────────────────────


class TokenInfo(BaseModel):
    """브로커 API 토큰 정보."""

    access_token: str = Field(description="액세스 토큰")
    token_type: str = Field(default="Bearer", description="토큰 타입")
    expires_at: datetime = Field(description="토큰 만료 시각")


# ── 실시간 WebSocket ──────────────────────────────────


class RealtimeSubscription(BaseModel):
    """WebSocket 구독/해지 요청 데이터."""

    trnm: str = Field(description="요청 구분 (REG: 등록, REMOVE: 해지)")
    grp_no: str = Field(default="0000", description="그룹번호")
    refresh: str = Field(default="1", description="기존 등록 유지 여부 (0: 해지, 1: 유지)")
    data: list[dict] = Field(description="구독 항목 리스트 [{item, type}, ...]")


class RealtimeTick(BaseModel):
    """실시간 주식체결(0B) 데이터 (WebSocket push)."""

    symbol: str = Field(description="종목코드 (6자리)")
    price: int = Field(description="현재가", ge=0)
    volume: int = Field(description="체결량", ge=0)
    timestamp: str = Field(description="체결시각 (YYYYMMDDHHMMSS 또는 HHMMSS)")
    raw: dict = Field(default_factory=dict, description="서버 원시 데이터")


class RealtimeOrderExec(BaseModel):
    """실시간 주문체결(00) 데이터 (WebSocket push)."""

    order_no: str = Field(description="주문번호")
    symbol: str = Field(description="종목코드 (6자리)")
    side: str = Field(description="매수/매도 구분")
    price: int = Field(description="체결가", ge=0)
    quantity: int = Field(description="체결수량", ge=0)
    status: str = Field(description="주문상태")
    timestamp: str = Field(description="체결시각")
    raw: dict = Field(default_factory=dict, description="서버 원시 데이터")


class RealtimeBalance(BaseModel):
    """실시간 잔고(04) 데이터 (WebSocket push)."""

    symbol: str = Field(description="종목코드 (6자리)")
    quantity: int = Field(description="보유수량", ge=0)
    avg_price: int = Field(description="평균매입가", ge=0)
    current_price: int = Field(description="현재가", ge=0)
    eval_amount: int = Field(description="평가금액", ge=0)
    profit_pct: float = Field(description="손익률 (%)")
    raw: dict = Field(default_factory=dict, description="서버 원시 데이터")
