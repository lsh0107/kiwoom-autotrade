"""strategy_config_suggestions에 telegram_sent_at 컬럼 추가.

Revision ID: 010_suggestion_telegram_sent_at
Revises: 009_llm_decisions
Create Date: 2026-04-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_suggestion_telegram_sent_at"
down_revision: str | None = "009_llm_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strategy_config_suggestions",
        sa.Column(
            "telegram_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="텔레그램 알림 전송 시각",
        ),
    )


def downgrade() -> None:
    op.drop_column("strategy_config_suggestions", "telegram_sent_at")
