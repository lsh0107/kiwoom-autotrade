"""strategy_config에 slippage_assumption 파라미터 seed 추가.

마이크로구조 개선(ADR-015): 지정가 주문 기본 전환으로 슬리피지 가정을 낮춤.
기존 키 있으면 덮어쓰지 않음 (멱등, ON CONFLICT DO NOTHING).

Revision ID: 014_slippage_config_seed
Revises: 013_daily_screening_cache
Create Date: 2026-04-24
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "014_slippage_config_seed"
down_revision: str | None = "013_daily_screening_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEED_ROWS: list[tuple[str, object, str]] = [
    (
        "slippage_assumption",
        0.0015,
        "지정가 주문 기준 슬리피지 가정 (0.15%). 시장가 0.30% 대비 절반.",
    ),
    (
        "limit_order_timeout_sec",
        30,
        "지정가 매수 미체결 시 취소 후 시장가 전환까지 대기 시간(초).",
    ),
    (
        "entry_blocked_windows",
        "11:30~13:00",
        "진입 차단 시간대 (점심 저유동성). 복수 설정 시 ','로 구분.",
    ),
    (
        "block_open_volatility",
        False,
        "장 초반(09:00~09:30) 시초가 변동성 구간 진입 차단 여부.",
    ),
]


def upgrade() -> None:
    """slippage_assumption 등 마이크로구조 설정 seed 삽입."""
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
    """slippage_assumption 등 마이크로구조 설정 삭제."""
    conn = op.get_bind()
    keys = [row[0] for row in _SEED_ROWS]
    placeholders = ", ".join(f"'{k}'" for k in keys)
    conn.execute(
        text(f"DELETE FROM strategy_config WHERE key IN ({placeholders})")  # noqa: S608
    )
