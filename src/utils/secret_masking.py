"""로그 시크릿 마스킹 공용 유틸.

파일/스트림/버퍼 로그에서 자격 증명 노출을 방지하기 위한 패턴 기반 마스킹 함수와
`logging.Filter` 구현을 제공한다.

적용 대상 패턴
    - Telegram bot API URL: ``https://api.telegram.org/bot<id>:<body>/...``
    - Telegram bot token: ``bot\\d+:<body>``
    - HTTP Authorization Bearer 토큰
    - 32자 이상 영숫자 장문 시크릿 (키움 app_key/secret 추정)

사용 예시
    로깅 설정부에서 핸들러에 `SecretMaskingFilter`를 붙여 사용한다::

        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.addFilter(SecretMaskingFilter())
"""

from __future__ import annotations

import contextlib
import logging
import re

# 시크릿 마스킹 패턴 (로그 라인에서 자격 증명 제거)
# 0) Telegram bot API URL: `https://api.telegram.org/bot<id>:<body>/<method>`
#    httpx INFO 로그가 full URL을 찍는 경우를 통째로 치환한다.
#    (token 단독 패턴보다 먼저 적용되어야 호스트까지 함께 마스킹된다.)
_TELEGRAM_URL_RE = re.compile(r"(https?://api\.telegram\.org/)bot\d+:[A-Za-z0-9_-]+")
# 1) Telegram bot token: `bot123456789:AAE...` 형식
_TELEGRAM_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")
# 2) Bearer 토큰
_BEARER_TOKEN_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]+")
# 3) 키움 app_key/secret 추정: 32자 이상 영숫자 (URL·해시 오탐 최소화 위해 32+)
_LONG_SECRET_RE = re.compile(r"\b[A-Za-z0-9]{32,}\b")


def mask_secrets(line: str) -> str:
    """로그 라인에서 시크릿을 마스킹한다.

    Telegram bot token, Bearer 토큰, 장문 API 키를 패턴 기반으로 치환한다.

    Args:
        line: 원본 로그 라인

    Returns:
        민감 정보가 마스킹된 라인. 입력이 문자열이 아니면 ``str(line)`` 후 마스킹.
    """
    if not isinstance(line, str):
        line = str(line)
    # 호스트까지 포함된 Telegram URL 형태를 먼저 치환 (경로에 토큰이 임베드된 경우).
    # 스킴(http/https)은 그룹 캡처로 보존한다.
    line = _TELEGRAM_URL_RE.sub(r"\1bot***:***", line)
    line = _TELEGRAM_TOKEN_RE.sub("bot***:***", line)
    line = _BEARER_TOKEN_RE.sub("Bearer ***", line)
    return _LONG_SECRET_RE.sub("***", line)


class SecretMaskingFilter(logging.Filter):
    """stdlib ``logging`` 핸들러용 시크릿 마스킹 필터.

    `LogRecord.msg`와 `LogRecord.args` 양쪽을 마스킹한다.
    `%` 포맷팅 이후가 아닌 원본 단계에서 치환하므로, 포맷팅된 최종 메시지도
    마스킹된 값 기반으로 생성된다.

    structlog의 ``stdlib.ProcessorFormatter`` 경유 경로에서도 `record.msg`가
    최종 렌더링된 문자열이므로 동일하게 적용된다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """LogRecord를 마스킹한다. 항상 ``True`` (레코드 통과)."""
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)
        else:
            # 예외/객체 등 문자열이 아닌 경우, 표현만 마스킹해서 교체 (best-effort)
            with contextlib.suppress(Exception):
                record.msg = mask_secrets(str(record.msg))

        args = record.args
        if args is None:
            return True
        if isinstance(args, dict):
            record.args = {k: _mask_arg(v) for k, v in args.items()}
        elif isinstance(args, tuple):
            record.args = tuple(_mask_arg(a) for a in args)
        # stdlib logging은 args를 tuple 또는 Mapping으로만 전달하므로
        # 그 외 타입은 정상적으로 도달하지 않는다.
        return True


def _mask_arg(value: object) -> object:
    """LogRecord.args 내 단일 값을 마스킹한다.

    문자열만 치환하고, 숫자/None 등은 그대로 반환한다.
    """
    if isinstance(value, str):
        return mask_secrets(value)
    return value


def structlog_mask_processor(
    _logger: object, _method_name: str, event_dict: dict[str, object]
) -> dict[str, object]:
    """structlog processor: event dict의 모든 문자열 값과 event 본문을 마스킹한다.

    `structlog.configure(processors=[..., structlog_mask_processor, ...])` 형태로
    추가한다. 렌더러(JSONRenderer 등) 직전에 위치시키는 것을 권장한다.

    Args:
        _logger: structlog이 전달하는 logger (미사용).
        _method_name: 호출된 로깅 메서드 이름 (미사용).
        event_dict: 이벤트 딕셔너리.

    Returns:
        시크릿이 마스킹된 event dict (in-place 수정 후 반환).
    """
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            event_dict[key] = mask_secrets(value)
    return event_dict
