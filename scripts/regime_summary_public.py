"""regime daily dry-run public-safe 요약 생성 (PR daily-routine).

R3 regime report + R4 allocation dry-run 의 **private 산출물**(실계좌 금융정보 포함)
에서 **공개 가능한 요약만** 추출한다. public repo(docs/observation)에 커밋해도
안전하도록 금융정보(현금/보유평가/종목별 평가액/notional/allowed_cash 등)는
**일절 포함하지 않는다**.

설계 원칙:
    - **allowlist 방식**: 안전 필드만 명시적으로 복사한다. account/holdings/allowed_cash
      같은 금융 필드는 애초에 읽지 않는다 (blocklist 누락 위험 회피).
    - budget_pct(비율), enabled(bool), regime label/confidence/flags, action 카운트,
      DB delta(0), strategy_runtime 변경 여부 등 **비민감 메타데이터만**.
    - 순수 함수. 파일/DB/네트워크 접근 없음.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# 요약에 절대 들어가면 안 되는 금융 필드 (테스트 가드용 — 누출 검출).
FINANCIAL_KEYS_BLOCKLIST: frozenset[str] = frozenset(
    {
        "available_cash",
        "holdings_eval_total",
        "total_equity",
        "pr2a_allowed_cash",
        "diagnostic_total_equity_budget",
        "max_order_amount",
        "suggested_notional_krw",
        "eval_amount",
        "holdings",
        "account",
        "available",
    }
)


def build_public_summary(
    *,
    date: str,
    regime_report: dict[str, Any],
    allocation: dict[str, Any],
    db_verify: dict[str, Any],
) -> dict[str, Any]:
    """private R3/R4 산출물 → public-safe 요약 (금융정보 제외).

    Args:
        date: YYYY-MM-DD.
        regime_report: R3 ``build_regime_report`` 출력.
        allocation: R4 ``build_allocation_dryrun`` 출력.
        db_verify: 실행 전후 검증값
            {orders_delta, trade_logs_delta, llm_decisions_delta,
             strategy_runtime_changed(bool), idle_in_transaction,
             broker_order_calls, decisions_posts}.

    Returns:
        public-safe 요약 dict (금융 수치 없음).
    """
    cur = regime_report.get("current_regime") or {}
    od = regime_report.get("overlay_dryrun", {})

    # sleeves: enabled + budget_pct(비율) + regime 권장만 (allowed_cash 등 KRW 제외)
    sleeves_public: list[dict[str, Any]] = []
    for s in allocation.get("sleeves", []):
        sleeves_public.append(
            {
                "strategy": s.get("strategy"),
                "enabled": bool(s.get("enabled", False)),
                "budget_pct": s.get("budget_pct"),  # 비율 (비민감)
                "regime_recommendation": s.get("regime_recommendation", ""),
            }
        )

    return {
        "date": date,
        "regime": {
            "label": cur.get("regime"),
            "confidence": cur.get("confidence"),
            "flags": list(cur.get("flags", [])),
        },
        "timeline_summary": regime_report.get("timeline_summary", {}),
        "proposals": {
            "count": od.get("proposal_count"),
            "action_changed_count": od.get("action_changed_count", 0),
            "boost_sell_auto_consumed": 0,  # 정책상 항상 0 (validator 수용 != 자동소비)
            "boost_sell_created_count": od.get("boost_sell_created_count", 0),
        },
        "sleeves_public": sleeves_public,
        "activation_blockers": allocation.get("activation_blockers", []),
        "safety": {
            "orders_delta": db_verify.get("orders_delta", 0),
            "trade_logs_delta": db_verify.get("trade_logs_delta", 0),
            "llm_decisions_delta": db_verify.get("llm_decisions_delta", 0),
            "strategy_runtime_changed": bool(db_verify.get("strategy_runtime_changed", False)),
            "idle_in_transaction": db_verify.get("idle_in_transaction", 0),
            "broker_order_calls": db_verify.get("broker_order_calls", 0),
            "decisions_posts": db_verify.get("decisions_posts", 0),
        },
    }


def assert_no_financials(summary: dict[str, Any]) -> None:
    """요약에 금융 필드가 없는지 재귀 검증 (누출 가드). 위반 시 ValueError."""

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in FINANCIAL_KEYS_BLOCKLIST:
                    raise ValueError(f"public summary 에 금융 필드 누출: {k}")
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(summary)


def to_markdown(summary: dict[str, Any]) -> str:
    """public-safe 요약 → markdown (docs/observation 커밋용)."""
    r = summary["regime"]
    p = summary["proposals"]
    s = summary["safety"]
    lines: list[str] = []
    lines.append(f"# Regime daily dry-run summary — {summary['date']}")
    lines.append("")
    lines.append("> public-safe 요약 (실계좌 금융정보 미포함). read-only dry-run, 거래 0.")
    lines.append("")
    lines.append(f"- **regime**: `{r['label']}` (confidence {r['confidence']})")
    if r["flags"]:
        lines.append(f"- flags: {', '.join(r['flags'])}")
    lines.append(f"- timeline 요약: {summary.get('timeline_summary', {})}")
    lines.append("")
    lines.append("## proposal overlay")
    lines.append("")
    lines.append(
        f"- proposal {p['count']}건 · action 변경 **{p['action_changed_count']}** "
        f"· boost_sell 자동소비 **{p['boost_sell_auto_consumed']}** "
        f"· boost_sell 신규생성 **{p['boost_sell_created_count']}**"
    )
    lines.append("")
    lines.append("## sleeves (enabled / budget_pct 비율만)")
    lines.append("")
    lines.append("| 전략 | enabled | budget_pct | regime 권장 |")
    lines.append("|---|---|---|---|")
    for sl in summary["sleeves_public"]:
        lines.append(
            f"| {sl['strategy']} | {sl['enabled']} | {sl['budget_pct']} "
            f"| {sl['regime_recommendation']} |"
        )
    lines.append("")
    lines.append("## 안전 (전후 검증)")
    lines.append("")
    lines.append(
        f"- orders Δ {s['orders_delta']} · trade_logs Δ {s['trade_logs_delta']} "
        f"· llm_decisions Δ {s['llm_decisions_delta']}"
    )
    lines.append(
        f"- strategy_runtime 변경 {s['strategy_runtime_changed']} "
        f"· idle in tx {s['idle_in_transaction']} "
        f"· broker order {s['broker_order_calls']} · decision POST {s['decisions_posts']}"
    )
    if summary.get("activation_blockers"):
        lines.append("")
        lines.append("## 활성화 blocker")
        lines.append("")
        for b in summary["activation_blockers"]:
            lines.append(f"- {b}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """private R3/R4 산출물 + db_verify JSON → public-safe 요약 md/json 생성."""
    parser = argparse.ArgumentParser(
        description="regime daily dry-run public-safe 요약 생성 (금융정보 제외)"
    )
    parser.add_argument("--date", required=True)
    parser.add_argument("--regime-report", required=True, help="R3 regime_report.json 경로")
    parser.add_argument("--allocation", required=True, help="R4 allocation_dry_run.json 경로")
    parser.add_argument("--db-verify", required=True, help="db_verify JSON 경로")
    parser.add_argument("--out-md", required=True, help="public summary md 출력 경로")
    parser.add_argument("--out-json", default=None, help="public summary json 출력 경로(옵션)")
    args = parser.parse_args(argv)

    regime_report = json.loads(Path(args.regime_report).read_text(encoding="utf-8"))
    allocation = json.loads(Path(args.allocation).read_text(encoding="utf-8"))
    db_verify = json.loads(Path(args.db_verify).read_text(encoding="utf-8"))

    summary = build_public_summary(
        date=args.date,
        regime_report=regime_report,
        allocation=allocation,
        db_verify=db_verify,
    )
    # 금융정보 누출 가드 — 위반 시 예외로 중단 (커밋 전 차단)
    assert_no_financials(summary)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(to_markdown(summary), encoding="utf-8")
    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
