"""텔레그램 양방향 핸들러 — Bot.get_updates() 직접 폴링.

Application/Updater 프레임워크 대신 Bot API를 직접 호출하여
기존 asyncio 이벤트 루프와의 충돌을 방지한다.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

log = logging.getLogger(__name__)

_POLL_INTERVAL = 2.0  # 폴링 간격 (초)
_POLL_TIMEOUT = 10  # long-polling timeout (초)


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
        self._bot: Any | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._last_update_id = 0

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
            from telegram import Bot

            self._bot = Bot(self._token)

            # 기존 pending 업데이트 무시
            async with self._bot:
                updates = await self._bot.get_updates(timeout=0)
                if updates:
                    self._last_update_id = updates[-1].update_id

            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            log.info("텔레그램 양방향 핸들러 시작 (chat_ids: %s)", self._allowed_chat_ids)

        except Exception:
            log.exception("텔레그램 핸들러 시작 실패")

    async def _poll_loop(self) -> None:
        """Bot.get_updates() 직접 폴링 루프."""
        if self._bot is None:
            return

        try:
            async with self._bot:
                while self._running:
                    try:
                        updates = await self._bot.get_updates(
                            offset=self._last_update_id + 1,
                            timeout=_POLL_TIMEOUT,
                        )
                        for update in updates:
                            self._last_update_id = update.update_id
                            await self._handle_update(update)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        log.warning(
                            "텔레그램 폴링 에러, %s초 후 재시도", _POLL_INTERVAL, exc_info=True
                        )
                        await asyncio.sleep(_POLL_INTERVAL)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("텔레그램 폴링 루프 종료")
        finally:
            self._running = False

    async def _handle_update(self, update: Any) -> None:
        """수신된 업데이트를 처리한다."""
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
                result = self._command_callback(text)
                reply = await result if asyncio.iscoroutine(result) else result
            except Exception as e:
                log.exception("명령 처리 에러: %s", text)
                reply = f"명령 처리 실패: {e}"

        try:
            await update.message.reply_text(reply)
        except Exception as e:
            log.warning("텔레그램 회신 실패: %s", e)

    async def stop(self) -> None:
        """폴링을 중지한다."""
        if not self._running:
            return

        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self._bot = None
        self._task = None
        log.info("텔레그램 양방향 핸들러 종료")
