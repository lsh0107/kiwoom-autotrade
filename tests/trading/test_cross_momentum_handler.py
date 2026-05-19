"""Cross-momentum handler 단위 테스트.

design-025: orchestrator 용 cross_momentum handler 래퍼.
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import Holding
from src.trading.handlers.cross_momentum_handler import handle

# lazy import 대상이므로 소스 모듈 경로로 patch
_CM_MOD = "src.trading.cross_momentum_rebalance"

# ── 테스트 ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_calls_check_monthly_rebalance(db: AsyncSession) -> None:
    """check_monthly_rebalance 가 올바른 인자로 호출되는지."""
    mock_check = AsyncMock(return_value=True)
    mock_load_params = AsyncMock()
    mock_adapter_cls = type("MockAdapter", (), {"params": mock_load_params.return_value})

    with (
        patch(f"{_CM_MOD}.check_monthly_rebalance", mock_check),
        patch(f"{_CM_MOD}.load_rebalance_params", mock_load_params),
        patch(f"{_CM_MOD}.CrossMomentumRebalanceAdapter", return_value=mock_adapter_cls()),
    ):
        result = await handle(
            db=db,
            client=AsyncMock(),
            holdings_map={
                "005930": Holding(
                    symbol="005930",
                    name="삼성전자",
                    quantity=10,
                    avg_price=70000,
                    current_price=72000,
                    eval_amount=720000,
                    profit=20000,
                    profit_pct=2.86,
                )
            },
            available_cash=10_000_000,
            allowed_budget=6_000_000,
            max_order_amount=50_000_000,
            today=date(2026, 5, 30),
            current_hhmm="1455",
        )

    assert result["executed"] is True
    assert result["error"] is None

    # check_monthly_rebalance 호출 인자 확인
    call_args = mock_check.call_args
    assert call_args[0][1] == "1455"  # current_hhmm
    assert call_args[0][2] == date(2026, 5, 30)  # today
    assert call_args[0][4] == {"005930": 10}  # current_holdings
    assert call_args[0][5] == 6_000_000  # allowed_budget (not full cash)


@pytest.mark.asyncio
async def test_handle_restores_env_on_success(db: AsyncSession) -> None:
    """핸들러 종료 후 ACTIVE_STRATEGY env 복원."""
    original = os.environ.get("ACTIVE_STRATEGY")

    with (
        patch(f"{_CM_MOD}.check_monthly_rebalance", AsyncMock(return_value=False)),
        patch(f"{_CM_MOD}.load_rebalance_params", AsyncMock()),
        patch(f"{_CM_MOD}.CrossMomentumRebalanceAdapter"),
    ):
        await handle(
            db=db,
            client=AsyncMock(),
            holdings_map={},
            available_cash=10_000_000,
            allowed_budget=6_000_000,
            max_order_amount=50_000_000,
            today=date(2026, 5, 30),
            current_hhmm="1000",
        )

    after = os.environ.get("ACTIVE_STRATEGY")
    assert after == original


@pytest.mark.asyncio
async def test_handle_restores_env_on_error(db: AsyncSession) -> None:
    """에러 발생 시에도 env 복원."""
    original = os.environ.get("ACTIVE_STRATEGY")

    with patch(f"{_CM_MOD}.load_rebalance_params", AsyncMock(side_effect=RuntimeError("boom"))):
        result = await handle(
            db=db,
            client=AsyncMock(),
            holdings_map={},
            available_cash=10_000_000,
            allowed_budget=6_000_000,
            max_order_amount=50_000_000,
            today=date(2026, 5, 30),
            current_hhmm="1455",
        )

    assert result["executed"] is False
    assert "boom" in result["error"]

    after = os.environ.get("ACTIVE_STRATEGY")
    assert after == original


@pytest.mark.asyncio
async def test_handle_uses_allowed_budget_not_full_cash(db: AsyncSession) -> None:
    """allowed_budget 이 check_monthly_rebalance 의 available_cash 로 전달."""
    mock_check = AsyncMock(return_value=False)

    with (
        patch(f"{_CM_MOD}.check_monthly_rebalance", mock_check),
        patch(f"{_CM_MOD}.load_rebalance_params", AsyncMock()),
        patch(f"{_CM_MOD}.CrossMomentumRebalanceAdapter"),
    ):
        await handle(
            db=db,
            client=AsyncMock(),
            holdings_map={},
            available_cash=10_000_000,  # 전체
            allowed_budget=3_000_000,  # 할당분
            max_order_amount=50_000_000,
            today=date(2026, 5, 30),
            current_hhmm="1455",
        )

    # 6번째 위치 인자가 allowed_budget
    assert mock_check.call_args[0][5] == 3_000_000
