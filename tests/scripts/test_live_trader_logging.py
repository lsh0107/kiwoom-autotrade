"""scripts/live_trader.py `setup_logging` 통합 테스트.

실제 파일 핸들러 출력이 SecretMaskingFilter 경유로 마스킹되는지 검증한다.
ADR: file log Telegram/키움 토큰 평문 노출 방지.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from collections.abc import Iterator

from scripts import live_trader


@pytest.fixture
def isolated_root_logger() -> Iterator[None]:
    """테스트 전 루트 로거 상태를 백업하고 테스트 후 복구한다."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_filters = list(root.filters)
    original_level = root.level

    root.handlers.clear()
    for f in original_filters:
        root.removeFilter(f)

    yield

    root.handlers.clear()
    for f in list(root.filters):
        root.removeFilter(f)
    for h in original_handlers:
        root.addHandler(h)
    for f in original_filters:
        root.addFilter(f)
    root.setLevel(original_level)


_BOT_PREFIX = "bot"


def _fake_telegram_token() -> str:
    return f"{_BOT_PREFIX}1234567890:" + "A" * 30 + "_B-C"


def test_setup_logging_masks_file_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_root_logger: None,
) -> None:
    """setup_logging 이후 파일에 쓰인 Telegram 토큰이 마스킹된다."""
    monkeypatch.setattr(live_trader, "RESULTS_DIR", tmp_path)

    live_trader.setup_logging()

    token = _fake_telegram_token()
    # live_trader가 쓰는 `log`는 `logging.getLogger("live_trader")` — 루트로 전파됨
    live_trader.log.info("HTTP Request: POST https://api.telegram.org/%s/sendMessage", token)
    live_trader.log.info("주문 체결 종목=005930 수량=10")

    # FileHandler 플러시
    for handler in logging.getLogger().handlers:
        handler.flush()

    log_files = list(tmp_path.glob("live_*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")

    assert token not in content, "Telegram bot token이 파일 로그에 평문으로 남음"
    assert f"{_BOT_PREFIX}***:***" in content
    # 정상 로그는 보존
    assert "005930" in content


def test_setup_logging_masks_long_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_root_logger: None,
) -> None:
    """32자+ 영숫자 시크릿(키움 app_key 등)도 파일 로그에서 마스킹된다."""
    monkeypatch.setattr(live_trader, "RESULTS_DIR", tmp_path)

    live_trader.setup_logging()

    long_key = "Q" * 45
    live_trader.log.info("app_key=%s loaded", long_key)

    for handler in logging.getLogger().handlers:
        handler.flush()

    log_files = list(tmp_path.glob("live_*.log"))
    content = log_files[0].read_text(encoding="utf-8")

    assert long_key not in content
    assert "***" in content


def test_setup_logging_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_root_logger: None,
) -> None:
    """setup_logging을 두 번 호출해도 핸들러가 중복 쌓이지 않는다."""
    monkeypatch.setattr(live_trader, "RESULTS_DIR", tmp_path)

    live_trader.setup_logging()
    handlers_after_first = list(logging.getLogger().handlers)
    live_trader.setup_logging()
    handlers_after_second = list(logging.getLogger().handlers)

    # setup_logging은 기존 핸들러를 제거 후 추가하므로 수가 동일해야 한다.
    assert len(handlers_after_first) == len(handlers_after_second)
