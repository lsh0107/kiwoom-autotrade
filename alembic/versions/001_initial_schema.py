"""초기 스키마 생성.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """초기 테이블 생성."""
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(50), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "user", name="userrole"),
            server_default="user",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # invites
    op.create_table(
        "invites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("used_by", sa.UUID(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default="false", nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"]),
    )
    op.create_index("ix_invites_code", "invites", ["code"], unique=True)

    # broker_credentials
    op.create_table(
        "broker_credentials",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("broker_name", sa.String(50), nullable=False),
        sa.Column("encrypted_app_key", sa.Text(), nullable=False),
        sa.Column("encrypted_app_secret", sa.Text(), nullable=False),
        sa.Column("account_no", sa.String(20), nullable=False),
        sa.Column("is_mock", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_broker_credentials_user_id", "broker_credentials", ["user_id"])

    # strategies
    op.create_table(
        "strategies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("config", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("symbols", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "paused", "stopped", name="strategystatus"),
            nullable=False,
        ),
        sa.Column("is_auto_trading", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("max_investment", sa.Integer(), nullable=False, server_default="1000000"),
        sa.Column("max_loss_pct", sa.Float(), nullable=False, server_default="-3.0"),
        sa.Column("max_position_pct", sa.Float(), nullable=False, server_default="30.0"),
        sa.Column("kill_switch_active", sa.Boolean(), server_default="false", nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_strategies_user_id", "strategies", ["user_id"])

    # orders
    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("symbol_name", sa.String(100), server_default="", nullable=False),
        sa.Column("side", sa.Enum("buy", "sell", name="orderside"), nullable=False),
        sa.Column("order_type", sa.String(20), server_default="limit", nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("filled_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("filled_price", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "submitted",
                "accepted",
                "partial_fill",
                "filled",
                "rejected",
                "cancelled",
                "expired",
                "failed",
                name="orderstatus",
            ),
            nullable=False,
        ),
        sa.Column("broker_order_no", sa.String(50), nullable=True),
        sa.Column("is_mock", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])
    op.create_index("ix_orders_status", "orders", ["status"])

    # trade_logs
    op.create_table(
        "trade_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("strategy_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(20), server_default="", nullable=False),
        sa.Column("side", sa.String(10), server_default="", nullable=False),
        sa.Column("price", sa.Integer(), server_default="0", nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column("details", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("is_mock", sa.Boolean(), server_default="true", nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_trade_logs_user_id", "trade_logs", ["user_id"])
    op.create_index("ix_trade_logs_event_type", "trade_logs", ["event_type"])

    # ai_signals
    op.create_table(
        "ai_signals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("target_price", sa.Integer(), nullable=True),
        sa.Column("position_size_pct", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("risk_level", sa.String(10), server_default="MEDIUM", nullable=False),
        sa.Column("reasoning", sa.Text(), server_default="", nullable=False),
        sa.Column("raw_analysis", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("is_executed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ai_signals_user_id", "ai_signals", ["user_id"])
    op.create_index("ix_ai_signals_symbol", "ai_signals", ["symbol"])

    # llm_call_logs
    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("prompt_type", sa.String(50), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("success", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_llm_call_logs_user_id", "llm_call_logs", ["user_id"])


def downgrade() -> None:
    """테이블 삭제."""
    op.drop_table("llm_call_logs")
    op.drop_table("ai_signals")
    op.drop_table("trade_logs")
    op.drop_table("orders")
    op.drop_table("strategies")
    op.drop_table("broker_credentials")
    op.drop_table("invites")
    op.drop_table("users")

    # Enum 타입 삭제
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS strategystatus")
    op.execute("DROP TYPE IF EXISTS orderside")
    op.execute("DROP TYPE IF EXISTS orderstatus")
