"""실시간 WebSocket API 테스트."""

import asyncio
import contextlib
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


# ── HOTFIX: DB transaction lifecycle (broker_credentials row lock) ─────────


class TestMarketWebSocketTransactionLifecycle:
    """HOTFIX (2026-06-01): WebSocket 핸들러가 broker_credentials 행에 대해
    long-lived idle in transaction 상태를 만들지 않는지 회귀 검증.

    배경: WebSocket 의 ``Depends(get_db)`` 세션은 WebSocket 이 종료될 때까지
    살아 있다. 그 안에서 ``_get_active_credential`` SELECT 와
    ``KiwoomClient.ensure_token()`` 의 ``broker_credentials`` UPDATE 가
    commit 되지 않으면 행 lock 이 점유되어 ``/account/balance`` 의 토큰
    UPDATE 가 lock 대기 → 12s fail-fast 504.

    수정: SELECT 직후 commit + ``_get_token()`` 콜백 안에서 ensure_token
    호출 직후 commit (예외 시 rollback).
    """

    def test_credential_select_commits_immediately(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """credential SELECT 직후 db.commit() 이 호출되어야 한다."""
        from src.config.database import get_db

        captured_session: AsyncMock = AsyncMock()
        captured_session.commit = AsyncMock()
        captured_session.rollback = AsyncMock()

        async def mock_get_db():
            yield captured_session

        realtime_app.dependency_overrides[get_db] = mock_get_db

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

        # SELECT 직후 commit 1번 이상.
        assert captured_session.commit.await_count >= 1, (
            "credential SELECT 후 db.commit() 미호출 — broker_credentials 행 "
            "idle in transaction 위험"
        )

    def test_get_token_commits_after_ensure_token(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """_get_token 콜백 호출 후 db.commit() 이 일어나야 한다.

        connect() 가 token 콜백을 호출한다고 가정하고, KiwoomWebSocket mock 의
        connect 안에서 get_token 을 강제 호출한다.
        """
        from src.config.database import get_db

        captured_session: AsyncMock = AsyncMock()
        captured_session.commit = AsyncMock()
        captured_session.rollback = AsyncMock()

        async def mock_get_db():
            yield captured_session

        realtime_app.dependency_overrides[get_db] = mock_get_db

        captured_get_token: list = []

        def capture_ws(*_a, **kwargs):
            captured_get_token.append(kwargs["get_token"])
            return mock_kiwoom_ws

        async def fake_connect():
            # connect 시점에 token 콜백 호출 → commit 발생해야 함.
            await captured_get_token[0]()

        mock_kiwoom_ws.connect = AsyncMock(side_effect=fake_connect)

        mock_kiwoom_client = MagicMock()
        mock_kiwoom_client.ensure_token = AsyncMock(return_value="TOKEN_X")
        mock_kiwoom_client.close = AsyncMock()

        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                return_value=mock_cred,
            ),
            patch("src.api.v1.realtime.KiwoomWebSocket", side_effect=capture_ws),
            patch("src.api.v1.realtime.KiwoomClient", return_value=mock_kiwoom_client),
            patch("src.api.v1.realtime.decrypt", return_value="decrypted"),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            ws.send_json({"action": "subscribe", "symbols": ["005930"], "type": "0B"})
            ws.receive_json()

        # ensure_token 호출됨.
        assert mock_kiwoom_client.ensure_token.await_count >= 1
        # SELECT 후 commit 1번 + ensure_token 후 commit 1번 → 최소 2번.
        assert captured_session.commit.await_count >= 2, (
            f"_get_token 콜백에서 db.commit() 미호출 (총 commit "
            f"{captured_session.commit.await_count}회) — 토큰 UPDATE 가 "
            "idle in transaction 으로 broker_credentials lock 점유 위험"
        )

    def test_get_token_rolls_back_on_error(
        self,
        realtime_app: FastAPI,
        valid_token: str,
        mock_cred: MagicMock,
        mock_kiwoom_ws: AsyncMock,
    ) -> None:
        """ensure_token 예외 시 rollback 호출 + 예외 재발생."""
        from src.config.database import get_db

        captured_session: AsyncMock = AsyncMock()
        captured_session.commit = AsyncMock()
        captured_session.rollback = AsyncMock()

        async def mock_get_db():
            yield captured_session

        realtime_app.dependency_overrides[get_db] = mock_get_db

        captured_get_token: list = []

        def capture_ws(*_a, **kwargs):
            captured_get_token.append(kwargs["get_token"])
            return mock_kiwoom_ws

        async def fake_connect():
            # 의도된 전파 — endpoint finally 가 close 처리.
            with contextlib.suppress(RuntimeError):
                await captured_get_token[0]()

        mock_kiwoom_ws.connect = AsyncMock(side_effect=fake_connect)

        mock_kiwoom_client = MagicMock()
        mock_kiwoom_client.ensure_token = AsyncMock(side_effect=RuntimeError("boom"))
        mock_kiwoom_client.close = AsyncMock()

        with (
            patch(
                "src.api.v1.realtime._get_active_credential",
                return_value=mock_cred,
            ),
            patch("src.api.v1.realtime.KiwoomWebSocket", side_effect=capture_ws),
            patch("src.api.v1.realtime.KiwoomClient", return_value=mock_kiwoom_client),
            patch("src.api.v1.realtime.decrypt", return_value="decrypted"),
            TestClient(realtime_app) as client,
            client.websocket_connect(
                "/api/v1/ws/market",
                cookies={"access_token": valid_token},
            ) as ws,
        ):
            ws.send_json({"action": "subscribe", "symbols": ["005930"], "type": "0B"})
            ws.receive_json()

        # rollback 최소 1번.
        assert captured_session.rollback.await_count >= 1, (
            "ensure_token 예외 시 db.rollback() 미호출 — 트랜잭션 정리 누락"
        )
