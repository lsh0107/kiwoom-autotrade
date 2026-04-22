"""SECTOR_MAP / THEME_ALIAS 커버리지 및 정규화 테스트."""

from __future__ import annotations

import pytest

from scripts.screen_symbols import (
    CANONICAL_SECTORS,
    SECTOR_MAP,
    THEME_ALIAS,
    UNIVERSE,
    canonicalize_theme,
    get_sector,
)


class TestSectorMapCoverage:
    """SECTOR_MAP이 UNIVERSE 전체를 커버하는지 검증."""

    def test_all_universe_symbols_mapped(self) -> None:
        """UNIVERSE 140종목 전체가 SECTOR_MAP에 존재."""
        missing = [sym for sym in UNIVERSE if sym not in SECTOR_MAP]
        assert missing == [], f"미매핑 종목: {missing}"

    def test_sector_map_values_in_canonical(self) -> None:
        """SECTOR_MAP의 모든 값이 CANONICAL_SECTORS에 속함."""
        for sym, sector in SECTOR_MAP.items():
            assert sector in CANONICAL_SECTORS, (
                f"{sym}의 섹터 '{sector}'가 CANONICAL_SECTORS에 없음"
            )

    def test_get_sector_returns_canonical(self) -> None:
        """get_sector는 UNIVERSE 종목에 대해 canonical 섹터 반환."""
        for sym in UNIVERSE:
            sector = get_sector(sym)
            assert sector in CANONICAL_SECTORS, f"{sym} → '{sector}' non-canonical"


class TestCanonicalizeTheme:
    """canonicalize_theme 동작 검증."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("반도체", "반도체"),  # 이미 canonical
            ("기술주", "반도체"),
            ("IT", "IT플랫폼"),
            ("환율", "금융"),
            ("배터리", "2차전지"),
            ("의료기기", "제약"),
            ("화장품", "소비재"),
            ("로봇", "AI로봇"),
            ("수소", "에너지"),
            ("리츠", "금융"),
        ],
    )
    def test_alias_maps_to_canonical(self, raw: str, expected: str) -> None:
        assert canonicalize_theme(raw) == expected

    def test_unknown_theme_passthrough(self) -> None:
        """매핑 없는 테마는 원본 그대로 반환."""
        assert canonicalize_theme("우주항공") == "우주항공"

    def test_all_alias_values_in_canonical(self) -> None:
        """THEME_ALIAS의 모든 값이 CANONICAL_SECTORS에 속함."""
        for alias, target in THEME_ALIAS.items():
            assert target in CANONICAL_SECTORS, (
                f"alias '{alias}' → '{target}'가 CANONICAL_SECTORS에 없음"
            )
