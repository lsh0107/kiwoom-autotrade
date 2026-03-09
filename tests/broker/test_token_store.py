"""token_store 모듈 테스트."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from src.broker import token_store
from src.broker.schemas import TokenInfo
from src.models.broker import BrokerCredential

# 테스트용 시각 상수
FUTURE_EXPIRES = datetime.now(UTC) + timedelta(hours=24)
PAST_EXPIRES = datetime.now(UTC) - timedelta(hours=1)
NEAR_EXPIRES = datetime.now(UTC) + timedelta(minutes=3)  # 5분 미만 → 만료 임박

CRED_ID = uuid.uuid4()


def _make_mock_cred(
    cached_token: str | None = "encrypted_token",  # noqa: S107
    token_expires_at: datetime | None = FUTURE_EXPIRES,
    token_type: str | None = "Bearer",  # noqa: S107
) -> BrokerCredential:
    """테스트용 BrokerCredential mock 생성."""
    cred = MagicMock(spec=BrokerCredential)
    cred.id = CRED_ID
    cred.cached_token = cached_token
    cred.token_expires_at = token_expires_at
    cred.token_type = token_type
    return cred


def _make_mock_db(cred: BrokerCredential | None = None) -> AsyncMock:
    """테스트용 AsyncSession mock 생성."""
    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = cred
    db.execute.return_value = mock_result
    return db


class TestLoadValidToken:
    """DB에 유효한 토큰이 있을 때 반환 테스트."""

    async def test_load_valid_token(self) -> None:
        """유효한 캐시 토큰 → TokenInfo 반환, decrypt 호출 확인."""
        cred = _make_mock_cred()
        db = _make_mock_db(cred)

        with patch(
            "src.broker.token_store.decrypt", return_value="decrypted_access_token"
        ) as mock_decrypt:
            result = await token_store.load(CRED_ID, db)

        assert result is not None
        assert result.access_token == "decrypted_access_token"
        assert result.token_type == "Bearer"
        assert result.expires_at == FUTURE_EXPIRES
        mock_decrypt.assert_called_once_with("encrypted_token")


class TestLoadExpiredToken:
    """만료된 토큰 테스트."""

    async def test_load_expired_token(self) -> None:
        """token_expires_at이 과거 → None 반환."""
        cred = _make_mock_cred(token_expires_at=PAST_EXPIRES)
        db = _make_mock_db(cred)

        result = await token_store.load(CRED_ID, db)

        assert result is None


class TestLoadNearExpiry:
    """만료 임박 토큰 테스트."""

    async def test_load_near_expiry(self) -> None:
        """token_expires_at이 5분 이내 → None 반환."""
        cred = _make_mock_cred(token_expires_at=NEAR_EXPIRES)
        db = _make_mock_db(cred)

        result = await token_store.load(CRED_ID, db)

        assert result is None


class TestSaveToken:
    """토큰 저장 테스트."""

    async def test_save_token(self) -> None:
        """save() 후 encrypt 호출 + db.execute + db.flush 확인."""
        db = AsyncMock(spec=AsyncSession)
        token_info = TokenInfo(
            access_token="my_access_token",
            token_type="Bearer",
            expires_at=FUTURE_EXPIRES,
        )

        with patch(
            "src.broker.token_store.encrypt", return_value="encrypted_value"
        ) as mock_encrypt:
            await token_store.save(CRED_ID, token_info, db)

        mock_encrypt.assert_called_once_with("my_access_token")
        db.execute.assert_called_once()
        db.flush.assert_called_once()


class TestConcurrentTokenFetch:
    """동시 토큰 발급 방지 (Double-Check Locking) 테스트."""

    async def test_concurrent_token_fetch(self) -> None:
        """asyncio.gather로 5개 동시 호출 → authenticate_fn 1번만 호출."""
        cred_id = uuid.uuid4()

        # 기존 Lock 초기화
        token_store._locks.pop(cred_id, None)

        # load가 항상 None을 반환하도록 설정 (캐시 미스)
        # 단, authenticate_fn 호출 후에는 유효 토큰 반환
        call_count = 0

        async def mock_authenticate() -> TokenInfo:
            nonlocal call_count
            call_count += 1
            # 실제 발급처럼 약간의 지연
            await asyncio.sleep(0.01)
            return TokenInfo(
                access_token="fresh_token",
                token_type="Bearer",
                expires_at=FUTURE_EXPIRES,
            )

        # load: Lock 밖에서는 None, Lock 안에서는 첫 호출만 None → 이후는 유효 토큰
        # 이를 시뮬레이션하기 위해: load는 처음에는 항상 None,
        # save 호출 후에는 유효 토큰 반환
        saved = False

        async def mock_load(cid: uuid.UUID, db: AsyncSession) -> TokenInfo | None:
            nonlocal saved
            if saved:
                return TokenInfo(
                    access_token="fresh_token",
                    token_type="Bearer",
                    expires_at=FUTURE_EXPIRES,
                )
            return None

        async def mock_save(cid: uuid.UUID, ti: TokenInfo, db: AsyncSession) -> None:
            nonlocal saved
            saved = True

        db = AsyncMock(spec=AsyncSession)

        with (
            patch.object(token_store, "load", side_effect=mock_load),
            patch.object(token_store, "save", side_effect=mock_save),
        ):
            results = await asyncio.gather(
                *[
                    token_store.get_or_refresh_token(cred_id, db, mock_authenticate)
                    for _ in range(5)
                ]
            )

        # 모두 같은 토큰 반환
        assert all(r == "fresh_token" for r in results)
        # authenticate_fn은 1번만 호출 (Double-Check Locking 효과)
        assert call_count == 1

        # 정리
        token_store._locks.pop(cred_id, None)
