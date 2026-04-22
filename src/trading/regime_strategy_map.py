"""시장 스타일 기반 전략 가중치 매트릭스 — Design 013 PR 6.

MarketStyle(추세방향 x 활발도) 별로 momentum/pullback/mean_reversion/range_trade 전략
가중치를 분배한다. 가중치 합이 1 미만일 경우 나머지는 현금 버퍼로 간주한다.

이 매트릭스는 StrategyBudget.apply_regime(..., style=MarketStyle)에서
리스크 레짐(pool_a/pool_b/buffer) 위에 추가 적용돼 전략별 자본 배분을 산출한다.
"""

from __future__ import annotations

from src.trading.market_style import MarketStyle

# 스타일별 전략 가중치 (합<=1.0; 부족분은 현금 보유)
REGIME_STRATEGY_WEIGHTS: dict[MarketStyle, dict[str, float]] = {
    MarketStyle.TREND_BULL_STRONG: {"momentum": 0.70, "pullback": 0.30},
    MarketStyle.TREND_BULL_QUIET: {
        "pullback": 0.50,
        "mean_reversion": 0.30,
        "momentum": 0.20,
    },
    MarketStyle.RANGE: {"range_trade": 0.60, "mean_reversion": 0.40},
    MarketStyle.TREND_BEAR: {"mean_reversion": 0.40, "momentum": 0.20},
    MarketStyle.CHOP: {"mean_reversion": 0.30},
}


def get_strategy_weights(style: MarketStyle) -> dict[str, float]:
    """스타일별 전략 가중치 사본을 반환한다.

    Args:
        style: MarketStyle

    Returns:
        전략명 -> 가중치 맵. 해당 스타일에 등록된 전략만 포함.
    """
    return dict(REGIME_STRATEGY_WEIGHTS.get(style, {}))


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """가중치 합이 1을 넘으면 1로 스케일. 합<=1이면 그대로 유지(버퍼는 호출자가 처리).

    Args:
        weights: 전략명 -> 가중치

    Returns:
        정규화된 가중치 사본
    """
    total = sum(weights.values())
    if total <= 0:
        return {}
    if total <= 1.0:
        return dict(weights)
    # total > 1이면 비례 축소
    return {k: v / total for k, v in weights.items()}
