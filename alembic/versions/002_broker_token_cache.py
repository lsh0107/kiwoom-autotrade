"""브로커 자격증명에 토큰 캐시 컬럼 추가.

Revision ID: 002_token_cache
Revises: 001_initial
Create Date: 2026-03-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_token_cache"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """broker_credentials 테이블에 토큰 캐시 컬럼 추가."""
    op.add_column("broker_credentials", sa.Column("cached_token", sa.Text(), nullable=True))
    op.add_column(
        "broker_credentials",
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "broker_credentials",
        sa.Column("token_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "broker_credentials",
        sa.Column("token_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """토큰 캐시 컬럼 제거."""
    op.drop_column("broker_credentials", "token_updated_at")
    op.drop_column("broker_credentials", "token_type")
    op.drop_column("broker_credentials", "token_expires_at")
    op.drop_column("broker_credentials", "cached_token")
