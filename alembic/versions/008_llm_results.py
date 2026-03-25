"""llm_briefings / trade_reviews 테이블 생성.

Revision ID: 008_llm_results
Revises: 007_monthly_signals
Create Date: 2026-03-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_llm_results"
down_revision: str | None = "007_monthly_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """llm_briefings, trade_reviews 테이블 생성."""
    # LLM 브리핑 결과 테이블
    op.create_table(
        "llm_briefings",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("theme_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("risk_flags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("weight_adjustments", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("raw_response", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(20), nullable=False, server_default=""),
        sa.Column("model", sa.String(50), nullable=False, server_default=""),
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
        sa.UniqueConstraint("date", name="uq_llm_briefings_date"),
    )
    op.create_index("ix_llm_briefings_date", "llm_briefings", ["date"])

    # 장후 매매 리뷰 테이블
    op.create_table(
        "trade_reviews",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("performance_analysis", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_assessment", sa.Text(), nullable=False, server_default=""),
        sa.Column("suggestions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("raw_response", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(20), nullable=False, server_default=""),
        sa.Column("model", sa.String(50), nullable=False, server_default=""),
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
        sa.UniqueConstraint("date", name="uq_trade_reviews_date"),
    )
    op.create_index("ix_trade_reviews_date", "trade_reviews", ["date"])


def downgrade() -> None:
    """llm_briefings, trade_reviews 테이블 삭제."""
    op.drop_index("ix_trade_reviews_date", "trade_reviews")
    op.drop_table("trade_reviews")
    op.drop_index("ix_llm_briefings_date", "llm_briefings")
    op.drop_table("llm_briefings")
