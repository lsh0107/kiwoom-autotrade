"""WebSocket Contract Test: PDF 스펙과 코드 출력 일치 검증.

fixture JSON은 PDF 원본 기준. 코드가 fixture에 맞아야 하며, 반대 방향 금지.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from src.broker.constants import WS_DEFAULT_GRP
from src.broker.realtime import KiwoomWebSocket

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "kiwoom" / "websocket"


def load_fixture(name: str) -> dict:
    """fixture JSON 로드 후 payload 반환."""
    with open(FIXTURE_DIR / name) as f:
        data = json.load(f)
    return data["payload"]


def _make_connected_ws(token: str = "test-token-value") -> tuple[KiwoomWebSocket, AsyncMock]:  # noqa: S107
    """_ws가 직접 설정된 KiwoomWebSocket 인스턴스와 mock_ws 반환."""
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()

    get_token = AsyncMock(return_value=token)
    client = KiwoomWebSocket(
        base_url="https://mockapi.kiwoom.com",
        get_token=get_token,
    )
    client._ws = mock_ws
    return client, mock_ws


def _capture_sent(mock_ws: AsyncMock, call_index: int = 0) -> dict:
    """mock_ws.send에 전달된 JSON을 파싱하여 반환."""
    raw = mock_ws.send.call_args_list[call_index][0][0]
    return json.loads(raw)


# ── 로그인 Contract ─────────────────────────────────────────────


class TestLoginContract:
    """_send_login()이 생성하는 패킷이 PDF 스펙과 일치하는지 검증."""

    async def test_login_request_matches_spec(self) -> None:
        """로그인 패킷 포맷이 fixture와 일치."""
        expected = load_fixture("login_request.json")

        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        # recv는 로그인 응답 반환 (타임아웃 방지)
        mock_ws.recv = AsyncMock(return_value=json.dumps(load_fixture("login_response_ok.json")))

        get_token = AsyncMock(return_value="test-token-value")
        client = KiwoomWebSocket(
            base_url="https://mockapi.kiwoom.com",
            get_token=get_token,
        )
        client._ws = mock_ws

        await client._send_login()

        actual = _capture_sent(mock_ws, call_index=0)
        assert actual == expected

    async def test_bearer_prefix_stripped_before_send(self) -> None:
        """get_token이 'Bearer ...' 반환 시 접두사를 제거하고 전송."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps(load_fixture("login_response_ok.json")))

        get_token = AsyncMock(return_value="Bearer test-token-value")
        client = KiwoomWebSocket(
            base_url="https://mockapi.kiwoom.com",
            get_token=get_token,
        )
        client._ws = mock_ws

        await client._send_login()

        actual = _capture_sent(mock_ws, call_index=0)
        # Bearer 제거 후 순수 토큰값만 전송
        assert actual["token"] == "test-token-value"
        assert not actual["token"].startswith("Bearer ")

    async def test_login_success_returns_true(self) -> None:
        """return_code=0 응답 시 True 반환."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps(load_fixture("login_response_ok.json")))

        get_token = AsyncMock(return_value="test-token-value")
        client = KiwoomWebSocket(
            base_url="https://mockapi.kiwoom.com",
            get_token=get_token,
        )
        client._ws = mock_ws

        result = await client._send_login()
        assert result is True


# ── 구독 Contract ───────────────────────────────────────────────


class TestSubscribeContract:
    """subscribe()가 생성하는 payload가 PDF 스펙과 일치하는지 검증."""

    async def test_stock_tick_subscribe_matches_spec(self) -> None:
        """주식체결(0B) 구독 요청이 subscribe_stock_tick.json fixture와 일치."""
        expected = load_fixture("subscribe_stock_tick.json")
        client, mock_ws = _make_connected_ws()

        await client.subscribe(["005930"], data_type="0B", grp_no="1")

        actual = _capture_sent(mock_ws)
        assert actual == expected

    async def test_order_exec_subscribe_matches_spec(self) -> None:
        """주문체결(00) 구독 요청이 subscribe_order_exec.json fixture와 일치."""
        expected = load_fixture("subscribe_order_exec.json")
        client, mock_ws = _make_connected_ws()

        await client.subscribe([""], data_type="00", grp_no="1")

        actual = _capture_sent(mock_ws)
        assert actual == expected

    async def test_balance_subscribe_matches_spec(self) -> None:
        """잔고(04) 구독 요청이 subscribe_balance.json fixture와 일치."""
        expected = load_fixture("subscribe_balance.json")
        client, mock_ws = _make_connected_ws()

        await client.subscribe([""], data_type="04", grp_no="1")

        actual = _capture_sent(mock_ws)
        assert actual == expected

    async def test_multi_symbol_subscribe_matches_spec(self) -> None:
        """여러 종목 동시 구독이 subscribe_multi_symbol.json fixture와 일치."""
        expected = load_fixture("subscribe_multi_symbol.json")
        client, mock_ws = _make_connected_ws()

        await client.subscribe(["005930", "000660", "035720"], data_type="0B", grp_no="1")

        actual = _capture_sent(mock_ws)
        assert actual == expected

    async def test_subscribe_item_is_array_not_string(self) -> None:
        """item이 문자열이 아닌 배열로 전송된다 (105111 에러 방지)."""
        client, mock_ws = _make_connected_ws()

        await client.subscribe(["005930"])

        actual = _capture_sent(mock_ws)
        assert isinstance(actual["data"][0]["item"], list)

    async def test_subscribe_type_is_array_not_string(self) -> None:
        """type이 문자열이 아닌 배열로 전송된다 (105111 에러 방지)."""
        client, mock_ws = _make_connected_ws()

        await client.subscribe(["005930"])

        actual = _capture_sent(mock_ws)
        assert isinstance(actual["data"][0]["type"], list)

    async def test_subscribe_is_flat_not_nested(self) -> None:
        """구독 메시지가 flat 구조 (header/body 중첩 없음)."""
        client, mock_ws = _make_connected_ws()

        await client.subscribe(["005930"])

        actual = _capture_sent(mock_ws)
        assert "header" not in actual
        assert "body" not in actual
        assert "trnm" in actual

    async def test_subscribe_no_authorization_field(self) -> None:
        """WebSocket 구독 메시지에 authorization 필드 없음 (로그인으로 인증됨)."""
        client, mock_ws = _make_connected_ws()

        await client.subscribe(["005930"])

        actual = _capture_sent(mock_ws)
        assert "authorization" not in actual
        assert "token" not in actual

    async def test_subscribe_uses_default_grp_no(self) -> None:
        """기본 grp_no는 WS_DEFAULT_GRP(='1')."""
        client, mock_ws = _make_connected_ws()

        await client.subscribe(["005930"])

        actual = _capture_sent(mock_ws)
        assert actual["grp_no"] == WS_DEFAULT_GRP


# ── 구독 해지 Contract ──────────────────────────────────────────


class TestUnsubscribeContract:
    """unsubscribe()가 생성하는 payload가 PDF 스펙과 일치하는지 검증."""

    async def test_unsubscribe_matches_spec(self) -> None:
        """구독 해지 요청이 unsubscribe.json fixture와 일치."""
        expected = load_fixture("unsubscribe.json")
        client, mock_ws = _make_connected_ws()

        await client.unsubscribe(["005930"], data_type="0B", grp_no="1")

        actual = _capture_sent(mock_ws)
        assert actual == expected

    async def test_unsubscribe_has_no_refresh_field(self) -> None:
        """해지 메시지에 refresh 필드 없음 (PDF 스펙)."""
        client, mock_ws = _make_connected_ws()

        await client.unsubscribe(["005930"])

        actual = _capture_sent(mock_ws)
        assert "refresh" not in actual

    async def test_unsubscribe_trnm_is_remove(self) -> None:
        """해지 메시지의 trnm은 REMOVE."""
        client, mock_ws = _make_connected_ws()

        await client.unsubscribe(["005930"])

        actual = _capture_sent(mock_ws)
        assert actual["trnm"] == "REMOVE"


# ── 응답 파싱 Contract ──────────────────────────────────────────


class TestResponseParsingContract:
    """서버 응답 fixture를 파싱하여 올바른 값이 추출되는지 검증."""

    async def test_stock_tick_parsed_from_spec(self) -> None:
        """real_stock_tick.json fixture를 파싱하면 올바른 tick 데이터가 추출된다."""
        from src.broker.schemas import RealtimeTick

        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        client, _ = _make_connected_ws()
        client.on_tick = on_tick

        payload = load_fixture("real_stock_tick.json")
        await client._handle_message(json.dumps(payload))

        assert len(received) == 1
        tick = received[0]
        assert tick.symbol == "005930"
        # "10": "-20800" → abs(int("-20800")) = 20800
        assert tick.price == 20800
        # "15": "+82" → abs(int("+82")) = 82
        assert tick.volume == 82
        # "20": "165208" (체결시간)
        assert tick.timestamp == "165208"

    async def test_order_exec_parsed_from_spec(self) -> None:
        """real_order_exec.json fixture를 파싱하면 올바른 주문체결 데이터가 추출된다."""
        from src.broker.schemas import RealtimeOrderExec

        received: list[RealtimeOrderExec] = []

        async def on_order_exec(oe: RealtimeOrderExec) -> None:
            received.append(oe)

        client, _ = _make_connected_ws()
        client.on_order_exec = on_order_exec

        payload = load_fixture("real_order_exec.json")
        await client._handle_message(json.dumps(payload))

        assert len(received) == 1
        oe = received[0]
        # "9203": "0000018" → 주문번호
        assert oe.order_no == "0000018"
        # "9001": "005930" → 종목코드
        assert oe.symbol == "005930"
        # "905": "+매수" → 주문구분
        assert oe.side == "+매수"
        # "910": "" → 체결가 없음 (접수 상태) → 0
        assert oe.price == 0
        # "911": "" → 체결량 없음 (접수 상태) → 0
        assert oe.quantity == 0
        # "913": "접수" → 주문상태
        assert oe.status == "접수"
        # "908": "094022" → 주문/체결시간
        assert oe.timestamp == "094022"

    async def test_balance_parsed_from_spec(self) -> None:
        """real_balance.json fixture를 파싱하면 올바른 잔고 데이터가 추출된다."""
        from src.broker.schemas import RealtimeBalance

        received: list[RealtimeBalance] = []

        async def on_balance(bal: RealtimeBalance) -> None:
            received.append(bal)

        client, _ = _make_connected_ws()
        client.on_balance = on_balance

        payload = load_fixture("real_balance.json")
        await client._handle_message(json.dumps(payload))

        assert len(received) == 1
        bal = received[0]
        # "9001": "005930"
        assert bal.symbol == "005930"
        # "930": "102" → 보유수량
        assert bal.quantity == 102
        # "931": "154116" → 매입단가
        assert bal.avg_price == 154116
        # "10": "-60150" → 현재가 절댓값
        assert bal.current_price == 60150
        # eval_amount = 60150 * 102 = 6135300
        assert bal.eval_amount == 6135300

    async def test_reg_response_ok_parsed(self) -> None:
        """구독 성공 응답(return_code=0)을 에러 없이 처리."""
        client, _ = _make_connected_ws()
        payload = load_fixture("reg_response_ok.json")
        # 예외 없이 처리되어야 함
        await client._handle_message(json.dumps(payload))

    async def test_reg_response_fail_parsed(self) -> None:
        """구독 실패 응답(return_code=105111)을 에러 없이 처리."""
        client, _ = _make_connected_ws()
        payload = load_fixture("reg_response_fail.json")
        await client._handle_message(json.dumps(payload))


# ── PING/PONG Contract ──────────────────────────────────────────


class TestPingPongContract:
    """PING 수신 시 PONG 응답 전송 검증."""

    async def test_ping_triggers_pong_response(self) -> None:
        """서버 PING 수신 → 클라이언트 PONG 응답 전송."""
        expected_pong = load_fixture("pong.json")
        client, mock_ws = _make_connected_ws()

        ping_payload = load_fixture("ping.json")
        await client._handle_message(json.dumps(ping_payload))

        mock_ws.send.assert_awaited_once()
        actual_pong = _capture_sent(mock_ws)
        assert actual_pong == expected_pong

    async def test_pong_response_is_flat(self) -> None:
        """PONG 응답은 flat 구조."""
        client, mock_ws = _make_connected_ws()

        ping_payload = load_fixture("ping.json")
        await client._handle_message(json.dumps(ping_payload))

        actual_pong = _capture_sent(mock_ws)
        assert "trnm" in actual_pong
        assert actual_pong["trnm"] == "PONG"
        assert "header" not in actual_pong
        assert "body" not in actual_pong
