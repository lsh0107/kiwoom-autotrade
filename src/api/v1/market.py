"""시세 조회 라우터."""

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import ActiveBrokerCredential, CurrentUser, DBSession
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import DailyPrice, Orderbook, Quote
from src.models.broker import BrokerCredential as BrokerCredentialModel
from src.utils.crypto import decrypt

router = APIRouter(prefix="/market", tags=["시세"])


def _create_kiwoom_client(cred: BrokerCredentialModel, db: AsyncSession) -> KiwoomClient:
    """DB 자격증명으로 KiwoomClient를 생성한다."""
    base_url = MOCK_BASE_URL if cred.is_mock else REAL_BASE_URL
    return KiwoomClient(
        base_url=base_url,
        app_key=decrypt(cred.encrypted_app_key),
        app_secret=decrypt(cred.encrypted_app_secret),
        is_mock=cred.is_mock,
        db=db,
        credential_id=cred.id,
    )


@router.get(
    "/quote/{symbol}",
    response_model=Quote,
)
async def get_quote(
    symbol: str,
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
) -> Quote:
    """종목 현재가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    client = _create_kiwoom_client(credential, db)
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
    db: DBSession,
) -> Orderbook:
    """종목 호가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    client = _create_kiwoom_client(credential, db)
    try:
        return await client.get_orderbook(symbol)
    finally:
        await client.close()


@router.get(
    "/chart/{symbol}/daily",
    response_model=list[DailyPrice],
)
async def get_daily_chart(
    symbol: str,
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
    days: int = Query(default=60, ge=1, le=365, description="조회 일수 (기본 60일)"),
) -> list[DailyPrice]:
    """종목 일봉 차트를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
        days: 조회 일수 (1~365, 기본 60)

    Returns:
        일봉 데이터 리스트 (최신 순)
    """
    client = _create_kiwoom_client(credential, db)
    try:
        prices = await client.get_daily_chart(symbol)
        return prices[:days]
    finally:
        await client.close()
