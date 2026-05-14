"""strategy_config에 cross_momentum 리밸런싱 파라미터 seed 추가.

ADR-022 cross-sectional momentum 전략의 하드코딩 파라미터를 strategy_config 로 외부화.
기존 키 있으면 덮어쓰지 않음 (멱등, ON CONFLICT DO NOTHING).

Revision ID: 015_cross_momentum_config_seed
Revises: 014_slippage_config_seed
Create Date: 2026-05-14
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "015_cross_momentum_config_seed"
down_revision: str | None = "014_slippage_config_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEED_ROWS: list[tuple[str, object, str]] = [
    (
        "cross_momentum.rebalance_freq",
        "monthly",
        "리밸런싱 주기: monthly(매월 말 영업일) | weekly(매주 금요일). 현재 monthly만 동작.",
    ),
    (
        "cross_momentum.n_positions",
        5,
        "목표 포트폴리오 종목 수. 계좌 규모 대비 적정 분산.",
    ),
    (
        "cross_momentum.top_pct",
        None,
        "모멘텀 상위 비율 (0.0~1.0). n_positions 설정 시 우선순위 낮음. null이면 n_positions 사용.",
    ),
    (
        "cross_momentum.use_vol_filter",
        False,
        "변동성 필터 사용 여부 (ADR-021 best combo: OFF).",
    ),
    (
        "cross_momentum.use_trend_filter",
        False,
        "추세 필터 사용 여부 (ADR-021 best combo: OFF).",
    ),
    (
        "cross_momentum.min_order_amount",
        500000,
        "최소 주문금액 (원). 미만 시 매수/매도 SKIP.",
    ),
    (
        "cross_momentum.max_order_amount_pct",
        0.20,
        "종목당 최대 주문금액 비율 (가용현금 기준). 0.20 = 가용현금의 20%.",
    ),
    (
        "cross_momentum.cash_buffer_pct",
        0.10,
        "현금 버퍼 비율. 가용현금의 10%는 매수에 사용하지 않음.",
    ),
]


def upgrade() -> None:
    """cross_momentum 리밸런싱 파라미터 seed 삽입."""
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
    """cross_momentum 리밸런싱 파라미터 삭제."""
    conn = op.get_bind()
    keys = [row[0] for row in _SEED_ROWS]
    placeholders = ", ".join(f"'{k}'" for k in keys)
    conn.execute(
        text(f"DELETE FROM strategy_config WHERE key IN ({placeholders})")  # noqa: S608
    )
