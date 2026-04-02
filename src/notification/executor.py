"""텔레그램 명령 실행기.

TradingContext를 통해 live_trader 상태에 접근하여 명령을 실행하고
응답 메시지를 반환한다.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.notification.commands import CommandType, ParsedCommand

log = logging.getLogger(__name__)


@dataclass
class TradingContext:
    """live_trader에서 주입하는 런타임 상태.

    live_trader.py의 main()에서 생성하여 executor에 전달.
    executor는 이 객체를 읽기 전용으로 사용 (킬스위치 제외).
    """

    # 포지션 정보 (symbol → {name, qty, entry_price, pnl_pct, strategy})
    positions: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 매매 기록
    total_buys: int = 0
    total_sells: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    # 계좌
    account_balance: int = 0
    budget_summary: str = ""
    # 레짐
    current_regime: str = "NEUTRAL"
    # 전략 파라미터 요약
    strategy_params: dict[str, str] = field(default_factory=dict)
    # 킬스위치
    user_id: uuid.UUID | None = None
    kill_switch_status: str = "normal"
    # pending 제안 목록 (config_key → {id, suggested_value, reason})
    pending_suggestions: list[dict[str, Any]] = field(default_factory=list)


HELP_TEXT = """📋 사용 가능한 명령:

/상태 — 포지션 + 매매 현황
/잔고 — 계좌 잔고 + 자금 버킷
/승인 [번호] — 제안 승인 (번호 생략 시 전체)
/거부 [번호] — 제안 거부
/중지 — 신규 매수 중단 (킬스위치)
/재개 — 매매 재개
/설정 — 전략 파라미터
/도움 — 이 도움말

단축: ㅇ=승인, ㄴ=거부, ?=도움"""


def execute_command(
    cmd: ParsedCommand,
    ctx: TradingContext,
    *,
    on_stop: Callable[[], str] | None = None,
    on_resume: Callable[[], str] | None = None,
    on_approve: Callable[[list[str]], str] | None = None,
    on_reject: Callable[[list[str]], str] | None = None,
) -> str:
    """명령을 실행하고 응답 메시지를 반환한다.

    Args:
        cmd: 파싱된 명령.
        ctx: 런타임 상태.
        on_stop: 킬스위치 중지 콜백 () -> str.
        on_resume: 킬스위치 재개 콜백 () -> str.
        on_approve: 제안 승인 콜백 (suggestion_ids: list[str]) -> str.
        on_reject: 제안 거부 콜백 (suggestion_ids: list[str]) -> str.

    Returns:
        텔레그램에 회신할 메시지 텍스트.
    """
    handlers = {
        CommandType.STATUS: lambda: _handle_status(ctx),
        CommandType.BALANCE: lambda: _handle_balance(ctx),
        CommandType.APPROVE: lambda: _handle_approve(cmd, ctx, on_approve),
        CommandType.REJECT: lambda: _handle_reject(cmd, ctx, on_reject),
        CommandType.STOP: lambda: _handle_stop(ctx, on_stop),
        CommandType.RESUME: lambda: _handle_resume(ctx, on_resume),
        CommandType.SETTINGS: lambda: _handle_settings(ctx),
        CommandType.HELP: lambda: HELP_TEXT,
    }

    handler = handlers.get(cmd.command)
    if handler is None:
        return "알 수 없는 명령입니다. /도움 을 입력해 보세요."

    try:
        return handler()
    except Exception as e:
        log.exception("명령 실행 에러: %s", cmd)
        return f"명령 실행 실패: {e}"


# ── 핸들러 구현 ──────────────────────────────────────────


def _handle_status(ctx: TradingContext) -> str:
    """포지션 + 매매 현황."""
    lines = [f"📊 매매 현황 [{ctx.current_regime}]"]

    if ctx.positions:
        lines.append(f"\n보유 {len(ctx.positions)}종목:")
        for sym, info in ctx.positions.items():
            pnl = info.get("pnl_pct", 0)
            sign = "+" if pnl >= 0 else ""
            lines.append(
                f"  {info.get('name', sym)} ({sym})"
                f" {info.get('qty', 0)}주"
                f" {sign}{pnl * 100:.1f}%"
                f" [{info.get('strategy', '')}]"
            )
    else:
        lines.append("\n보유 포지션 없음")

    lines.append(f"\n매수 {ctx.total_buys}건 / 매도 {ctx.total_sells}건")
    if ctx.total_sells > 0:
        sign = "+" if ctx.total_pnl >= 0 else ""
        lines.append(f"승률 {ctx.win_rate * 100:.1f}% / 손익 {sign}{ctx.total_pnl * 100:.2f}%")

    if ctx.kill_switch_status != "normal":
        lines.append(f"\n⚠️ 킬스위치: {ctx.kill_switch_status}")

    return "\n".join(lines)


def _handle_balance(ctx: TradingContext) -> str:
    """계좌 잔고."""
    lines = [
        f"💰 계좌 잔고: {ctx.account_balance:,}원",
    ]
    if ctx.budget_summary:
        lines.append(f"자금 버킷: {ctx.budget_summary}")
    return "\n".join(lines)


def _handle_approve(
    cmd: ParsedCommand,
    ctx: TradingContext,
    callback: Callable[[list[str]], str] | None,
) -> str:
    """제안 승인."""
    if not ctx.pending_suggestions:
        return "승인 대기 중인 제안이 없습니다."

    if callback is None:
        return "승인 기능이 연결되지 않았습니다."

    # 번호 지정 시 해당 제안만, 미지정 시 전체
    if cmd.args:
        try:
            indices = [int(a) - 1 for a in cmd.args]
            ids = [
                ctx.pending_suggestions[i]["id"]
                for i in indices
                if 0 <= i < len(ctx.pending_suggestions)
            ]
        except (ValueError, IndexError):
            return "잘못된 번호입니다. /상태 로 제안 목록을 확인하세요."
    else:
        ids = [s["id"] for s in ctx.pending_suggestions]

    if not ids:
        return "승인할 제안이 없습니다."

    return callback(ids)


def _handle_reject(
    cmd: ParsedCommand,
    ctx: TradingContext,
    callback: Callable[[list[str]], str] | None,
) -> str:
    """제안 거부."""
    if not ctx.pending_suggestions:
        return "거부할 제안이 없습니다."

    if callback is None:
        return "거부 기능이 연결되지 않았습니다."

    if cmd.args:
        try:
            indices = [int(a) - 1 for a in cmd.args]
            ids = [
                ctx.pending_suggestions[i]["id"]
                for i in indices
                if 0 <= i < len(ctx.pending_suggestions)
            ]
        except (ValueError, IndexError):
            return "잘못된 번호입니다."
    else:
        ids = [s["id"] for s in ctx.pending_suggestions]

    if not ids:
        return "거부할 제안이 없습니다."

    return callback(ids)


def _handle_stop(ctx: TradingContext, callback: Callable[[], str] | None) -> str:
    """킬스위치 — 신규 매수 중단."""
    if ctx.kill_switch_status != "normal":
        return f"이미 킬스위치 상태입니다: {ctx.kill_switch_status}"

    if callback is None:
        return "킬스위치 기능이 연결되지 않았습니다."

    return callback()


def _handle_resume(ctx: TradingContext, callback: Callable[[], str] | None) -> str:
    """매매 재개."""
    if ctx.kill_switch_status == "normal":
        return "이미 정상 매매 상태입니다."

    if callback is None:
        return "재개 기능이 연결되지 않았습니다."

    return callback()


def _handle_settings(ctx: TradingContext) -> str:
    """전략 파라미터."""
    if not ctx.strategy_params:
        return "전략 파라미터 정보가 없습니다."

    lines = ["⚙️ 전략 파라미터"]
    for name, summary in ctx.strategy_params.items():
        lines.append(f"\n[{name}]\n{summary}")
    return "\n".join(lines)
