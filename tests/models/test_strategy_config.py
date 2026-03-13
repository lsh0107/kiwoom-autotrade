"""StrategyConfig / StrategyConfigSuggestion 모델 테스트."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_config import StrategyConfig, StrategyConfigSuggestion


class TestStrategyConfigCRUD:
    """StrategyConfig CRUD 테스트."""

    async def test_create_config(self, db: AsyncSession) -> None:
        """기본 파라미터 생성."""
        cfg = StrategyConfig(
            key="atr_stop_mult",
            value=1.5,
            description="ATR 손절 승수",
            updated_by="system",
        )
        db.add(cfg)
        await db.flush()
        await db.refresh(cfg)

        assert cfg.id is not None
        assert cfg.key == "atr_stop_mult"
        assert cfg.value == 1.5
        assert cfg.updated_by == "system"

    async def test_unique_key_constraint(self, db: AsyncSession) -> None:
        """같은 key 중복 시 IntegrityError."""
        cfg1 = StrategyConfig(key="max_positions", value=3, description="", updated_by="system")
        cfg2 = StrategyConfig(key="max_positions", value=5, description="", updated_by="user")
        db.add(cfg1)
        db.add(cfg2)

        with pytest.raises((IntegrityError, Exception)):
            await db.flush()

    async def test_update_value(self, db: AsyncSession) -> None:
        """value 업데이트."""
        cfg = StrategyConfig(key="volume_ratio", value=1.5, description="", updated_by="system")
        db.add(cfg)
        await db.flush()

        cfg.value = 2.0
        cfg.updated_by = "user"
        await db.flush()
        await db.refresh(cfg)

        assert cfg.value == 2.0
        assert cfg.updated_by == "user"

    async def test_jsonb_supports_string_value(self, db: AsyncSession) -> None:
        """JSONB에 문자열 값 저장."""
        cfg = StrategyConfig(
            key="entry_start_time",
            value="09:05",
            description="진입 시작",
            updated_by="system",
        )
        db.add(cfg)
        await db.flush()
        await db.refresh(cfg)

        assert cfg.value == "09:05"

    async def test_delete_config(self, db: AsyncSession) -> None:
        """파라미터 삭제."""
        cfg = StrategyConfig(key="take_profit", value=0.015, description="", updated_by="system")
        db.add(cfg)
        await db.flush()

        cfg_id = cfg.id
        await db.delete(cfg)
        await db.flush()

        result = await db.execute(select(StrategyConfig).where(StrategyConfig.id == cfg_id))
        assert result.scalar_one_or_none() is None


class TestStrategyConfigSuggestionCRUD:
    """StrategyConfigSuggestion CRUD 테스트."""

    async def test_create_suggestion(self, db: AsyncSession) -> None:
        """제안 생성."""
        suggestion = StrategyConfigSuggestion(
            config_key="atr_stop_mult",
            current_value=1.5,
            suggested_value=2.0,
            reason="ATR 변동성 증가로 손절 승수 상향 권장",
            source="postmarket_review",
            status="pending",
        )
        db.add(suggestion)
        await db.flush()
        await db.refresh(suggestion)

        assert suggestion.id is not None
        assert suggestion.status == "pending"
        assert suggestion.reviewed_at is None

    async def test_approve_suggestion(self, db: AsyncSession) -> None:
        """제안 승인 처리."""
        suggestion = StrategyConfigSuggestion(
            config_key="volume_ratio",
            current_value=1.5,
            suggested_value=2.0,
            reason="거래량 기준 상향",
            source="param_tuner",
            status="pending",
        )
        db.add(suggestion)
        await db.flush()

        now = datetime.now(UTC)
        suggestion.status = "approved"
        suggestion.reviewed_at = now
        suggestion.reviewed_by = "test_user"
        await db.flush()
        await db.refresh(suggestion)

        assert suggestion.status == "approved"
        assert suggestion.reviewed_by == "test_user"
        assert suggestion.reviewed_at is not None

    async def test_reject_suggestion(self, db: AsyncSession) -> None:
        """제안 거부 처리."""
        suggestion = StrategyConfigSuggestion(
            config_key="stop_loss",
            current_value=-0.005,
            suggested_value=-0.008,
            reason="손절 강화 제안",
            source="postmarket_review",
            status="pending",
        )
        db.add(suggestion)
        await db.flush()

        suggestion.status = "rejected"
        suggestion.reviewed_at = datetime.now(UTC)
        suggestion.reviewed_by = "user"
        await db.flush()
        await db.refresh(suggestion)

        assert suggestion.status == "rejected"

    async def test_list_pending_suggestions(self, db: AsyncSession) -> None:
        """pending 제안만 필터링."""
        pending = StrategyConfigSuggestion(
            config_key="take_profit",
            current_value=0.015,
            suggested_value=0.020,
            reason="수익 목표 상향",
            source="param_tuner",
            status="pending",
        )
        approved = StrategyConfigSuggestion(
            config_key="max_positions",
            current_value=3,
            suggested_value=5,
            reason="분산 투자",
            source="param_tuner",
            status="approved",
        )
        db.add(pending)
        db.add(approved)
        await db.flush()

        result = await db.execute(
            select(StrategyConfigSuggestion).where(StrategyConfigSuggestion.status == "pending")
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].config_key == "take_profit"
