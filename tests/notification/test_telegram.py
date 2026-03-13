"""텔레그램 알림 모듈 테스트.

TelegramNotifier의 메시지 발송, 포맷, 예외 처리를 검증한다.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.notification.telegram import TelegramNotifier, _reason_label

# ── 초기화 ───────────────────────────────────────────


class TestTelegramNotifierInit:
    """TelegramNotifier 초기화 테스트."""

    def test_empty_token_no_bot(self) -> None:
        """토큰 없으면 봇 미생성."""
        notifier = TelegramNotifier("", "chat-id")
        assert notifier._bot is None

    def test_empty_chat_id_no_bot(self) -> None:
        """chat_id 없으면 봇 미생성."""
        notifier = TelegramNotifier("token", "")
        assert notifier._bot is None

    def test_both_empty_no_bot(self) -> None:
        """토큰과 chat_id 둘 다 없으면 봇 미생성."""
        notifier = TelegramNotifier("", "")
        assert notifier._bot is None

    @patch("telegram.Bot")
    def test_with_credentials_creates_bot(self, mock_bot_cls: AsyncMock) -> None:
        """토큰·chat_id 있으면 봇 생성."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")

        mock_bot_cls.assert_called_once_with("test-token")
        assert notifier._bot is mock_bot


# ── send ─────────────────────────────────────────────


class TestSend:
    """send 메서드 테스트."""

    async def test_no_bot_returns_silently(self) -> None:
        """봇 없으면 아무것도 안 하고 리턴."""
        notifier = TelegramNotifier("", "")
        await notifier.send("테스트 메시지")  # 예외 없이 완료

    @patch("telegram.Bot")
    async def test_calls_send_message(self, mock_bot_cls: AsyncMock) -> None:
        """봇 있으면 send_message 호출."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send("테스트")

        mock_bot.send_message.assert_called_once_with(chat_id="test-chat-id", text="테스트")

    @patch("telegram.Bot")
    async def test_truncates_long_message(self, mock_bot_cls: AsyncMock) -> None:
        """4096자 초과 메시지는 잘라서 전송."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        long_msg = "X" * 5000
        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send(long_msg)

        sent_text = mock_bot.send_message.call_args.kwargs["text"]
        assert len(sent_text) == 4096

    @patch("telegram.Bot")
    async def test_exception_does_not_propagate(self, mock_bot_cls: AsyncMock) -> None:
        """send_message 예외가 밖으로 전파되지 않음."""
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = Exception("네트워크 오류")
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send("테스트")  # 예외 없이 완료


# ── send_start ───────────────────────────────────────


class TestSendStart:
    """send_start 메서드 테스트."""

    @patch("telegram.Bot")
    async def test_format(self, mock_bot_cls: AsyncMock) -> None:
        """시작 알림 포맷 확인."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send_start(["momentum", "mean_reversion"], 10)

        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "자동매매 시작" in text
        assert "momentum, mean_reversion" in text
        assert "10종목" in text


# ── send_buy ─────────────────────────────────────────


class TestSendBuy:
    """send_buy 메서드 테스트."""

    @patch("telegram.Bot")
    async def test_format(self, mock_bot_cls: AsyncMock) -> None:
        """매수 알림 포맷 확인: 종목명, 수량, 가격, 합계, 전략."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send_buy("005930", "삼성전자", 10, 70000, "momentum")

        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "매수" in text
        assert "삼성전자" in text
        assert "10주" in text
        assert "70,000원" in text
        assert "700,000원" in text  # 10 * 70000
        assert "momentum" in text


# ── send_sell ────────────────────────────────────────


class TestSendSell:
    """send_sell 메서드 테스트."""

    @patch("telegram.Bot")
    async def test_profit_format(self, mock_bot_cls: AsyncMock) -> None:
        """익절 메시지: 양수 손익·한글 사유 포함."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send_sell("005930", "삼성전자", 10, 71000, 0.0123, "take_profit", "momentum")

        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "매도" in text
        assert "삼성전자" in text
        assert "10주" in text
        assert "+1.23%" in text
        assert "익절" in text
        assert "momentum" in text

    @patch("telegram.Bot")
    async def test_loss_format(self, mock_bot_cls: AsyncMock) -> None:
        """손절 메시지: 음수 손익 포맷."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send_sell("005930", "삼성전자", 10, 69500, -0.0050, "stop_loss", "momentum")

        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "-0.50%" in text
        assert "손절" in text


# ── send_summary ─────────────────────────────────────


class TestSendSummary:
    """send_summary 메서드 테스트."""

    @patch("telegram.Bot")
    async def test_format(self, mock_bot_cls: AsyncMock) -> None:
        """매매 요약 포맷 확인."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send_summary(5, 3, 0.667, 0.0234)

        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "매매 요약" in text
        assert "매수 5건" in text
        assert "매도 3건" in text
        assert "66.7%" in text
        assert "+2.34%" in text

    @patch("telegram.Bot")
    async def test_negative_pnl_format(self, mock_bot_cls: AsyncMock) -> None:
        """손실 요약 포맷 확인 (음수 손익)."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send_summary(3, 2, 0.5, -0.0150)

        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "-1.50%" in text


# ── send_error ───────────────────────────────────────


class TestSendError:
    """send_error 메서드 테스트."""

    @patch("telegram.Bot")
    async def test_format(self, mock_bot_cls: AsyncMock) -> None:
        """에러 메시지 포맷 확인."""
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        notifier = TelegramNotifier("test-token", "test-chat-id")
        await notifier.send_error("연결 실패: timeout")

        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "에러" in text
        assert "연결 실패: timeout" in text


# ── _reason_label ────────────────────────────────────


class TestReasonLabel:
    """_reason_label 헬퍼 함수 테스트."""

    @pytest.mark.parametrize(
        ("reason", "expected"),
        [
            ("take_profit", "익절"),
            ("stop_loss", "손절"),
            ("trailing_stop", "트레일링"),
            ("force_close", "강제청산"),
            ("end_of_day", "장마감"),
        ],
    )
    def test_known_reasons(self, reason: str, expected: str) -> None:
        """알려진 사유는 한글 레이블로 변환."""
        assert _reason_label(reason) == expected

    def test_unknown_reason_passthrough(self) -> None:
        """알 수 없는 사유는 원문 그대로 반환."""
        assert _reason_label("custom_reason") == "custom_reason"
