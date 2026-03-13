"""Phase 3 데이터 테이블 생성 + strategy_config 초기 seed.

Revision ID: 003_phase3_data_tables
Revises: 002_token_cache
Create Date: 2026-03-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_phase3_data_tables"
down_revision: str | None = "002_token_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Phase 3 테이블 생성 및 초기 데이터 삽입."""
    # market_data
    op.create_table(
        "market_data",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "date", name="uq_market_data_category_date"),
    )
    op.create_index("ix_market_data_category", "market_data", ["category"])
    op.create_index("ix_market_data_date", "market_data", ["date"])

    # news_articles
    op.create_table(
        "news_articles",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("keyword", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("sentiment", sa.String(10), nullable=False, server_default="neutral"),
        sa.Column("sentiment_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_news_articles_url"),
    )
    op.create_index("ix_news_articles_keyword", "news_articles", ["keyword"])

    # strategy_config
    op.create_table(
        "strategy_config",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(100), nullable=False, server_default="system"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_strategy_config_key"),
    )
    op.create_index("ix_strategy_config_key", "strategy_config", ["key"], unique=True)

    # strategy_config_suggestions
    op.create_table(
        "strategy_config_suggestions",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("current_value", postgresql.JSONB(), nullable=False),
        sa.Column("suggested_value", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_config_suggestions_config_key",
        "strategy_config_suggestions",
        ["config_key"],
    )
    op.create_index(
        "ix_strategy_config_suggestions_status",
        "strategy_config_suggestions",
        ["status"],
    )

    # strategy_config 초기 seed 데이터 (설계문서 §10-1 기본값 10개)
    seed_table = sa.table(
        "strategy_config",
        sa.column("id", sa.UUID()),
        sa.column("key", sa.String()),
        sa.column("value", postgresql.JSONB()),
        sa.column("description", sa.String()),
        sa.column("updated_by", sa.String()),
    )
    op.bulk_insert(
        seed_table,
        [
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "atr_stop_mult",
                "value": 1.5,
                "description": "ATR 손절 승수",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "atr_tp_mult",
                "value": 3.0,
                "description": "ATR 익절 승수",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "volume_ratio",
                "value": 1.5,
                "description": "거래량 배수",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "entry_start_time",
                "value": "09:05",
                "description": "진입 시작 시간",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "entry_end_time",
                "value": "13:00",
                "description": "진입 마감 시간",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "max_holding_days",
                "value": 5,
                "description": "스윙 최대 보유일",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "gap_risk_threshold",
                "value": -0.03,
                "description": "갭다운 손절 기준",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "take_profit",
                "value": 0.015,
                "description": "고정 익절 비율",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "stop_loss",
                "value": -0.005,
                "description": "고정 손절 비율",
                "updated_by": "system",
            },
            {
                "id": sa.text("gen_random_uuid()"),
                "key": "max_positions",
                "value": 3,
                "description": "최대 동시 포지션 수",
                "updated_by": "system",
            },
        ],
    )


def downgrade() -> None:
    """Phase 3 테이블 삭제."""
    op.drop_table("strategy_config_suggestions")
    op.drop_table("strategy_config")
    op.drop_table("news_articles")
    op.drop_table("market_data")
