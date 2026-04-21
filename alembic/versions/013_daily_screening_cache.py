"""daily_screening_cache 테이블 생성.

장 마감 후 Airflow DAG가 사전 스크리닝 결과를 저장하는 테이블.
(date, profile, symbol) 복합 PK — 같은 날 다른 프로파일로 중복 계산 가능.

Revision ID: 013_daily_screening_cache
Revises: 012_daily_candles
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_daily_screening_cache"
down_revision: str | None = "012_daily_candles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """daily_screening_cache 테이블 + 인덱스 생성."""
    op.create_table(
        "daily_screening_cache",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "profile",
            sa.String(40),
            nullable=False,
            server_default="momentum_breakout",
        ),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, server_default=""),
        sa.Column("sector", sa.String(50), nullable=False, server_default=""),
        sa.Column("hint", sa.String(20), nullable=False, server_default=""),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "passed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("price_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("vol_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bonus_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("close", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("high_52w", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("avg_volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("threshold", sa.Float(), nullable=False, server_default="0"),
        sa.Column("volume_ratio_param", sa.Float(), nullable=False, server_default="0"),
        sa.Column("min_stocks_param", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_id", sa.String(100), nullable=True),
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
        sa.PrimaryKeyConstraint("date", "profile", "symbol", name="pk_daily_screening_cache"),
    )
    op.create_index(
        "idx_dsc_date_profile_rank",
        "daily_screening_cache",
        ["date", "profile", "rank"],
    )
    op.create_index(
        "idx_dsc_date_passed",
        "daily_screening_cache",
        ["date", "passed"],
    )


def downgrade() -> None:
    """daily_screening_cache 테이블 삭제."""
    op.drop_index("idx_dsc_date_passed", table_name="daily_screening_cache")
    op.drop_index("idx_dsc_date_profile_rank", table_name="daily_screening_cache")
    op.drop_table("daily_screening_cache")
