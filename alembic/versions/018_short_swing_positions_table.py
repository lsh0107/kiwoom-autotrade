"""short_swing_positions 테이블 생성.

진입 후 청산까지의 포지션 상태 추적용.
status='open' 종목 중복 금지 (partial unique index).

Revision ID: 018_short_swing_positions_table
Revises: 017_short_swing_candidates_table
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018_short_swing_positions_table"
down_revision: str | None = "017_short_swing_candidates_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """short_swing_positions 테이블 + 인덱스 생성."""
    op.create_table(
        "short_swing_positions",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("highest_price_since_entry", sa.Integer(), nullable=False),
        sa.Column("stop_price", sa.Integer(), nullable=False),
        sa.Column("take_profit_price", sa.Integer(), nullable=False),
        sa.Column("trailing_armed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("max_holding_until", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closing", "closed", name="positionstatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("exit_reason", sa.String(30), nullable=True),
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
    # status 인덱스
    op.create_index(
        "idx_short_swing_positions_status",
        "short_swing_positions",
        ["status"],
    )
    # PostgreSQL partial unique index: 같은 종목에 open 포지션 중복 금지
    op.execute(
        "CREATE UNIQUE INDEX uq_short_swing_positions_symbol_open "
        "ON short_swing_positions (symbol) WHERE status = 'open'"
    )


def downgrade() -> None:
    """short_swing_positions 테이블 삭제."""
    op.execute("DROP INDEX IF EXISTS uq_short_swing_positions_symbol_open")
    op.drop_index("idx_short_swing_positions_status", table_name="short_swing_positions")
    op.drop_table("short_swing_positions")
    op.execute("DROP TYPE IF EXISTS positionstatus")
