"""키움 API 토큰 DB 캐시 + 동시 발급 방지."""

import asyncio
import uuid
import weakref
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import TokenInfo
from src.models.broker import BrokerCredential
from src.utils.crypto import decrypt, encrypt

TOKEN_REFRESH_BUFFER_SECONDS = 300  # 만료 5분 전 갱신

# credential_id별 Lock — WeakValueDictionary로 자동 GC (메모리 누수 방지)
_locks: weakref.WeakValueDictionary[uuid.UUID, asyncio.Lock] = weakref.WeakValueDictionary()


def _get_lock(credential_id: uuid.UUID) -> asyncio.Lock:
    """credential_id별 asyncio.Lock을 반환한다.

    WeakValueDictionary를 사용하여 Lock 사용이 끝나면 자동으로 GC된다.
    """
    lock = _locks.get(credential_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[credential_id] = lock
    return lock


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
    authenticate_fn: Callable[[], Awaitable[TokenInfo]],
) -> str:
    """유효한 토큰을 반환한다. 없거나 만료 임박이면 발급 후 DB 저장.

    Double-Check Locking으로 동시 발급을 방지한다.

    주의:
        본 함수는 호출자의 ``db`` 세션을 사용한다. ``broker_credentials``
        UPDATE 가 일어나도 commit 책임은 **호출자에게** 있다. 호출자가
        long-lived session (예: WebSocket) 인 경우 commit 누락 시 row lock
        idle in transaction 위험이 있다. 안전한 사용은
        :func:`get_or_refresh_token_isolated` 권장.
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


async def get_or_refresh_token_isolated(
    credential_id: uuid.UUID,
    authenticate_fn: Callable[[], Awaitable[TokenInfo]],
) -> str:
    """호출자 세션과 무관하게 short-lived session 으로 토큰 조회/저장.

    호출자가 long-lived ``AsyncSession`` (WebSocket / background task) 을
    들고 있더라도, 본 함수 안에서 자체적으로 새 세션을 열고 commit/rollback
    후 close 하므로 ``broker_credentials`` row lock 이 호출자 트랜잭션에
    묶여 idle in transaction 되지 않는다.

    내부적으로 :func:`get_or_refresh_token` 을 재사용해 double-check
    locking 동작을 그대로 유지한다.

    실패 시 rollback + 예외 재발생. close 는 ``async with`` 가 보장.
    """
    from src.config.database import async_session_factory

    async with async_session_factory() as isolated_db:
        try:
            token = await get_or_refresh_token(credential_id, isolated_db, authenticate_fn)
            await isolated_db.commit()
            return token
        except Exception:
            await isolated_db.rollback()
            raise


async def invalidate_cached_token_isolated(credential_id: uuid.UUID) -> None:
    """short-lived session 으로 캐시된 토큰을 만료 처리.

    ``KiwoomClient._invalidate_cached_token`` 의 short-lived 대응판.
    빈 토큰 + 만료 시각으로 덮어써 다음 ``ensure_token`` 호출이 재발급하게
    한다. 호출자 세션과 무관 → row lock 점유 없음.
    """
    from src.config.database import async_session_factory

    expired = TokenInfo(  # nosec B106
        access_token="",
        token_type="Bearer",  # noqa: S106
        expires_at=datetime.now(UTC),
    )
    async with async_session_factory() as isolated_db:
        try:
            await save(credential_id, expired, isolated_db)
            await isolated_db.commit()
        except Exception:
            await isolated_db.rollback()
            raise
