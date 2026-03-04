"""브로커 클라이언트 프로토콜 (추상 인터페이스)."""

from typing import Protocol

from src.broker.schemas import (
    AccountBalance,
    CancelRequest,
    CancelResponse,
    Holding,
    Orderbook,
    OrderRequest,
    OrderResponse,
    Quote,
    TokenInfo,
)


class BrokerClient(Protocol):
    """증권사 API 클라이언트 프로토콜.

    키움증권 등 여러 브로커를 동일한 인터페이스로 다루기 위한 프로토콜.
    모든 메서드는 비동기(async)로 정의한다.
    """

    async def authenticate(self) -> TokenInfo:
        """API 인증 (토큰 발급).

        Returns:
            TokenInfo: 발급된 토큰 정보
        """
        ...

    async def get_quote(self, symbol: str) -> Quote:
        """종목 현재가 조회.

        Args:
            symbol: 종목코드 (6자리, 예: "005930")

        Returns:
            Quote: 현재가 정보
        """
        ...

    async def get_orderbook(self, symbol: str) -> Orderbook:
        """종목 호가 조회.

        Args:
            symbol: 종목코드

        Returns:
            Orderbook: 호가 정보
        """
        ...

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """주문 실행 (매수/매도).

        Args:
            order: 주문 요청

        Returns:
            OrderResponse: 주문 결과
        """
        ...

    async def cancel_order(self, cancel: CancelRequest) -> CancelResponse:
        """주문 취소.

        Args:
            cancel: 취소 요청

        Returns:
            CancelResponse: 취소 결과
        """
        ...

    async def get_balance(self) -> AccountBalance:
        """계좌 잔고 및 보유종목 조회.

        Returns:
            AccountBalance: 계좌 잔고 + 보유종목
        """
        ...

    async def get_holdings(self) -> list[Holding]:
        """보유종목만 조회.

        Returns:
            list[Holding]: 보유종목 리스트
        """
        ...
