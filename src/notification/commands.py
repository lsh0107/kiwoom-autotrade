"""텔레그램 양방향 명령 정의 + 파서."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CommandType(StrEnum):
    """텔레그램 명령 유형."""

    STATUS = "status"  # 현재 포지션 + 매매 현황
    BALANCE = "balance"  # 계좌 잔고
    APPROVE = "approve"  # 제안 승인
    REJECT = "reject"  # 제안 거부
    STOP = "stop"  # 킬스위치 (신규 매수 중단)
    RESUME = "resume"  # 매매 재개
    SETTINGS = "settings"  # 전략 파라미터 조회
    HELP = "help"  # 도움말


@dataclass(frozen=True)
class ParsedCommand:
    """파싱된 명령."""

    command: CommandType
    args: list[str] = field(default_factory=list)
    raw_text: str = ""


# 명령 매핑 (한글 + 영문 + 슬래시)
_COMMAND_MAP: dict[str, CommandType] = {
    # 상태
    "/상태": CommandType.STATUS,
    "/status": CommandType.STATUS,
    "상태": CommandType.STATUS,
    "현황": CommandType.STATUS,
    "포지션": CommandType.STATUS,
    # 잔고
    "/잔고": CommandType.BALANCE,
    "/balance": CommandType.BALANCE,
    "잔고": CommandType.BALANCE,
    "계좌": CommandType.BALANCE,
    # 승인
    "/승인": CommandType.APPROVE,
    "/approve": CommandType.APPROVE,
    "승인": CommandType.APPROVE,
    "ㅇ": CommandType.APPROVE,
    # 거부
    "/거부": CommandType.REJECT,
    "/reject": CommandType.REJECT,
    "거부": CommandType.REJECT,
    "ㄴ": CommandType.REJECT,
    # 중지
    "/중지": CommandType.STOP,
    "/stop": CommandType.STOP,
    "중지": CommandType.STOP,
    "스톱": CommandType.STOP,
    "멈춰": CommandType.STOP,
    # 재개
    "/재개": CommandType.RESUME,
    "/resume": CommandType.RESUME,
    "재개": CommandType.RESUME,
    "시작": CommandType.RESUME,
    # 설정
    "/설정": CommandType.SETTINGS,
    "/settings": CommandType.SETTINGS,
    "설정": CommandType.SETTINGS,
    "파라미터": CommandType.SETTINGS,
    # 도움
    "/도움": CommandType.HELP,
    "/help": CommandType.HELP,
    "도움": CommandType.HELP,
    "?": CommandType.HELP,
}


def parse_command(text: str) -> ParsedCommand | None:
    """텔레그램 메시지를 명령으로 파싱한다.

    Args:
        text: 사용자 메시지 원문.

    Returns:
        파싱된 명령. 인식 불가 시 None.
    """
    text = text.strip()
    if not text:
        return None

    parts = text.split(maxsplit=1)
    keyword = parts[0].lower()
    args = parts[1].split() if len(parts) > 1 else []

    cmd_type = _COMMAND_MAP.get(keyword)
    if cmd_type is None:
        return None

    return ParsedCommand(command=cmd_type, args=args, raw_text=text)
