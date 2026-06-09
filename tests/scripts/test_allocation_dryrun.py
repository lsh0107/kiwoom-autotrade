"""allocation_dryrun 단위 테스트 (PR R4).

cross_momentum + short_swing mixed allocation dry-run. read-only.
enabled 변경/주문/DB write/POST 없음. PR2a allowed_cash = available_cash*budget_pct.
"""

from __future__ import annotations

import json
from decimal import Decimal

from scripts.allocation_dryrun import (
    _pr2a_allowed_cash,
    build_allocation_dryrun,
    generate_report_files,
    main,
    to_markdown,
)


def _strategies() -> list[dict]:
    return [
        {
            "strategy": "cross_momentum",
            "enabled": True,
            "budget_pct": 0.6,
            "max_order_amount": 50_000_000,
        },
        {
            "strategy": "short_swing",
            "enabled": False,
            "budget_pct": 0.3,
            "max_order_amount": 5_000_000,
        },
    ]


def _holdings() -> list[dict]:
    return [{"symbol": "005930", "eval_amount": 40_000_000}]


def _build(regime_label: str = "structural_bull", available_cash: int = 100_000_000) -> dict:
    return build_allocation_dryrun(
        as_of="2026-06-09",
        regime={"regime": regime_label, "confidence": 74},
        available_cash=available_cash,
        holdings=_holdings(),
        strategies=_strategies(),
        source="fixture",
    )


class TestPr2aAllowedCash:
    def test_matches_budget_manager_formula(self) -> None:
        """BudgetManager.allowed_cash 와 동일: int(Decimal(available) * budget_pct)."""
        assert _pr2a_allowed_cash(100_000_000, 0.6) == int(Decimal("100000000") * Decimal("0.6"))
        assert _pr2a_allowed_cash(100_000_000, 0.3) == 30_000_000
        assert _pr2a_allowed_cash(0, 0.6) == 0


class TestBuildAllocation:
    def test_sleeves_and_budget(self) -> None:
        rep = _build()
        cm = next(s for s in rep["sleeves"] if s["strategy"] == "cross_momentum")
        ss = next(s for s in rep["sleeves"] if s["strategy"] == "short_swing")
        assert cm["pr2a_allowed_cash"] == 60_000_000
        assert ss["pr2a_allowed_cash"] == 30_000_000
        # total_equity = 100M cash + 40M holdings
        assert rep["account"]["total_equity"] == 140_000_000
        # diagnostic total-equity budget (참고용)
        assert cm["diagnostic_total_equity_budget"] == 84_000_000  # 140M*0.6

    def test_short_swing_disabled_still_reported(self) -> None:
        rep = _build()
        ss = next(s for s in rep["sleeves"] if s["strategy"] == "short_swing")
        assert ss["enabled"] is False
        # disabled 여도 budget_pct/max_order 표시
        assert ss["budget_pct"] == 0.3
        assert ss["max_order_amount"] == 5_000_000

    def test_safety_block_read_only(self) -> None:
        s = _build()["safety"]
        assert s["read_only"] is True
        assert s["strategy_runtime_enabled_changed"] is False
        assert s["short_swing_enabled_forced"] is False
        assert s["db_writes"] == 0
        assert s["decisions_posts"] == 0
        assert s["orders_changed"] == 0
        assert s["trade_logs_changed"] == 0
        assert s["broker_order_calls"] == 0

    def test_activation_blockers_present(self) -> None:
        rep = _build()
        joined = " ".join(rep["activation_blockers"])
        assert "PR 2b" in joined
        assert "PR 3" in joined
        assert "boost_sell 자동 소비" in joined

    def test_regime_recommendations(self) -> None:
        for label in ("structural_bull", "bull_overheat", "volatile_bull", "risk_off", "neutral"):
            rep = _build(regime_label=label)
            for s in rep["sleeves"]:
                assert s["regime_recommendation"], f"{label} {s['strategy']} 권장 없음"

    def test_risk_off_recommendation_restrictive(self) -> None:
        rep = _build(regime_label="risk_off")
        ss = next(s for s in rep["sleeves"] if s["strategy"] == "short_swing")
        assert "review_sell" in ss["regime_recommendation"]


class TestMarkdownAndFiles:
    def test_markdown_renders(self) -> None:
        md = to_markdown(_build())
        assert "Mixed Allocation Dry-run" in md
        assert "read-only" in md
        assert "cross_momentum" in md

    def test_generate_files(self, tmp_path) -> None:
        json_path, md_path = generate_report_files(_build(), tmp_path)
        assert json_path.exists() and md_path.exists()
        assert json_path.name == "allocation_dry_run.json"

    def test_main_no_side_effects(self, tmp_path) -> None:
        inp = tmp_path / "in.json"
        inp.write_text(
            json.dumps(
                {
                    "as_of": "2026-06-09",
                    "source": "fixture",
                    "regime": {"regime": "structural_bull", "confidence": 74},
                    "available_cash": 100_000_000,
                    "holdings": _holdings(),
                    "strategies": _strategies(),
                }
            ),
            encoding="utf-8",
        )
        out_root = tmp_path / "outputs" / "regime"
        rc = main(["--input", str(inp), "--output-root", str(out_root)])
        assert rc == 0
        assert (out_root / "2026-06-09" / "allocation_dry_run.json").exists()
        assert (out_root / "2026-06-09" / "allocation_dry_run.md").exists()
