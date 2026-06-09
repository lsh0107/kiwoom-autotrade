"""regime_report_dryrun 단위 테스트 (PR R3).

read-only 보고서 생성 검증. POST/DB write/orders/trade_logs/broker 없음.
boost_sell 은 kiwoom 미허용으로 표시만 (vocabulary alignment 안 함).
"""

from __future__ import annotations

import json

from scripts.regime_report_dryrun import (
    _KIWOOM_ALLOWED_BIAS,
    build_regime_report,
    generate_report_files,
    main,
    to_markdown,
)


def _timeline() -> list[dict]:
    return [
        {"date": "2025-12-01", "regime": "structural_bull", "confidence": 70, "flags": []},
        {"date": "2026-03-01", "regime": "bull_overheat", "confidence": 65, "flags": ["X"]},
        {"date": "2026-06-09", "regime": "structural_bull", "confidence": 75, "flags": []},
    ]


def _overlay_items() -> list[dict]:
    return [
        {
            "symbol": "005930",
            "action": "buy",
            "action_unchanged": True,
            "confidence_before": 75,
            "confidence_after": 83,
            "bias_before": "boost_buy",
            "bias_after": "boost_buy",
            "added_flags": ["REGIME_OVERLAY_STRUCTURAL_BULL_SUPPORT"],
        },
        {
            "symbol": "000660",
            "action": "sell",
            "action_unchanged": True,
            "confidence_before": 70,
            "confidence_after": 70,
            "bias_before": "review_sell",
            "bias_after": "review_sell",
            "added_flags": [],
        },
    ]


class TestBuildReport:
    def test_basic_structure(self) -> None:
        rep = build_regime_report(
            as_of="2026-06-09",
            regime_timeline=_timeline(),
            overlay_items=_overlay_items(),
            source="fixture",
        )
        assert rep["current_regime"]["regime"] == "structural_bull"
        assert rep["timeline_summary"]["structural_bull"] == 2
        assert rep["overlay_dryrun"]["action_changed_count"] == 0
        assert rep["overlay_dryrun"]["boost_sell_created_count"] == 0
        # 전략 유불리 매핑 존재
        assert "cross_momentum" in rep["strategy_outlook"]
        assert "short_swing" in rep["strategy_outlook"]

    def test_safety_block_all_zero(self) -> None:
        rep = build_regime_report(
            as_of="2026-06-09", regime_timeline=_timeline(), overlay_items=_overlay_items()
        )
        s = rep["safety"]
        assert s["read_only"] is True
        assert s["db_writes"] == 0
        assert s["decisions_posts"] == 0
        assert s["orders_changed"] == 0
        assert s["trade_logs_changed"] == 0
        assert s["broker_order_calls"] == 0

    def test_boost_sell_flagged_unsupported(self) -> None:
        # lab 이 boost_sell 을 내보낸 경우 → kiwoom 미허용으로 표시 (전송 안 함)
        items = [
            *_overlay_items(),
            {
                "symbol": "042700",
                "action": "sell",
                "action_unchanged": True,
                "confidence_before": 85,
                "confidence_after": 85,
                "bias_before": "boost_sell",
                "bias_after": "boost_sell",
                "added_flags": [],
            },
        ]
        rep = build_regime_report(
            as_of="2026-06-09", regime_timeline=_timeline(), overlay_items=items
        )
        kc = rep["kiwoom_compat"]
        assert "boost_sell" in kc["unsupported_biases"]
        assert kc["boost_sell_kiwoom_compatible"] is False
        assert "boost_sell" not in _KIWOOM_ALLOWED_BIAS

    def test_review_sell_supported(self) -> None:
        rep = build_regime_report(
            as_of="2026-06-09", regime_timeline=_timeline(), overlay_items=_overlay_items()
        )
        assert rep["kiwoom_compat"]["unsupported_biases"] == []
        assert rep["kiwoom_compat"]["boost_sell_kiwoom_compatible"] is True

    def test_action_changed_detected(self) -> None:
        items = [
            {
                "symbol": "X",
                "action": "buy",
                "action_unchanged": False,  # 계약 위반 케이스 감지
                "confidence_before": 60,
                "confidence_after": 60,
                "bias_before": "boost_buy",
                "bias_after": "boost_buy",
                "added_flags": [],
            }
        ]
        rep = build_regime_report(as_of="2026-06-09", regime_timeline=[], overlay_items=items)
        assert rep["overlay_dryrun"]["action_changed_count"] == 1


class TestMarkdown:
    def test_markdown_renders(self) -> None:
        rep = build_regime_report(
            as_of="2026-06-09", regime_timeline=_timeline(), overlay_items=_overlay_items()
        )
        md = to_markdown(rep)
        assert "Korea Regime Report" in md
        assert "read-only" in md
        assert "005930" in md


class TestFileGenerationAndMain:
    def test_generate_files(self, tmp_path) -> None:
        rep = build_regime_report(
            as_of="2026-06-09", regime_timeline=_timeline(), overlay_items=_overlay_items()
        )
        json_path, md_path = generate_report_files(rep, tmp_path)
        assert json_path.exists() and md_path.exists()
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["as_of"] == "2026-06-09"
        assert "2026-06-09" in str(json_path)

    def test_main_no_side_effects(self, tmp_path) -> None:
        # 입력 JSON → 보고서 파일만. POST/DB 없음.
        inp = tmp_path / "in.json"
        inp.write_text(
            json.dumps(
                {
                    "as_of": "2026-06-09",
                    "source": "fixture",
                    "regime_timeline": _timeline(),
                    "overlay_items": _overlay_items(),
                }
            ),
            encoding="utf-8",
        )
        out_root = tmp_path / "outputs" / "regime"
        rc = main(["--input", str(inp), "--output-root", str(out_root)])
        assert rc == 0
        assert (out_root / "2026-06-09" / "regime_report.json").exists()
        assert (out_root / "2026-06-09" / "regime_report.md").exists()
