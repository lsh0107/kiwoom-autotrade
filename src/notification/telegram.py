"""텔레그램 알림 모듈."""

import logging

log = logging.getLogger(__name__)

_MAX_MESSAGE_LEN = 4096


class TelegramNotifier:
    """텔레그램 알림 발송."""

    def __init__(self, token: str, chat_id: str) -> None:
        """초기화.

        Args:
            token: 텔레그램 봇 토큰.
            chat_id: 알림을 보낼 채팅 ID.
        """
        self._chat_id = chat_id
        if token and chat_id:
            try:
                from telegram import Bot

                self._bot: object | None = Bot(token)
            except Exception as e:
                log.warning("텔레그램 봇 초기화 실패: %s", e)
                self._bot = None
        else:
            self._bot = None

    async def send(self, message: str) -> None:
        """텍스트 메시지 발송.

        Args:
            message: 발송할 메시지. 4096자 초과 시 잘라서 보냄.
        """
        if self._bot is None:
            return
        text = message[:_MAX_MESSAGE_LEN]
        try:
            from telegram import Bot

            bot: Bot = self._bot  # type: ignore[assignment]
            await bot.send_message(chat_id=self._chat_id, text=text)
        except Exception as e:
            log.warning("텔레그램 메시지 발송 실패: %s", e)

    async def send_start(self, strategy_names: list[str], symbol_count: int) -> None:
        """매매 시작 알림.

        Args:
            strategy_names: 실행 전략 이름 목록.
            symbol_count: 감시 종목 수.
        """
        strategies_str = ", ".join(strategy_names)
        msg = f"📈 자동매매 시작\n전략: {strategies_str}\n감시: {symbol_count}종목"
        await self.send(msg)

    async def send_buy(
        self,
        symbol: str,  # noqa: ARG002
        name: str,
        qty: int,
        price: int,
        strategy: str,
    ) -> None:
        """매수 알림.

        Args:
            symbol: 종목코드.
            name: 종목명.
            qty: 매수 수량.
            price: 매수 가격 (원).
            strategy: 진입 전략명.
        """
        total = qty * price
        msg = f"🟢 매수 | {name}\n{qty}주 x {price:,}원 = {total:,}원\n전략: {strategy}"
        await self.send(msg)

    async def send_sell(
        self,
        symbol: str,  # noqa: ARG002
        name: str,
        qty: int,
        price: int,
        pnl_pct: float,
        reason: str,
        strategy: str,
    ) -> None:
        """매도 알림.

        Args:
            symbol: 종목코드.
            name: 종목명.
            qty: 매도 수량.
            price: 매도 가격 (원).
            pnl_pct: 손익률 (소수, 예: 0.0123 = +1.23%).
            reason: 매도 사유 (예: 익절, 손절, force_close).
            strategy: 전략명.
        """
        sign = "+" if pnl_pct >= 0 else ""
        reason_label = _reason_label(reason)
        msg = (
            f"🔴 매도 | {name}\n"
            f"{qty}주 x {price:,}원\n"
            f"손익: {sign}{pnl_pct * 100:.2f}% ({reason_label})\n"
            f"전략: {strategy}"
        )
        await self.send(msg)

    async def send_summary(
        self,
        total_buys: int,
        total_sells: int,
        win_rate: float,
        total_pnl: float,
    ) -> None:
        """매매 요약 알림.

        Args:
            total_buys: 총 매수 건수.
            total_sells: 총 매도 건수.
            win_rate: 승률 (소수, 예: 0.5 = 50%).
            total_pnl: 총 손익률 (소수).
        """
        sign = "+" if total_pnl >= 0 else ""
        msg = (
            f"📊 매매 요약\n"
            f"매수 {total_buys}건 / 매도 {total_sells}건\n"
            f"승률: {win_rate * 100:.1f}%\n"
            f"총 손익: {sign}{total_pnl * 100:.2f}%"
        )
        await self.send(msg)

    async def send_error(self, error: str) -> None:
        """에러 알림.

        Args:
            error: 에러 메시지.
        """
        await self.send(f"🚨 에러\n{error}")


def _reason_label(reason: str) -> str:
    """매도 사유 한글 레이블 변환."""
    labels: dict[str, str] = {
        "take_profit": "익절",
        "stop_loss": "손절",
        "trailing_stop": "트레일링",
        "force_close": "강제청산",
        "end_of_day": "장마감",
    }
    return labels.get(reason, reason)
