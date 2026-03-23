"""LLM 브리핑 결과 모델."""

import uuid
from datetime import date

from sqlalchemy import JSON, Date, String, Text
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class LLMBriefing(UUIDMixin, TimestampMixin, Base):
    """LLM 시장 브리핑 결과 모델.

    하루에 1건만 허용 (date 유니크 제약).
    브리핑 요약, 테마 점수, 리스크 플래그, 비중 조정 등을 저장한다.
    """

    __tablename__ = "llm_briefings"

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
        comment="브리핑 대상 날짜 (하루에 1건)",
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="LLM이 생성한 시장 요약",
    )
    theme_scores: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment='테마별 점수 (예: {"반도체": 0.8, "바이오": 0.3})',
    )
    risk_flags: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment='리스크 플래그 목록 (예: ["VIX 30 초과", "달러 강세"])',
    )
    weight_adjustments: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment='비중 조정 제안 (예: {"반도체": 0.1, "바이오": -0.05})',
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
