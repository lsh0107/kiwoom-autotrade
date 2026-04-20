"""FlowSignal 수급 시그널 테스트."""

from __future__ import annotations

import pytest

from src.strategy.flow_signal import FlowSignal


class TestFlowSignalScore:
    """score() 메서드 테스트."""

    @pytest.mark.parametrize(
        ("market_flow", "expected"),
        [
            # 외국인+기관 모두 순매수 → 최대 1.0
            ({"foreign": 1_000_000, "institution": 500_000}, 1.0),
            # 외국인+기관 모두 순매도 → 최소 -1.0
            ({"foreign": -1_000_000, "institution": -500_000}, -1.0),
            # 외국인만 순매수 → 0.6 (외국인 가중치)
            ({"foreign": 1_000_000, "institution": 0}, 0.6),
            # 기관만 순매수 → 0.4 (기관 가중치)
            ({"foreign": 0, "institution": 500_000}, 0.4),
            # 모두 0 → 0.0
            ({"foreign": 0, "institution": 0, "individual": 0}, 0.0),
            # 빈 dict → 0.0
            ({}, 0.0),
            # 외국인 매수 + 기관 매도 → 0.6 - 0.4 = 0.2
            ({"foreign": 1_000_000, "institution": -500_000}, 0.2),
        ],
    )
    def test_market_score_reflects_foreign_and_institution_direction(
        self, market_flow: dict, expected: float
    ) -> None:
        """시장 수급 점수는 외국인(가중치 0.6)과 기관(0.4)의 매수/매도 방향 합산."""
        assert FlowSignal(market_flow).score() == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("market_flow", "stock_flow", "expected"),
        [
            # 시장 1.0 + 종목 대량매수 +0.2 → 1.0으로 clamp
            (
                {"foreign": 1_000_000, "institution": 500_000},
                {"foreign": 600_000_000},
                1.0,
            ),
            # 시장 0.6 + 종목 일반매수 +0.1 → 0.7
            (
                {"foreign": 500_000, "institution": 0},
                {"foreign": 100_000_000},
                0.7,
            ),
            # 시장 0.6 + 종목 매도 -0.1 → 0.5
            (
                {"foreign": 500_000, "institution": 0},
                {"foreign": -100_000_000},
                0.5,
            ),
        ],
    )
    def test_symbol_bonus_applied_on_top_of_market_score(
        self, market_flow: dict, stock_flow: dict, expected: float
    ) -> None:
        """종목별 외국인 순매수/매도에 따라 ±보너스가 시장 점수에 합산된다."""
        fs = FlowSignal(market_flow=market_flow, stock_flows={"005930": stock_flow})
        assert fs.score("005930") == pytest.approx(expected)

    def test_symbol_not_in_stock_flows_uses_market_only(self) -> None:
        """stock_flows에 없는 종목 → 시장 수급 점수만 반환."""
        fs = FlowSignal(
            market_flow={"foreign": 500_000, "institution": 0},
            stock_flows={"000660": {"foreign": 200_000_000}},
        )
        # 005930은 stock_flows에 없으므로 시장 점수 0.6만 반환
        assert fs.score("005930") == pytest.approx(0.6)

    @pytest.mark.parametrize(
        ("market_flow", "stock_flow", "lower", "upper"),
        [
            # 극단적 매수: 1.0 상한 유지
            (
                {"foreign": 1_000_000, "institution": 500_000},
                {"foreign": 1_000_000_000},
                -1.0,
                1.0,
            ),
            # 극단적 매도: -1.0 하한 유지
            (
                {"foreign": -1_000_000, "institution": -500_000},
                {"foreign": -1_000_000_000},
                -1.0,
                1.0,
            ),
        ],
    )
    def test_score_stays_within_bounds(
        self, market_flow: dict, stock_flow: dict, lower: float, upper: float
    ) -> None:
        """수급 점수는 항상 [-1.0, 1.0] 범위를 벗어나지 않는다."""
        fs = FlowSignal(market_flow=market_flow, stock_flows={"005930": stock_flow})
        score = fs.score("005930")
        assert lower <= score <= upper


class TestFlowSignalIsBullish:
    """is_bullish() 메서드 테스트."""

    def test_bullish_when_score_above_default_threshold(self) -> None:
        """점수가 기본 임계값(0.2) 초과 시 True."""
        fs = FlowSignal({"foreign": 500_000, "institution": 0})
        assert fs.is_bullish() is True

    def test_not_bullish_when_score_at_threshold(self) -> None:
        """점수가 임계값과 정확히 같으면 False (strictly greater than)."""
        fs = FlowSignal({"foreign": 500_000, "institution": -500_000})
        # score = 0.6 - 0.4 = 0.2, threshold = 0.2 → score > threshold 불만족
        assert fs.is_bullish() is False

    def test_not_bullish_when_score_below_threshold(self) -> None:
        """점수가 임계값 미만 시 False."""
        fs = FlowSignal({"foreign": -500_000, "institution": 500_000})
        # score = -0.6 + 0.4 = -0.2 → False
        assert fs.is_bullish() is False

    def test_bullish_with_custom_threshold(self) -> None:
        """커스텀 임계값 적용."""
        fs = FlowSignal({"foreign": 0, "institution": 500_000})
        # score = 0.4, threshold=0.5 → False
        assert fs.is_bullish(threshold=0.5) is False
        # threshold=0.3 → True
        assert fs.is_bullish(threshold=0.3) is True

    def test_bullish_with_symbol(self) -> None:
        """종목별 수급 포함 매수 압력 확인."""
        fs = FlowSignal(
            market_flow={"foreign": 0, "institution": 500_000},
            stock_flows={"005930": {"foreign": 1_000_000_000}},
        )
        # 시장 0.4 + 종목 대량매수 0.2 = 0.6 > 0.2
        assert fs.is_bullish("005930") is True


class TestFlowSignalTopSymbols:
    """get_top_flow_symbols() 메서드 테스트."""

    def test_sorted_by_combined_flow(self) -> None:
        """외국인+기관 합산 순매수 기준 내림차순 정렬."""
        fs = FlowSignal(
            market_flow={},
            stock_flows={
                "000660": {"foreign": 100_000_000, "institution": 50_000_000},
                "005930": {"foreign": 500_000_000, "institution": 200_000_000},
                "035420": {"foreign": 200_000_000, "institution": 100_000_000},
            },
        )
        result = fs.get_top_flow_symbols(n=3)
        assert result[0] == "005930"  # 700M 1위
        assert result[1] == "035420"  # 300M 2위
        assert result[2] == "000660"  # 150M 3위

    def test_empty_stock_flows_returns_empty(self) -> None:
        """stock_flows 없으면 빈 리스트 반환."""
        fs = FlowSignal({"foreign": 500_000})
        assert fs.get_top_flow_symbols() == []

    def test_n_limit_honored(self) -> None:
        """n개 제한이 적용된다."""
        fs = FlowSignal(
            market_flow={},
            stock_flows={
                "A": {"foreign": 300_000_000},
                "B": {"foreign": 200_000_000},
                "C": {"foreign": 100_000_000},
            },
        )
        result = fs.get_top_flow_symbols(n=2)
        assert len(result) == 2
        assert "A" in result
        assert "B" in result

    def test_n_larger_than_symbols_returns_all(self) -> None:
        """n이 종목 수보다 크면 전체 반환."""
        fs = FlowSignal(
            market_flow={},
            stock_flows={
                "A": {"foreign": 100_000_000},
                "B": {"foreign": 50_000_000},
            },
        )
        result = fs.get_top_flow_symbols(n=10)
        assert len(result) == 2

    def test_negative_flow_symbol_sorted_last(self) -> None:
        """순매도 종목은 순매수 종목보다 후순위."""
        fs = FlowSignal(
            market_flow={},
            stock_flows={
                "SELL": {"foreign": -500_000_000, "institution": -200_000_000},
                "BUY": {"foreign": 100_000_000, "institution": 50_000_000},
            },
        )
        result = fs.get_top_flow_symbols(n=2)
        assert result[0] == "BUY"
        assert result[1] == "SELL"

    def test_none_stock_flows_init(self) -> None:
        """stock_flows=None으로 초기화 시 빈 리스트 반환."""
        fs = FlowSignal({"foreign": 500_000}, stock_flows=None)
        assert fs.get_top_flow_symbols() == []
