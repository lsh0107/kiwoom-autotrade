"""monthly_signals 테이블 생성.

Revision ID: 007_monthly_signals
Revises: 006_stock_relations
Create Date: 2026-03-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_monthly_signals"
down_revision: str | None = "006_stock_relations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monthly_signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("signal", sa.String(10), nullable=False),
        sa.Column("close", sa.BigInteger, nullable=True),
        sa.Column("ma12", sa.Float, nullable=True),
        sa.Column("adx", sa.Float, nullable=True),
        sa.Column("volume_ratio", sa.Float, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("signal_date", sa.Date, server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("symbol", "signal_date", name="uq_monthly_signals_symbol_date"),
    )


def downgrade() -> None:
    op.drop_table("monthly_signals")
