"""계좌 잔고/보유종목 라우터."""

import time

import structlog
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import ActiveBrokerCredential, CurrentUser, DBSession
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import AccountBalance
from src.models.broker import BrokerCredential as BrokerCredentialModel
from src.utils.crypto import decrypt

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/account", tags=["계좌"])

# 잔고 캐시: credential_id → (timestamp, data)
# 모의투자 초당 5건 제한 방어 — 같은 계정 10초 내 재요청 시 캐시 반환
_balance_cache: dict[str, tuple[float, AccountBalance]] = {}
_CACHE_TTL_SEC = 10.0


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
    "/balance",
    response_model=AccountBalance,
)
async def get_balance(
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
) -> AccountBalance:
    """계좌 잔고와 보유종목을 조회한다.

    모의투자 rate limit(초당 5건) 방어를 위해 10초 캐시 적용.
    """
    cache_key = str(credential.id)
    now = time.monotonic()

    # 캐시 히트
    cached = _balance_cache.get(cache_key)
    if cached is not None:
        cached_at, cached_data = cached
        if now - cached_at < _CACHE_TTL_SEC:
            return cached_data

    # 캐시 미스 — 키움 API 호출
    client = _create_kiwoom_client(credential, db)
    try:
        balance = await client.get_balance()
    except Exception:
        logger.exception(
            "잔고 조회 실패", credential_id=str(credential.id), is_mock=credential.is_mock
        )
        raise
    finally:
        await client.close()

    _balance_cache[cache_key] = (now, balance)
    return balance
