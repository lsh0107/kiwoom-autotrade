"""strategy_runtime 테이블 추가 + 초기 시드 (design-025).

ACTIVE_STRATEGY env 단일 토글을 DB 기반 다중 전략 토글 + budget 분리로 전환.

Revision ID: 021_strategy_runtime
Revises: 020_short_swing_prev_day_high
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_strategy_runtime"
down_revision: str | None = "020_short_swing_prev_day_high"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEEDS = [
    ("cross_momentum", True, 0.60, 50_000_000, 200),
    ("short_swing", False, 0.30, 5_000_000, 100),
    ("multi_regime", False, 0.0, 1_000_000, 50),
]
"""Tuple 순서: (strategy, enabled, budget_pct, max_order_amount, max_daily_orders)"""


def upgrade() -> None:
    """strategy_runtime 테이블 생성 + 시드."""
    op.create_table(
        "strategy_runtime",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("strategy", sa.String(50), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("budget_pct", sa.Numeric(5, 4), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "max_order_amount", sa.Integer(), nullable=False, server_default=sa.text("1000000")
        ),
        sa.Column("max_daily_orders", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_by", sa.String(50), nullable=True),
    )
    op.create_index("ix_strategy_runtime_strategy", "strategy_runtime", ["strategy"], unique=True)

    # 초기 시드
    for strategy, enabled, budget_pct, max_order_amount, max_daily_orders in _SEEDS:
        op.execute(
            sa.text(
                "INSERT INTO strategy_runtime "
                "(id, strategy, enabled, budget_pct, max_order_amount, "
                "max_daily_orders, updated_by) "
                "VALUES (gen_random_uuid(), :s, :e, :b, :mo, :md, 'migration_021') "
                "ON CONFLICT (strategy) DO NOTHING"
            ).bindparams(
                s=strategy,
                e=enabled,
                b=budget_pct,
                mo=max_order_amount,
                md=max_daily_orders,
            )
        )


def downgrade() -> None:
    """strategy_runtime 테이블 제거."""
    op.drop_index("ix_strategy_runtime_strategy", table_name="strategy_runtime")
    op.drop_table("strategy_runtime")
