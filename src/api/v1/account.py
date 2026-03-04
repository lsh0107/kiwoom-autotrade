"""계좌 잔고/보유종목 라우터."""

from fastapi import APIRouter, Depends

from src.api.deps import CurrentUser
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import AccountBalance
from src.config.settings import get_settings

router = APIRouter(prefix="/account", tags=["계좌"])


def _get_kiwoom_client() -> KiwoomClient:
    """설정 기반 KiwoomClient 팩토리.

    환경변수에서 키움 API 키를 읽어 클라이언트를 생성한다.
    """
    settings = get_settings()
    return KiwoomClient(
        base_url=settings.kiwoom_base_url,
        app_key=settings.kiwoom_app_key,
        app_secret=settings.kiwoom_app_secret,
        account_no=settings.kiwoom_account_no,
        account_product_code=settings.kiwoom_account_product_code,
        is_mock=settings.is_mock_trading,
    )


@router.get(
    "/balance",
    response_model=AccountBalance,
)
async def get_balance(
    _current_user: CurrentUser,
    client: KiwoomClient = Depends(_get_kiwoom_client),
) -> AccountBalance:
    """계좌 잔고와 보유종목을 조회한다."""
    try:
        return await client.get_balance()
    finally:
        await client.close()
