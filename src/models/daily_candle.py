"""일봉 캐시 모델.

Airflow pykrx 수집 결과 및 키움 API fallback 데이터를 저장한다.
(symbol, date) 복합 PK로 중복 방지, source 컬럼으로 수집 출처 구분.
"""

from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import BigInteger, Date, Index, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class DailyCandle(TimestampMixin, Base):
    """일봉 OHLCV 캐시.

    Attributes:
        symbol: 종목 코드 (6자리, 앞자리 0 유지).
        date: 일자 (YYYY-MM-DD).
        open: 시가 (원 단위 정수).
        high: 고가.
        low: 저가.
        close: 종가.
        volume: 거래량.
        source: 데이터 출처 ("pykrx" | "kiwoom" | "backfill").
    """

    __tablename__ = "daily_candles"
    __table_args__ = (
        PrimaryKeyConstraint("symbol", "date", name="pk_daily_candles"),
        Index("idx_daily_candles_date", "date"),
        Index("idx_daily_candles_symbol_date", "symbol", "date"),
    )

    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    open: Mapped[int] = mapped_column(BigInteger, nullable=False)
    high: Mapped[int] = mapped_column(BigInteger, nullable=False)
    low: Mapped[int] = mapped_column(BigInteger, nullable=False)
    close: Mapped[int] = mapped_column(BigInteger, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pykrx",
        server_default="pykrx",
    )
