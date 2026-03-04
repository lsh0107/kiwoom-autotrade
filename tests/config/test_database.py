"""데이터베이스 세션 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class TestGetDb:
    """get_db 제너레이터 테스트."""

    async def test_get_db_yields_session(self) -> None:
        """get_db가 AsyncSession을 yield하고 정상 종료 시 commit한다."""
        mock_session = AsyncMock(spec=AsyncSession)

        # async context manager를 모킹
        mock_session_factory = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = False
        mock_session_factory.return_value = mock_cm

        with patch("src.config.database.async_session_factory", mock_session_factory):
            from src.config.database import get_db

            gen = get_db()
            session = await gen.__anext__()

            assert session is mock_session

            # 제너레이터 종료 (정상 경로 → commit)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

            mock_session.commit.assert_awaited_once()

    async def test_get_db_rollback_on_error(self) -> None:
        """get_db에서 예외 발생 시 rollback한다."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_session_factory = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = False
        mock_session_factory.return_value = mock_cm

        with patch("src.config.database.async_session_factory", mock_session_factory):
            from src.config.database import get_db

            gen = get_db()
            session = await gen.__anext__()

            assert session is mock_session

            # 예외를 throw하여 rollback 경로 테스트
            with pytest.raises(ValueError, match="test error"):
                await gen.athrow(ValueError("test error"))

            mock_session.rollback.assert_awaited_once()
