"""텔레그램 명령 실행기 테스트."""

import uuid

import pytest

from src.notification.commands import CommandType, ParsedCommand
from src.notification.executor import HELP_TEXT, TradingContext, execute_command


@pytest.fixture()
def ctx() -> TradingContext:
    """기본 TradingContext."""
    return TradingContext(
        positions={
            "005930": {
                "name": "삼성전자",
                "qty": 10,
                "entry_price": 75000,
                "pnl_pct": 0.015,
                "strategy": "momentum",
            },
        },
        total_buys=3,
        total_sells=1,
        win_rate=1.0,
        total_pnl=0.015,
        account_balance=10_000_000,
        budget_summary="momentum: 5M / mr: 5M",
        current_regime="NEUTRAL",
        strategy_params={"momentum": "vol_ratio=0.8, SL=-0.02"},
        user_id=uuid.uuid4(),
        kill_switch_status="normal",
    )


class TestStatusCommand:
    """STATUS 명령 테스트."""

    def test_with_positions(self, ctx: TradingContext) -> None:
        """포지션이 있을 때 상태 출력."""
        cmd = ParsedCommand(command=CommandType.STATUS)
        result = execute_command(cmd, ctx)
        assert "삼성전자" in result
        assert "005930" in result
        assert "10주" in result
        assert "NEUTRAL" in result
        assert "매수 3건" in result

    def test_no_positions(self, ctx: TradingContext) -> None:
        """포지션 없을 때."""
        ctx.positions = {}
        cmd = ParsedCommand(command=CommandType.STATUS)
        result = execute_command(cmd, ctx)
        assert "포지션 없음" in result

    def test_kill_switch_warning(self, ctx: TradingContext) -> None:
        """킬스위치 상태 표시."""
        ctx.kill_switch_status = "soft_stopped"
        cmd = ParsedCommand(command=CommandType.STATUS)
        result = execute_command(cmd, ctx)
        assert "킬스위치" in result
        assert "soft_stopped" in result


class TestBalanceCommand:
    """BALANCE 명령 테스트."""

    def test_balance(self, ctx: TradingContext) -> None:
        """잔고 출력."""
        cmd = ParsedCommand(command=CommandType.BALANCE)
        result = execute_command(cmd, ctx)
        assert "10,000,000" in result
        assert "momentum" in result


class TestStopCommand:
    """STOP 명령 테스트."""

    def test_stop_calls_callback(self, ctx: TradingContext) -> None:
        """킬스위치 콜백 호출."""
        called = []

        def on_stop() -> str:
            called.append(True)
            return "중지됨"

        cmd = ParsedCommand(command=CommandType.STOP)
        result = execute_command(cmd, ctx, on_stop=on_stop)
        assert called
        assert result == "중지됨"

    def test_stop_already_stopped(self, ctx: TradingContext) -> None:
        """이미 중지 상태."""
        ctx.kill_switch_status = "soft_stopped"
        cmd = ParsedCommand(command=CommandType.STOP)
        result = execute_command(cmd, ctx)
        assert "이미" in result

    def test_stop_no_callback(self, ctx: TradingContext) -> None:
        """콜백 없으면 안내 메시지."""
        cmd = ParsedCommand(command=CommandType.STOP)
        result = execute_command(cmd, ctx)
        assert "연결되지 않았습니다" in result


class TestResumeCommand:
    """RESUME 명령 테스트."""

    def test_resume_calls_callback(self, ctx: TradingContext) -> None:
        """재개 콜백 호출."""
        ctx.kill_switch_status = "soft_stopped"
        called = []

        def on_resume() -> str:
            called.append(True)
            return "재개됨"

        cmd = ParsedCommand(command=CommandType.RESUME)
        result = execute_command(cmd, ctx, on_resume=on_resume)
        assert called
        assert result == "재개됨"

    def test_resume_already_normal(self, ctx: TradingContext) -> None:
        """이미 정상 상태."""
        cmd = ParsedCommand(command=CommandType.RESUME)
        result = execute_command(cmd, ctx)
        assert "정상" in result


class TestApproveRejectCommand:
    """APPROVE / REJECT 명령 테스트."""

    def test_approve_no_suggestions(self, ctx: TradingContext) -> None:
        """제안 없으면 안내."""
        cmd = ParsedCommand(command=CommandType.APPROVE)
        result = execute_command(cmd, ctx)
        assert "없습니다" in result

    def test_approve_all(self, ctx: TradingContext) -> None:
        """전체 승인."""
        ctx.pending_suggestions = [
            {"id": "abc", "config_key": "vol_ratio", "suggested_value": 1.0},
        ]
        approved_ids: list[list[str]] = []

        def on_approve(ids: list[str]) -> str:
            approved_ids.append(ids)
            return f"{len(ids)}건 승인"

        cmd = ParsedCommand(command=CommandType.APPROVE)
        result = execute_command(cmd, ctx, on_approve=on_approve)
        assert "1건 승인" in result
        assert approved_ids[0] == ["abc"]

    def test_approve_by_index(self, ctx: TradingContext) -> None:
        """번호 지정 승인."""
        ctx.pending_suggestions = [
            {"id": "a", "config_key": "k1"},
            {"id": "b", "config_key": "k2"},
        ]

        def on_approve(ids: list[str]) -> str:
            return f"승인: {ids}"

        cmd = ParsedCommand(command=CommandType.APPROVE, args=["2"])
        result = execute_command(cmd, ctx, on_approve=on_approve)
        assert "b" in result

    def test_reject_all(self, ctx: TradingContext) -> None:
        """전체 거부."""
        ctx.pending_suggestions = [{"id": "x"}]
        rejected: list[list[str]] = []

        def on_reject(ids: list[str]) -> str:
            rejected.append(ids)
            return "거부됨"

        cmd = ParsedCommand(command=CommandType.REJECT)
        result = execute_command(cmd, ctx, on_reject=on_reject)
        assert result == "거부됨"


class TestSettingsCommand:
    """SETTINGS 명령 테스트."""

    def test_settings_output(self, ctx: TradingContext) -> None:
        """설정 출력."""
        cmd = ParsedCommand(command=CommandType.SETTINGS)
        result = execute_command(cmd, ctx)
        assert "momentum" in result
        assert "vol_ratio" in result

    def test_settings_empty(self, ctx: TradingContext) -> None:
        """파라미터 없으면 안내."""
        ctx.strategy_params = {}
        cmd = ParsedCommand(command=CommandType.SETTINGS)
        result = execute_command(cmd, ctx)
        assert "없습니다" in result


class TestHelpCommand:
    """HELP 명령 테스트."""

    def test_help(self, ctx: TradingContext) -> None:
        """도움말 출력."""
        cmd = ParsedCommand(command=CommandType.HELP)
        result = execute_command(cmd, ctx)
        assert result == HELP_TEXT
