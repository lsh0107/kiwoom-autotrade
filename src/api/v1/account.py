"""계좌 잔고/보유종목 라우터.

HOTFIX (2026-05-27): ``/account/balance`` 가 외부 키움 API hang 으로 무한
대기하지 않도록 endpoint 레벨에서 fail-fast 처리. 자세한 정책은
``BALANCE_UPSTREAM_TIMEOUT_SEC`` 주석 참조.
"""

import asyncio
import time

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import ActiveBrokerCredential, CurrentUser, DBSession
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import AccountBalance
from src.models.broker import BrokerCredential as BrokerCredentialModel
from src.utils.crypto import decrypt
from src.utils.exceptions import BrokerAuthError, BrokerError, BrokerRateLimitError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/account", tags=["계좌"])

# 잔고 캐시: credential_id → (timestamp, data)
# 모의투자 초당 5건 제한 방어 — 같은 계정 10초 내 재요청 시 캐시 반환
_balance_cache: dict[str, tuple[float, AccountBalance]] = {}
_CACHE_TTL_SEC = 10.0

# HOTFIX — endpoint 레벨 전체 timeout.
#
# 배경:
#   ``KiwoomClient.get_balance()`` 는 ka10085 / kt00018 / kt00001 3개의 외부
#   키움 API 를 직렬 호출한다 (각 httpx read timeout 10s + 429/토큰 재시도
#   최대 12s). 외부 키움 서버가 응답을 안 주거나 토큰 재발급 루프에 빠지면
#   요청이 수십 초 이상 hang 할 수 있다. 그 동안 lab 의 daily proposal
#   수집 같은 호출자가 무한 대기 상태가 된다.
#
# 정책:
#   12 초 안에 응답이 안 오면 HTTPException(504) 로 fail-fast.
#   12 초는 정상 응답 (~3초) + 429 재시도 (최대 12초) 여유를 고려한 상한.
#   상한 초과는 거의 항상 외부 키움 서버 hang 으로 봄 → 조용히 기다리지
#   않고 명시적 에러로 반환한다.
#
# 금지:
#   - timeout / upstream 실패를 가짜 잔고로 조용히 처리 금지 (사용자 정책).
#   - 캐시에 빈 데이터 저장 금지 (다음 호출도 잘못된 값 받게 됨).
BALANCE_UPSTREAM_TIMEOUT_SEC = 12.0


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

    실패 동작 (HOTFIX 2026-05-27):
        - 외부 키움 API 가 ``BALANCE_UPSTREAM_TIMEOUT_SEC`` 안에 응답하지
          않으면 ``504 Gateway Timeout``.
        - 키움 인증/rate-limit/일반 broker 오류는 ``502 Bad Gateway``.
        - 그 외 예기치 못한 오류는 그대로 ``500`` (FastAPI 기본).
        - **timeout/upstream 실패를 가짜 잔고로 대체하지 않는다**.
    """
    cache_key = str(credential.id)
    now = time.monotonic()

    # 캐시 히트
    cached = _balance_cache.get(cache_key)
    if cached is not None:
        cached_at, cached_data = cached
        if now - cached_at < _CACHE_TTL_SEC:
            return cached_data

    # 캐시 미스 — 키움 API 호출. 전체 호출을 wait_for 로 wrap 해 fail-fast.
    client = _create_kiwoom_client(credential, db)
    started_monotonic = time.monotonic()
    try:
        balance = await asyncio.wait_for(client.get_balance(), timeout=BALANCE_UPSTREAM_TIMEOUT_SEC)
    except TimeoutError:
        elapsed = time.monotonic() - started_monotonic
        logger.error(
            "잔고 조회 timeout (upstream hang)",
            credential_id=str(credential.id),
            is_mock=credential.is_mock,
            elapsed_sec=round(elapsed, 2),
            limit_sec=BALANCE_UPSTREAM_TIMEOUT_SEC,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                f"키움 잔고 API 응답 없음 (>{BALANCE_UPSTREAM_TIMEOUT_SEC:.0f}s). "
                f"외부 키움 서버 상태를 확인하세요."
            ),
        ) from None
    except httpx.HTTPError as exc:
        elapsed = time.monotonic() - started_monotonic
        logger.error(
            "잔고 조회 HTTP 오류",
            credential_id=str(credential.id),
            is_mock=credential.is_mock,
            elapsed_sec=round(elapsed, 2),
            error_class=type(exc).__name__,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"키움 잔고 API HTTP 오류: {type(exc).__name__}",
        ) from exc
    except (BrokerAuthError, BrokerRateLimitError, BrokerError) as exc:
        elapsed = time.monotonic() - started_monotonic
        logger.error(
            "잔고 조회 broker 오류",
            credential_id=str(credential.id),
            is_mock=credential.is_mock,
            elapsed_sec=round(elapsed, 2),
            error_class=type(exc).__name__,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"키움 잔고 API 오류: {type(exc).__name__}",
        ) from exc
    except Exception:
        # 예기치 못한 오류는 로그만 남기고 그대로 raise (FastAPI 가 500 처리).
        # 가짜 잔고로 조용히 대체하지 않는다 (정책).
        logger.exception(
            "잔고 조회 실패 (분류 불가)",
            credential_id=str(credential.id),
            is_mock=credential.is_mock,
        )
        raise
    finally:
        await client.close()

    _balance_cache[cache_key] = (now, balance)
    return balance
