"""short_swing_regime overlay 모듈 테스트 (PR B)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.trading.short_swing_regime import (
    RegimeOverlay,
    RegimeSnapshot,
    load_current_regime,
    regime_overlay_decision,
)


class TestRegimeOverlayDecision:
    """regime label → RegimeOverlay 매핑."""

    def test_none_snapshot_returns_neutral_allow(self) -> None:
        overlay = regime_overlay_decision(None)
        assert overlay.allow_new_entry is True
        assert overlay.max_new_entries_override is None
        assert "regime_unknown" in overlay.reason

    def test_risk_off_blocks_new_entry(self) -> None:
        overlay = regime_overlay_decision(RegimeSnapshot(regime="risk_off", confidence=88))
        assert overlay.allow_new_entry is False
        assert overlay.max_new_entries_override == 0
        assert overlay.reason == "regime_block_risk_off"

    def test_bull_overheat_limits_to_one(self) -> None:
        overlay = regime_overlay_decision(
            RegimeSnapshot(regime="bull_overheat", confidence=93),
        )
        assert overlay.allow_new_entry is True
        assert overlay.max_new_entries_override == 1
        assert overlay.reason == "regime_limit_bull_overheat"

    def test_volatile_bull_allows_with_no_override(self) -> None:
        overlay = regime_overlay_decision(
            RegimeSnapshot(regime="volatile_bull", confidence=70),
        )
        assert overlay.allow_new_entry is True
        assert overlay.max_new_entries_override is None
        assert overlay.reason == "regime_allow_volatile_bull"

    def test_structural_bull_allows_with_no_override(self) -> None:
        overlay = regime_overlay_decision(
            RegimeSnapshot(regime="structural_bull", confidence=80),
        )
        assert overlay.allow_new_entry is True
        assert overlay.max_new_entries_override is None

    def test_unknown_regime_defaults_allow(self) -> None:
        overlay = regime_overlay_decision(
            RegimeSnapshot(regime="some_future_label", confidence=50),
        )
        assert overlay.allow_new_entry is True
        assert overlay.max_new_entries_override is None


class TestLoadCurrentRegime:
    """outputs/regime/<DATE>/regime_report.json 로드."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        result = load_current_regime(date(2026, 6, 16), root=tmp_path)
        assert result is None

    def test_valid_file_returns_snapshot(self, tmp_path: Path) -> None:
        d = tmp_path / "2026-06-16"
        d.mkdir()
        (d / "regime_report.json").write_text(
            json.dumps(
                {
                    "as_of": "2026-06-16",
                    "current_regime": {
                        "regime": "bull_overheat",
                        "confidence": 93,
                    },
                },
            ),
            encoding="utf-8",
        )
        result = load_current_regime(date(2026, 6, 16), root=tmp_path)
        assert result is not None
        assert result.regime == "bull_overheat"
        assert result.confidence == 93

    def test_malformed_json_returns_none(self, tmp_path: Path) -> None:
        d = tmp_path / "2026-06-16"
        d.mkdir()
        (d / "regime_report.json").write_text("{ not valid json", encoding="utf-8")
        result = load_current_regime(date(2026, 6, 16), root=tmp_path)
        assert result is None

    def test_missing_current_regime_returns_none(self, tmp_path: Path) -> None:
        d = tmp_path / "2026-06-16"
        d.mkdir()
        (d / "regime_report.json").write_text(
            json.dumps({"as_of": "2026-06-16", "other": "data"}),
            encoding="utf-8",
        )
        result = load_current_regime(date(2026, 6, 16), root=tmp_path)
        assert result is None


class TestRegimeOverlayNeutral:
    """RegimeOverlay.neutral 보조 생성자."""

    def test_neutral_is_allow(self) -> None:
        n = RegimeOverlay.neutral()
        assert n.allow_new_entry is True
        assert n.max_new_entries_override is None
        assert n.regime is None
