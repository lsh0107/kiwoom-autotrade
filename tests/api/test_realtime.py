"""실시간 WebSocket API 테스트."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.models.broker import BrokerCredential
from src.utils.jwt import create_access_token

# ── 픽스처 ─────────────────────────────────────────────────────


@pytest.fixture
def realtime_app() -> FastAPI:
    """WebSocket 테스트용 FastAPI 앱 (DB 모킹)."""
    from src.config.database import get_db
    from src.main import create_app

    test_app = create_app()
    mock_session = AsyncMock()

    async def mock_get_db() -> AsyncGenerator:
        yield mock_session

    test_app.dependency_overrides[get_db] = mock_get_db
    return test_app


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """테스트용 사용자 UUID."""
    return uuid.uuid4()


@pytest.fixture
def valid_token(test_user_id: uuid.UUID) -> str:
    """유효한 JWT access_token."""
    return create_access_token(test_user_id)


@pytest.fixture
def mock_cred(test_user_id: uuid.UUID) -> MagicMock:
    """모의 브로커 자격증명."""
    cred = MagicMock(spec=BrokerCredential)
    cred.user_id = test_user_id
    cred.is_mock = True
    cred.encrypted_app_key = b"encrypted_key"
    cred.encrypted_app_secret = b"encrypted_secret"
    cred.id = uuid.uuid4()
    return cred


@pytest.fixture
def mock_kiwoom_ws() -> AsyncMock:
    """모의 KiwoomWebSocket 인스턴스."""
    ws = AsyncMock()
    ws.on_tick = None
    ws.connect = AsyncMock()
    ws.close = AsyncMock()
    ws.subscribe = AsyncMock()
    ws.unsubscribe = AsyncMock()
    return ws


# ── 인증 테스트 ────────────────────────────────────────────────


class TestMarketWebSocketAuth:
    """WebSocket 인증 실패 테스트."""

    def test_no_token_close_4001(self, realtime_app: FastAPI) -> None:
        """액세스 토큰 없이 연결 시 4001로 종료."""
        with (
            TestClient(realtime_app) as client,
            client.websocket_connect("/api/v1/ws/market") as ws,
            pytest.raises(WebSocketDisconnect) as exc_info,
        ):
            ws.receive_json()
        assert exc_info.value.code == 4001

    def test_invalid_token_close_4001(self, realtime_app: FastAPI) -> None:
        """유효하지 않은 토큰으로 연결 시 4001로 종료."""
        with (
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": "invalid.jwt.token"},
            ) as ws,
            pytest.raises(WebSocketDisconnect) as exc_info,
        ):
            ws.receive_json()
        assert exc_info.value.code == 4001

    def test_refresh_token_rejected(self, realtime_app: FastAPI, test_user_id: uuid.UUID) -> None:
        """refresh_token으로 연결 시 4001로 종료 (type != access)."""
        from src.utils.jwt import create_refresh_token

        refresh_token = create_refresh_token(test_user_id)
        with (
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": refresh_token},
            ) as ws,
            pytest.raises(WebSocketDisconnect) as exc_info,
        ):
            ws.receive_json()
        assert exc_info.value.code == 4001


# ── 자격증명 없음 테스트 ───────────────────────────────────────


class TestMarketWebSocketNoCredential:
    """자격증명 없는 사용자 테스트."""

    def test_no_credential_close_4002(
        self,
        realtime_app: FastAPI,
        valid_token: str,
    ) -> None:
        """자격증명 없으면 error 메시지 전송 후 4002로 연결 종료."""
        from src.utils.exceptions import CredentialNotFoundError

        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                side_effect=CredentialNotFoundError,
            ),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            error_msg = ws.receive_json()
            assert error_msg["type"] == "error"
            assert "자격증명" in error_msg["message"]
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_json()
        assert exc_info.value.code == 4002


# ── 메시지 처리 테스트 ─────────────────────────────────────────


class TestMarketWebSocketMessages:
    """WebSocket 메시지 처리 테스트."""

    def test_subscribe_message(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """subscribe 메시지 전송 시 subscribed 응답 수신."""
        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                return_value=mock_cred,
            ),
            patch("src.api.v1.realtime.KiwoomWebSocket", return_value=mock_kiwoom_ws),
            patch("src.api.v1.realtime.KiwoomClient"),
            patch("src.api.v1.realtime.decrypt", return_value="decrypted"),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            ws.send_json({"action": "subscribe", "symbols": ["005930", "000660"], "type": "0B"})
            data = ws.receive_json()

        assert data["type"] == "subscribed"
        assert data["symbols"] == ["005930", "000660"]
        mock_kiwoom_ws.subscribe.assert_called_once_with(["005930", "000660"], data_type="0B")

    def test_unsubscribe_message(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """unsubscribe 메시지 전송 시 unsubscribed 응답 수신."""
        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                return_value=mock_cred,
            ),
            patch("src.api.v1.realtime.KiwoomWebSocket", return_value=mock_kiwoom_ws),
            patch("src.api.v1.realtime.KiwoomClient"),
            patch("src.api.v1.realtime.decrypt", return_value="decrypted"),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            ws.send_json({"action": "unsubscribe", "symbols": ["005930"]})
            data = ws.receive_json()

        assert data["type"] == "unsubscribed"
        assert data["symbols"] == ["005930"]
        mock_kiwoom_ws.unsubscribe.assert_called_once_with(["005930"])

    def test_unknown_action_returns_error(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """알 수 없는 action 전송 시 error 메시지 수신."""
        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                return_value=mock_cred,
            ),
            patch("src.api.v1.realtime.KiwoomWebSocket", return_value=mock_kiwoom_ws),
            patch("src.api.v1.realtime.KiwoomClient"),
            patch("src.api.v1.realtime.decrypt", return_value="decrypted"),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            ws.send_json({"action": "ping", "symbols": []})
            data = ws.receive_json()

        assert data["type"] == "error"
        assert "ping" in data["message"]

    def test_kiwoom_ws_closed_on_disconnect(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """클라이언트 연결 종료 시 KiwoomWebSocket.close() 호출 확인."""
        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                return_value=mock_cred,
            ),
            patch("src.api.v1.realtime.KiwoomWebSocket", return_value=mock_kiwoom_ws),
            patch("src.api.v1.realtime.KiwoomClient"),
            patch("src.api.v1.realtime.decrypt", return_value="decrypted"),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            ws.send_json({"action": "subscribe", "symbols": ["005930"], "type": "0B"})
            ws.receive_json()
            # 컨텍스트 매니저 종료 → 연결 해제

        # finally 블록에서 close() 호출 확인
        mock_kiwoom_ws.close.assert_called_once()


# ── 틱 전달 테스트 ─────────────────────────────────────────────


class TestMarketWebSocketTickForwarding:
    """실시간 틱 데이터 전달 테스트."""

    def test_on_tick_callback_set(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """KiwoomWebSocket.on_tick 콜백이 async callable로 설정되는지 확인."""
        captured_ws = mock_kiwoom_ws

        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                return_value=mock_cred,
            ),
            patch("src.api.v1.realtime.KiwoomWebSocket", return_value=captured_ws),
            patch("src.api.v1.realtime.KiwoomClient"),
            patch("src.api.v1.realtime.decrypt", return_value="decrypted"),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            ws.send_json({"action": "subscribe", "symbols": ["005930"], "type": "0B"})
            ws.receive_json()

        assert captured_ws.on_tick is not None
        assert asyncio.iscoroutinefunction(captured_ws.on_tick)
