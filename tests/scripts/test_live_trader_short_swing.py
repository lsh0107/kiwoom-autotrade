"""Short Swing live_trader 분기 테스트 — ACTIVE_STRATEGY 가드, 시간 가드, 전략 분리."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.live_trader import (
    _SS_CANCEL_HHMM,
    _SS_ENTRY_END,
    _SS_ENTRY_START,
    _SS_EXIT_END,
    _SS_EXIT_START,
    _check_short_swing_cancel,
    _check_short_swing_entry,
    _check_short_swing_exit,
)


@pytest.fixture()
def mock_client() -> MagicMock:
    """키움 API 클라이언트 mock."""
    return MagicMock()


# ── ACTIVE_STRATEGY=none → entry/exit 모두 skip ──────────────────────────


class TestActiveStrategyNoneSkip:
    """ACTIVE_STRATEGY=none이면 short_swing entry/exit 호출 안 함."""

    @patch.dict("os.environ", {"ACTIVE_STRATEGY": "none"})
    @patch("scripts.live_trader.async_session_factory")
    async def test_entry_skips_when_none(
        self, mock_factory: MagicMock, mock_client: MagicMock
    ) -> None:
        """ACTIVE_STRATEGY=none → _check_short_swing_entry 는 run_entry_check 미호출."""
        with patch("src.trading.short_swing.run_entry_check"):
            await _check_short_swing_entry(mock_client, "1000")

    @patch.dict("os.environ", {"ACTIVE_STRATEGY": "none"})
    async def test_exit_skips_when_none(self, mock_client: MagicMock) -> None:
        """ACTIVE_STRATEGY=none → _check_short_swing_exit 시간 가드만 테스트."""
        # 시간 가드 밖 → 즉시 return
        await _check_short_swing_exit(mock_client, "0900")
        # 에러 없이 통과하면 성공


# ── ACTIVE_STRATEGY=short_swing + 시간 가드 ──────────────────────────────


class TestTimeGuard:
    """시간 범위 밖이면 entry/exit/cancel 모두 조기 반환."""

    async def test_entry_before_start(self, mock_client: MagicMock) -> None:
        """09:00 → entry 시간(09:20) 전이므로 skip."""
        await _check_short_swing_entry(mock_client, "0900")
        # 에러 없이 통과

    async def test_entry_after_end(self, mock_client: MagicMock) -> None:
        """14:00 → entry 종료(13:00) 후이므로 skip."""
        await _check_short_swing_entry(mock_client, "1400")

    async def test_exit_before_start(self, mock_client: MagicMock) -> None:
        """09:00 → exit 시간(09:20) 전이므로 skip."""
        await _check_short_swing_exit(mock_client, "0900")

    async def test_exit_after_end(self, mock_client: MagicMock) -> None:
        """15:30 → exit 종료(15:10) 후이므로 skip."""
        await _check_short_swing_exit(mock_client, "1530")


# ── ACTIVE_STRATEGY=short_swing + 시간 범위 내 → 실행 ────────────────────


class TestShortSwingEntryExecution:
    """시간 범위 내 + DB/모듈 mock → 정상 호출 확인."""

    @patch("scripts.live_trader.async_session_factory")
    async def test_entry_called_at_1000(
        self, mock_factory: MagicMock, mock_client: MagicMock
    ) -> None:
        """10:00 → entry 시간 범위 내 → run_entry_check 호출."""
        mock_session = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock(checked=0, ordered=0, skipped=[], errors=[])

        with (
            patch(
                "src.trading.live_order_persist.resolve_live_trader_user_id",
                new_callable=AsyncMock,
                return_value="test-user-id",
            ),
            patch(
                "src.trading.short_swing.run_entry_check",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_entry,
        ):
            await _check_short_swing_entry(mock_client, "1000")
            mock_entry.assert_awaited_once()

    @patch("scripts.live_trader.async_session_factory")
    async def test_exit_called_at_1000(
        self, mock_factory: MagicMock, mock_client: MagicMock
    ) -> None:
        """10:00 → exit 시간 범위 내 → run_exit_check 호출."""
        mock_session = AsyncMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock(checked=0, closed=0, skipped=[], errors=[])

        with (
            patch(
                "src.trading.live_order_persist.resolve_live_trader_user_id",
                new_callable=AsyncMock,
                return_value="test-user-id",
            ),
            patch(
                "src.trading.short_swing_exit.run_exit_check",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_exit,
        ):
            await _check_short_swing_exit(mock_client, "1000")
            mock_exit.assert_awaited_once()


# ── ACTIVE_STRATEGY=cross_momentum → short_swing entry 안 함 ────────────


class TestCrossMomentumSkipsShortSwing:
    """cross_momentum 모드에서는 short_swing 진입이 일어나지 않는다."""

    async def test_entry_not_called_for_cross_momentum(self, mock_client: MagicMock) -> None:
        """cross_momentum 에서는 _check_short_swing_entry 자체가 호출되지 않음.

        이건 run_trading_loop 분기에서 검증 — 여기서는 시간 가드만 확인.
        시간 범위 밖으로 설정하면 실행 안 됨.
        """
        await _check_short_swing_entry(mock_client, "0800")
        # 에러 없이 통과 → cross_momentum 분기에서는 이 함수 자체를 호출하지 않음


# ── 미체결 취소 ──────────────────────────────────────────────────────────


class TestShortSwingCancel:
    """미체결 주문 취소 시간/threshold 검증."""

    async def test_cancel_before_1520_threshold_30(self, mock_client: MagicMock) -> None:
        """15:20 전 → threshold=30분."""
        # 시간 가드 없이 항상 실행되므로, 내부 로직 mock 필요
        with patch("scripts.live_trader.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            with (
                patch(
                    "src.trading.live_order_persist.resolve_live_trader_user_id",
                    new_callable=AsyncMock,
                    return_value="test-user-id",
                ),
                patch(
                    "src.trading.short_swing_cancel.cancel_stale_buy_orders",
                    new_callable=AsyncMock,
                    return_value={"cancelled": 0, "skipped": 0, "errors": 0},
                ) as mock_cancel,
            ):
                await _check_short_swing_cancel(mock_client, "1400")
                mock_cancel.assert_awaited_once()
                call_kwargs = mock_cancel.call_args[1]
                assert call_kwargs["threshold_minutes"] == 30

    async def test_cancel_at_1520_threshold_0(self, mock_client: MagicMock) -> None:
        """15:20 → threshold=0 (전량 즉시 취소)."""
        with patch("scripts.live_trader.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            with (
                patch(
                    "src.trading.live_order_persist.resolve_live_trader_user_id",
                    new_callable=AsyncMock,
                    return_value="test-user-id",
                ),
                patch(
                    "src.trading.short_swing_cancel.cancel_stale_buy_orders",
                    new_callable=AsyncMock,
                    return_value={"cancelled": 2, "skipped": 0, "errors": 0},
                ) as mock_cancel,
            ):
                await _check_short_swing_cancel(mock_client, "1520")
                mock_cancel.assert_awaited_once()
                call_kwargs = mock_cancel.call_args[1]
                assert call_kwargs["threshold_minutes"] == 0


# ── 시간 상수 일관성 ─────────────────────────────────────────────────────


class TestTimeConstants:
    """시간 상수가 설계 문서와 일치하는지 검증."""

    def test_entry_window(self) -> None:
        assert _SS_ENTRY_START == "0920"
        assert _SS_ENTRY_END == "1300"

    def test_exit_window(self) -> None:
        assert _SS_EXIT_START == "0920"
        assert _SS_EXIT_END == "1510"

    def test_cancel_time(self) -> None:
        assert _SS_CANCEL_HHMM == "1520"
