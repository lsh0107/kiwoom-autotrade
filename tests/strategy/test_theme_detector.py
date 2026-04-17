"""ThemeDetector 테마 감지 테스트."""

from __future__ import annotations

import pytest

from src.strategy.theme_detector import ThemeDetector

# 테스트 공통 픽스처
_THEME_SCORES: dict[str, float] = {
    "반도체": 0.9,
    "AI": 0.8,
    "2차전지": 0.5,
    "바이오": 0.3,
}

_SECTOR_MAP: dict[str, list[str]] = {
    "반도체": ["005930", "000660", "009150"],
    "AI": ["035420", "377300"],
    "2차전지": ["051910", "006400"],
    "바이오": ["068270", "207940"],
}


class TestGetHotThemes:
    """get_hot_themes() 메서드 테스트."""

    def test_returns_themes_above_threshold(self) -> None:
        """기본 임계값(0.6) 이상 테마만 반환."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        hot = detector.get_hot_themes()
        assert "반도체" in hot  # 0.9
        assert "AI" in hot  # 0.8
        assert "2차전지" not in hot  # 0.5
        assert "바이오" not in hot  # 0.3

    def test_sorted_by_score_descending(self) -> None:
        """점수 높은 순으로 정렬."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        hot = detector.get_hot_themes()
        assert hot[0] == "반도체"  # 0.9
        assert hot[1] == "AI"  # 0.8

    def test_custom_threshold(self) -> None:
        """커스텀 임계값 적용."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        # threshold=0.4 → 반도체(0.9), AI(0.8), 2차전지(0.5) 포함
        hot = detector.get_hot_themes(threshold=0.4)
        assert len(hot) == 3
        assert "2차전지" in hot
        assert "바이오" not in hot

    def test_threshold_1_0_returns_empty(self) -> None:
        """임계값 1.0 → 아무것도 없으면 빈 리스트."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        hot = detector.get_hot_themes(threshold=1.0)
        assert hot == []

    def test_threshold_0_returns_all(self) -> None:
        """임계값 0.0 → 전체 반환."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        hot = detector.get_hot_themes(threshold=0.0)
        assert len(hot) == len(_THEME_SCORES)

    def test_empty_theme_scores(self) -> None:
        """테마 점수 없으면 빈 리스트."""
        detector = ThemeDetector({}, _SECTOR_MAP)
        assert detector.get_hot_themes() == []

    def test_exact_threshold_boundary_included(self) -> None:
        """정확히 임계값과 같으면 포함(>=)."""
        detector = ThemeDetector({"테마A": 0.6}, {"테마A": ["005930"]})
        hot = detector.get_hot_themes(threshold=0.6)
        assert "테마A" in hot


class TestGetThemeScore:
    """get_theme_score() 메서드 테스트."""

    def test_known_symbol_returns_max_theme_score(self) -> None:
        """알려진 종목 → 소속 테마 점수 반환."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        # 005930은 반도체(0.9) 소속
        assert detector.get_theme_score("005930") == pytest.approx(0.9)

    def test_another_known_symbol(self) -> None:
        """다른 알려진 종목 → 해당 테마 점수."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        # 035420은 AI(0.8) 소속
        assert detector.get_theme_score("035420") == pytest.approx(0.8)

    def test_unknown_symbol_returns_zero(self) -> None:
        """미분류 종목 → 0.0 반환."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        assert detector.get_theme_score("999999") == pytest.approx(0.0)

    def test_symbol_in_multiple_themes_returns_max(self) -> None:
        """여러 테마에 속한 종목 → 최고 점수 반환."""
        # 동일 종목이 두 테마에 속하는 케이스
        scores = {"테마A": 0.7, "테마B": 0.9}
        sector = {
            "테마A": ["005930"],
            "테마B": ["005930"],
        }
        detector = ThemeDetector(scores, sector)
        assert detector.get_theme_score("005930") == pytest.approx(0.9)

    def test_symbol_theme_not_in_scores_returns_zero(self) -> None:
        """sector_map에는 있지만 theme_scores에 없는 테마 → 0.0 반환."""
        scores = {"반도체": 0.9}  # AI 점수 없음
        sector = {"AI": ["035420"]}
        detector = ThemeDetector(scores, sector)
        assert detector.get_theme_score("035420") == pytest.approx(0.0)

    def test_empty_sector_map_returns_zero(self) -> None:
        """sector_map 없으면 0.0 반환."""
        detector = ThemeDetector(_THEME_SCORES, {})
        assert detector.get_theme_score("005930") == pytest.approx(0.0)


class TestGetThemeSymbols:
    """get_theme_symbols() 메서드 테스트."""

    def test_known_theme_returns_symbols(self) -> None:
        """존재하는 테마 → 종목 목록 반환."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        symbols = detector.get_theme_symbols("반도체")
        assert "005930" in symbols
        assert "000660" in symbols
        assert "009150" in symbols

    def test_unknown_theme_returns_empty(self) -> None:
        """존재하지 않는 테마 → 빈 리스트 반환."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        assert detector.get_theme_symbols("없는테마") == []

    def test_returns_copy_not_reference(self) -> None:
        """반환된 리스트를 수정해도 내부 상태가 변하지 않는다."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        symbols = detector.get_theme_symbols("반도체")
        original_len = len(symbols)
        symbols.append("999999")
        # 다시 조회해도 원본 유지
        assert len(detector.get_theme_symbols("반도체")) == original_len

    def test_empty_sector_map_returns_empty(self) -> None:
        """sector_map 없으면 빈 리스트 반환."""
        detector = ThemeDetector(_THEME_SCORES, {})
        assert detector.get_theme_symbols("반도체") == []


class TestThemeDetectorSymbolIndex:
    """_build_symbol_index() 역인덱스 생성 테스트."""

    def test_symbol_index_built_on_init(self) -> None:
        """초기화 시 역인덱스가 생성된다."""
        detector = ThemeDetector(_THEME_SCORES, _SECTOR_MAP)
        # 005930은 반도체 소속
        assert "반도체" in detector._symbol_to_themes["005930"]

    def test_symbol_in_multiple_themes_all_listed(self) -> None:
        """여러 테마에 속한 종목은 역인덱스에 모두 기록된다."""
        scores = {"테마A": 0.7, "테마B": 0.5}
        sector = {"테마A": ["X"], "테마B": ["X"]}
        detector = ThemeDetector(scores, sector)
        themes = detector._symbol_to_themes["X"]
        assert "테마A" in themes
        assert "테마B" in themes
