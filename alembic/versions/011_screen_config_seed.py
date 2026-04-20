"""strategy_config에 스크리닝 파라미터 seed 추가.

3개 키: screen_threshold, screen_volume_ratio, screen_min_stocks.
기존 키 있으면 덮어쓰지 않음 (멱등, ON CONFLICT DO NOTHING).

Revision ID: 011_screen_config_seed
Revises: 010_suggestion_telegram_sent_at
Create Date: 2026-04-20
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "011_screen_config_seed"
down_revision: str | None = "010_suggestion_telegram_sent_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEED_ROWS: list[tuple[str, object, str]] = [
    ("screen_threshold", 0.75, "스크리닝 52주고가 대비 비율 임계"),
    ("screen_volume_ratio", 0.8, "스크리닝 거래량 배수 임계"),
    ("screen_min_stocks", 100, "스크리닝 최소 통과 종목 수 (조건 미달 시 상위로 채움)"),
]


def upgrade() -> None:
    conn = op.get_bind()
    stmt = text(
        "INSERT INTO strategy_config "
        "(id, key, value, description, updated_by, created_at, updated_at) "
        "VALUES (gen_random_uuid(), :k, CAST(:v AS jsonb), :d, 'system', NOW(), NOW()) "
        "ON CONFLICT (key) DO NOTHING"
    )
    for key, value, description in _SEED_ROWS:
        conn.execute(
            stmt,
            {"k": key, "v": json.dumps(value), "d": description},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DELETE FROM strategy_config "
            "WHERE key IN ('screen_threshold', 'screen_volume_ratio', 'screen_min_stocks')"
        )
    )
