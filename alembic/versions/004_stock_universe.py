"""stock_universe 테이블 생성 + Pool A seed 데이터.

Revision ID: 004_stock_universe
Revises: 003_phase3_data_tables
Create Date: 2026-03-18
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_stock_universe"
down_revision: str | None = "003_phase3_data_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POOL_A_SEED: list[tuple[str, str, str, str]] = [
    # 반도체
    ("005930", "삼성전자", "반도체", "KOSPI"),
    ("000660", "SK하이닉스", "반도체", "KOSPI"),
    ("009150", "삼성전기", "반도체", "KOSPI"),
    ("403870", "HPSP", "반도체", "KOSDAQ"),
    ("095340", "ISC", "반도체", "KOSDAQ"),
    ("058470", "리노공업", "반도체", "KOSDAQ"),
    # 2차전지
    ("051910", "LG화학", "2차전지", "KOSPI"),
    ("003670", "포스코퓨처엠", "2차전지", "KOSPI"),
    ("006400", "삼성SDI", "2차전지", "KOSPI"),
    ("247540", "에코프로비엠", "2차전지", "KOSDAQ"),
    ("086520", "에코프로", "2차전지", "KOSDAQ"),
    # 자동차
    ("005380", "현대차", "자동차", "KOSPI"),
    ("000270", "기아", "자동차", "KOSPI"),
    ("012330", "현대모비스", "자동차", "KOSPI"),
    # 바이오
    ("068270", "셀트리온", "바이오", "KOSPI"),
    ("196170", "알테오젠", "바이오", "KOSDAQ"),
    ("145020", "휴젤", "바이오", "KOSDAQ"),
    ("328130", "루닛", "바이오", "KOSDAQ"),
    ("207940", "삼성바이오로직스", "바이오", "KOSPI"),
    # IT/플랫폼
    ("035420", "NAVER", "IT플랫폼", "KOSPI"),
    ("035720", "카카오", "IT플랫폼", "KOSPI"),
    ("377300", "카카오페이", "IT플랫폼", "KOSPI"),
    ("018260", "삼성에스디에스", "IT플랫폼", "KOSPI"),
    # 금융
    ("055550", "신한지주", "금융", "KOSPI"),
    ("105560", "KB금융", "금융", "KOSPI"),
    ("086790", "하나금융지주", "금융", "KOSPI"),
    ("316140", "우리금융지주", "금융", "KOSPI"),
    ("032830", "삼성생명", "금융", "KOSPI"),
    # 조선
    ("009540", "HD한국조선해양", "조선", "KOSPI"),
    ("042660", "한화오션", "조선", "KOSPI"),
    ("329180", "HD현대중공업", "조선", "KOSPI"),
    ("011200", "HMM", "조선", "KOSPI"),
    # 방산
    ("012450", "한화에어로스페이스", "방산", "KOSPI"),
    ("079550", "LIG넥스원", "방산", "KOSPI"),
    # 엔터
    ("352820", "하이브", "엔터", "KOSPI"),
    ("041510", "에스엠", "엔터", "KOSPI"),
    ("035900", "JYP Ent.", "엔터", "KOSDAQ"),
    # 게임
    ("263750", "펄어비스", "게임", "KOSDAQ"),
    ("036570", "엔씨소프트", "게임", "KOSPI"),
    ("293490", "카카오게임즈", "게임", "KOSDAQ"),
    ("112040", "위메이드", "게임", "KOSDAQ"),
    # 건설
    ("000720", "현대건설", "건설", "KOSPI"),
    ("028260", "삼성물산", "건설", "KOSPI"),
    # 에너지
    ("010950", "S-Oil", "에너지", "KOSPI"),
    ("015760", "한국전력", "에너지", "KOSPI"),
    ("034020", "두산에너빌리티", "에너지", "KOSPI"),
    ("047050", "포스코인터내셔널", "에너지", "KOSPI"),
    # 철강/소재
    ("005490", "POSCO홀딩스", "철강", "KOSPI"),
    ("010130", "고려아연", "철강", "KOSPI"),
    # 소비재
    ("033780", "KT&G", "소비재", "KOSPI"),
    ("090430", "아모레퍼시픽", "소비재", "KOSPI"),
    ("051900", "LG생활건강", "소비재", "KOSPI"),
    # 지주
    ("003550", "LG", "지주", "KOSPI"),
    ("034730", "SK", "지주", "KOSPI"),
    ("267250", "HD현대", "지주", "KOSPI"),
]


def upgrade() -> None:
    """stock_universe 테이블 생성 및 Pool A seed 데이터 삽입."""
    op.create_table(
        "stock_universe",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("pool", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sector", sa.String(50), nullable=False, server_default="기타"),
        sa.Column("market", sa.String(20), nullable=False, server_default="KOSPI"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "pool", name="uq_stock_universe_symbol_pool"),
    )
    op.create_index("ix_stock_universe_pool", "stock_universe", ["pool"])
    op.create_index("ix_stock_universe_symbol", "stock_universe", ["symbol"])
    op.create_index("ix_stock_universe_is_active", "stock_universe", ["is_active"])

    # Pool A seed 데이터 삽입
    seed_table = sa.table(
        "stock_universe",
        sa.column("id", sa.UUID()),
        sa.column("pool", sa.String()),
        sa.column("symbol", sa.String()),
        sa.column("name", sa.String()),
        sa.column("sector", sa.String()),
        sa.column("market", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        seed_table,
        [
            {
                "id": uuid.uuid4(),
                "pool": "pool_a",
                "symbol": symbol,
                "name": name,
                "sector": sector,
                "market": market,
                "is_active": True,
            }
            for symbol, name, sector, market in _POOL_A_SEED
        ],
    )


def downgrade() -> None:
    """stock_universe 테이블 삭제."""
    op.drop_index("ix_stock_universe_is_active", "stock_universe")
    op.drop_index("ix_stock_universe_symbol", "stock_universe")
    op.drop_index("ix_stock_universe_pool", "stock_universe")
    op.drop_table("stock_universe")
