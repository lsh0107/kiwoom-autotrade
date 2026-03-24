"""llm_decisions 테이블 생성 — LLM 투자 결정 추적.

Revision ID: 009_llm_decisions
Revises: 008_llm_results
Create Date: 2026-03-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_llm_decisions"
down_revision: str | None = "008_llm_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column(
            "decision_type",
            sa.String(30),
            nullable=False,
            comment="weight_adjust, risk_mode, param_tune, stock_swap",
        ),
        sa.Column(
            "context_source",
            sa.String(20),
            nullable=False,
            comment="overnight, premarket, postmarket",
        ),
        sa.Column("content", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation", sa.JSON, nullable=True),
        sa.Column("raw_response", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_llm_decisions_date_type", "llm_decisions", ["date", "decision_type"])
    op.create_index("ix_llm_decisions_status", "llm_decisions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_llm_decisions_status", table_name="llm_decisions")
    op.drop_index("ix_llm_decisions_date_type", table_name="llm_decisions")
    op.drop_table("llm_decisions")
