"""계좌 잔고/보유종목 라우터."""

from fastapi import APIRouter

from src.api.deps import ActiveBrokerCredential, CurrentUser
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import AccountBalance
from src.models.broker import BrokerCredential as BrokerCredentialModel
from src.utils.crypto import decrypt

router = APIRouter(prefix="/account", tags=["계좌"])


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
    "/balance",
    response_model=AccountBalance,
)
async def get_balance(
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
) -> AccountBalance:
    """계좌 잔고와 보유종목을 조회한다."""
    client = _create_kiwoom_client(credential)
    try:
        return await client.get_balance()
    finally:
        await client.close()
