"""텔레그램 양방향 핸들러 — 폴링 기반 메시지 수신 + 명령 디스패치.

python-telegram-bot v22 Application을 사용하여 별도 asyncio task로 실행.
live_trader의 이벤트 루프 안에서 start/stop으로 제어한다.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

log = logging.getLogger(__name__)


class TelegramHandler:
    """텔레그램 폴링 수신 + 명령 실행.

    Args:
        token: 봇 토큰.
        allowed_chat_ids: 허용된 chat_id 목록 (인증).
        command_callback: 명령 처리 콜백 (text: str) -> str.
    """

    def __init__(
        self,
        token: str,
        allowed_chat_ids: list[str],
        command_callback: Any | None = None,
    ) -> None:
        self._token = token
        self._allowed_chat_ids = set(allowed_chat_ids)
        self._command_callback = command_callback
        self._app: Any | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def running(self) -> bool:
        """폴링 실행 중 여부."""
        return self._running

    def set_command_callback(self, callback: Any) -> None:
        """명령 처리 콜백 설정. (text: str) -> str."""
        self._command_callback = callback

    async def start(self) -> None:
        """폴링을 시작한다 (백그라운드 태스크)."""
        if not self._token:
            log.warning("텔레그램 봇 토큰 없음 — 양방향 비활성")
            return
        if not self._allowed_chat_ids:
            log.warning("허용된 chat_id 없음 — 양방향 비활성")
            return
        if self._running:
            return

        try:
            from telegram import Update
            from telegram.ext import ApplicationBuilder, MessageHandler, filters

            self._app = ApplicationBuilder().token(self._token).build()

            async def _on_message(update: Update, context: Any) -> None:  # noqa: ARG001
                """모든 텍스트 메시지 핸들러."""
                if update.message is None:
                    return
                chat_id = str(update.message.chat_id)
                if chat_id not in self._allowed_chat_ids:
                    log.warning("미등록 chat_id 무시: %s", chat_id)
                    return

                text = update.message.text or ""
                if not text.strip():
                    return

                log.info("텔레그램 수신: [%s] %s", chat_id, text)

                if self._command_callback is None:
                    reply = "명령 처리가 준비되지 않았습니다."
                else:
                    try:
                        reply = self._command_callback(text)
                    except Exception as e:
                        log.exception("명령 처리 에러: %s", text)
                        reply = f"명령 처리 실패: {e}"

                try:
                    await update.message.reply_text(reply)
                except Exception as e:
                    log.warning("텔레그램 회신 실패: %s", e)

            self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

            # 슬래시 명령도 동일 핸들러로 처리
            self._app.add_handler(MessageHandler(filters.COMMAND, _on_message))

            await self._app.initialize()
            await self._app.start()
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            log.info("텔레그램 양방향 핸들러 시작 (chat_ids: %s)", self._allowed_chat_ids)

        except Exception:
            log.exception("텔레그램 핸들러 시작 실패")

    async def _poll_loop(self) -> None:
        """updater 폴링 루프."""
        if self._app is None:
            return
        try:
            updater = self._app.updater
            if updater is None:
                log.error("Updater가 없음 — 폴링 불가")
                return
            await updater.start_polling(drop_pending_updates=True)
            # 폴링은 자체 루프로 동작 — 여기서는 종료 대기만
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("텔레그램 폴링 에러")
        finally:
            self._running = False

    async def stop(self) -> None:
        """폴링을 중지한다."""
        if not self._running:
            return

        self._running = False

        try:
            if self._app and self._app.updater:
                await self._app.updater.stop()
            if self._app:
                await self._app.stop()
                await self._app.shutdown()
        except Exception:
            log.exception("텔레그램 핸들러 종료 에러")

        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self._app = None
        self._task = None
        log.info("텔레그램 양방향 핸들러 종료")
