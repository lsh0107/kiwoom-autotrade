"""src.utils.secret_masking 테스트.

공용 시크릿 마스킹 함수/Filter/structlog processor 동작을 검증한다.
`process_manager._mask_secrets`가 이 유틸로 통합되었으므로,
기존 패턴 보존 + 새로운 logging.Filter/structlog 경로를 같이 확인한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.utils.secret_masking import (
    SecretMaskingFilter,
    mask_secrets,
    structlog_mask_processor,
)

# 테스트용 가짜 시크릿 (런타임 조립 — 리터럴이면 pre-commit/훅에 차단됨)
_BOT_PREFIX = "bot"


def _fake_telegram_token() -> str:
    """테스트용 Telegram bot token 조립."""
    return f"{_BOT_PREFIX}1234567890:" + "A" * 30 + "_B-C"


class TestMaskSecrets:
    """`mask_secrets` 단위 테스트."""

    def test_mask_telegram_bot_token(self) -> None:
        """Telegram bot token이 마스킹된다."""
        token = _fake_telegram_token()
        line = f"sending update via https://api.telegram.org/{token}/sendMessage"
        masked = mask_secrets(line)
        assert token not in masked
        assert f"{_BOT_PREFIX}***:***" in masked

    def test_mask_bearer_token(self) -> None:
        """Bearer 토큰이 마스킹된다."""
        token_body = "eyJhbGciOiJIUzI1NiJ9.abc.def"
        line = f"Authorization: Bearer {token_body}"
        masked = mask_secrets(line)
        assert token_body not in masked
        assert "Bearer ***" in masked

    def test_mask_long_api_key(self) -> None:
        """32자 이상 영숫자(키움 app_key 등)가 마스킹된다."""
        long_key = "A" * 40
        line = f"app_key={long_key} loaded"
        masked = mask_secrets(line)
        assert long_key not in masked
        assert "***" in masked

    def test_normal_log_preserved(self) -> None:
        """일반 로그(시크릿 없음)는 그대로 유지된다."""
        line = "[live_trader] 종목 005930 매수 주문 완료 (수량=10)"
        assert mask_secrets(line) == line

    def test_short_alnum_not_masked(self) -> None:
        """짧은 영숫자 토큰(종목코드 등)은 마스킹되지 않는다."""
        line = "종목코드 005930 주문"
        masked = mask_secrets(line)
        assert "005930" in masked

    def test_non_string_input_coerced(self) -> None:
        """문자열이 아닌 입력도 str() 거쳐 처리되며 예외를 던지지 않는다."""
        assert mask_secrets(12345) == "12345"  # type: ignore[arg-type]


class TestSecretMaskingFilter:
    """`SecretMaskingFilter` 동작 테스트."""

    def test_filter_masks_msg(self) -> None:
        """record.msg가 마스킹된다."""
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="t",
            lineno=0,
            msg=f"Bearer {'x' * 40}",
            args=None,
            exc_info=None,
        )
        SecretMaskingFilter().filter(record)
        assert "Bearer ***" in record.msg  # type: ignore[operator]
        assert "x" * 40 not in record.msg  # type: ignore[operator]

    def test_filter_masks_args_tuple(self) -> None:
        """`%s` args tuple의 문자열 요소가 마스킹된다."""
        token = _fake_telegram_token()
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="t",
            lineno=0,
            msg="calling %s with body %s",
            args=(f"https://api.telegram.org/{token}/sendMessage", "ok"),
            exc_info=None,
        )
        SecretMaskingFilter().filter(record)
        rendered = record.getMessage()
        assert token not in rendered
        assert f"{_BOT_PREFIX}***:***" in rendered

    def test_filter_masks_args_dict(self) -> None:
        """`%(key)s` 스타일 dict args의 문자열 값이 마스킹된다."""
        token = _fake_telegram_token()
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="t",
            lineno=0,
            msg="url=%(url)s status=%(status)s",
            args={"url": f"https://t.me/{token}", "status": 200},
            exc_info=None,
        )
        SecretMaskingFilter().filter(record)
        assert token not in record.getMessage()
        assert record.getMessage().count("200") == 1  # 숫자는 보존

    def test_filter_returns_true(self) -> None:
        """filter는 레코드를 항상 통과시킨다."""
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="t",
            lineno=0,
            msg="ok",
            args=None,
            exc_info=None,
        )
        assert SecretMaskingFilter().filter(record) is True


class TestFileHandlerIntegration:
    """실제 파일 핸들러 경로에서 마스킹이 적용되는지 검증."""

    def test_file_handler_masks_output(self, tmp_path: Path) -> None:
        """파일에 쓰이는 최종 출력이 마스킹된다."""
        log_path = tmp_path / "out.log"
        logger = logging.getLogger("test_secret_masking.file_handler")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False

        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.addFilter(SecretMaskingFilter())
        logger.addHandler(handler)

        token = _fake_telegram_token()
        logger.info("HTTP Request: POST https://api.telegram.org/%s/sendMessage", token)
        logger.info("normal order log 종목=005930 quantity=10")

        handler.flush()
        handler.close()

        content = log_path.read_text(encoding="utf-8")
        assert token not in content
        assert f"{_BOT_PREFIX}***:***" in content
        assert "005930" in content  # 정상 로그는 보존


class TestStructlogProcessor:
    """structlog processor 동작 테스트."""

    def test_processor_masks_event_values(self) -> None:
        """event dict의 문자열 값이 마스킹된다."""
        token = _fake_telegram_token()
        event = {
            "event": f"posting to {token}",
            "url": f"https://api.telegram.org/{token}",
            "status": 200,
        }
        result = structlog_mask_processor(None, "info", event)
        assert token not in result["event"]  # type: ignore[operator]
        assert token not in result["url"]  # type: ignore[operator]
        assert result["status"] == 200

    def test_processor_preserves_non_string(self) -> None:
        """문자열이 아닌 값은 변형되지 않는다."""
        event = {"count": 10, "ok": True, "tags": ["a", "b"]}
        result = structlog_mask_processor(None, "info", event)
        assert result == event
