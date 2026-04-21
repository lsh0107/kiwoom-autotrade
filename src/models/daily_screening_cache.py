"""일일 사전 스크리닝 캐시 모델.

장 마감 후 Airflow DAG가 스크리닝을 수행하고 결과를 저장한다.
live_trader는 당일 데이터를 단일 쿼리로 읽어 0~10초 초기화를 달성한다.

(date, profile, symbol) 복합 PK.
통과/미통과 모두 저장해 디버깅/분석에 활용.
"""

from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class DailyScreeningCache(TimestampMixin, Base):
    """일별 스크리닝 결과 캐시.

    Attributes:
        date: 거래일 (YYYY-MM-DD, 장 마감 기준일).
        profile: 스크리닝 프로파일명 (예: "momentum_breakout").
        symbol: 종목 코드 (6자리, 앞자리 0 유지).
        name: 종목명.
        sector: 업종.
        hint: 표시용 힌트 (예: "BO" / "MB" 등).
        rank: 통과 종목 점수 순위 (미통과는 0 또는 큰 값).
        passed: 스크리닝 통과 여부.
        price_ratio: 52주 고가 대비 현재가 비율.
        vol_ratio: 평균거래량 대비 거래량 비율.
        bonus_score: 부가 스코어.
        close: 종가.
        high_52w: 52주 고가.
        volume: 당일 거래량.
        avg_volume: 평균 거래량.
        threshold: 사용된 52주 고가 근접 임계값 (파라미터 스냅샷).
        volume_ratio_param: 사용된 거래량 비율 파라미터.
        min_stocks_param: 사용된 최소 종목 수 파라미터.
        run_id: Airflow DAG run_id (감사/추적).
    """

    __tablename__ = "daily_screening_cache"
    __table_args__ = (
        PrimaryKeyConstraint("date", "profile", "symbol", name="pk_daily_screening_cache"),
        Index("idx_dsc_date_profile_rank", "date", "profile", "rank"),
        Index("idx_dsc_date_passed", "date", "passed"),
    )

    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    profile: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="momentum_breakout",
        server_default="momentum_breakout",
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    sector: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    hint: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vol_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bonus_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    close: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    high_52w: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    avg_volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    volume_ratio_param: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_stocks_param: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
