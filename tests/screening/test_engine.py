"""src/screening/engine 신규 로직 테스트.

기존 순수 함수는 `tests/scripts/test_screen_symbols.py`가 회귀 커버.
여기서는 `rank_and_fill` 동작만 추가 검증한다.
"""

from __future__ import annotations

from src.screening.engine import rank_and_fill


def _cand(
    symbol: str,
    bonus: int = 0,
    price_ratio: float = 0.9,
    *,
    passed: bool = True,
) -> dict:
    return {
        "symbol": symbol,
        "name": f"NAME_{symbol}",
        "passed": passed,
        "bonus_score": bonus,
        "price_ratio": price_ratio,
    }


class TestRankAndFill:
    """rank_and_fill — 통과 종목 정렬 + 최소 종목 보충."""

    def test_only_passed_sorted_by_bonus_then_price_ratio(self) -> None:
        candidates = [
            _cand("A", bonus=0, price_ratio=0.95),
            _cand("B", bonus=2, price_ratio=0.80),
            _cand("C", bonus=1, price_ratio=0.90),
        ]
        passed = rank_and_fill(candidates, min_stocks=0)
        assert [p["symbol"] for p in passed] == ["B", "C", "A"]
        assert [p["rank"] for p in passed] == [1, 2, 3]

    def test_fill_when_passed_less_than_min(self) -> None:
        """통과 2개 + 요구 4개 → 미통과에서 상위 2개 보충."""
        candidates = [
            _cand("A", bonus=2, price_ratio=0.90, passed=True),
            _cand("B", bonus=1, price_ratio=0.92, passed=True),
            _cand("C", bonus=0, price_ratio=0.85, passed=False),
            _cand("D", bonus=1, price_ratio=0.70, passed=False),
            _cand("E", bonus=0, price_ratio=0.60, passed=False),
        ]
        passed = rank_and_fill(candidates, min_stocks=4)
        assert len(passed) == 4
        assert [p["symbol"] for p in passed[:2]] == ["A", "B"]
        # 보충: D(bonus=1)가 C(bonus=0, price=0.85)보다 우선
        assert passed[2]["symbol"] == "D"

    def test_no_fill_needed_when_passed_enough(self) -> None:
        candidates = [
            _cand("A", bonus=1, passed=True),
            _cand("B", bonus=0, passed=True),
            _cand("C", bonus=3, passed=False),  # 추가 후보 (사용 안 됨)
        ]
        passed = rank_and_fill(candidates, min_stocks=2)
        assert {p["symbol"] for p in passed} == {"A", "B"}

    def test_empty_candidates_returns_empty(self) -> None:
        assert rank_and_fill([], min_stocks=5) == []

    def test_fill_does_not_duplicate_already_passed(self) -> None:
        """보충 루프에서 이미 통과한 종목은 건너뛴다."""
        candidates = [
            _cand("A", bonus=2, passed=True),
            _cand("B", bonus=1, passed=False),
        ]
        passed = rank_and_fill(candidates, min_stocks=3)
        # 보충해도 2개밖에 없음
        assert {p["symbol"] for p in passed} == {"A", "B"}
