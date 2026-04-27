"""크로스-섹션 모멘텀 전략 (Jegadeesh-Titman 1993 기반).

12-1 month cross-sectional momentum:
  - 신호: 형성 12개월, skip 1개월 수익률 (단기 반전 회피)
  - 필터1: 변동성 하위 50% (Low-vol anomaly, Hsu 2013)
  - 필터2: 200일 이평 위 (Trend filter, Moskowitz 2012)
  - 포지션: 상위 데실 (~10-20종목), equal weight, monthly rebalance
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.broker.schemas import DailyPrice

# 월 거래일 수 추정값
_TRADING_DAYS_PER_MONTH: int = 21


@dataclass
class CrossMomentumParams:
    """크로스-섹션 모멘텀 전략 파라미터."""

    formation_months: int = 12  # 모멘텀 형성 기간 (월)
    skip_months: int = 1  # 최근 skip 기간 (월) — 단기 반전 회피
    vol_window: int = 252  # 변동성 계산 윈도우 (거래일)
    vol_percentile: float = 50.0  # 변동성 하위 필터 기준 (%)
    trend_window: int = 200  # 추세 이평선 기간 (거래일)
    top_decile: float = 0.1  # 상위 데실 비율 (0.1 = 상위 10%)
    use_vol_filter: bool = True  # Low-vol 필터 활성화
    use_trend_filter: bool = True  # 200일 MA 추세 필터 활성화
    slippage_pct: float = 0.0015  # ADR-015 슬리피지 비율
    commission_rate: float = 0.00015  # 매매 수수료율
    tax_rate: float = 0.0023  # 거래세율 (매도 시만 적용)

    @property
    def formation_days(self) -> int:
        """형성 기간 거래일 수 (formation_months x 21)."""
        return self.formation_months * _TRADING_DAYS_PER_MONTH

    @property
    def skip_days(self) -> int:
        """skip 기간 거래일 수 (skip_months x 21)."""
        return self.skip_months * _TRADING_DAYS_PER_MONTH

    @property
    def min_history_days(self) -> int:
        """점수 계산에 필요한 최소 이력 거래일 수 (여유분 10일 포함)."""
        return self.formation_days + self.skip_days + 10

    def label(self) -> str:
        """파라미터 요약 레이블 (로그/파일명용).

        Returns:
            str: 예) "top10%_vol_trend"
        """
        vol = "vol" if self.use_vol_filter else "novol"
        trend = "trend" if self.use_trend_filter else "notrend"
        return f"top{int(self.top_decile * 100)}pct_{vol}_{trend}"

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용 딕셔너리 변환.

        Returns:
            dict: 파라미터 딕셔너리
        """
        return {
            "formation_months": self.formation_months,
            "skip_months": self.skip_months,
            "vol_window": self.vol_window,
            "vol_percentile": self.vol_percentile,
            "trend_window": self.trend_window,
            "top_decile": self.top_decile,
            "use_vol_filter": self.use_vol_filter,
            "use_trend_filter": self.use_trend_filter,
            "slippage_pct": self.slippage_pct,
            "commission_rate": self.commission_rate,
            "tax_rate": self.tax_rate,
        }


def compute_momentum_score(
    daily: list[DailyPrice],
    params: CrossMomentumParams,
) -> float | None:
    """12-1 month cross-sectional momentum score 계산.

    look-ahead 방지: daily는 신호 기준일 T0까지의 데이터만 포함해야 한다.
    score = close[T0 - skip_days] / close[T0 - skip_days - formation_days] - 1

    Args:
        daily: 일봉 데이터 (날짜 오름차순, T0 이전 + T0 포함)
        params: 전략 파라미터

    Returns:
        float | None: 모멘텀 점수 (수익률). 데이터 부족 시 None.
    """
    n = len(daily)
    required = params.formation_days + params.skip_days + 1
    if n < required:
        return None

    # formation_end: skip 기간 이전 마지막 바 (T0 - skip_days)
    end_idx = n - params.skip_days - 1
    start_idx = end_idx - params.formation_days

    if start_idx < 0:
        return None

    price_start = daily[start_idx].close
    price_end = daily[end_idx].close

    if price_start <= 0:
        return None

    return (price_end / price_start) - 1.0


def apply_vol_filter(
    universe_data: dict[str, list[DailyPrice]],
    params: CrossMomentumParams,
) -> set[str]:
    """변동성 하위 vol_percentile% 종목 집합 반환.

    일간 수익률 표준편차 기준으로 종목 순위 산정.
    하위 50%면 저변동성 half만 통과 (Low-vol anomaly 적용).

    look-ahead 방지: universe_data의 각 daily는 T0까지만 포함해야 한다.

    Args:
        universe_data: 종목별 일봉 데이터 (T0까지 슬라이스 후 전달)
        params: 전략 파라미터

    Returns:
        set[str]: 저변동성 필터 통과 종목 코드 집합
    """
    vols: dict[str, float] = {}

    for symbol, daily in universe_data.items():
        if len(daily) < params.vol_window + 1:
            continue

        prices = [d.close for d in daily[-params.vol_window :]]
        returns: list[float] = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

        if len(returns) < 20:
            continue

        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        vols[symbol] = math.sqrt(variance)

    if not vols:
        return set()

    sorted_vols = sorted(vols.items(), key=lambda x: x[1])
    n_pass = max(1, int(len(sorted_vols) * params.vol_percentile / 100))
    return {s for s, _ in sorted_vols[:n_pass]}


def apply_trend_filter(
    universe_data: dict[str, list[DailyPrice]],
    params: CrossMomentumParams,
) -> set[str]:
    """200일 이평 위 종목 집합 반환.

    현재 종가 > trend_window일 단순이평이면 통과.
    Moskowitz (2012) time-series trend filter 적용.

    look-ahead 방지: universe_data의 각 daily는 T0까지만 포함해야 한다.

    Args:
        universe_data: 종목별 일봉 데이터 (T0까지 슬라이스 후 전달)
        params: 전략 파라미터

    Returns:
        set[str]: 추세 필터 통과 종목 코드 집합
    """
    passing: set[str] = set()

    for symbol, daily in universe_data.items():
        if len(daily) < params.trend_window + 1:
            continue

        recent = daily[-params.trend_window :]
        ma = sum(d.close for d in recent) / params.trend_window
        current_close = daily[-1].close

        if current_close > ma:
            passing.add(symbol)

    return passing


def select_portfolio(
    candidates: list[str],
    momentum_scores: dict[str, float],
    params: CrossMomentumParams,
) -> list[str]:
    """상위 데실 종목 선택 (모멘텀 점수 내림차순).

    Args:
        candidates: 필터 통과 후 후보 종목 리스트
        momentum_scores: 종목별 모멘텀 점수 딕셔너리
        params: 전략 파라미터

    Returns:
        list[str]: 선택된 포트폴리오 종목 (모멘텀 내림차순, 최소 1개)
    """
    scored = [(s, momentum_scores[s]) for s in candidates if s in momentum_scores]
    scored.sort(key=lambda x: x[1], reverse=True)

    n_select = max(1, int(len(scored) * params.top_decile))
    return [s for s, _ in scored[:n_select]]
