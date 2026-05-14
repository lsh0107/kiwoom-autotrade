"""ADR-024: 활성 전략 단일 enum 관리 모듈."""

from __future__ import annotations

import os
from enum import StrEnum


class ActiveStrategy(StrEnum):
    """활성 전략 enum.

    CROSS_MOMENTUM: 월말 리밸런싱 전략 (cross-momentum)
    MULTI_REGIME: 다중 레짐 기반 5분봉 전략
    SHORT_SWING: 단기 스윙 전략 (2~10 거래일 보유)
    NONE: 모든 매매 비활성 (기본값, 시스템 idle)
    """

    CROSS_MOMENTUM = "cross_momentum"
    MULTI_REGIME = "multi_regime"
    SHORT_SWING = "short_swing"
    NONE = "none"


def get_active_strategy() -> ActiveStrategy:
    """환경변수 ACTIVE_STRATEGY에서 활성 전략을 읽는다.

    잘못된 값이면 NONE으로 폴백한다.

    Returns:
        ActiveStrategy 인스턴스.
    """
    raw = os.environ.get("ACTIVE_STRATEGY", "none").strip().lower()
    try:
        return ActiveStrategy(raw)
    except ValueError:
        return ActiveStrategy.NONE
