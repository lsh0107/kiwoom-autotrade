"""파라미터 자동 조정 분석기.

LLM 리뷰 결과 + 최근 매매 통계 → 파라미터 조정 제안 생성.
제안은 DB에 status="pending"으로 저장되며, 사용자 승인 없이 자동 적용하지 않는다.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# 파라미터 허용 범위 — 이 범위 밖의 제안은 클램핑 또는 제외
_PARAM_BOUNDS: dict[str, tuple[Any, Any]] = {
    "atr_stop_mult": (1.0, 3.0),
    "atr_tp_mult": (2.0, 5.0),
    "volume_ratio": (1.0, 3.0),
    "max_positions": (1, 5),
}

# 시간 파라미터 키 목록 (HH:MM 형식, 09:00~15:00)
_TIME_PARAM_KEYS = {"entry_start_time", "entry_end_time", "exit_time"}
_TIME_MIN = "09:00"
_TIME_MAX = "15:00"

# confidence 필터 기준
_MIN_CONFIDENCE = 0.7


@dataclass
class ParamSuggestion:
    """파라미터 조정 제안."""

    key: str  # strategy_config 키
    current_value: Any
    suggested_value: Any
    reason: str  # 제안 근거
    confidence: float  # 0.0 ~ 1.0
    source: str = "param_tuner"  # 제안 출처


def _clamp_numeric(key: str, value: Any) -> Any:
    """허용 범위로 숫자 파라미터 클램핑.

    Args:
        key: 파라미터 키.
        value: 제안 값.

    Returns:
        클램핑된 값. 범위 정의 없으면 원본 반환.
    """
    if key not in _PARAM_BOUNDS:
        return value
    lo, hi = _PARAM_BOUNDS[key]
    try:
        # max_positions는 int, 나머지는 float
        if isinstance(lo, int):
            return max(lo, min(hi, int(round(float(value)))))
        return max(float(lo), min(float(hi), float(value)))
    except (TypeError, ValueError):
        return value


def _validate_time(value: Any) -> bool:
    """시간 파라미터가 HH:MM 형식이고 09:00~15:00 범위인지 검증."""
    if not isinstance(value, str):
        return False
    parts = value.strip().split(":")
    if len(parts) != 2:
        return False
    try:
        h, m = int(parts[0]), int(parts[1])
        time_str = f"{h:02d}:{m:02d}"
        return _TIME_MIN <= time_str <= _TIME_MAX
    except ValueError:
        return False


def _is_within_bounds(key: str, value: Any) -> bool:
    """제안 값이 허용 범위 내인지 확인.

    시간 파라미터는 별도 검증. 나머지는 _PARAM_BOUNDS 참조.
    """
    if key in _TIME_PARAM_KEYS:
        return _validate_time(value)

    if key not in _PARAM_BOUNDS:
        return True  # 알 수 없는 키는 범위 제한 없음

    lo, hi = _PARAM_BOUNDS[key]
    try:
        v = float(value)
        return float(lo) <= v <= float(hi)
    except (TypeError, ValueError):
        return False


def _merge_suggestions(
    llm_suggestions: list[dict],
    trade_stats: dict,
) -> list[ParamSuggestion]:
    """LLM 제안과 매매 통계를 결합해 최종 제안 목록 생성.

    LLM 제안을 기반으로 하되, 매매 통계로 confidence를 조정한다.

    Args:
        llm_suggestions: LLM review.py의 ParamSuggestion 딕셔너리 목록.
        trade_stats: 매매 통계 (win_rate, avg_pnl, total_trades 등).

    Returns:
        필터링 + 범위 검증된 ParamSuggestion 목록.
    """
    result: list[ParamSuggestion] = []
    win_rate = float(trade_stats.get("win_rate", 0.5))

    for item in llm_suggestions:
        key = str(item.get("key", ""))
        if not key:
            continue

        confidence = float(item.get("confidence", 0.0))

        # 승률이 낮으면 confidence 소폭 상향 (더 적극적 조정 필요)
        if win_rate < 0.4:
            confidence = min(1.0, confidence + 0.05)

        # confidence 기준 미달 필터
        if confidence < _MIN_CONFIDENCE:
            logger.debug("confidence 미달 제외: %s (%.2f)", key, confidence)
            continue

        current_value = item.get("current_value")
        suggested_raw = item.get("suggested_value")

        # 시간 파라미터: 범위 벗어나면 제외
        if key in _TIME_PARAM_KEYS:
            if not _validate_time(suggested_raw):
                logger.warning("시간 파라미터 범위 초과 제외: %s = %s", key, suggested_raw)
                continue
            suggested_value = suggested_raw
        else:
            # 숫자 파라미터: 범위 클램핑
            suggested_value = _clamp_numeric(key, suggested_raw)

        result.append(
            ParamSuggestion(
                key=key,
                current_value=current_value,
                suggested_value=suggested_value,
                reason=str(item.get("reason", "")),
                confidence=confidence,
                source="param_tuner",
            )
        )

    return result


def _compute_trade_stats(trade_history: list[dict]) -> dict:
    """매매 기록에서 통계 계산.

    Args:
        trade_history: 매매 기록 목록. pnl 필드 포함 여부에 따라 통계 계산.

    Returns:
        win_rate, avg_pnl, total_trades, profitable_trades 딕셔너리.
    """
    if not trade_history:
        return {"win_rate": 0.5, "avg_pnl": 0.0, "total_trades": 0, "profitable_trades": 0}

    pnl_list = [float(t.get("pnl", 0)) for t in trade_history if "pnl" in t]
    if not pnl_list:
        return {
            "win_rate": 0.5,
            "avg_pnl": 0.0,
            "total_trades": len(trade_history),
            "profitable_trades": 0,
        }

    profitable = sum(1 for p in pnl_list if p > 0)
    return {
        "win_rate": profitable / len(pnl_list),
        "avg_pnl": sum(pnl_list) / len(pnl_list),
        "total_trades": len(trade_history),
        "profitable_trades": profitable,
    }


def analyze_and_suggest(
    review_result: dict,
    trade_history: list[dict],
    market_context: dict | None = None,  # noqa: ARG001 (향후 확장용)
) -> list[ParamSuggestion]:
    """LLM 리뷰 결과와 매매 통계를 결합해 파라미터 조정 제안 생성.

    주의: 이 함수는 제안만 생성한다. 자동 적용하지 않는다.
    사용자 승인 후 strategy_config가 업데이트되어야 한다.

    Args:
        review_result: llm.review.generate_review() 결과의 딕셔너리 표현.
            suggestions 키에 ParamSuggestion 목록 포함.
        trade_history: 최근 매매 기록 목록.
        market_context: 시장 컨텍스트 (향후 확장용, 현재 미사용).

    Returns:
        필터링 + 범위 검증된 ParamSuggestion 목록.
        confidence 0.7 미만은 제외.
        범위 초과 숫자 파라미터는 클램핑.
        범위 초과 시간 파라미터는 제외.
    """
    raw_suggestions = review_result.get("suggestions", [])
    if not raw_suggestions:
        logger.info("LLM 리뷰에 파라미터 제안 없음")
        return []

    trade_stats = _compute_trade_stats(trade_history)
    logger.info(
        "매매 통계: total=%d, win_rate=%.2f, avg_pnl=%.0f",
        trade_stats["total_trades"],
        trade_stats["win_rate"],
        trade_stats["avg_pnl"],
    )

    suggestions = _merge_suggestions(raw_suggestions, trade_stats)
    logger.info("파라미터 제안 생성 완료: %d개", len(suggestions))
    return suggestions


def save_suggestions(suggestions: list[ParamSuggestion]) -> int:
    """제안 목록을 DB에 status='pending'으로 저장.

    DB 연결: DATABASE_URL 또는 AIRFLOW_CONN_KIWOOM_DB 환경변수.
    자동 적용하지 않음 — 사용자가 /strategy/suggestions/{id}/approve로 승인해야 한다.

    Args:
        suggestions: 저장할 ParamSuggestion 목록.

    Returns:
        저장된 행 수.
    """
    if not suggestions:
        logger.info("저장할 제안 없음")
        return 0

    conn_uri = os.environ.get("AIRFLOW_CONN_KIWOOM_DB") or os.environ.get("DATABASE_URL")
    if not conn_uri:
        logger.warning("DB 연결 정보 미설정 — 제안 저장 스킵")
        return 0

    import psycopg2

    # 스키마 정규화
    conn_uri = conn_uri.replace("postgresql+psycopg2://", "postgresql://")
    conn_uri = conn_uri.replace("postgres+psycopg2://", "postgresql://")
    conn_uri = conn_uri.replace("postgres://", "postgresql://")

    saved = 0
    try:
        conn = psycopg2.connect(conn_uri)
        try:
            with conn.cursor() as cur:
                for s in suggestions:
                    import json

                    cur.execute(
                        """
                        INSERT INTO strategy_config_suggestions
                            (config_key, current_value, suggested_value,
                             reason, source, status, created_at, updated_at)
                        VALUES (%s, %s::jsonb, %s::jsonb, %s, %s, 'pending', NOW(), NOW())
                        """,
                        (
                            s.key,
                            json.dumps(s.current_value, default=str),
                            json.dumps(s.suggested_value, default=str),
                            s.reason,
                            s.source,
                        ),
                    )
                    saved += 1
            conn.commit()
            logger.info("제안 %d개 DB 저장 완료 (status=pending)", saved)
        finally:
            conn.close()
    except Exception as exc:
        logger.error("제안 DB 저장 실패: %s", exc)
        saved = 0

    return saved
