"""모멘텀 돌파 스크리닝 순수 계산 엔진.

- 네트워크/I/O 없음. 입력: `list[DailyPrice]` + 파라미터. 출력: dict/데이터클래스.
- `scripts/screen_symbols.py`와 Airflow DAG (`postmarket/daily_screening`)에서 공유한다.
- 기존 `scripts/screen_symbols.py`의 함수 시그니처/동작을 그대로 보존 (스냅샷 회귀 방지).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.broker.schemas import DailyPrice


@dataclass(frozen=True)
class ScreeningParams:
    """스크리닝 파라미터 스냅샷.

    Attributes:
        threshold: 52주 고가 대비 최소 비율 (기본 0.75).
        volume_ratio: 평균 거래량 대비 최소 배수 (기본 0.8).
        min_stocks: 최소 통과 종목 수. 부족 시 bonus/price_ratio 상위로 보충 (기본 10).
        profile: 프로파일명 (캐시 테이블의 구분자).
    """

    threshold: float = 0.75
    volume_ratio: float = 0.8
    min_stocks: int = 10
    profile: str = "momentum_breakout"


@dataclass
class ScreeningResult:
    """스크리닝 결과 엔트리 (통과/미통과/보충 공통).

    저장 편의를 위해 선택적 필드는 기본값을 둔다.
    """

    symbol: str
    name: str
    sector: str
    hint: str
    # 기본 지표
    close: int
    high_52w: int
    volume: int
    avg_volume: int
    price_ratio: float
    vol_ratio: float
    date: str
    daily_bars: int
    # 통과 여부 + 순위
    passed: bool
    bonus_score: int = 0
    rank: int = 0
    # 보너스 세부
    prev_day_change_pct: float = 0.0
    prev_day_vol_surge: bool = False
    consecutive_bullish: int = 0
    is_52w_high: bool = False
    # 메타
    extras: dict[str, Any] = field(default_factory=dict)


# ── 보너스 조건 헬퍼 ─────────────────────────────────


def calc_prev_day_change(daily: list[DailyPrice]) -> float:
    """전일 등락률(%) 계산.

    (전일종가 - 전전일종가) / 전전일종가 * 100.
    데이터 2일 미만이면 0.0 반환.
    """
    if len(daily) < 2:
        return 0.0
    prev = daily[-1]
    prev_prev = daily[-2]
    if prev_prev.close == 0:
        return 0.0
    return (prev.close - prev_prev.close) / prev_prev.close * 100


def check_volume_surge(daily: list[DailyPrice], multiplier: float = 2.0) -> bool:
    """전일 거래량이 20일 평균의 multiplier배 이상인지."""
    if len(daily) < 20:
        return False
    recent_20 = daily[-20:]
    avg_volume = sum(d.volume for d in recent_20) / len(recent_20)
    if avg_volume == 0:
        return False
    return daily[-1].volume >= avg_volume * multiplier


def count_consecutive_bullish(daily: list[DailyPrice]) -> int:
    """최근 연속 양봉 수 (close > open)."""
    count = 0
    for d in reversed(daily):
        if d.close > d.open:
            count += 1
        else:
            break
    return count


def is_52w_new_high(daily: list[DailyPrice]) -> bool:
    """전일 종가가 52주 신고가인지."""
    if not daily:
        return False
    recent_250 = daily[-250:] if len(daily) > 250 else daily
    high_52w = max(d.high for d in recent_250)
    return daily[-1].close >= high_52w


# ── 스크리닝 단일 종목 ──────────────────────────────


def check_screen_condition(
    daily: list[DailyPrice],
    threshold: float,
    volume_ratio: float,
) -> dict[str, Any] | None:
    """52주 신고가 근처 + 거래량 조건 확인 + 보너스 점수.

    기본 조건: 52주고가 비율 >= threshold, 거래량 비율 >= volume_ratio
    보너스: 전일등락률 3%+, 전일거래량 폭증, 5일연속양봉, 52주신고가.

    Args:
        daily: 일봉 리스트 (시간순 오름차순).
        threshold: 52주 고가 대비 최소 비율.
        volume_ratio: 평균 거래량 대비 최소 배수.

    Returns:
        스크리닝 정보 dict (항상 반환). 데이터 20 bars 미만이면 None.
    """
    if len(daily) < 20:
        return None

    recent_250 = daily[-250:] if len(daily) > 250 else daily
    high_52w = max(d.high for d in recent_250)

    recent_20 = daily[-20:]
    avg_volume = sum(d.volume for d in recent_20) // len(recent_20)

    latest = daily[-1]

    price_ratio = latest.close / high_52w if high_52w > 0 else 0
    vol_ratio = latest.volume / avg_volume if avg_volume > 0 else 0

    passed = price_ratio >= threshold and vol_ratio >= volume_ratio

    bonus_score = 0
    prev_day_change_pct = calc_prev_day_change(daily)
    prev_day_vol_surge = check_volume_surge(daily)
    consecutive_bullish = count_consecutive_bullish(daily)
    new_high = is_52w_new_high(daily)

    if prev_day_change_pct >= 3.0:
        bonus_score += 1
    if prev_day_vol_surge:
        bonus_score += 1
    if consecutive_bullish >= 5:
        bonus_score += 1
    if new_high:
        bonus_score += 1

    return {
        "close": latest.close,
        "high_52w": high_52w,
        "price_ratio": round(price_ratio, 4),
        "volume": latest.volume,
        "avg_volume": avg_volume,
        "vol_ratio": round(vol_ratio, 2),
        "date": latest.date,
        "daily_bars": len(daily),
        "passed": passed,
        "bonus_score": bonus_score,
        "prev_day_change_pct": round(prev_day_change_pct, 2),
        "prev_day_vol_surge": prev_day_vol_surge,
        "consecutive_bullish": consecutive_bullish,
        "is_52w_high": new_high,
    }


# ── 순위 산정 + 최소 종목 보충 ──────────────────────


def rank_and_fill(
    candidates: list[dict[str, Any]],
    min_stocks: int,
) -> list[dict[str, Any]]:
    """통과 종목을 bonus_score + price_ratio 내림차순으로 정렬.

    통과가 min_stocks 미만이면 전체 후보에서 상위 랭킹으로 보충.

    Args:
        candidates: 모든 후보 (passed True/False 모두 포함).
        min_stocks: 최소 반환 종목 수.

    Returns:
        passed=True 인 엔트리에 rank(1부터)가 부여된 리스트 + 보충 항목.
    """
    passed = [c for c in candidates if c.get("passed")]
    passed.sort(
        key=lambda x: (x.get("bonus_score", 0), x.get("price_ratio", 0.0)),
        reverse=True,
    )

    # rank 부여
    for i, c in enumerate(passed, 1):
        c["rank"] = i

    if len(passed) < min_stocks and candidates:
        ranked = sorted(
            candidates,
            key=lambda x: (x.get("bonus_score", 0), x.get("price_ratio", 0.0)),
            reverse=True,
        )
        existing = {c["symbol"] for c in passed}
        for candidate in ranked:
            if candidate["symbol"] in existing:
                continue
            # 보충 항목도 rank 부여
            candidate = {**candidate, "rank": len(passed) + 1}
            passed.append(candidate)
            existing.add(candidate["symbol"])
            if len(passed) >= min_stocks:
                break

    return passed
