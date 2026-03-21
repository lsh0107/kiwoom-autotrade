"""stocks 마스터 테이블 생성 + stock_universe/news_articles FK 추가.

Revision ID: 005_stocks_master
Revises: 004_stock_universe
Create Date: 2026-03-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_stocks_master"
down_revision: str | None = "004_stock_universe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """stocks 테이블 생성, stock_universe 데이터 마이그레이션, FK 컬럼 추가."""
    # 1. stocks 테이블 생성
    op.create_table(
        "stocks",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("market", sa.String(20), nullable=False, server_default="KOSPI"),
        sa.Column("sector", sa.String(50), nullable=False, server_default="기타"),
        sa.Column("theme", sa.String(50), nullable=True),
        sa.Column("strategy_hint", sa.String(20), nullable=True),
        sa.Column("market_cap_tier", sa.String(10), nullable=True),
        sa.Column("dart_corp_code", sa.String(8), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", name="uq_stocks_symbol"),
    )
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"])
    op.create_index("ix_stocks_is_active", "stocks", ["is_active"])

    # 2. stock_universe → stocks 데이터 마이그레이션
    op.execute("""
        INSERT INTO stocks (id, symbol, name, market, sector, is_active, created_at, updated_at)
        SELECT DISTINCT ON (symbol)
            gen_random_uuid(), symbol, name, market, sector, is_active, NOW(), NOW()
        FROM stock_universe
        ORDER BY symbol, created_at
        ON CONFLICT (symbol) DO NOTHING
    """)

    # 3. stock_universe에 stock_id FK 컬럼 추가
    op.add_column("stock_universe", sa.Column("stock_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_stock_universe_stock_id",
        "stock_universe",
        "stocks",
        ["stock_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_stock_universe_stock_id", "stock_universe", ["stock_id"])

    # stock_universe.stock_id 채우기
    op.execute("""
        UPDATE stock_universe su
        SET stock_id = s.id
        FROM stocks s
        WHERE su.symbol = s.symbol
    """)

    # 4. news_articles에 stock_id FK 컬럼 추가
    op.add_column("news_articles", sa.Column("stock_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_news_articles_stock_id",
        "news_articles",
        "stocks",
        ["stock_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_news_articles_stock_id", "news_articles", ["stock_id"])


def downgrade() -> None:
    """stocks 테이블 삭제 + FK 컬럼 제거."""
    op.drop_index("ix_news_articles_stock_id", "news_articles")
    op.drop_constraint("fk_news_articles_stock_id", "news_articles", type_="foreignkey")
    op.drop_column("news_articles", "stock_id")
    op.drop_index("ix_stock_universe_stock_id", "stock_universe")
    op.drop_constraint("fk_stock_universe_stock_id", "stock_universe", type_="foreignkey")
    op.drop_column("stock_universe", "stock_id")
    op.drop_index("ix_stocks_is_active", "stocks")
    op.drop_index("ix_stocks_symbol", "stocks")
    op.drop_table("stocks")
