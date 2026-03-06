"""시세 조회 라우터."""

from fastapi import APIRouter, Depends

from src.api.deps import CurrentUser
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import Orderbook, Quote
from src.config.settings import get_settings

router = APIRouter(prefix="/market", tags=["시세"])


def _get_kiwoom_client() -> KiwoomClient:
    """설정 기반 KiwoomClient 팩토리.

    환경변수에서 키움 API 키를 읽어 클라이언트를 생성한다.
    """
    settings = get_settings()
    return KiwoomClient(
        base_url=settings.kiwoom_base_url,
        app_key=settings.kiwoom_app_key,
        app_secret=settings.kiwoom_app_secret,
        is_mock=settings.is_mock_trading,
    )


@router.get(
    "/quote/{symbol}",
    response_model=Quote,
)
async def get_quote(
    symbol: str,
    _current_user: CurrentUser,
    client: KiwoomClient = Depends(_get_kiwoom_client),
) -> Quote:
    """종목 현재가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    try:
        return await client.get_quote(symbol)
    finally:
        await client.close()


@router.get(
    "/orderbook/{symbol}",
    response_model=Orderbook,
)
async def get_orderbook(
    symbol: str,
    _current_user: CurrentUser,
    client: KiwoomClient = Depends(_get_kiwoom_client),
) -> Orderbook:
    """종목 호가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    try:
        return await client.get_orderbook(symbol)
    finally:
        await client.close()
