"""short_swing_positions 상태머신 확장 + user_id 스코핑 + exit 컬럼.

P0: PENDING_ENTRY, RECONCILIATION_ERROR 상태 추가.
P1.A: entry_order_id, exit_order_id, exit_price, exit_quantity, exit_time, realized_pnl.
P1.C: user_id (FK users.id) + partial unique index (user_id, symbol).

Revision ID: 019_short_swing_state_machine_user_scope
Revises: 018_short_swing_positions_table
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019_short_swing_state_machine_user_scope"
down_revision: str | None = "018_short_swing_positions_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """상태머신 확장 + user_id + exit 컬럼 추가."""
    # 1) positionstatus enum에 새 값 추가 (PostgreSQL ALTER TYPE)
    op.execute("ALTER TYPE positionstatus ADD VALUE IF NOT EXISTS 'pending_entry' BEFORE 'open'")
    op.execute("ALTER TYPE positionstatus ADD VALUE IF NOT EXISTS 'reconciliation_error'")

    # 2) user_id 컬럼 추가 (nullable 먼저, backfill 후 NOT NULL)
    op.add_column(
        "short_swing_positions",
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )

    # 3) 기존 row backfill: 첫 번째 사용자 ID 사용
    op.execute(
        "UPDATE short_swing_positions SET user_id = ("
        "  SELECT id FROM users ORDER BY created_at ASC LIMIT 1"
        ") WHERE user_id IS NULL"
    )

    # 4) NOT NULL 제약 + FK 설정
    op.alter_column("short_swing_positions", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_short_swing_positions_user_id",
        "short_swing_positions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_short_swing_positions_user_id",
        "short_swing_positions",
        ["user_id"],
    )

    # 5) entry/exit 관련 컬럼 추가
    op.add_column(
        "short_swing_positions",
        sa.Column("entry_order_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "short_swing_positions",
        sa.Column("exit_order_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "short_swing_positions",
        sa.Column("exit_price", sa.Integer(), nullable=True),
    )
    op.add_column(
        "short_swing_positions",
        sa.Column("exit_quantity", sa.Integer(), nullable=True),
    )
    op.add_column(
        "short_swing_positions",
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "short_swing_positions",
        sa.Column("realized_pnl", sa.Integer(), nullable=True),
    )

    # 6) 기존 partial unique index 교체 → (user_id, symbol) WHERE 활성 상태
    op.execute("DROP INDEX IF EXISTS uq_short_swing_positions_symbol_open")
    op.execute(
        "CREATE UNIQUE INDEX uq_short_swing_positions_user_symbol_active "
        "ON short_swing_positions (user_id, symbol) "
        "WHERE status IN ('pending_entry', 'open', 'closing')"
    )


def downgrade() -> None:
    """상태머신 확장 롤백."""
    # partial unique index 복원
    op.execute("DROP INDEX IF EXISTS uq_short_swing_positions_user_symbol_active")
    op.execute(
        "CREATE UNIQUE INDEX uq_short_swing_positions_symbol_open "
        "ON short_swing_positions (symbol) WHERE status = 'open'"
    )

    # exit 컬럼 제거
    op.drop_column("short_swing_positions", "realized_pnl")
    op.drop_column("short_swing_positions", "exit_time")
    op.drop_column("short_swing_positions", "exit_quantity")
    op.drop_column("short_swing_positions", "exit_price")
    op.drop_column("short_swing_positions", "exit_order_id")
    op.drop_column("short_swing_positions", "entry_order_id")

    # user_id 제거
    op.drop_index("idx_short_swing_positions_user_id", table_name="short_swing_positions")
    op.drop_constraint(
        "fk_short_swing_positions_user_id",
        "short_swing_positions",
        type_="foreignkey",
    )
    op.drop_column("short_swing_positions", "user_id")

    # enum 값 제거는 PostgreSQL에서 불가 — 무시 (unused values remain)
