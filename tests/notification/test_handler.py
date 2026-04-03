"""텔레그램 핸들러 테스트."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.notification.handler import TelegramHandler


class TestTelegramHandlerInit:
    """초기화 테스트."""

    def test_default_state(self) -> None:
        """기본 상태: 미실행."""
        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])
        assert not handler.running
        assert handler._bot is None

    def test_set_command_callback(self) -> None:
        """콜백 설정."""
        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])

        def cb(text: str) -> str:
            return text

        handler.set_command_callback(cb)
        assert handler._command_callback is cb


class TestTelegramHandlerStart:
    """시작/종료 테스트."""

    @pytest.mark.asyncio()
    async def test_no_token_skips(self) -> None:
        """토큰 없으면 시작 안함."""
        handler = TelegramHandler(token="", allowed_chat_ids=["123"])
        await handler.start()
        assert not handler.running

    @pytest.mark.asyncio()
    async def test_no_chat_ids_skips(self) -> None:
        """chat_id 없으면 시작 안함."""
        handler = TelegramHandler(token="tok", allowed_chat_ids=[])
        await handler.start()
        assert not handler.running

    @pytest.mark.asyncio()
    async def test_start_and_stop(self) -> None:
        """시작 후 종료 — 내부 상태 직접 설정."""
        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])

        # 직접 내부 상태 설정으로 stop 흐름 테스트
        handler._bot = MagicMock()
        handler._running = True
        handler._task = asyncio.create_task(asyncio.sleep(10))

        await handler.stop()

        assert not handler.running
        assert handler._bot is None
        assert handler._task is None


class TestTelegramHandlerCallback:
    """콜백 호출 테스트."""

    def test_callback_called_with_text(self) -> None:
        """콜백이 텍스트와 함께 호출된다."""
        results: list[str] = []

        def cb(text: str) -> str:
            results.append(text)
            return f"reply: {text}"

        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])
        handler.set_command_callback(cb)

        # 직접 콜백 호출 테스트
        reply = handler._command_callback("/상태")  # type: ignore[misc]
        assert reply == "reply: /상태"
        assert results == ["/상태"]


class TestHandleUpdate:
    """_handle_update 테스트."""

    @pytest.mark.asyncio()
    async def test_allowed_chat_id(self) -> None:
        """허용된 chat_id 메시지 처리."""

        def cb(text: str) -> str:
            return f"ok: {text}"

        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])
        handler.set_command_callback(cb)

        # mock update
        update = MagicMock()
        update.message.chat_id = 123
        update.message.text = "/상태"
        update.message.reply_text = AsyncMock()

        await handler._handle_update(update)

        update.message.reply_text.assert_awaited_once_with("ok: /상태")

    @pytest.mark.asyncio()
    async def test_rejected_chat_id(self) -> None:
        """미등록 chat_id 무시."""
        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])

        update = MagicMock()
        update.message.chat_id = 999
        update.message.text = "/상태"
        update.message.reply_text = AsyncMock()

        await handler._handle_update(update)

        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_empty_message_ignored(self) -> None:
        """빈 메시지 무시."""
        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])

        update = MagicMock()
        update.message.chat_id = 123
        update.message.text = "   "
        update.message.reply_text = AsyncMock()

        await handler._handle_update(update)

        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_no_message_ignored(self) -> None:
        """message가 None이면 무시."""
        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])

        update = MagicMock()
        update.message = None

        await handler._handle_update(update)  # 에러 없이 통과

    @pytest.mark.asyncio()
    async def test_callback_exception_returns_error(self) -> None:
        """콜백 예외 시 에러 메시지 회신."""

        def bad_cb(text: str) -> str:
            raise ValueError("테스트 에러")

        handler = TelegramHandler(token="tok", allowed_chat_ids=["123"])
        handler.set_command_callback(bad_cb)

        update = MagicMock()
        update.message.chat_id = 123
        update.message.text = "/상태"
        update.message.reply_text = AsyncMock()

        await handler._handle_update(update)

        args = update.message.reply_text.call_args[0][0]
        assert "실패" in args
        assert "테스트 에러" in args
