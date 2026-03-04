"""AI 자동매매 설정."""

from pydantic import BaseModel


class AIConfig(BaseModel):
    """AI 엔진 설정."""

    # 자동매매 활성화 (기본: 비활성)
    enable_auto_trading: bool = False

    # 분석 간격 (분)
    analysis_interval_minutes: int = 30

    # 신뢰도 임계값
    buy_confidence_threshold: float = 0.7
    sell_confidence_threshold: float = 0.6

    # 포지션 제한
    max_position_pct: float = 30.0
    max_symbols: int = 10

    # 장 시간 체크
    check_market_hours: bool = True
