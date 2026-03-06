"""시세 조회 라우터."""

from fastapi import APIRouter

from src.api.deps import ActiveBrokerCredential, CurrentUser
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import Orderbook, Quote
from src.models.broker import BrokerCredential as BrokerCredentialModel
from src.utils.crypto import decrypt

router = APIRouter(prefix="/market", tags=["시세"])


def _create_kiwoom_client(cred: BrokerCredentialModel) -> KiwoomClient:
    """DB 자격증명으로 KiwoomClient를 생성한다."""
    base_url = MOCK_BASE_URL if cred.is_mock else REAL_BASE_URL
    return KiwoomClient(
        base_url=base_url,
        app_key=decrypt(cred.encrypted_app_key),
        app_secret=decrypt(cred.encrypted_app_secret),
        is_mock=cred.is_mock,
    )


@router.get(
    "/quote/{symbol}",
    response_model=Quote,
)
async def get_quote(
    symbol: str,
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
) -> Quote:
    """종목 현재가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    client = _create_kiwoom_client(credential)
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
    credential: ActiveBrokerCredential,
) -> Orderbook:
    """종목 호가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    client = _create_kiwoom_client(credential)
    try:
        return await client.get_orderbook(symbol)
    finally:
        await client.close()
