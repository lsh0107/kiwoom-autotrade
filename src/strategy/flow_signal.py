"""수급 기반 시그널 모듈."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# 시장 수급 점수 가중치: 한국 시장은 외국인 수급이 주도적
_FOREIGN_WEIGHT: float = 0.6
_INSTITUTION_WEIGHT: float = 0.4

# 종목별 외국인 대량 매수 임계값 (원 단위, 5억)
_STOCK_FOREIGN_LARGE_THRESHOLD: float = 500_000_000


class FlowSignal:
    """수급 기반 시그널 계산기.

    외국인/기관 순매수 데이터를 바탕으로 시장 전체 및 종목별 수급 압력 점수를
    계산한다. Strategy Protocol과 별개의 독립 인터페이스로 동작한다.

    Attributes:
        DEFAULT_THRESHOLD: is_bullish() 기본 임계값
    """

    DEFAULT_THRESHOLD: float = 0.2

    def __init__(
        self,
        market_flow: dict,
        stock_flows: dict | None = None,
    ) -> None:
        """FlowSignal 초기화.

        Args:
            market_flow: 시장 전체 수급 데이터.
                예: {"foreign": 1_000_000, "institution": 500_000, "individual": -1_500_000}
                단위: 원. 양수 = 순매수, 음수 = 순매도.
            stock_flows: 종목별 수급 데이터 (선택).
                예: {"005930": {"foreign": 300_000_000, "institution": 100_000_000}}
        """
        self._market_flow = market_flow
        self._stock_flows = stock_flows or {}

    def score(self, symbol: str | None = None) -> float:
        """수급 압력 점수를 계산한다.

        시장 전체 수급 점수를 기반으로, symbol이 주어지면 종목별 보너스를 합산한다.

        Args:
            symbol: 종목코드. None이면 시장 전체 수급만 반영.

        Returns:
            수급 압력 점수. -1.0(강한 매도압력) ~ 1.0(강한 매수압력).
        """
        base = self._market_score()

        if symbol and symbol in self._stock_flows:
            bonus = self._stock_bonus(symbol)
            return max(-1.0, min(1.0, base + bonus))

        return base

    def is_bullish(
        self,
        symbol: str | None = None,
        threshold: float = 0.2,
    ) -> bool:
        """수급 매수 압력 여부를 반환한다.

        Args:
            symbol: 종목코드. None이면 시장 전체 수급 기준.
            threshold: 매수 판단 최소 점수 (기본 0.2).

        Returns:
            True이면 수급 매수 압력 우세.
        """
        return self.score(symbol) > threshold

    def get_top_flow_symbols(self, n: int = 10) -> list[str]:
        """외국인+기관 합산 순매수 상위 종목을 반환한다.

        Args:
            n: 반환할 종목 수 (기본 10).

        Returns:
            외국인+기관 합산 순매수 상위 N개 종목코드 (내림차순 정렬).
        """
        if not self._stock_flows:
            return []

        def _combined(flows: dict) -> float:
            """외국인+기관 합산 순매수."""
            return float(flows.get("foreign", 0)) + float(flows.get("institution", 0))

        ranked = sorted(
            self._stock_flows.items(),
            key=lambda kv: _combined(kv[1]),
            reverse=True,
        )
        return [symbol for symbol, _ in ranked[:n]]

    # ── 내부 계산 ──────────────────────────────────────────

    def _market_score(self) -> float:
        """시장 전체 수급 점수를 계산한다.

        외국인/기관 순매수 방향(+/-)에 가중치를 적용하여 -1.0 ~ 1.0 점수 반환.
        외국인 60%, 기관 40% 가중치 적용.

        Returns:
            시장 수급 점수 (-1.0 ~ 1.0).
        """
        foreign = float(self._market_flow.get("foreign", 0))
        institution = float(self._market_flow.get("institution", 0))

        def _sign(val: float) -> float:
            if val > 0:
                return 1.0
            if val < 0:
                return -1.0
            return 0.0

        raw = _sign(foreign) * _FOREIGN_WEIGHT + _sign(institution) * _INSTITUTION_WEIGHT
        return max(-1.0, min(1.0, raw))

    def _stock_bonus(self, symbol: str) -> float:
        """종목별 외국인 순매수 보너스 점수를 계산한다.

        외국인 대량 매수(5억 이상) → +0.2, 일반 매수 → +0.1, 매도 → -0.1.

        Args:
            symbol: 종목코드.

        Returns:
            보너스 점수 (-0.1 ~ 0.2).
        """
        flows = self._stock_flows.get(symbol, {})
        foreign = float(flows.get("foreign", 0))

        if foreign >= _STOCK_FOREIGN_LARGE_THRESHOLD:
            return 0.2
        if foreign > 0:
            return 0.1
        if foreign < 0:
            return -0.1
        return 0.0
