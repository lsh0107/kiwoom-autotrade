"""Short Swing 전략 후보 종목 모델.

장마감 후 스크리닝으로 생성된 다음 거래일 감시 대상을 저장한다.
"""

from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import JSON, BigInteger, Date, Float, Index, Integer, String, UniqueConstraint
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
