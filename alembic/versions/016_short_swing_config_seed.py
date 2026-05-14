"""strategy_config에 short_swing 전략 파라미터 seed 추가.

short_swing 단기 스윙 전략의 28개 파라미터를 strategy_config 에 멱등 삽입.
기존 키 있으면 덮어쓰지 않음 (ON CONFLICT DO NOTHING).

Revision ID: 016_short_swing_config_seed
Revises: 015_cross_momentum_config_seed
Create Date: 2026-05-14
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "016_short_swing_config_seed"
down_revision: str | None = "015_cross_momentum_config_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEED_ROWS: list[tuple[str, object, str]] = [
    (
        "short_swing.short_swing_enabled",
        True,
        "short_swing 전략 활성화 여부.",
    ),
    (
        "short_swing.max_positions",
        5,
        "동시 보유 최대 종목 수.",
    ),
    (
        "short_swing.max_daily_new_positions",
        2,
        "하루 신규 매수 최대 종목 수.",
    ),
    (
        "short_swing.cash_buffer_pct",
        0.15,
        "현금 버퍼 비율. 가용현금의 15%는 매수에 사용하지 않음.",
    ),
    (
        "short_swing.min_order_amount",
        500000,
        "최소 주문금액 (원). 미만 시 매수 SKIP.",
    ),
    (
        "short_swing.entry_start_time",
        "09:20",
        "신규 진입 시작 시각 (HH:MM).",
    ),
    (
        "short_swing.entry_end_time",
        "13:00",
        "신규 진입 종료 시각 (HH:MM).",
    ),
    (
        "short_swing.stop_loss",
        -0.02,
        "매수가 대비 손절률 (음수). -0.02 = -2%.",
    ),
    (
        "short_swing.take_profit",
        0.04,
        "매수가 대비 기본 익절률. 0.04 = +4%.",
    ),
    (
        "short_swing.trailing_armed_pct",
        0.03,
        "트레일링 활성화 수익률. 0.03 = +3%.",
    ),
    (
        "short_swing.trailing_stop_pct",
        -0.015,
        "고점 대비 트레일링 청산률 (음수). -0.015 = -1.5%.",
    ),
    (
        "short_swing.max_holding_days",
        7,
        "최대 보유 거래일 수.",
    ),
    (
        "short_swing.min_price",
        1000,
        "최소 주가 (원). 미만 종목 유니버스 제외.",
    ),
    (
        "short_swing.min_avg_trading_value",
        3000000000,
        "최근 20일 평균 거래대금 최소값 (원). 30억 미만 제외.",
    ),
    (
        "short_swing.avoid_gap_up_pct",
        0.08,
        "시초 갭상승 회피 기준. 0.08 = 8% 이상 갭업 시 진입 안 함.",
    ),
    (
        "short_swing.avoid_intraday_rise_pct",
        0.15,
        "당일 과열 추격 회피 기준. 0.15 = 15% 이상 상승 시 진입 안 함.",
    ),
    (
        "short_swing.pullback_min_pct",
        -0.10,
        "60일 고점 대비 최대 눌림률 (음수). -0.10 = -10%.",
    ),
    (
        "short_swing.pullback_max_pct",
        -0.03,
        "60일 고점 대비 최소 눌림률 (음수). -0.03 = -3%.",
    ),
    (
        "short_swing.market_ma_period",
        20,
        "시장 지수 이동평균 기간 (거래일).",
    ),
    (
        "short_swing.stock_ma_short",
        20,
        "종목 단기 이동평균 기간 (거래일).",
    ),
    (
        "short_swing.stock_ma_long",
        60,
        "종목 장기 이동평균 기간 (거래일).",
    ),
    (
        "short_swing.candidate_limit",
        20,
        "후보 저장 상한 (상위 N개만 candidates 테이블에 insert).",
    ),
    (
        "short_swing.watchlist_limit",
        20,
        "감시 대상 상한 (다음 거래일 entry check 대상 수).",
    ),
]


def upgrade() -> None:
    """short_swing 전략 파라미터 seed 삽입."""
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
    """short_swing 전략 파라미터 삭제."""
    conn = op.get_bind()
    keys = [row[0] for row in _SEED_ROWS]
    placeholders = ", ".join(f"'{k}'" for k in keys)
    conn.execute(
        text(f"DELETE FROM strategy_config WHERE key IN ({placeholders})")  # noqa: S608
    )
