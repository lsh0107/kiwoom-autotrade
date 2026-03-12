"""키움증권 WebSocket 실시간 시세 클라이언트."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import structlog
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from src.broker.constants import (
    REALTIME_TYPES,
    WS_DEFAULT_GRP,
    WS_ENDPOINT,
    WS_PORT,
    WS_RECONNECT_BASE_DELAY,
    WS_RECONNECT_MAX_DELAY,
    WS_RECONNECT_MAX_RETRIES,
    WS_TRNM_LOGIN,
    WS_TRNM_PING,
    WS_TRNM_PONG,
    WS_TRNM_REAL,
    WS_TRNM_REG,
    WS_TRNM_REMOVE,
)
from src.broker.schemas import RealtimeBalance, RealtimeOrderExec, RealtimeTick
from src.utils.exceptions import BrokerError

logger = structlog.get_logger("broker.realtime")

# 콜백 타입 정의
TickCallback = Callable[[RealtimeTick], Coroutine[Any, Any, None]]
OrderExecCallback = Callable[[RealtimeOrderExec], Coroutine[Any, Any, None]]
BalanceCallback = Callable[[RealtimeBalance], Coroutine[Any, Any, None]]


def _to_ws_url(base_url: str) -> str:
    """REST API 베이스 URL을 WebSocket URL로 변환 (포트 10000 포함).

    https://mockapi.kiwoom.com → wss://mockapi.kiwoom.com:10000/api/dostk/websocket

    Args:
        base_url: REST API 베이스 URL

    Returns:
        WebSocket URL (포트 10000 포함)
    """
    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    host = ws_base.rstrip("/")
    return f"{host}:{WS_PORT}{WS_ENDPOINT}"


def _safe_ws_int(value: str | int | None, default: int = 0) -> int:
    """WebSocket 데이터 정수 변환 (부호 제거, 빈값 처리).

    부호 있는 문자열("+20800", "-20800")에서 절대값 정수를 추출한다.
    가격 등 크기만 필요한 필드에 사용한다.

    Args:
        value: 변환 대상 값
        default: 변환 실패 시 기본값

    Returns:
        절댓값 정수
    """
    if value is None:
        return default
    if isinstance(value, int):
        return abs(value)
    try:
        return abs(int(str(value).strip().replace(",", "")))
    except (ValueError, TypeError):
        return default


class KiwoomWebSocket:
    """키움증권 WebSocket 실시간 시세 클라이언트.

    구독 등록 → 실시간 데이터 수신 → 콜백 호출.
    연결 끊김 시 exponential backoff로 자동 재연결.
    """

    def __init__(
        self,
        *,
        base_url: str,
        get_token: Callable[[], Coroutine[Any, Any, str]],
        is_mock: bool = True,
    ) -> None:
        """클라이언트 초기화.

        Args:
            base_url: 키움 API 베이스 URL (예: https://mockapi.kiwoom.com)
            get_token: 유효한 Bearer 토큰을 반환하는 async callable
            is_mock: 모의투자 여부 (로깅 목적)
        """
        self._ws_url = _to_ws_url(base_url)
        self._get_token = get_token
        self._is_mock = is_mock

        self._ws: ClientConnection | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._reconnect_attempt: int = 0
        self._login_ok: bool = False

        # 재연결 시 재구독을 위한 구독 이력 저장 (symbols, data_type, grp_no)
        self._subscriptions_log: list[tuple[list[str], str, str]] = []

        # 타입별 콜백
        self.on_tick: TickCallback | None = None
        self.on_order_exec: OrderExecCallback | None = None
        self.on_balance: BalanceCallback | None = None

        logger.info(
            "WebSocket 클라이언트 초기화",
            ws_url=self._ws_url,
            is_mock=is_mock,
        )

    @property
    def is_connected(self) -> bool:
        """WebSocket 연결 상태를 반환한다."""
        return self._ws is not None

    async def connect(self) -> None:
        """WebSocket 서버에 연결하고 재연결 포함 수신 루프를 시작한다.

        Raises:
            BrokerError: 이미 실행 중인 경우
        """
        if self._run_task is not None and not self._run_task.done():
            raise BrokerError("이미 WebSocket이 연결 중입니다.")

        self._reconnect_attempt = 0
        self._run_task = asyncio.create_task(self._run_loop())
        logger.info("WebSocket 연결 태스크 시작", url=self._ws_url)

    async def close(self) -> None:
        """WebSocket 연결을 종료하고 수신 루프를 정리한다."""
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._run_task
            self._run_task = None

        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

        self._login_ok = False
        self._subscriptions_log.clear()
        logger.info("WebSocket 연결 종료")

    # disconnect는 close의 별칭 (하위 호환)
    disconnect = close

    async def subscribe(
        self,
        symbols: list[str],
        data_type: str = REALTIME_TYPES["stock_tick"],
        grp_no: str = WS_DEFAULT_GRP,
    ) -> None:
        """종목 실시간 데이터 구독을 등록한다.

        flat JSON 포맷, item/type은 배열, authorization 불필요 (로그인으로 인증).

        Args:
            symbols: 종목코드 리스트 (예: ["005930", "000660"])
                     계좌 레벨 구독(주문체결/잔고)은 [""] 전달
            data_type: 실시간 타입 코드 (기본값: "0B" 주식체결)
            grp_no: 그룹 번호

        Raises:
            BrokerError: WebSocket이 연결되지 않은 경우
        """
        if self._ws is None:
            raise BrokerError("WebSocket이 연결되지 않았습니다. connect()를 먼저 호출하세요.")

        message = {
            "trnm": WS_TRNM_REG,
            "grp_no": grp_no,
            "refresh": "1",
            "data": [{"item": symbols, "type": [data_type]}],
        }

        await self._ws.send(json.dumps(message))
        self._subscriptions_log.append((symbols, data_type, grp_no))
        logger.info("구독 등록 요청 전송", symbols=symbols, data_type=data_type, grp_no=grp_no)

    async def unsubscribe(
        self,
        symbols: list[str],
        data_type: str = REALTIME_TYPES["stock_tick"],
        grp_no: str = WS_DEFAULT_GRP,
    ) -> None:
        """종목 실시간 데이터 구독을 해지한다.

        flat JSON 포맷, item/type은 배열.

        Args:
            symbols: 종목코드 리스트
            data_type: 실시간 타입 코드
            grp_no: 그룹 번호

        Raises:
            BrokerError: WebSocket이 연결되지 않은 경우
        """
        if self._ws is None:
            raise BrokerError("WebSocket이 연결되지 않았습니다.")

        message = {
            "trnm": WS_TRNM_REMOVE,
            "grp_no": grp_no,
            "data": [{"item": symbols, "type": [data_type]}],
        }

        await self._ws.send(json.dumps(message))
        # 구독 이력에서 해당 항목 제거
        self._subscriptions_log = [
            (syms, dt, gn)
            for syms, dt, gn in self._subscriptions_log
            if not (set(syms) == set(symbols) and dt == data_type and gn == grp_no)
        ]
        logger.info("구독 해지 요청 전송", symbols=symbols, data_type=data_type)

    async def run_until(self, stop_time: str) -> None:
        """지정 시각까지 WebSocket 수신을 유지한 후 종료한다.

        connect()가 아직 호출되지 않았으면 자동으로 연결한다.

        Args:
            stop_time: 종료 시각 (HHMMSS 형식, 예: "153000")
        """
        if self._run_task is None or self._run_task.done():
            await self.connect()

        now = datetime.now(UTC)
        target = now.replace(
            hour=int(stop_time[:2]),
            minute=int(stop_time[2:4]),
            second=int(stop_time[4:6]),
            microsecond=0,
        )
        remaining = (target - now).total_seconds()

        if remaining <= 0:
            logger.info("종료 시각이 이미 지남, 즉시 종료", stop_time=stop_time)
            await self.close()
            return

        logger.info("지정 시각까지 실행", stop_time=stop_time, remaining_sec=remaining)
        await asyncio.sleep(remaining)
        await self.close()

    # ── 내부 루프 ────────────────────────────────────────

    async def _send_login(self) -> bool:
        """WebSocket 로그인 패킷을 전송하고 성공 여부를 반환한다.

        연결 직후 반드시 호출해야 한다. 로그인 없이 구독 시 R10004 에러.
        토큰에서 'Bearer ' 접두사를 제거하여 순수 토큰값만 전송.

        Returns:
            로그인 성공 여부
        """
        token = await self._get_token()
        # Bearer 접두사 제거 (WebSocket은 순수 토큰값만 허용)
        if token.startswith("Bearer "):
            token = token[7:]

        await self._ws.send(json.dumps({"trnm": WS_TRNM_LOGIN, "token": token}))
        logger.debug("로그인 패킷 전송")

        # 로그인 응답 대기 (최대 10초)
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
        except TimeoutError:
            logger.error("로그인 응답 시간 초과")
            return False

        try:
            resp = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("로그인 응답 JSON 파싱 실패", raw=str(raw)[:200])
            return False

        if resp.get("trnm") != WS_TRNM_LOGIN:
            logger.error("예상치 못한 로그인 응답", resp=resp)
            return False

        return_code = resp.get("return_code", -1)
        if return_code == 0:
            logger.info("WebSocket 로그인 성공")
            return True

        logger.error(
            "WebSocket 로그인 실패",
            return_code=return_code,
            return_msg=resp.get("return_msg", ""),
        )
        return False

    async def _run_loop(self) -> None:
        """재연결 포함 메인 실행 루프.

        연결 끊김 발생 시 exponential backoff로 재연결을 시도한다.
        최대 재시도 횟수 초과 시 루프를 종료한다.
        """
        while True:
            try:
                # ping_interval=None: 키움 자체 PING/PONG 사용 (websockets 자동 ping 비활성화)
                async with connect(
                    self._ws_url,
                    ping_interval=None,
                    ping_timeout=None,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    self._login_ok = False
                    self._reconnect_attempt = 0
                    logger.info("WebSocket 연결 수립", url=self._ws_url)

                    # 연결 직후 로그인 필수
                    self._login_ok = await self._send_login()
                    if not self._login_ok:
                        logger.error("로그인 실패로 연결 종료")
                        break

                    # 재연결 후 기존 구독 복구
                    if self._subscriptions_log:
                        await self._replay_subscriptions()

                    async for raw in ws:
                        await self._handle_message(raw)

            except asyncio.CancelledError:
                logger.debug("실행 루프 취소됨")
                break

            except ConnectionClosed as exc:
                self._ws = None
                self._login_ok = False
                logger.warning("WebSocket 연결 끊김", reason=str(exc))

            except Exception as exc:
                self._ws = None
                self._login_ok = False
                logger.error("WebSocket 오류", error=str(exc))

            # 재연결 시도 여부 판단
            self._reconnect_attempt += 1
            if self._reconnect_attempt > WS_RECONNECT_MAX_RETRIES:
                logger.error(
                    "최대 재연결 횟수 초과, 루프 종료",
                    max_retries=WS_RECONNECT_MAX_RETRIES,
                )
                break

            delay = min(
                WS_RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempt - 1)),
                WS_RECONNECT_MAX_DELAY,
            )
            logger.info(
                "재연결 대기",
                attempt=self._reconnect_attempt,
                delay_sec=delay,
            )
            await asyncio.sleep(delay)

        self._ws = None
        self._login_ok = False

    async def _replay_subscriptions(self) -> None:
        """재연결 후 기존 구독을 복구한다."""
        logger.info("구독 복구 시작", count=len(self._subscriptions_log))
        # 복구 중 _subscriptions_log가 변경되지 않도록 스냅샷 사용
        snapshot = list(self._subscriptions_log)
        self._subscriptions_log = []

        for symbols, data_type, grp_no in snapshot:
            try:
                await self.subscribe(symbols, data_type, grp_no)
            except Exception as exc:
                logger.error(
                    "구독 복구 실패",
                    symbols=symbols,
                    data_type=data_type,
                    error=str(exc),
                )

    async def _handle_message(self, raw: str | bytes) -> None:
        """수신된 WebSocket 메시지를 파싱하고 처리한다.

        응답은 flat 구조 (body 감싸기 없음).

        Args:
            raw: 원시 메시지 (JSON 문자열 또는 bytes)
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패", raw=str(raw)[:200])
            return

        # 응답은 flat (body 없음): data에서 직접 trnm 추출
        trnm = data.get("trnm", "")

        if trnm == WS_TRNM_PING:
            # 서버 PING → 즉시 PONG 응답 (미응답 시 서버가 연결 종료)
            await self._ws.send(json.dumps({"trnm": WS_TRNM_PONG}))
            logger.debug("PING 수신 → PONG 전송")

        elif trnm == WS_TRNM_REG:
            # 구독 등록 서버 확인 응답 (return_code는 int)
            return_code = data.get("return_code", -1)
            if return_code == 0:
                logger.info("구독 등록 확인", msg=data.get("return_msg", ""))
            else:
                logger.warning(
                    "구독 등록 실패",
                    code=return_code,
                    msg=data.get("return_msg", ""),
                )

        elif trnm == WS_TRNM_REMOVE:
            return_code = data.get("return_code", -1)
            if return_code == 0:
                logger.info("구독 해지 확인")
            else:
                logger.warning("구독 해지 실패", code=return_code)

        elif trnm == WS_TRNM_REAL:
            # 실시간 데이터: data["data"] 배열 순회
            for item_data in data.get("data", []):
                await self._dispatch_realtime(item_data)

        else:
            logger.debug("알 수 없는 trnm 수신", trnm=trnm)

    async def _dispatch_realtime(self, item_data: dict) -> None:
        """실시간 데이터 항목을 타입에 따라 파싱하여 콜백을 호출한다.

        REAL 데이터 각 항목 구조:
          {"type":"0B","name":"주식체결","item":"005930","values":{"10":"-20800",...}}

        values 숫자 코드:
          주식체결(0B): "10"=현재가, "20"=체결시간, "15"=거래량, "13"=누적거래량
          주문체결(00): "9203"=주문번호, "9001"=종목코드, "905"=주문구분,
                        "907"=매도수구분, "910"=체결가, "911"=체결량,
                        "913"=주문상태, "908"=주문/체결시간
          잔고(04):     "9001"=종목코드, "10"=현재가, "930"=보유수량,
                        "931"=매입단가, "8019"=손익률

        Args:
            item_data: REAL data 배열의 개별 항목
        """
        data_type: str = item_data.get("type", "")
        symbol: str = item_data.get("item", "")
        values: dict = item_data.get("values", {})

        if data_type == REALTIME_TYPES["stock_tick"]:
            # 주식체결(0B): "10"=현재가(부호), "20"=체결시간, "15"=거래량, "13"=누적거래량
            if self.on_tick is not None:
                tick = RealtimeTick(
                    symbol=symbol,
                    price=_safe_ws_int(values.get("10")),
                    volume=_safe_ws_int(values.get("15")),
                    timestamp=str(values.get("20", "")),
                    raw=item_data,
                )
                await self._safe_callback(self.on_tick, tick, symbol=symbol)

        elif data_type == REALTIME_TYPES["order_exec"]:
            # 주문체결(00): "9203"=주문번호, "9001"=종목코드, "905"=주문구분,
            #               "910"=체결가, "911"=체결량, "913"=주문상태, "908"=체결시간
            if self.on_order_exec is not None:
                order_exec = RealtimeOrderExec(
                    order_no=str(values.get("9203", "")),
                    symbol=str(values.get("9001", symbol)),
                    side=str(values.get("905", "")),
                    price=_safe_ws_int(values.get("910")),
                    quantity=_safe_ws_int(values.get("911")),
                    status=str(values.get("913", "")),
                    timestamp=str(values.get("908", "")),
                    raw=item_data,
                )
                await self._safe_callback(self.on_order_exec, order_exec, symbol=symbol)

        elif data_type == REALTIME_TYPES["balance"]:
            # 잔고(04): "9001"=종목코드, "10"=현재가, "930"=보유수량,
            #           "931"=매입단가, "8019"=손익률
            if self.on_balance is not None:
                quantity = _safe_ws_int(values.get("930"))
                avg_price = _safe_ws_int(values.get("931"))
                current_price = _safe_ws_int(values.get("10"))
                eval_amount = current_price * quantity
                pur_amount = avg_price * quantity
                profit_pct = (
                    round(((eval_amount - pur_amount) / pur_amount) * 100, 2)
                    if pur_amount > 0
                    else 0.0
                )
                balance = RealtimeBalance(
                    symbol=str(values.get("9001", symbol)),
                    quantity=quantity,
                    avg_price=avg_price,
                    current_price=current_price,
                    eval_amount=eval_amount,
                    profit_pct=profit_pct,
                    raw=item_data,
                )
                await self._safe_callback(self.on_balance, balance, symbol=symbol)

        else:
            logger.debug("처리되지 않은 실시간 데이터 타입", data_type=data_type, symbol=symbol)

    async def _safe_callback(
        self,
        callback: Callable[..., Coroutine[Any, Any, None]],
        payload: Any,
        *,
        symbol: str,
    ) -> None:
        """콜백을 안전하게 실행한다. 예외가 발생해도 수신 루프는 계속된다.

        Args:
            callback: 실행할 async 콜백
            payload: 콜백에 전달할 데이터
            symbol: 로깅용 종목코드
        """
        try:
            await callback(payload)
        except Exception as exc:
            logger.error("콜백 실행 오류", symbol=symbol, error=str(exc))
