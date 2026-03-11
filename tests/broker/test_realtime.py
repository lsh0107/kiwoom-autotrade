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
    WS_TRNM_REAL,
    WS_TRNM_REG,
    WS_TRNM_REMOVE,
)
from src.broker.realtime import KiwoomWebSocket, _safe_ws_int, _to_ws_url, _ws_symbol
from src.broker.schemas import (
    RealtimeBalance,
    RealtimeOrderExec,
    RealtimeSubscription,
    RealtimeTick,
)
from src.utils.exceptions import BrokerError

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
    """_to_ws_url: REST URL → WebSocket URL 변환."""

    def test_https_to_wss(self) -> None:
        """https → wss 변환."""
        result = _to_ws_url("https://mockapi.kiwoom.com")
        assert result == f"wss://mockapi.kiwoom.com{WS_ENDPOINT}"

    def test_http_to_ws(self) -> None:
        """http → ws 변환."""
        result = _to_ws_url("http://localhost:8080")
        assert result == f"ws://localhost:8080{WS_ENDPOINT}"

    def test_trailing_slash_removed(self) -> None:
        """후행 슬래시 제거 후 엔드포인트 추가."""
        result = _to_ws_url("https://mockapi.kiwoom.com/")
        assert result == f"wss://mockapi.kiwoom.com{WS_ENDPOINT}"

    def test_endpoint_appended(self) -> None:
        """WS_ENDPOINT가 URL 끝에 붙는다."""
        result = _to_ws_url("https://api.kiwoom.com")
        assert result.endswith(WS_ENDPOINT)


class TestWsSymbol:
    """_ws_symbol: 종목코드 WebSocket 구독 형식 변환."""

    def test_plain_symbol_gets_krx_prefix(self) -> None:
        """6자리 코드 → KRX: 접두사 추가."""
        assert _ws_symbol("005930") == "KRX:005930"

    def test_already_prefixed_unchanged(self) -> None:
        """KRX: 접두사 이미 있으면 그대로."""
        assert _ws_symbol("KRX:005930") == "KRX:005930"

    def test_other_exchange_prefix_unchanged(self) -> None:
        """다른 거래소 접두사(콜론 포함)도 그대로."""
        assert _ws_symbol("KOSDAQ:035720") == "KOSDAQ:035720"


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
        """base_url이 WebSocket URL로 변환된다."""
        client = KiwoomWebSocket(base_url="https://mock.test", get_token=get_token)
        assert client._ws_url == f"wss://mock.test{WS_ENDPOINT}"

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
            await asyncio.sleep(0)  # 루프 실행 기회 제공
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
            await asyncio.sleep(0)
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


# ── subscribe/unsubscribe 테스트 ──────────────────────────────


class TestSubscribe:
    """subscribe / unsubscribe 동작 테스트."""

    async def test_subscribe_sends_reg_message(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """subscribe 시 REG trnm 메시지 전송."""
        await connected_ws.subscribe(["005930"])

        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["body"]["trnm"] == WS_TRNM_REG
        assert sent["header"]["api-id"] == REALTIME_TYPES["stock_tick"]
        assert any(d["item"] == "KRX:005930" for d in sent["body"]["data"])

    async def test_subscribe_default_data_type_is_stock_tick(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """subscribe 기본 data_type은 stock_tick("0B")."""
        await connected_ws.subscribe(["005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["body"]["data"][0]["type"] == REALTIME_TYPES["stock_tick"]

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
        """여러 종목 한 번에 구독 가능."""
        await connected_ws.subscribe(["005930", "035720"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        items = [d["item"] for d in sent["body"]["data"]]
        assert "KRX:005930" in items
        assert "KRX:035720" in items

    async def test_subscribe_not_connected_raises_broker_error(
        self, ws_client: KiwoomWebSocket
    ) -> None:
        """미연결 상태에서 subscribe → BrokerError."""
        with pytest.raises(BrokerError, match="connect\\(\\)"):
            await ws_client.subscribe(["005930"])

    async def test_subscribe_includes_bearer_token(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """subscribe 메시지에 Bearer 토큰이 포함된다."""
        await connected_ws.subscribe(["005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["header"]["authorization"] == "Bearer test-token"

    async def test_subscribe_includes_grp_no_and_refresh(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """subscribe 메시지에 grp_no, refresh 포함."""
        await connected_ws.subscribe(["005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["body"]["grp_no"] == WS_DEFAULT_GRP
        assert sent["body"]["refresh"] == "1"

    async def test_subscribe_custom_grp_no(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """커스텀 grp_no로 구독."""
        await connected_ws.subscribe(["005930"], grp_no="0001")

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["body"]["grp_no"] == "0001"

    async def test_subscribe_with_already_prefixed_symbol(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """이미 KRX: 접두사 있는 종목 → 중복 추가 없이 그대로."""
        await connected_ws.subscribe(["KRX:005930"])

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["body"]["data"][0]["item"] == "KRX:005930"

    async def test_unsubscribe_sends_remove_message(
        self, connected_ws: KiwoomWebSocket, mock_ws: AsyncMock
    ) -> None:
        """unsubscribe 시 REMOVE trnm 메시지 전송."""
        await connected_ws.subscribe(["005930"])
        mock_ws.send.reset_mock()
        await connected_ws.unsubscribe(["005930"])

        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["body"]["trnm"] == WS_TRNM_REMOVE

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


# ── 메시지 처리 테스트 ─────────────────────────────────────────


class TestHandleMessage:
    """_handle_message: 메시지 파싱/처리 테스트."""

    async def test_reg_success_response_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """구독 성공 응답(return_code=0) → 에러 없이 처리."""
        msg = json.dumps({"body": {"trnm": WS_TRNM_REG, "return_code": "0", "return_msg": "성공"}})
        await ws_client._handle_message(msg)

    async def test_reg_error_response_no_exception(self, ws_client: KiwoomWebSocket) -> None:
        """구독 실패 응답(return_code=1) → 예외 없이 경고 처리."""
        msg = json.dumps({"body": {"trnm": WS_TRNM_REG, "return_code": "1", "return_msg": "에러"}})
        await ws_client._handle_message(msg)

    async def test_real_stock_tick_triggers_on_tick(self, ws_client: KiwoomWebSocket) -> None:
        """REAL(0B) 메시지 수신 시 on_tick 콜백이 호출된다."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["stock_tick"],
                    "stk_cd": "KRX:005930",
                    "cur_prc": "70000",
                    "trde_qty": "100",
                    "cntr_tm": "143000",
                }
            }
        )
        await ws_client._handle_message(msg)

        assert len(received) == 1
        assert received[0].symbol == "005930"
        assert received[0].price == 70000
        assert received[0].volume == 100
        assert received[0].timestamp == "143000"

    async def test_real_stock_tick_no_type_uses_cur_prc_heuristic(
        self, ws_client: KiwoomWebSocket
    ) -> None:
        """type 필드 없어도 cur_prc 있으면 주식체결로 처리."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "stk_cd": "005930",
                    "cur_prc": "-68000",
                    "trde_qty": "50",
                    "cntr_tm": "090000",
                }
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
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["order_exec"],
                    "stk_cd": "005930",
                    "ord_no": "12345",
                    "trde_tp": "BUY",
                    "cntr_prc": "70000",
                    "cntr_qty": "10",
                    "ord_stat": "filled",
                    "cntr_tm": "143000",
                }
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
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["balance"],
                    "stk_cd": "005930",
                    "rmnd_qty": "100",
                    "pur_pric": "65000",
                    "cur_prc": "70000",
                }
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
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["balance"],
                    "stk_cd": "005930",
                    "rmnd_qty": "10",
                    "pur_pric": "65000",
                    "cur_prc": "70000",
                }
            }
        )
        await ws_client._handle_message(msg)
        assert received[0].eval_amount == 700000  # 70000 * 10

    async def test_real_without_stk_cd_uses_item_field(self, ws_client: KiwoomWebSocket) -> None:
        """stk_cd 없으면 item 필드를 종목코드로 사용."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["stock_tick"],
                    "item": "005930",
                    "cur_prc": "50000",
                    "trde_qty": "200",
                    "cntr_tm": "103000",
                }
            }
        )
        await ws_client._handle_message(msg)
        assert received[0].symbol == "005930"

    async def test_invalid_json_handled_gracefully(self, ws_client: KiwoomWebSocket) -> None:
        """JSON 파싱 실패 → 에러 없이 무시."""
        await ws_client._handle_message("not valid json {{")

    async def test_unknown_trnm_handled_gracefully(self, ws_client: KiwoomWebSocket) -> None:
        """알 수 없는 trnm → 에러 없이 무시."""
        msg = json.dumps({"body": {"trnm": "UNKNOWN_TYPE"}})
        await ws_client._handle_message(msg)

    async def test_bytes_message_processed(self, ws_client: KiwoomWebSocket) -> None:
        """bytes 형식 메시지도 처리 가능."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        msg = json.dumps(
            {
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["stock_tick"],
                    "stk_cd": "005930",
                    "cur_prc": "60000",
                    "trde_qty": "50",
                    "cntr_tm": "120000",
                }
            }
        ).encode()
        await ws_client._handle_message(msg)
        assert len(received) == 1

    async def test_real_raw_field_preserved_in_tick(self, ws_client: KiwoomWebSocket) -> None:
        """수신된 body 딕셔너리가 RealtimeTick.raw에 보존된다."""
        received: list[RealtimeTick] = []

        async def on_tick(tick: RealtimeTick) -> None:
            received.append(tick)

        ws_client.on_tick = on_tick
        body: dict[str, Any] = {
            "trnm": WS_TRNM_REAL,
            "type": REALTIME_TYPES["stock_tick"],
            "stk_cd": "005930",
            "cur_prc": "70000",
            "trde_qty": "100",
            "cntr_tm": "143000",
            "extra": "extra_value",
        }
        await ws_client._handle_message(json.dumps({"body": body}))
        assert received[0].raw == body


# ── 콜백 동작 테스트 ───────────────────────────────────────────


class TestCallbacks:
    """on_tick / on_order_exec / on_balance 콜백 동작."""

    async def test_on_tick_not_set_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """on_tick 미설정 시 주식체결 메시지 처리도 에러 없음."""
        msg = json.dumps(
            {
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["stock_tick"],
                    "stk_cd": "005930",
                    "cur_prc": "70000",
                    "trde_qty": "100",
                    "cntr_tm": "143000",
                }
            }
        )
        await ws_client._handle_message(msg)

    async def test_on_order_exec_not_set_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """on_order_exec 미설정 시 주문체결 메시지 처리도 에러 없음."""
        msg = json.dumps(
            {
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["order_exec"],
                    "stk_cd": "005930",
                    "ord_no": "1",
                    "trde_tp": "BUY",
                    "cntr_prc": "70000",
                    "cntr_qty": "1",
                    "ord_stat": "",
                    "cntr_tm": "",
                }
            }
        )
        await ws_client._handle_message(msg)

    async def test_on_balance_not_set_no_error(self, ws_client: KiwoomWebSocket) -> None:
        """on_balance 미설정 시 잔고 메시지 처리도 에러 없음."""
        msg = json.dumps(
            {
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["balance"],
                    "stk_cd": "005930",
                    "rmnd_qty": "10",
                    "pur_pric": "65000",
                    "cur_prc": "70000",
                }
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
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["stock_tick"],
                    "stk_cd": "005930",
                    "cur_prc": "70000",
                    "trde_qty": "100",
                    "cntr_tm": "143000",
                }
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
                "body": {
                    "trnm": WS_TRNM_REAL,
                    "type": REALTIME_TYPES["stock_tick"],
                    "stk_cd": "005930",
                    "cur_prc": "70000",
                    "trde_qty": "100",
                    "cntr_tm": "143000",
                }
            }
        )
        mock_ws = _make_mock_ws([message])
        with patch("src.broker.realtime.connect", _make_mock_connect(mock_ws)):
            await ws_client.connect()
            await asyncio.sleep(0.05)
            await ws_client.close()

        assert len(received) == 1
        assert received[0].symbol == "005930"

    async def test_run_loop_reconnects_on_exception(self, ws_client: KiwoomWebSocket) -> None:
        """연결 오류 발생 시 재연결을 시도한다."""
        call_count = [0]

        async def failing_aiter() -> AsyncIterator[str]:
            raise RuntimeError("연결 끊김")
            yield  # type: ignore[misc]  # 제너레이터 표시용

        # 첫 번째: 내부 에러 발생, 두 번째: 빈 메시지로 대기
        mock_fail = AsyncMock()
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
            await asyncio.sleep(0.15)
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
            await asyncio.sleep(0.15)
            await ws_client.close()

        # 두 번째 연결에서 subscribe가 재호출되어야 함
        assert ws2.send.await_count >= 1


# ── 스키마 테스트 ─────────────────────────────────────────────


class TestRealtimeSubscription:
    """RealtimeSubscription Pydantic 스키마 검증."""

    def test_creation_with_required_fields(self) -> None:
        """필수 필드로 정상 생성."""
        sub = RealtimeSubscription(
            trnm=WS_TRNM_REG,
            data=[{"item": "KRX:005930", "type": "0B"}],
        )
        assert sub.trnm == WS_TRNM_REG
        assert sub.grp_no == "0000"
        assert sub.refresh == "1"

    def test_remove_trnm(self) -> None:
        """REMOVE trnm으로 생성."""
        sub = RealtimeSubscription(
            trnm=WS_TRNM_REMOVE,
            data=[{"item": "KRX:005930", "type": "0B"}],
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
