"""테마 감지 모듈."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class ThemeDetector:
    """LLM 테마 점수 기반 종목 테마 강도 감지기.

    LLM이 생성한 테마별 점수와 섹터 맵을 활용하여 종목의 테마 강도를
    계산하고 활성 테마를 감지한다. Strategy Protocol과 별개의 독립 인터페이스.
    """

    def __init__(
        self,
        theme_scores: dict[str, float],
        sector_map: dict[str, list[str]],
    ) -> None:
        """ThemeDetector 초기화.

        Args:
            theme_scores: 테마별 점수 (예: {"반도체": 0.8, "2차전지": 0.6}).
                점수 범위: 0.0 (냉각) ~ 1.0 (핫).
            sector_map: 테마별 종목 목록 (예: {"반도체": ["005930", "000660"]}).
                screen_symbols.SECTOR_MAP의 역변환(symbol→sector → sector→[symbols]) 형태.
        """
        self._theme_scores = theme_scores
        self._sector_map = sector_map
        # 역인덱스: symbol → [테마, ...] (get_theme_score 성능 최적화)
        self._symbol_to_themes: dict[str, list[str]] = self._build_symbol_index()

    def get_hot_themes(self, threshold: float = 0.6) -> list[str]:
        """활성 테마 목록을 반환한다.

        Args:
            threshold: 활성 테마 판단 최소 점수 (기본 0.6).

        Returns:
            임계값 이상 테마 목록 (점수 내림차순 정렬).
        """
        hot = [theme for theme, score in self._theme_scores.items() if score >= threshold]
        return sorted(hot, key=lambda t: self._theme_scores[t], reverse=True)

    def get_theme_score(self, symbol: str) -> float:
        """종목의 테마 강도를 반환한다.

        종목이 속한 모든 테마의 점수 중 최댓값을 반환한다.
        테마 미분류 또는 테마 점수 미존재 시 0.0 반환.

        Args:
            symbol: 종목코드.

        Returns:
            테마 강도 (0.0 ~ 1.0). 테마 미분류 종목은 0.0.
        """
        themes = self._symbol_to_themes.get(symbol, [])
        if not themes:
            return 0.0

        return max(self._theme_scores.get(theme, 0.0) for theme in themes)

    def get_theme_symbols(self, theme: str) -> list[str]:
        """특정 테마에 속하는 종목 목록을 반환한다.

        Args:
            theme: 테마명 (예: "반도체").

        Returns:
            해당 테마의 종목코드 목록. 테마 미존재 시 빈 리스트.
        """
        return list(self._sector_map.get(theme, []))

    # ── 내부 유틸 ──────────────────────────────────────────

    def _build_symbol_index(self) -> dict[str, list[str]]:
        """섹터 맵에서 symbol → themes 역인덱스를 생성한다.

        Returns:
            종목코드를 키로, 소속 테마 목록을 값으로 가지는 딕셔너리.
        """
        index: dict[str, list[str]] = {}
        for theme, symbols in self._sector_map.items():
            for symbol in symbols:
                index.setdefault(symbol, []).append(theme)
        return index
