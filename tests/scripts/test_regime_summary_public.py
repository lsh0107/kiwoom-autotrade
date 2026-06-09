"""regime_summary_public 단위 테스트 (daily dry-run routine).

핵심: public-safe 요약에 실계좌 금융정보가 절대 들어가지 않는지 검증.
"""

from __future__ import annotations

import pytest

from scripts.regime_summary_public import (
    FINANCIAL_KEYS_BLOCKLIST,
    assert_no_financials,
    build_public_summary,
    to_markdown,
)


def _regime_report() -> dict:
    return {
        "current_regime": {"regime": "risk_off", "confidence": 88, "flags": ["REGIME_VOL_SPIKE"]},
        "timeline_summary": {"structural_bull": 3, "risk_off": 1},
        "overlay_dryrun": {
            "proposal_count": 15,
            "action_changed_count": 0,
            "boost_sell_created_count": 0,
        },
    }


def _allocation() -> dict:
    # R4 출력엔 금융정보(account/allowed_cash 등)가 들어있다 — 요약은 이를 제외해야 한다.
    return {
        "account": {
            "available_cash": 112_020_295,
            "holdings_eval_total": 422_025_100,
            "total_equity": 534_045_395,
        },
        "sleeves": [
            {
                "strategy": "cross_momentum",
                "enabled": True,
                "budget_pct": 0.6,
                "max_order_amount": 50_000_000,
                "pr2a_allowed_cash": 67_212_177,
                "diagnostic_total_equity_budget": 320_427_237,
                "regime_recommendation": "신규매수 제한 (보존)",
            },
            {
                "strategy": "short_swing",
                "enabled": False,
                "budget_pct": 0.3,
                "max_order_amount": 5_000_000,
                "pr2a_allowed_cash": 33_606_088,
                "diagnostic_total_equity_budget": 160_213_618,
                "regime_recommendation": "신규매수 제한, review_sell evidence 만",
            },
        ],
        "activation_blockers": ["boost_sell 자동 소비 미개방 ..."],
    }


def _db_verify() -> dict:
    return {
        "orders_delta": 0,
        "trade_logs_delta": 0,
        "llm_decisions_delta": 0,
        "strategy_runtime_changed": False,
        "idle_in_transaction": 0,
        "broker_order_calls": 0,
        "decisions_posts": 0,
    }


def _summary() -> dict:
    return build_public_summary(
        date="2026-06-09",
        regime_report=_regime_report(),
        allocation=_allocation(),
        db_verify=_db_verify(),
    )


class TestPublicSummary:
    def test_regime_and_proposals(self) -> None:
        s = _summary()
        assert s["regime"]["label"] == "risk_off"
        assert s["regime"]["confidence"] == 88
        assert s["proposals"]["action_changed_count"] == 0
        assert s["proposals"]["boost_sell_auto_consumed"] == 0

    def test_sleeves_keep_ratio_only(self) -> None:
        s = _summary()
        cm = next(x for x in s["sleeves_public"] if x["strategy"] == "cross_momentum")
        assert cm["enabled"] is True
        assert cm["budget_pct"] == 0.6  # 비율은 OK
        assert "regime_recommendation" in cm
        # KRW 필드는 없어야 한다
        assert "pr2a_allowed_cash" not in cm
        assert "max_order_amount" not in cm
        assert "diagnostic_total_equity_budget" not in cm

    def test_no_account_block(self) -> None:
        s = _summary()
        assert "account" not in s
        # 전체 트리에 금융 필드 없음
        assert_no_financials(s)

    def test_assert_no_financials_detects_leak(self) -> None:
        bad = {"x": {"available_cash": 1}}
        with pytest.raises(ValueError):
            assert_no_financials(bad)

    def test_safety_block(self) -> None:
        s = _summary()["safety"]
        assert s["orders_delta"] == 0
        assert s["trade_logs_delta"] == 0
        assert s["llm_decisions_delta"] == 0
        assert s["strategy_runtime_changed"] is False
        assert s["broker_order_calls"] == 0
        assert s["decisions_posts"] == 0

    def test_markdown_has_no_real_amounts(self) -> None:
        md = to_markdown(_summary())
        # 실계좌 금액 문자열이 마크다운에 없어야 한다
        for amount in ("112,020,295", "422,025,100", "534,045,395", "67,212,177", "112020295"):
            assert amount not in md
        assert "risk_off" in md
        assert "Regime daily dry-run summary" in md

    def test_blocklist_nonempty(self) -> None:
        assert "available_cash" in FINANCIAL_KEYS_BLOCKLIST
        assert "total_equity" in FINANCIAL_KEYS_BLOCKLIST
