"""Short-swing handler 단위 테스트.

design-025: orchestrator 용 short_swing handler 래퍼 — 시간대별 dispatch 확인.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.trading.handlers.short_swing_handler import handle

# 소스 모듈 경로 (lazy import 대상)
_LOP_MOD = "src.trading.live_order_persist"
# handler 모듈 경로 (module-level 함수 _run_* 등)
_HANDLER_MOD = "src.trading.handlers.short_swing_handler"

_TEST_USER_ID = uuid.uuid4()


# ── 공통 fixture ─────────────────────────────────────────────────────────────


def _base_patches():
    """resolve_live_trader_user_id + _run_* 전체 mock."""
    return {
        "resolve": patch(
            f"{_LOP_MOD}.resolve_live_trader_user_id", AsyncMock(return_value=_TEST_USER_ID)
        ),
        "reconcile": patch(f"{_HANDLER_MOD}._run_reconcile", AsyncMock(return_value={})),
        "entry": patch(
            f"{_HANDLER_MOD}._run_entry", AsyncMock(return_value={"checked": 5, "ordered": 1})
        ),
        "exit": patch(
            f"{_HANDLER_MOD}._run_exit", AsyncMock(return_value={"checked": 3, "closed": 1})
        ),
        "cancel": patch(f"{_HANDLER_MOD}._run_cancel", AsyncMock(return_value={"cancelled": 0})),
    }


async def _call_handle(db: AsyncSession, current_hhmm: str = "1000") -> dict:
    return await handle(
        db=db,
        client=AsyncMock(),
        holdings_map={},
        available_cash=10_000_000,
        allowed_budget=3_000_000,
        max_order_amount=5_000_000,
        today=date(2026, 5, 19),
        current_hhmm=current_hhmm,
    )


# ── 테스트 ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_entry_window(db: AsyncSession) -> None:
    """09:20~13:00 시간대에 entry 호출."""
    patches = _base_patches()
    with (
        patches["resolve"],
        patches["reconcile"],
        patches["entry"] as mock_entry,
        patches["exit"],
        patches["cancel"],
    ):
        await _call_handle(db, "1000")

    mock_entry.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_outside_entry_window(db: AsyncSession) -> None:
    """13:00 이후 entry 미호출."""
    patches = _base_patches()
    with patches["resolve"], patches["reconcile"], patches["exit"], patches["cancel"]:
        result = await _call_handle(db, "1400")

    assert result["entry"] is None


@pytest.mark.asyncio
async def test_handle_exit_window(db: AsyncSession) -> None:
    """09:20~15:10 시간대에 exit 호출."""
    patches = _base_patches()
    with (
        patches["resolve"],
        patches["reconcile"],
        patches["entry"],
        patches["exit"] as mock_exit,
        patches["cancel"],
    ):
        result = await _call_handle(db, "1400")

    mock_exit.assert_awaited_once()
    assert result["exit"] is not None


@pytest.mark.asyncio
async def test_handle_outside_exit_window(db: AsyncSession) -> None:
    """15:10 이후 exit 미호출."""
    patches = _base_patches()
    with patches["resolve"], patches["reconcile"], patches["cancel"]:
        result = await _call_handle(db, "1520")

    assert result["entry"] is None
    assert result["exit"] is None


@pytest.mark.asyncio
async def test_handle_cancel_always_called(db: AsyncSession) -> None:
    """cancel 은 매 cycle 호출."""
    patches = _base_patches()
    with (
        patches["resolve"],
        patches["reconcile"],
        patches["entry"],
        patches["exit"],
        patches["cancel"] as mock_cancel,
    ):
        await _call_handle(db, "1000")

    mock_cancel.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_restores_env(db: AsyncSession) -> None:
    """ACTIVE_STRATEGY env 복원."""
    original = os.environ.get("ACTIVE_STRATEGY")

    patches = _base_patches()
    with patches["resolve"], patches["reconcile"], patches["cancel"]:
        await _call_handle(db, "1600")

    after = os.environ.get("ACTIVE_STRATEGY")
    assert after == original


@pytest.mark.asyncio
async def test_reconcile_always_called(db: AsyncSession) -> None:
    """reconcile 은 시간대 무관하게 항상 호출."""
    patches = _base_patches()
    with patches["resolve"], patches["reconcile"] as mock_reconcile, patches["cancel"]:
        await _call_handle(db, "0800")

    mock_reconcile.assert_awaited_once()
