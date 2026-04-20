"""token_store 모듈 테스트.

감사 문서(T5-B PR 2): `assert_called_once*` 기반 implementation coupling 제거.
`save()` → `load()` round-trip 동작 검증으로 전환하여 내부 호출 방식이 아닌
"저장 후 회복 가능한가"를 검증한다.
"""

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
    """테스트용 AsyncSession mock 생성 (load 전용)."""
    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = cred
    db.execute.return_value = mock_result
    return db


class _RoundTripFakeSession:
    """save → load 라운드트립 검증을 위한 in-memory AsyncSession fake.

    `save()`는 `update(...).values(...)` 구문으로 호출되므로, 실행된 SQL의
    values()를 꺼내 메모리상의 credential 상태에 반영한다. `load()`는
    같은 세션으로 `select(...)`를 실행하며, fake가 현재 상태를 scalar 결과로
    반환한다. 내부 호출 횟수가 아닌 "저장된 값이 복원되는가"를 검증하기 위한 용도.
    """

    def __init__(self) -> None:
        self._cred: BrokerCredential | None = None

    def seed(self, cred: BrokerCredential) -> None:
        self._cred = cred

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        # update 문: values()로 저장 상태 갱신
        if getattr(stmt, "is_update", False):
            values = {
                (col.key if hasattr(col, "key") else str(col)): (
                    val.value if hasattr(val, "value") else val
                )
                for col, val in stmt._values.items()
            }
            if self._cred is None:
                self._cred = MagicMock(spec=BrokerCredential)
                self._cred.id = CRED_ID
                self._cred.token_type = None
            for key, val in values.items():
                setattr(self._cred, key, val)
            return MagicMock()

        # select 문: 현재 cred 반환
        result = MagicMock()
        result.scalar_one_or_none.return_value = self._cred
        return result

    async def flush(self) -> None:
        return None


class TestLoadValidToken:
    """DB에 유효한 토큰이 있을 때 TokenInfo 반환."""

    async def test_load_valid_token_returns_decrypted_token_info(self) -> None:
        """유효한 캐시 토큰 → 복호화된 access_token을 포함한 TokenInfo 반환.

        Behavior: "어떻게 복호화하는지"가 아닌 "반환값이 평문 토큰인가"를 검증.
        """
        cred = _make_mock_cred()
        db = _make_mock_db(cred)

        with patch("src.broker.token_store.decrypt", return_value="decrypted_access_token"):
            result = await token_store.load(CRED_ID, db)

        assert result is not None
        assert result.access_token == "decrypted_access_token"
        assert result.token_type == "Bearer"
        assert result.expires_at == FUTURE_EXPIRES


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


class TestSaveLoadRoundTrip:
    """save() → load() 라운드트립 동작 검증.

    감사 문서 지시에 따라 "내부 호출 횟수" 대신 "저장 후 회복 가능한가"를 검증.
    encrypt/decrypt는 identity로 패치하여 round-trip 보존을 직접 확인한다.
    """

    async def test_save_then_load_returns_same_token(self) -> None:
        """save() 후 load() 호출 시 저장된 access_token을 그대로 복원한다."""
        db = _RoundTripFakeSession()
        # 기존 credential 존재 상태 (save는 UPDATE 구문이므로 row 필요)
        db.seed(_make_mock_cred(cached_token=None, token_expires_at=None))
        token_info = TokenInfo(
            access_token="my_access_token",
            token_type="Bearer",
            expires_at=FUTURE_EXPIRES,
        )

        # encrypt/decrypt를 identity로 만들어 round-trip 보존성만 검증
        with (
            patch("src.broker.token_store.encrypt", side_effect=lambda x: f"enc::{x}"),
            patch(
                "src.broker.token_store.decrypt",
                side_effect=lambda x: x.removeprefix("enc::"),
            ),
        ):
            await token_store.save(CRED_ID, token_info, db)  # type: ignore[arg-type]
            loaded = await token_store.load(CRED_ID, db)  # type: ignore[arg-type]

        assert loaded is not None
        # round-trip: 저장한 평문 토큰이 그대로 복원됨
        assert loaded.access_token == "my_access_token"
        assert loaded.token_type == "Bearer"
        assert loaded.expires_at == FUTURE_EXPIRES

    async def test_save_persists_encrypted_not_plaintext(self) -> None:
        """저장된 cached_token은 평문이 아닌 암호화된 값이어야 한다 (보안 불변식)."""
        db = _RoundTripFakeSession()
        db.seed(_make_mock_cred(cached_token=None, token_expires_at=None))
        token_info = TokenInfo(
            access_token="plaintext_secret",
            token_type="Bearer",
            expires_at=FUTURE_EXPIRES,
        )

        with patch("src.broker.token_store.encrypt", side_effect=lambda x: f"enc::{x}"):
            await token_store.save(CRED_ID, token_info, db)  # type: ignore[arg-type]

        # 저장된 cached_token은 평문이 아니어야 함
        assert db._cred is not None
        assert db._cred.cached_token != "plaintext_secret"
        assert db._cred.cached_token == "enc::plaintext_secret"


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
