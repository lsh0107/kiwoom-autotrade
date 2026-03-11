"""실시간 WebSocket API 라우터."""

import uuid

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.realtime import KiwoomWebSocket
from src.broker.schemas import RealtimeTick
from src.config.database import get_db
from src.models.broker import BrokerCredential
from src.utils.crypto import decrypt
from src.utils.exceptions import CredentialNotFoundError, InvalidTokenError, TokenExpiredError
from src.utils.jwt import decode_token

logger = structlog.get_logger("api.realtime")
router = APIRouter(tags=["실시간"])


def _verify_jwt_cookie(websocket: WebSocket) -> uuid.UUID:
    """WebSocket 쿠키에서 JWT access_token을 검증하고 user_id를 반환한다.

    Args:
        websocket: WebSocket 연결 객체

    Returns:
        인증된 사용자 UUID

    Raises:
        InvalidTokenError: 토큰 없음, 유효하지 않음
        TokenExpiredError: 토큰 만료
    """
    token = websocket.cookies.get("access_token")
    if not token:
        raise InvalidTokenError

    payload = decode_token(token)  # 만료/무효 시 예외 발생

    if payload.get("type") != "access":
        raise InvalidTokenError

    try:
        return uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise InvalidTokenError from exc


async def _get_active_credential(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> BrokerCredential:
    """사용자의 활성 브로커 자격증명을 조회한다.

    Args:
        user_id: 사용자 UUID
        db: DB 세션

    Returns:
        활성 BrokerCredential

    Raises:
        CredentialNotFoundError: 자격증명 없음
    """
    result = await db.execute(
        select(BrokerCredential)
        .where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.is_active.is_(True),
        )
        .order_by(BrokerCredential.created_at.desc())
        .limit(1)
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise CredentialNotFoundError
    return cred


@router.websocket("/ws/market")
async def market_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> None:
    """실시간 시세 WebSocket 엔드포인트.

    클라이언트 → 서버 메시지:
        {"action": "subscribe", "symbols": ["005930"], "type": "0B"}
        {"action": "unsubscribe", "symbols": ["005930"]}

    서버 → 클라이언트 메시지:
        {"type": "tick", "symbol": "005930", "price": 72000, "volume": 1234, "timestamp": "100530"}
        {"type": "subscribed", "symbols": ["005930"]}
        {"type": "unsubscribed", "symbols": ["005930"]}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()

    # 1. JWT 인증
    try:
        user_id = _verify_jwt_cookie(websocket)
    except (InvalidTokenError, TokenExpiredError):
        await websocket.close(code=4001, reason="인증 필요")
        return

    # 2. 브로커 자격증명 조회
    try:
        cred = await _get_active_credential(user_id, db)
    except CredentialNotFoundError:
        await websocket.send_json({"type": "error", "message": "브로커 자격증명 없음"})
        await websocket.close(code=4002, reason="자격증명 없음")
        return

    # 3. KiwoomWebSocket 생성
    base_url = MOCK_BASE_URL if cred.is_mock else REAL_BASE_URL
    kiwoom_client = KiwoomClient(
        base_url=base_url,
        app_key=decrypt(cred.encrypted_app_key),
        app_secret=decrypt(cred.encrypted_app_secret),
        is_mock=cred.is_mock,
        db=db,
        credential_id=cred.id,
    )

    async def _get_token() -> str:
        """브로커 access_token을 반환한다."""
        token_info = await kiwoom_client.authenticate()
        return token_info.access_token

    kiwoom_ws = KiwoomWebSocket(
        base_url=base_url,
        get_token=_get_token,
        is_mock=cred.is_mock,
    )

    # 4. on_tick 콜백: 키움 → 클라이언트 브릿지
    async def on_tick(tick: RealtimeTick) -> None:
        """실시간 틱 데이터를 클라이언트에 전송한다."""
        try:
            await websocket.send_json(
                {
                    "type": "tick",
                    "symbol": tick.symbol,
                    "price": tick.price,
                    "volume": tick.volume,
                    "timestamp": tick.timestamp,
                }
            )
        except Exception as exc:
            logger.warning("틱 전송 실패", error=str(exc))

    kiwoom_ws.on_tick = on_tick

    try:
        await kiwoom_ws.connect()
        logger.info("실시간 WebSocket 브릿지 시작", user_id=str(user_id))

        # 5. 클라이언트 메시지 수신 루프
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            symbols: list[str] = data.get("symbols", [])
            data_type: str = data.get("type", "0B")

            if action == "subscribe":
                await kiwoom_ws.subscribe(symbols, data_type=data_type)
                await websocket.send_json({"type": "subscribed", "symbols": symbols})

            elif action == "unsubscribe":
                await kiwoom_ws.unsubscribe(symbols)
                await websocket.send_json({"type": "unsubscribed", "symbols": symbols})

            else:
                await websocket.send_json(
                    {"type": "error", "message": f"알 수 없는 action: {action}"}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket 클라이언트 연결 종료", user_id=str(user_id))
    except Exception as exc:
        logger.error("WebSocket 처리 오류", error=str(exc), user_id=str(user_id))
    finally:
        await kiwoom_ws.close()
