"""키움 API 토큰 DB 캐시 + 동시 발급 방지."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import TokenInfo
from src.models.broker import BrokerCredential
from src.utils.crypto import decrypt, encrypt

TOKEN_REFRESH_BUFFER_SECONDS = 300  # 만료 5분 전 갱신

# credential_id별 Lock — 모듈 레벨로 프로세스 내 공유
_locks: dict[uuid.UUID, asyncio.Lock] = {}


def _get_lock(credential_id: uuid.UUID) -> asyncio.Lock:
    """credential_id별 asyncio.Lock을 반환한다."""
    if credential_id not in _locks:
        _locks[credential_id] = asyncio.Lock()
    return _locks[credential_id]


async def load(credential_id: uuid.UUID, db: AsyncSession) -> TokenInfo | None:
    """DB에서 캐시된 토큰을 조회한다. 만료 임박이면 None."""
    result = await db.execute(select(BrokerCredential).where(BrokerCredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if not cred or not cred.cached_token or not cred.token_expires_at:
        return None

    buffer = timedelta(seconds=TOKEN_REFRESH_BUFFER_SECONDS)
    if datetime.now(UTC) >= cred.token_expires_at - buffer:
        return None

    return TokenInfo(
        access_token=decrypt(cred.cached_token),
        token_type=cred.token_type or "Bearer",
        expires_at=cred.token_expires_at,
    )


async def save(credential_id: uuid.UUID, token_info: TokenInfo, db: AsyncSession) -> None:
    """토큰을 DB에 저장한다. cached_token은 암호화."""
    await db.execute(
        update(BrokerCredential)
        .where(BrokerCredential.id == credential_id)
        .values(
            cached_token=encrypt(token_info.access_token),
            token_expires_at=token_info.expires_at,
            token_type=token_info.token_type,
            token_updated_at=datetime.now(UTC),
        )
    )
    await db.flush()


async def get_or_refresh_token(
    credential_id: uuid.UUID,
    db: AsyncSession,
    authenticate_fn,  # Callable[[], Awaitable[TokenInfo]]
) -> str:
    """유효한 토큰을 반환한다. 없거나 만료 임박이면 발급 후 DB 저장.

    Double-Check Locking으로 동시 발급을 방지한다.
    """
    # 1차: Lock 없이 빠른 조회
    token = await load(credential_id, db)
    if token:
        return token.access_token

    # 2차: Lock 획득 후 재확인
    lock = _get_lock(credential_id)
    async with lock:
        token = await load(credential_id, db)
        if token:
            return token.access_token

        # 실제 발급
        token_info = await authenticate_fn()
        await save(credential_id, token_info, db)
        return token_info.access_token
