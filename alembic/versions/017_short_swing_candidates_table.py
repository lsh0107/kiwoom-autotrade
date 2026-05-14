"""short_swing_candidates 테이블 생성.

장마감 후 스크리닝 결과 — 다음 거래일 진입 감시 대상 저장용.
(trade_date, symbol) UNIQUE 제약.

Revision ID: 017_short_swing_candidates_table
Revises: 016_short_swing_config_seed
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_short_swing_candidates_table"
down_revision: str | None = "016_short_swing_config_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """short_swing_candidates 테이블 + 인덱스 생성."""
    op.create_table(
        "short_swing_candidates",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("close", sa.Integer(), nullable=False),
        sa.Column("ma20", sa.Float(), nullable=False),
        sa.Column("ma60", sa.Float(), nullable=False),
        sa.Column("high_60d", sa.Integer(), nullable=False),
        sa.Column("drawdown_from_high", sa.Float(), nullable=False),
        sa.Column("trading_value", sa.BigInteger(), nullable=False),
        sa.Column("avg_trading_value_20d", sa.BigInteger(), nullable=False),
        sa.Column("return_5d", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason_json", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("trade_date", "symbol", name="uq_short_swing_candidates_date_symbol"),
    )
    op.create_index(
        "idx_short_swing_candidates_trade_date",
        "short_swing_candidates",
        ["trade_date"],
    )


def downgrade() -> None:
    """short_swing_candidates 테이블 삭제."""
    op.drop_index("idx_short_swing_candidates_trade_date", table_name="short_swing_candidates")
    op.drop_table("short_swing_candidates")
