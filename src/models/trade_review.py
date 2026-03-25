"""장후 매매 리뷰 모델."""

import uuid
from datetime import date

from sqlalchemy import JSON, Date, String, Text
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class TradeReview(UUIDMixin, TimestampMixin, Base):
    """장후 매매 리뷰 결과 모델.

    하루에 1건만 허용 (date 유니크 제약).
    매매 성과 분석, 리스크 평가, 파라미터 개선 제안 등을 저장한다.
    """

    __tablename__ = "trade_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="리뷰 대상 날짜 (하루에 1건)",
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="매매 리뷰 요약",
    )
    performance_analysis: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="당일 매매 성과 분석",
    )
    risk_assessment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="리스크 평가 내용",
    )
    suggestions: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="파라미터 개선 제안 목록",
    )
    raw_response: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="LLM 원본 응답 텍스트",
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="",
        comment="LLM 공급자 (claude/gpt/gemini 등)",
    )
    model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        comment="사용된 LLM 모델명",
    )
