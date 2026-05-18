"""live_trader _get_rebalance_adapter / _check_monthly_rebalance 단위 테스트 (HOTFIX F.2)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.trading.cross_momentum_rebalance import RebalanceParams

# ── _get_rebalance_adapter: DB params 주입 ───────────────────────────────────


class TestGetRebalanceAdapter:
    """_get_rebalance_adapter: DB load_rebalance_params 로 params 주입."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self) -> None:
        """매 테스트마다 싱글턴 초기화."""
        import scripts.live_trader as lt

        lt._rebalance_adapter = None
        yield
        lt._rebalance_adapter = None

    @pytest.mark.asyncio
    async def test_adapter_receives_db_params(self) -> None:
        """첫 호출 시 load_rebalance_params 결과가 adapter.params 에 반영."""
        from scripts.live_trader import _get_rebalance_adapter

        weekly_params = RebalanceParams(rebalance_freq="weekly", n_positions=10)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.config.database.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "src.trading.cross_momentum_rebalance.load_rebalance_params",
                new=AsyncMock(return_value=weekly_params),
            ),
        ):
            adapter = await _get_rebalance_adapter()

        assert adapter.params.rebalance_freq == "weekly"
        assert adapter.params.n_positions == 10

    @pytest.mark.asyncio
    async def test_adapter_cached_on_second_call(self) -> None:
        """두 번째 호출 시 DB 재조회 없이 캐시 반환."""
        from scripts.live_trader import _get_rebalance_adapter

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_load = AsyncMock(return_value=RebalanceParams())

        with (
            patch(
                "src.config.database.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "src.trading.cross_momentum_rebalance.load_rebalance_params",
                new=mock_load,
            ),
        ):
            a1 = await _get_rebalance_adapter()
            a2 = await _get_rebalance_adapter()

        assert a1 is a2
        mock_load.assert_called_once()


# ── _check_monthly_rebalance: 월말 선행 return 제거 ──────────────────────────


class TestCheckMonthlyRebalanceNoEarlyReturn:
    """_check_monthly_rebalance: 월말 선행 return 제거 검증."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self) -> None:
        """매 테스트마다 싱글턴 초기화."""
        import scripts.live_trader as lt

        lt._rebalance_adapter = None
        yield
        lt._rebalance_adapter = None

    @pytest.mark.asyncio
    async def test_weekly_friday_calls_check(self) -> None:
        """freq=weekly + 금요일 영업일 + 14:55 → check_monthly_rebalance 호출.

        기존에는 monthly-only 선행 return 으로 차단됐던 시나리오.
        """
        from scripts.live_trader import _check_monthly_rebalance

        # 2026-05-22 = 금요일
        friday = date(2026, 5, 22)
        weekly_params = RebalanceParams(rebalance_freq="weekly")

        mock_adapter = MagicMock()
        mock_adapter.params = weekly_params

        mock_state = MagicMock()
        mock_state.positions = {}
        mock_state.cumulative_pnl_won = 0
        mock_state.t2_pending = None

        mock_client = MagicMock()

        mock_check = AsyncMock(return_value=True)

        with (
            patch("scripts.live_trader.now_kst") as mock_now,
            patch(
                "scripts.live_trader._get_rebalance_adapter",
                new=AsyncMock(return_value=mock_adapter),
            ),
            patch("src.trading.cross_momentum_rebalance.check_monthly_rebalance", new=mock_check),
        ):
            mock_now.return_value.date.return_value = friday

            await _check_monthly_rebalance(mock_client, "1455", mock_state, 10_000_000)

        mock_check.assert_called_once()
        # adapter 가 인자로 전달됐는지 확인
        call_args = mock_check.call_args[0]
        assert call_args[0] is mock_adapter
        assert call_args[1] == "1455"
        assert call_args[2] == friday
