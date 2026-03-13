"""KiwoomWebSocket 실시간 WebSocket 클라이언트 테스트."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.broker.constants import (
    REALTIME_TYPES,
    WS_DEFAULT_GRP,
    WS_ENDPOINT,
    WS_PORT,
    WS_TRNM_LOGIN,
    WS_TRNM_PING,
    WS_TRNM_PONG,
    WS_TRNM_REAL,
    WS_TRNM_REG,
    WS_TRNM_REMOVE,
)
from src.broker.realtime import KiwoomWebSocket, _safe_ws_int, _to_ws_url
from src.broker.schemas import (
    RealtimeBalance,
    RealtimeOrderExec,
    RealtimeSubscription,
    RealtimeTick,
)
from src.utils.exceptions import BrokerError

# 로그인 성공 응답 (run_loop 테스트에서 recv()에 사용)
_LOGIN_OK_RESPONSE = json.dumps(
    {"trnm": WS_TRNM_LOGIN, "return_code": 0, "return_msg": "", "sor_yn": "Y"}
)


# ── 모의 객체 헬퍼 ────────────────────────────────────────────


async def _aiter_messages(messages: list[str | bytes]) -> AsyncIterator[str | bytes]:
    """테스트용 비동기 메시지 이터레이터."""
    for msg in messages:
        yield msg


def _make_mock_ws(messages: list[str | bytes] | None = None) -> AsyncMock:
    """테스트용 WebSocket 모의 객체.

    Args:
        messages: async for로 반환할 메시지 목록.
    """
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    # recv()는 로그인 응답 반환 (_send_login이 연결 직후 호출)
    ws.recv = AsyncMock(return_value=_LOGIN_OK_RESPONSE)
    ws.__aiter__ = MagicMock(return_value=_aiter_messages(messages or []))
    return ws


def _make_mock_connect(mock_ws: AsyncMock) -> MagicMock:
    """async with connect(...) as ws: 패턴을 위한 컨텍스트 매니저 모의."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_ws)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_ws() -> AsyncMock:
    """메시지 없는 모의 WebSocket."""
    return _make_mock_ws()


@pytest.fixture
def get_token() -> AsyncMock:
    """모의 토큰 제공자."""
    return AsyncMock(return_value="test-token")


@pytest.fixture
def ws_client(get_token: AsyncMock) -> KiwoomWebSocket:
    """연결 전 KiwoomWebSocket 인스턴스."""
    return KiwoomWebSocket(
        base_url="https://mock.test",
        get_token=get_token,
        is_mock=True,
    )


@pytest.fixture
def connected_ws(ws_client: KiwoomWebSocket, mock_ws: AsyncMock) -> KiwoomWebSocket:
    """_ws를 직접 설정하여 연결 상태로 만든 클라이언트."""
    ws_client._ws = mock_ws
    return ws_client


# ── 유틸 함수 테스트 ──────────────────────────────────────────


class TestToWsUrl:
    """_to_ws_url: REST URL → WebSocket URL 변환 (포트 10000 필수 포함)."""

    def test_https_to_wss_with_port(self) -> None:
        """https → wss 변환, 포트 10000 포함."""
        result = _to_ws_url("https://mockapi.kiwoom.com")
        assert result == f"wss://mockapi.kiwoom.com:{WS_PORT}{WS_ENDPOINT}"

    def test_http_to_ws_with_port(self) -> None:
        """http → ws 변환, 포트 10000 포함."""
        result = _to_ws_url("http://localhost:8080")
        assert result == f"ws://localhost:8080:{WS_PORT}{WS_ENDPOINT}"

    def test_trailing_slash_removed(self) -> None:
        """후행 슬래시 제거 후 포트+엔드포인트 추가."""
        result = _to_ws_url("https://mockapi.kiwoom.com/")
        assert result == f"wss://mockapi.kiwoom.com:{WS_PORT}{WS_ENDPOINT}"

    def test_endpoint_appended(self) -> None:
        """WS_ENDPOINT가 URL 끝에 붙는다."""
        result = _to_ws_url("https://api.kiwoom.com")
        assert result.endswith(WS_ENDPOINT)

    def test_port_10000_included(self) -> None:
        """포트 10000이 URL에 포함된다 (연결 실패 방지)."""
        result = _to_ws_url("https://api.kiwoom.com")
        assert f":{WS_PORT}" in result


class TestSafeWsInt:
    """_safe_ws_int: 안전 정수 변환."""

    def test_positive_integer(self) -> None:
        """양수 정수 그대로 반환."""
        assert _safe_ws_int(12345) == 12345

    def test_negative_integer_returns_abs(self) -> None:
        """음수 → 절댓값 반환."""
        assert _safe_ws_int(-5000) == 5000

    def test_string_integer(self) -> None:
        """문자열 정수 변환."""
        assert _safe_ws_int("12345") == 12345

    def test_none_returns_default_zero(self) -> None:
        """None → 기본값 0."""
        assert _safe_ws_int(None) == 0

    def test_none_with_custom_default(self) -> None:
        """None + 커스텀 기본값."""
        assert _safe_ws_int(None, default=99) == 99

    def test_signed_string_returns_abs(self) -> None:
        """부호 있는 문자열 → 절댓값."""
        assert _safe_ws_int("-3000") == 3000

    def test_comma_separated_string(self) -> None:
        """콤마 포함 문자열 → 정수 변환."""
        assert _safe_ws_int("1,234,567") == 1234567

    def test_empty_string_returns_default(self) -> None:
        """빈 문자열 → 기본값 0."""
        assert _safe_ws_int("") == 0

    def test_non_numeric_string_returns_default(self) -> None:
        """숫자가 아닌 문자열 → 기본값 0."""
        assert _safe_ws_int("abc") == 0

    def test_whitespace_string_returns_default(self) -> None:
        """공백 문자열 → 기본값 0."""
        assert _safe_ws_int("   ") == 0


# ── 초기화 테스트 ─────────────────────────────────────────────


class TestKiwoomWebSocketInit:
    """KiwoomWebSocket 초기화 테스트."""

    def test_ws_url_converted_from_base_url(self, get_token: AsyncMock) -> None:
        """base_url이 포트 10000 포함 WebSocket URL로 변환된다."""
        client = KiwoomWebSocket(base_url="https://mock.test", get_token=get_token)
        assert client._ws_url == f"wss://mock.test:{WS_PORT}{WS_ENDPOINT}"

    def test_is_connected_initially_false(self, ws_client: KiwoomWebSocket) -> None:
        """초기 연결 상태는 False."""
        assert ws_client.is_connected is False

    def test_subscriptions_log_initially_empty(self, ws_client: KiwoomWebSocket) -> None:
        """초기 구독 이력은 비어있다."""
        assert len(ws_client._subscriptions_log) == 0

    def test_callbacks_initially_none(self, ws_client: KiwoomWebSocket) -> None:
        """초기 콜백은 모두 None."""
        assert ws_client.on_tick is None
        assert ws_client.on_order_exec is None
        assert ws_client.on_balance is None


# ── connect/close 테스트 ─────────────────────────────────────


class TestConnect:
    """connect / close 동작 테스트."""

    async def test_connect_starts_run_task(
        self, ws_client: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """connect 후 _run_task 태스크가 생성된다."""
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            assert ws_client._run_task is not None
            await ws_client.close()

    async def test_connect_sets_is_connected_after_task_runs(
        self, ws_client: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """connect 후 이벤트 루프 실행 시 is_connected == True."""
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            await asyncio.sleep(0.05)  # 루프 실행 기회 제공 (로그인 포함)
            assert ws_client.is_connected is True
            await ws_client.close()

    async def test_connect_twice_raises_broker_error(
        self, ws_client: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """이미 실행 중에 connect → BrokerError."""
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            with pytest.raises(BrokerError, match="이미 WebSocket이 연결 중"):
                await ws_client.connect()
            await ws_client.close()

    async def test_close_stops_run_task(
        self, ws_client: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """close 후 _run_task가 정리된다."""
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            await ws_client.close()
            assert ws_client._run_task is None

    async def test_close_sets_is_connected_false(
        self, ws_client: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """close 후 is_connected == False."""
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            await asyncio.sleep(0.05)
            await ws_client.close()
        assert ws_client.is_connected is False

    async def test_close_clears_subscriptions_log(
        self, ws_client: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """close 후 구독 이력 초기화."""
        ws_client._subscriptions_log.append(
            (["005930"], REALTIME_TYPES["stock_tick"], WS_DEFAULT_GRP)
        )
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            await ws_client.close()
        assert len(ws_client._subscriptions_log) == 0

    def test_disconnect_is_alias_for_close(self, ws_client: KiwoomWebSocket) -> None:
        """disconnect는 close의 별칭이다."""
        assert ws_client.disconnect == ws_client.close

    async def test_reconnect_after_close(
        self, ws_client: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """close 후 재연결 가능."""
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            await ws_client.close()
            await ws_client.connect()
            assert ws_client._run_task is not None
            await ws_client.close()


# ── 로그인 테스트 ─────────────────────────────────────────────


class TestSendLogin:
    """_send_login: WebSocket 로그인 패킷 전송/처리."""

    async def test_login_sends_trnm_login(self, ws_client: KiwoomWebSocket) -> None:
        """로그인 패킷의 trnm은 LOGIN."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=_LOGIN_OK_RESPONSE)
        ws_client._ws = mock_ws

        await ws_client._send_login()

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["trnm"] == WS_TRNM_LOGIN

    async def test_login_strips_bearer_prefix(self, ws_client: KiwoomWebSocket) -> None:
        """get_token이 'Bearer ...' 반환 시 접두사를 제거하고 전송."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=_LOGIN_OK_RESPONSE)
        ws_client._ws = mock_ws
        ws_client._get_token = AsyncMock(return_value="Bearer my-raw-token")

        await ws_client._send_login()

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["token"] == "my-raw-token"
        assert not sent["token"].startswith("Bearer ")

    async def test_login_returns_true_on_success(self, ws_client: KiwoomWebSocket) -> None:
        """return_code=0 응답 시 True 반환."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=_LOGIN_OK_RESPONSE)
        ws_client._ws = mock_ws

        result = await ws_client._send_login()
        assert result is True

    async def test_login_returns_false_on_error_code(self, ws_client: KiwoomWebSocket) -> None:
        """return_code != 0 응답 시 False 반환."""
        error_resp = json.dumps(
            {"trnm": WS_TRNM_LOGIN, "return_code": 8005, "return_msg": "Token이 유효하지 않습니다"}
        )
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=error_resp)
        ws_client._ws = mock_ws

        result = await ws_client._send_login()
        assert result is False

    async def test_login_returns_false_on_timeout(self, ws_client: KiwoomWebSocket) -> None:
        """recv 타임아웃 시 False 반환."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(side_effect=TimeoutError)
        ws_client._ws = mock_ws

        result = await ws_client._send_login()
        assert result is False


# ── subscribe/unsubscribe 테스트 ──────────────────────────────


class TestSubscribe:
    """subscribe / unsubscribe 동작 테스트."""

    async def test_subscribe_sends_reg_message(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """subscribe 시 flat 구조 REG 메시지 전송."""
        await connected_ws.subscribe(["005930"])

        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["trnm"] == WS_TRNM_REG
        # item과 type은 배열이어야 함 (105111 에러 방지)
        assert sent["data"][0]["item"] == ["005930"]
        assert isinstance(sent["data"][0]["type"], list)

    async def test_subscribe_default_data_type_is_stock_tick(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """subscribe 기본 data_type은 stock_tick("0B")."""
        await connected_ws.subscribe(["005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["data"][0]["type"] == [REALTIME_TYPES["stock_tick"]]

    async def test_subscribe_adds_to_subscriptions_log(self, connected_ws: KiwoomWebSocket) -> None:
        """subscribe 후 _subscriptions_log에 추가된다."""
        await connected_ws.subscribe(["005930"])
        assert len(connected_ws._subscriptions_log) == 1
        symbols, data_type, _ = connected_ws._subscriptions_log[0]
        assert symbols == ["005930"]
        assert data_type == REALTIME_TYPES["stock_tick"]

    async def test_subscribe_multiple_symbols_at_once(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """여러 종목을 하나의 item 배열로 묶어 전송."""
        await connected_ws.subscribe(["005930", "035720"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        items = sent["data"][0]["item"]
        assert "005930" in items
        assert "035720" in items
        # 하나의 data 항목으로 묶여야 함 (분리 금지)
        assert len(sent["data"]) == 1

    async def test_subscribe_not_connected_raises_broker_error(
        self, ws_client: KiwoomWebSocket
    ) -> None:
        """미연결 상태에서 subscribe → BrokerError."""
        with pytest.raises(BrokerError, match="connect\\(\\)"):
            await ws_client.subscribe(["005930"])

    async def test_subscribe_includes_grp_no_and_refresh(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """subscribe 메시지에 grp_no, refresh 포함."""
        await connected_ws.subscribe(["005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["grp_no"] == WS_DEFAULT_GRP
        assert sent["refresh"] == "1"

    async def test_subscribe_custom_grp_no(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """커스텀 grp_no로 구독."""
        await connected_ws.subscribe(["005930"], grp_no="0001")

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["grp_no"] == "0001"

    async def test_subscribe_is_flat_not_nested(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """구독 메시지는 flat 구조 (header/body 중첩 없음)."""
        await connected_ws.subscribe(["005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert "header" not in sent
        assert "body" not in sent

    async def test_unsubscribe_sends_remove_message(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """unsubscribe 시 REMOVE trnm 메시지 전송."""
        await connected_ws.subscribe(["005930"])
        mock_ws.send.reset_mock()
        await connected_ws.unsubscribe(["005930"])

        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["trnm"] == WS_TRNM_REMOVE

    async def test_unsubscribe_removes_from_subscriptions_log(
        self, connected_ws: KiwoomWebSocket
    ) -> None:
        """unsubscribe 후 _subscriptions_log에서 제거된다."""
        await connected_ws.subscribe(["005930"])
        await connected_ws.unsubscribe(["005930"])
        assert len(connected_ws._subscriptions_log) == 0

    async def test_unsubscribe_not_connected_raises_broker_error(
        self,
        ws_client: KiwoomWebSocket,
    ) -> None:
        """미연결 상태에서 unsubscribe → BrokerError."""
        with pytest.raises(BrokerError, match="연결"):
            await ws_client.unsubscribe(["005930"])

    async def test_unsubscribe_has_no_refresh_field(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """해지 메시지에 refresh 필드 없음."""
        await connected_ws.unsubscribe(["005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert "refresh" not in sent


# ── 메시지 처리 테스트 ─────────────────────────────────────────


class TestHandleMessage:
    """_handle_message: 메시지 파싱/처리 테스트 (flat 구조, values 숫자코드)."""

    async def test_reg_success_response_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """구독 성공 응답(return_code=0) → 에러 없이 처리."""
        msg = json.dumps({"trnm": WS_TRNM_REG, "return_code": 0, "return_msg": "성공"})
        await ws_client._handle_message(msg)

    async def test_reg_error_response_no_exception(self, ws_client: KiwoomWebSocket) -> None:
        """구독 실패 응답(return_code=105111) → 예외 없이 경고 처리."""
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REG,
                "return_code": 105111,
                "return_msg": "실시간 항목 등록에 실패했습니다",
            }
        )
        await ws_client._handle_message(msg)

    async def test_ping_triggers_pong_response(self, ws_client: KiwoomWebSocket) -> None:
        """PING 수신 시 PONG 응답 전송."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        ws_client._ws = mock_ws

        await ws_client._handle_message(json.dumps({"trnm": WS_TRNM_PING}))

        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["trnm"] == WS_TRNM_PONG

    async def test_real_stock_tick_triggers_on_tick(self, ws_client: KiwoomWebSocket) -> None:
        """REAL(0B) 메시지 수신 시 on_tick 콜백이 호출된다."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        # flat 구조, values에 숫자코드
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "005930",
                        "values": {
                            "20": "143000",  # 체결시간
                            "10": "70000",  # 현재가
                            "15": "100",  # 거래량
                            "13": "1000000",  # 누적거래량
                        },
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)

        assert len(received) == 1
        assert received[0].symbol == "005930"
        assert received[0].price == 70000
        assert received[0].volume == 100
        assert received[0].timestamp == "143000"

    async def test_real_stock_tick_signed_price_abs_value(self, ws_client: KiwoomWebSocket) -> None:
        """현재가 부호 있는 값 → 절댓값 변환."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "005930",
                        "values": {"20": "090000", "10": "-68000", "15": "50", "13": "500"},
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)
        assert len(received) == 1
        assert received[0].price == 68000  # 부호 있는 가격 → 절댓값

    async def test_real_order_exec_triggers_on_order_exec(self, ws_client: KiwoomWebSocket) -> None:
        """REAL(00) 메시지 수신 시 on_order_exec 콜백이 호출된다."""
        received: list[RealtimeOrderExec] = []

        async def on_order_exec(oe: RealtimeOrderExec) -> None:
            received.append(oe)

        ws_client.on_order_exec = on_order_exec
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["order_exec"],
                        "name": "주문체결",
                        "item": "005930",
                        "values": {
                            "9203": "12345",  # 주문번호
                            "9001": "005930",  # 종목코드
                            "905": "+매수",  # 주문구분
                            "910": "70000",  # 체결가
                            "911": "10",  # 체결량
                            "913": "체결",  # 주문상태
                            "908": "143000",  # 체결시간
                        },
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)

        assert len(received) == 1
        assert received[0].order_no == "12345"
        assert received[0].symbol == "005930"
        assert received[0].price == 70000

    async def test_real_balance_triggers_on_balance(self, ws_client: KiwoomWebSocket) -> None:
        """REAL(04) 메시지 수신 시 on_balance 콜백이 호출된다."""
        received: list[RealtimeBalance] = []

        async def on_balance(bal: RealtimeBalance) -> None:
            received.append(bal)

        ws_client.on_balance = on_balance
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["balance"],
                        "name": "현물잔고",
                        "item": "005930",
                        "values": {
                            "9001": "005930",  # 종목코드
                            "930": "100",  # 보유수량
                            "931": "65000",  # 매입단가
                            "10": "70000",  # 현재가
                            "8019": "7.69",  # 손익률
                        },
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)

        assert len(received) == 1
        assert received[0].symbol == "005930"
        assert received[0].quantity == 100
        assert received[0].avg_price == 65000
        assert received[0].current_price == 70000

    async def test_real_balance_eval_amount_calculated(self, ws_client: KiwoomWebSocket) -> None:
        """on_balance: eval_amount = current_price * quantity 계산."""
        received: list[RealtimeBalance] = []

        async def on_balance(bal: RealtimeBalance) -> None:
            received.append(bal)

        ws_client.on_balance = on_balance
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["balance"],
                        "name": "현물잔고",
                        "item": "005930",
                        "values": {
                            "9001": "005930",
                            "930": "10",  # 보유수량
                            "931": "65000",  # 매입단가
                            "10": "70000",  # 현재가
                            "8019": "0.00",
                        },
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)
        assert received[0].eval_amount == 700000  # 70000 * 10

    async def test_real_symbol_from_item_field(self, ws_client: KiwoomWebSocket) -> None:
        """실시간 데이터의 종목코드는 data[].item 필드에서 추출된다."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "000660",  # 하이닉스
                        "values": {"20": "103000", "10": "50000", "15": "200", "13": "500"},
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)
        assert received[0].symbol == "000660"

    async def test_invalid_json_handled_gracefully(self, ws_client: KiwoomWebSocket) -> None:
        """JSON 파싱 실패 → 에러 없이 무시."""
        await ws_client._handle_message("not valid json {{")

    async def test_unknown_trnm_handled_gracefully(self, ws_client: KiwoomWebSocket) -> None:
        """알 수 없는 trnm → 에러 없이 무시."""
        msg = json.dumps({"trnm": "UNKNOWN_TYPE"})
        await ws_client._handle_message(msg)

    async def test_bytes_message_processed(self, ws_client: KiwoomWebSocket) -> None:
        """bytes 형식 메시지도 처리 가능."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "005930",
                        "values": {"20": "120000", "10": "60000", "15": "50", "13": "300"},
                    }
                ],
            }
        ).encode()
        await ws_client._handle_message(msg)
        assert len(received) == 1

    async def test_real_raw_field_preserved_in_tick(self, ws_client: KiwoomWebSocket) -> None:
        """수신된 data 항목 딕셔너리가 RealtimeTick.raw에 보존된다."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        item_data: dict[str, Any] = {
            "type": REALTIME_TYPES["stock_tick"],
            "name": "주식체결",
            "item": "005930",
            "values": {
                "20": "143000",
                "10": "70000",
                "15": "100",
                "13": "1000000",
                "extra": "extra_value",
            },
        }
        await ws_client._handle_message(json.dumps({"trnm": WS_TRNM_REAL, "data": [item_data]}))
        assert received[0].raw == item_data

    async def test_real_multiple_items_dispatched(self, ws_client: KiwoomWebSocket) -> None:
        """REAL 메시지에 data 항목이 여럿이면 모두 콜백 호출."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "005930",
                        "values": {"20": "143000", "10": "70000", "15": "100", "13": "1000"},
                    },
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "000660",
                        "values": {"20": "143001", "10": "80000", "15": "50", "13": "2000"},
                    },
                ],
            }
        )
        await ws_client._handle_message(msg)
        assert len(received) == 2
        assert received[0].symbol == "005930"
        assert received[1].symbol == "000660"


# ── 콜백 동작 테스트 ───────────────────────────────────────────


class TestCallbacks:
    """on_tick / on_order_exec / on_balance 콜백 동작."""

    async def test_on_tick_not_set_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """on_tick 미설정 시 주식체결 메시지 처리도 에러 없음."""
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "005930",
                        "values": {"20": "143000", "10": "70000", "15": "100", "13": "1000"},
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)

    async def test_on_order_exec_not_set_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """on_order_exec 미설정 시 주문체결 메시지 처리도 에러 없음."""
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["order_exec"],
                        "name": "주문체결",
                        "item": "005930",
                        "values": {
                            "9203": "1",
                            "9001": "005930",
                            "905": "+매수",
                            "910": "70000",
                            "911": "1",
                            "913": "체결",
                            "908": "143000",
                        },
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)

    async def test_on_balance_not_set_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """on_balance 미설정 시 잔고 메시지 처리도 에러 없음."""
        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["balance"],
                        "name": "현물잔고",
                        "item": "005930",
                        "values": {
                            "9001": "005930",
                            "930": "10",
                            "931": "65000",
                            "10": "70000",
                            "8019": "7.69",
                        },
                    }
                ],
            }
        )
        await ws_client._handle_message(msg)

    async def test_callback_exception_handled_without_propagation(
        self, ws_client: KiwoomWebSocket
    ) -> None:
        """콜백 예외 발생 시 에러 로깅하고 _handle_message는 정상 반환."""

        async def failing_on_tick(_tick: RealtimeTick) -> None:
            raise RuntimeError("콜백 에러")

        ws_client.on_tick = failing_on_tick

        msg = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "005930",
                        "values": {"20": "143000", "10": "70000", "15": "100", "13": "1000"},
                    }
                ],
            }
        )
        # 예외가 전파되지 않아야 함
        await ws_client._handle_message(msg)


# ── 수신 루프 / 재연결 테스트 ─────────────────────────────────


class TestRunLoop:
    """_run_loop: 재연결 포함 실행 루프 테스트."""

    async def test_run_loop_processes_message_and_calls_on_tick(
        self, ws_client: KiwoomWebSocket
    ) -> None:
        """수신 루프가 WebSocket 메시지를 처리하여 on_tick 콜백을 호출한다."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick

        message = json.dumps(
            {
                "trnm": WS_TRNM_REAL,
                "data": [
                    {
                        "type": REALTIME_TYPES["stock_tick"],
                        "name": "주식체결",
                        "item": "005930",
                        "values": {"20": "143000", "10": "70000", "15": "100", "13": "1000"},
                    }
                ],
            }
        )
        mock_ws = _make_mock_ws([message])
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            await asyncio.sleep(0.1)
            await ws_client.close()

        assert len(received) == 1
        assert received[0].symbol == "005930"

    async def test_run_loop_reconnects_on_exception(self, ws_client: KiwoomWebSocket) -> None:
        """연결 오류 발생 시 재연결을 시도한다."""
        call_count = [0]

        async def failing_aiter() -> AsyncIterator[str]:
            raise RuntimeError("연결 끊김")
            yield  # type: ignore[misc]  # 제너레이터 표시용

        # 첫 번째: __aiter__ 에러 발생, 두 번째: 빈 메시지로 대기
        mock_fail = AsyncMock()
        mock_fail.recv = AsyncMock(return_value=_LOGIN_OK_RESPONSE)
        mock_fail.__aiter__ = MagicMock(return_value=failing_aiter())
        cm1 = MagicMock()
        cm1.__aenter__ = AsyncMock(return_value=mock_fail)
        cm1.__aexit__ = AsyncMock(return_value=False)

        mock_ok = _make_mock_ws([])
        cm2 = MagicMock()
        cm2.__aenter__ = AsyncMock(return_value=mock_ok)
        cm2.__aexit__ = AsyncMock(return_value=False)

        def connect_factory(*args: Any, **kwargs: Any) -> MagicMock:
            call_count[0] += 1
            return cm1 if call_count[0] == 1 else cm2

        with (
            patch("src.broker.realtime.connect", connect_factory),
            patch("src.broker.realtime.WS_RECONNECT_BASE_DELAY", 0.01),
        ):
            await ws_client.connect()
            await asyncio.sleep(0.2)
            await ws_client.close()

        assert call_count[0] >= 2

    async def test_run_loop_stops_after_max_retries(self, ws_client: KiwoomWebSocket) -> None:
        """최대 재연결 횟수 초과 시 루프가 종료된다.

        reconnect_attempt는 async with 블록 진입 시 0으로 리셋되므로
        __aenter__에서 예외를 발생시켜 카운터가 정상 누적되도록 한다.
        """

        def make_failing_cm() -> MagicMock:
            """__aenter__ 단계에서 실패하는 컨텍스트 매니저."""
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(side_effect=RuntimeError("연결 실패"))
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        with (
            patch(
                "src.broker.realtime.connect",
                MagicMock(side_effect=lambda *a, **kw: make_failing_cm()),
            ),
            patch("src.broker.realtime.WS_RECONNECT_BASE_DELAY", 0.001),
            patch("src.broker.realtime.WS_RECONNECT_MAX_RETRIES", 2),
        ):
            await ws_client.connect()
            # 최대 재시도(3회) 완료 대기: 0.001 + 0.002 = 0.003s + 여유
            for _ in range(50):
                await asyncio.sleep(0.02)
                if ws_client._run_task and ws_client._run_task.done():
                    break

        assert ws_client._run_task is not None
        assert ws_client._run_task.done()

    async def test_replay_subscriptions_on_reconnect(self, ws_client: KiwoomWebSocket) -> None:
        """재연결 후 기존 구독이 자동 복구된다."""

        async def first_conn_aiter() -> AsyncIterator[str]:
            raise RuntimeError("연결 끊김")
            yield  # type: ignore[misc]  # 제너레이터 표시용

        ws1 = AsyncMock()
        ws1.send = AsyncMock()
        ws1.recv = AsyncMock(return_value=_LOGIN_OK_RESPONSE)
        ws1.__aiter__ = MagicMock(return_value=first_conn_aiter())
        cm1 = MagicMock()
        cm1.__aenter__ = AsyncMock(return_value=ws1)
        cm1.__aexit__ = AsyncMock(return_value=False)

        ws2 = _make_mock_ws([])
        ws2.send = AsyncMock()
        cm2 = MagicMock()
        cm2.__aenter__ = AsyncMock(return_value=ws2)
        cm2.__aexit__ = AsyncMock(return_value=False)

        call_count = [0]

        def connect_factory(*args: Any, **kwargs: Any) -> MagicMock:
            call_count[0] += 1
            return cm1 if call_count[0] == 1 else cm2

        # 구독 이력 미리 설정
        ws_client._subscriptions_log.append(
            (["005930"], REALTIME_TYPES["stock_tick"], WS_DEFAULT_GRP)
        )

        with (
            patch("src.broker.realtime.connect", connect_factory),
            patch("src.broker.realtime.WS_RECONNECT_BASE_DELAY", 0.01),
        ):
            await ws_client.connect()
            await asyncio.sleep(0.2)
            await ws_client.close()

        # 두 번째 연결에서 subscribe가 재호출되어야 함 (login + subscribe = 최소 2회)
        assert ws2.send.await_count >= 1


# ── 스키마 테스트 ─────────────────────────────────────────────


class TestRealtimeSubscription:
    """RealtimeSubscription Pydantic 스키마 검증."""

    def test_creation_with_required_fields(self) -> None:
        """필수 필드로 정상 생성."""
        sub = RealtimeSubscription(
            trnm=WS_TRNM_REG,
            data=[{"item": ["005930"], "type": ["0B"]}],
        )
        assert sub.trnm == WS_TRNM_REG
        assert sub.refresh == "1"

    def test_remove_trnm(self) -> None:
        """REMOVE trnm으로 생성."""
        sub = RealtimeSubscription(
            trnm=WS_TRNM_REMOVE,
            data=[{"item": ["005930"], "type": ["0B"]}],
        )
        assert sub.trnm == WS_TRNM_REMOVE


class TestRealtimeTick:
    """RealtimeTick Pydantic 스키마 유효성 검사."""

    def test_creation_with_all_fields(self) -> None:
        """모든 필드를 지정한 정상 생성."""
        tick = RealtimeTick(
            symbol="005930",
            price=70000,
            volume=100,
            timestamp="143000",
            raw={"stk_cd": "005930"},
        )
        assert tick.symbol == "005930"
        assert tick.price == 70000
        assert tick.volume == 100
        assert tick.timestamp == "143000"

    def test_raw_field_defaults_to_empty_dict(self) -> None:
        """raw 필드 기본값은 빈 dict."""
        tick = RealtimeTick(symbol="005930", price=0, volume=0, timestamp="")
        assert tick.raw == {}

    def test_price_zero_is_valid(self) -> None:
        """price == 0 허용 (하한가 상황)."""
        tick = RealtimeTick(symbol="005930", price=0, volume=0, timestamp="090000")
        assert tick.price == 0

    def test_negative_price_raises_validation_error(self) -> None:
        """price < 0 → ValidationError 발생."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RealtimeTick(symbol="005930", price=-1, volume=0, timestamp="")

    def test_negative_volume_raises_validation_error(self) -> None:
        """volume < 0 → ValidationError 발생."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RealtimeTick(symbol="005930", price=0, volume=-1, timestamp="")


class TestRealtimeOrderExec:
    """RealtimeOrderExec Pydantic 스키마 유효성 검사."""

    def test_creation_with_all_fields(self) -> None:
        """모든 필드를 지정한 정상 생성."""
        oe = RealtimeOrderExec(
            order_no="12345",
            symbol="005930",
            side="BUY",
            price=70000,
            quantity=10,
            status="filled",
            timestamp="143000",
        )
        assert oe.order_no == "12345"
        assert oe.symbol == "005930"
        assert oe.price == 70000
        assert oe.quantity == 10

    def test_raw_field_defaults_to_empty_dict(self) -> None:
        """raw 필드 기본값은 빈 dict."""
        oe = RealtimeOrderExec(
            order_no="1",
            symbol="005930",
            side="BUY",
            price=0,
            quantity=0,
            status="",
            timestamp="",
        )
        assert oe.raw == {}

    def test_negative_price_raises_validation_error(self) -> None:
        """price < 0 → ValidationError 발생."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RealtimeOrderExec(
                order_no="1",
                symbol="005930",
                side="BUY",
                price=-1,
                quantity=0,
                status="",
                timestamp="",
            )


class TestRealtimeBalance:
    """RealtimeBalance Pydantic 스키마 유효성 검사."""

    def test_creation_with_all_fields(self) -> None:
        """모든 필드를 지정한 정상 생성."""
        bal = RealtimeBalance(
            symbol="005930",
            quantity=100,
            avg_price=65000,
            current_price=70000,
            eval_amount=7000000,
            profit_pct=7.69,
        )
        assert bal.symbol == "005930"
        assert bal.quantity == 100
        assert bal.eval_amount == 7000000

    def test_raw_field_defaults_to_empty_dict(self) -> None:
        """raw 필드 기본값은 빈 dict."""
        bal = RealtimeBalance(
            symbol="005930",
            quantity=0,
            avg_price=0,
            current_price=0,
            eval_amount=0,
            profit_pct=0.0,
        )
        assert bal.raw == {}

    def test_negative_quantity_raises_validation_error(self) -> None:
        """quantity < 0 → ValidationError 발생."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RealtimeBalance(
                symbol="005930",
                quantity=-1,
                avg_price=0,
                current_price=0,
                eval_amount=0,
                profit_pct=0.0,
            )
