"""Short Swing 전략 모델 — 후보 종목 + 포지션 관리.

장마감 후 스크리닝으로 생성된 다음 거래일 감시 대상 + 보유 포지션 상태를 저장한다.
"""

from __future__ import annotations

import enum
from datetime import date as date_type
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class ShortSwingCandidate(UUIDMixin, TimestampMixin, Base):
    """Short Swing 후보 종목.

    장마감 후 스크리닝 결과 — 다음 거래일 진입 감시 대상.

    Attributes:
        trade_date: 후보 생성 기준일.
        symbol: 종목 코드 (6자리).
        name: 종목명.
        close: 기준일 종가.
        ma20: 20일 이동평균.
        ma60: 60일 이동평균.
        high_60d: 60일 고가.
        drawdown_from_high: 고점 대비 눌림률 (음수, 예: -0.05).
        trading_value: 당일 거래대금.
        avg_trading_value_20d: 20일 평균 거래대금.
        return_5d: 최근 5거래일 수익률.
        score: 후보 점수 (0~100).
        reason_json: 통과 사유 상세.
    """

    __tablename__ = "short_swing_candidates"
    __table_args__ = (
        UniqueConstraint("trade_date", "symbol", name="uq_short_swing_candidates_date_symbol"),
        Index("idx_short_swing_candidates_trade_date", "trade_date"),
    )

    trade_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    close: Mapped[int] = mapped_column(Integer, nullable=False)
    ma20: Mapped[float] = mapped_column(Float, nullable=False)
    ma60: Mapped[float] = mapped_column(Float, nullable=False)
    high_60d: Mapped[int] = mapped_column(Integer, nullable=False)
    drawdown_from_high: Mapped[float] = mapped_column(Float, nullable=False)
    trading_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    avg_trading_value_20d: Mapped[int] = mapped_column(BigInteger, nullable=False)
    return_5d: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# ── 포지션 상태/사유 enum ────────────────────────────────────────────────────


class PositionStatus(enum.StrEnum):
    """Short Swing 포지션 상태."""

    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


class ExitReason(enum.StrEnum):
    """청산 사유."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    MAX_HOLDING_DAYS = "max_holding_days"
    MA20_BREAKDOWN = "ma20_breakdown"
    KILL_SWITCH = "kill_switch"
    MANUAL = "manual"


# ── 포지션 모델 ──────────────────────────────────────────────────────────────


class ShortSwingPosition(UUIDMixin, TimestampMixin, Base):
    """Short Swing 전략 보유 포지션.

    진입 후 청산까지의 포지션 상태를 추적한다.

    Attributes:
        symbol: 종목 코드 (6자리).
        name: 종목명.
        entry_date: 진입일.
        entry_time: 진입 시각.
        entry_price: 평균 진입가.
        quantity: 보유 수량.
        highest_price_since_entry: 진입 후 최고가.
        stop_price: 손절 가격.
        take_profit_price: 익절 가격.
        trailing_armed: 트레일링 활성 여부.
        max_holding_until: 최대 보유 종료일.
        status: 포지션 상태 (open/closing/closed).
        exit_reason: 청산 사유.
    """

    __tablename__ = "short_swing_positions"
    __table_args__ = (
        # PostgreSQL partial unique index: 같은 종목에 open 포지션 중복 금지
        Index(
            "uq_short_swing_positions_symbol_open",
            "symbol",
            unique=True,
            postgresql_where="status = 'open'",
        ),
        Index("idx_short_swing_positions_status", "status"),
    )

    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    entry_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    highest_price_since_entry: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_price: Mapped[int] = mapped_column(Integer, nullable=False)
    take_profit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    trailing_armed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_holding_until: Mapped[date_type] = mapped_column(Date, nullable=False)
    status: Mapped[PositionStatus] = mapped_column(
        Enum(PositionStatus, values_callable=lambda e: [m.value for m in e]),
        default=PositionStatus.OPEN,
        nullable=False,
    )
    exit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
