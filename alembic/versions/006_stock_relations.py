"""stock_relations 테이블 생성 + sector_peer 시드 데이터.

Revision ID: 006_stock_relations
Revises: 005_stocks_master
Create Date: 2026-03-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_stock_relations"
down_revision: str | None = "005_stocks_master"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """stock_relations 테이블 생성 + sector_peer 시드 데이터 삽입."""
    op.create_table(
        "stock_relations",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("from_stock_id", sa.UUID(), nullable=False),
        sa.Column("to_stock_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.String(30), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("period_days", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["from_stock_id"],
            ["stocks.id"],
            ondelete="CASCADE",
            name="fk_stock_relations_from",
        ),
        sa.ForeignKeyConstraint(
            ["to_stock_id"],
            ["stocks.id"],
            ondelete="CASCADE",
            name="fk_stock_relations_to",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_stock_id",
            "to_stock_id",
            "relation_type",
            name="uq_stock_relation",
        ),
    )
    op.create_index("ix_stock_relations_from", "stock_relations", ["from_stock_id"])
    op.create_index("ix_stock_relations_to", "stock_relations", ["to_stock_id"])
    op.create_index("ix_stock_relations_type", "stock_relations", ["relation_type"])

    # sector_peer 시드 데이터
    op.execute("""
        INSERT INTO stock_relations
            (id, from_stock_id, to_stock_id, relation_type, source, valid_from)
        SELECT
            gen_random_uuid(),
            s1.id,
            s2.id,
            'sector_peer',
            'seed',
            CURRENT_DATE
        FROM stocks s1
        JOIN stocks s2 ON s1.sector = s2.sector AND s1.id != s2.id
        ON CONFLICT (from_stock_id, to_stock_id, relation_type) DO NOTHING
    """)


def downgrade() -> None:
    """stock_relations 테이블 삭제."""
    op.drop_index("ix_stock_relations_type", "stock_relations")
    op.drop_index("ix_stock_relations_to", "stock_relations")
    op.drop_index("ix_stock_relations_from", "stock_relations")
    op.drop_table("stock_relations")
