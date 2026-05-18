"""short_swing_candidates에 prev_day_high 컬럼 추가.

HOTFIX B: 진입 신호에 실제 전일 고가 사용. 기존 row는 NULL 유지.

Revision ID: 020_short_swing_prev_day_high
Revises: 019_ss_state_user_scope
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_short_swing_prev_day_high"
down_revision: str | None = "019_ss_state_user_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """prev_day_high 컬럼 추가 (NULLABLE, 기존 row는 NULL)."""
    op.add_column(
        "short_swing_candidates",
        sa.Column("prev_day_high", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """prev_day_high 컬럼 제거."""
    op.drop_column("short_swing_candidates", "prev_day_high")
