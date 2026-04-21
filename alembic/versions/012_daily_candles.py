"""daily_candles 테이블 생성.

일봉 OHLCV 캐시 테이블. (symbol, date) 복합 PK.
pykrx Airflow DAG 수집 + 키움 API fallback 결과 저장용.

Revision ID: 012_daily_candles
Revises: 011_screen_config_seed
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_daily_candles"
down_revision: str | None = "011_screen_config_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """daily_candles 테이블 + 인덱스 생성."""
    op.create_table(
        "daily_candles",
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.BigInteger(), nullable=False),
        sa.Column("high", sa.BigInteger(), nullable=False),
        sa.Column("low", sa.BigInteger(), nullable=False),
        sa.Column("close", sa.BigInteger(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="pykrx",
        ),
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
        sa.PrimaryKeyConstraint("symbol", "date", name="pk_daily_candles"),
    )
    op.create_index("idx_daily_candles_date", "daily_candles", ["date"])
    op.create_index(
        "idx_daily_candles_symbol_date",
        "daily_candles",
        ["symbol", "date"],
    )


def downgrade() -> None:
    """daily_candles 테이블 삭제."""
    op.drop_index("idx_daily_candles_symbol_date", table_name="daily_candles")
    op.drop_index("idx_daily_candles_date", table_name="daily_candles")
    op.drop_table("daily_candles")
