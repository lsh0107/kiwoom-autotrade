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
        assert handler._app is None

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

        mock_app = MagicMock()
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()

        mock_updater = MagicMock()
        mock_updater.stop = AsyncMock()
        mock_app.updater = mock_updater

        # 직접 내부 상태 설정으로 stop 흐름 테스트
        handler._app = mock_app
        handler._running = True
        handler._task = asyncio.create_task(asyncio.sleep(10))

        await handler.stop()

        assert not handler.running
        mock_updater.stop.assert_awaited_once()
        mock_app.stop.assert_awaited_once()
        mock_app.shutdown.assert_awaited_once()


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
