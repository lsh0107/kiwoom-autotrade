"""텔레그램 명령 파서 테스트."""

import pytest

from src.notification.commands import CommandType, ParsedCommand, parse_command


class TestParseCommand:
    """parse_command 함수 테스트."""

    @pytest.mark.parametrize(
        ("text", "expected_type"),
        [
            ("/상태", CommandType.STATUS),
            ("/status", CommandType.STATUS),
            ("상태", CommandType.STATUS),
            ("현황", CommandType.STATUS),
            ("포지션", CommandType.STATUS),
            ("/잔고", CommandType.BALANCE),
            ("계좌", CommandType.BALANCE),
            ("/승인", CommandType.APPROVE),
            ("ㅇ", CommandType.APPROVE),
            ("/거부", CommandType.REJECT),
            ("ㄴ", CommandType.REJECT),
            ("/중지", CommandType.STOP),
            ("멈춰", CommandType.STOP),
            ("/재개", CommandType.RESUME),
            ("시작", CommandType.RESUME),
            ("/설정", CommandType.SETTINGS),
            ("파라미터", CommandType.SETTINGS),
            ("/도움", CommandType.HELP),
            ("?", CommandType.HELP),
        ],
    )
    def test_recognized_commands(self, text: str, expected_type: CommandType) -> None:
        """인식되는 명령어 파싱."""
        result = parse_command(text)
        assert result is not None
        assert result.command == expected_type

    def test_unrecognized_returns_none(self) -> None:
        """인식 불가 메시지는 None."""
        assert parse_command("아무말이나쓰면") is None
        assert parse_command("hello world") is None

    def test_empty_returns_none(self) -> None:
        """빈 메시지는 None."""
        assert parse_command("") is None
        assert parse_command("   ") is None

    def test_args_parsed(self) -> None:
        """인자가 파싱된다."""
        result = parse_command("/승인 1 2 3")
        assert result is not None
        assert result.command == CommandType.APPROVE
        assert result.args == ["1", "2", "3"]

    def test_raw_text_preserved(self) -> None:
        """원본 텍스트 보존."""
        result = parse_command("/상태")
        assert result is not None
        assert result.raw_text == "/상태"

    def test_case_insensitive(self) -> None:
        """/STATUS → status."""
        result = parse_command("/Status")
        assert result is not None
        assert result.command == CommandType.STATUS

    def test_parsed_command_frozen(self) -> None:
        """ParsedCommand는 immutable."""
        cmd = ParsedCommand(command=CommandType.HELP)
        with pytest.raises(AttributeError):
            cmd.command = CommandType.STATUS  # type: ignore[misc]
