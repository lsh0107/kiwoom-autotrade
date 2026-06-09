"""cross_momentum + short_swing mixed allocation dry-run (PR R4).

cross_momentum 과 short_swing 을 **동시에 운영할 경우** 예산/상태/regime 이 어떻게
나오는지 read-only 로 시뮬레이션한다. "어느 전략 하나만" 이 아니라 **섞을 때** 의
sleeve 배분/권장을 즉시 본다.

엄격한 read-only 계약:
    - 실제 ``strategy_runtime.enabled`` 변경 **금지** (short_swing enabled=true 금지).
    - 주문 / DB write / decision POST **금지**. broker order 호출 **금지**.
    - 입력은 JSON 계약 (regime + strategy_runtime 설정 snapshot + balance/holdings
      read-only snapshot). 본 스크립트는 DB 세션/httpx 미생성 — 보고서 파일 생성만.

예산 계산:
    - PR 2a 기준: ``allowed_cash = int(Decimal(available_cash) * budget_pct)``
      (``BudgetManager.allowed_cash`` 와 동일). 이것이 현재 실제 사이징 기준.
    - total-equity budget (= total_equity * budget_pct) 은 **PR 2b 전이라 diagnostic
      only** — 표시만 하고 실제 사이징에 쓰지 않는다.

입력 JSON 계약:
    {
      "as_of": "2026-06-09",
      "source": "...",
      "regime": {"regime": "structural_bull", "confidence": 74},
      "available_cash": 100000000,
      "holdings": [{"symbol": "005930", "eval_amount": 40000000}, ...],
      "strategies": [
        {"strategy": "cross_momentum", "enabled": true,  "budget_pct": 0.6,
         "max_order_amount": 50000000},
        {"strategy": "short_swing",   "enabled": false, "budget_pct": 0.3,
         "max_order_amount": 5000000}
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("allocation_dryrun")

# regime 별 sleeve 권장 (정성, 주문 영향 없음).
_SLEEVE_RECOMMENDATION: dict[str, dict[str, str]] = {
    "structural_bull": {
        "cross_momentum": "core 유지",
        "short_swing": "소액 보조 가능",
    },
    "bull_overheat": {
        "cross_momentum": "유지 (추격 자제)",
        "short_swing": "신규 축소/보수",
    },
    "volatile_bull": {
        "cross_momentum": "유지",
        "short_swing": "가능하나 size clamp",
    },
    "risk_off": {
        "cross_momentum": "신규매수 제한 (보존)",
        "short_swing": "신규매수 제한, review_sell evidence 만",
    },
    "neutral": {
        "cross_momentum": "현 상태 유지",
        "short_swing": "현 상태 유지",
    },
}

# 실제 동시 매매 활성화 전 해소해야 할 blocker (현재 미구현).
_ACTIVATION_BLOCKERS: list[str] = [
    "PR 2b total-equity budget 미구현 (현재 available_cash*budget_pct 현금 기준만)",
    "PR 3 ownership / sell authority 미구현 (전략별 보유/청산 권한 분리 안 됨)",
    "boost_sell 자동 소비 미개방 (validator 는 수용하지만 자동 매도/주문 연결 금지)",
]


def _pr2a_allowed_cash(available_cash: int, budget_pct: float) -> int:
    """PR 2a 기준 allowed cash (BudgetManager.allowed_cash 와 동일 계산)."""
    return int(Decimal(str(available_cash)) * Decimal(str(budget_pct)))


def build_allocation_dryrun(
    *,
    as_of: str,
    regime: dict[str, Any],
    available_cash: int,
    holdings: list[dict[str, Any]],
    strategies: list[dict[str, Any]],
    source: str = "",
) -> dict[str, Any]:
    """mixed allocation dry-run 보고서 dict (read-only, 주문/DB/POST 없음)."""
    total_held = sum(int(h.get("eval_amount", 0)) for h in holdings)
    total_equity = available_cash + total_held
    regime_label = regime.get("regime", "neutral")
    rec = _SLEEVE_RECOMMENDATION.get(regime_label, _SLEEVE_RECOMMENDATION["neutral"])

    sleeves: list[dict[str, Any]] = []
    for s in strategies:
        name = s["strategy"]
        budget_pct = float(s.get("budget_pct", 0.0))
        sleeves.append(
            {
                "strategy": name,
                "enabled": bool(s.get("enabled", False)),
                "budget_pct": budget_pct,
                "max_order_amount": int(s.get("max_order_amount", 0)),
                # 현재 실제 사이징 기준 (PR 2a)
                "pr2a_allowed_cash": _pr2a_allowed_cash(available_cash, budget_pct),
                # 참고용 — PR 2b 전이라 미적용
                "diagnostic_total_equity_budget": int(
                    Decimal(str(total_equity)) * Decimal(str(budget_pct))
                ),
                "regime_recommendation": rec.get(name, ""),
            }
        )

    return {
        "as_of": as_of,
        "source": source,
        "current_regime": regime,
        "account": {
            "available_cash": available_cash,
            "holdings_eval_total": total_held,
            "total_equity": total_equity,
        },
        "sleeves": sleeves,
        "budget_basis": {
            "active": "pr2a_available_cash_times_budget_pct",
            "diagnostic_only": "total_equity_times_budget_pct (PR 2b 전 미적용)",
        },
        "activation_blockers": _ACTIVATION_BLOCKERS,
        "safety": {
            "read_only": True,
            "strategy_runtime_enabled_changed": False,
            "short_swing_enabled_forced": False,
            "db_writes": 0,
            "decisions_posts": 0,
            "orders_changed": 0,
            "trade_logs_changed": 0,
            "broker_order_calls": 0,
        },
    }


def to_markdown(report: dict[str, Any]) -> str:
    cur = report.get("current_regime") or {}
    acc = report["account"]
    lines: list[str] = []
    lines.append(f"# Mixed Allocation Dry-run (read-only) — {report['as_of']}")
    lines.append("")
    lines.append(
        f"> source: `{report.get('source', '')}` · **read-only** "
        "(enabled 변경 0 / 주문 0 / DB write 0 / POST 0 / broker order 0)"
    )
    lines.append("")
    lines.append(
        f"## 현재 regime: **{cur.get('regime', 'n/a')}** "
        f"(confidence {cur.get('confidence', 'n/a')})"
    )
    lines.append("")
    lines.append("## 계좌 (read-only snapshot)")
    lines.append("")
    lines.append(f"- available_cash: {acc['available_cash']:,}")
    lines.append(f"- holdings 평가액: {acc['holdings_eval_total']:,}")
    lines.append(f"- total_equity: {acc['total_equity']:,}")
    lines.append("")
    lines.append("## Sleeve 배분 (cross_momentum + short_swing 동시 가정)")
    lines.append("")
    lines.append(
        "| 전략 | enabled | budget_pct | max_order | PR2a allowed_cash | "
        "total-equity(diag) | regime 권장 |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for s in report["sleeves"]:
        lines.append(
            f"| {s['strategy']} | {s['enabled']} | {s['budget_pct']} "
            f"| {s['max_order_amount']:,} | {s['pr2a_allowed_cash']:,} "
            f"| {s['diagnostic_total_equity_budget']:,} | {s['regime_recommendation']} |"
        )
    lines.append("")
    lines.append("> PR2a allowed_cash = 현재 실제 사이징 기준 (available_cash x budget_pct).")
    lines.append("> total-equity(diag) 는 PR 2b 전이라 **참고용 (미적용)**.")
    lines.append("")
    lines.append("## 실제 동시 매매 활성화 전 blocker")
    lines.append("")
    for b in report["activation_blockers"]:
        lines.append(f"- {b}")
    lines.append("")
    lines.append("> 본 보고서는 dry-run. short_swing enabled=true 전환/주문 없음.")
    lines.append("")
    return "\n".join(lines)


def generate_report_files(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    out_dir = output_root / report["as_of"]
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "allocation_dry_run.json"
    md_path = out_dir / "allocation_dry_run.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="cross_momentum + short_swing mixed allocation dry-run (read-only)"
    )
    parser.add_argument("--input", required=True, help="regime + 설정 + 계좌 snapshot JSON")
    parser.add_argument("--output-root", default="outputs/regime", help="출력 루트")
    parser.add_argument("--as-of", default=None, help="기준일 (기본 입력 JSON 값)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    as_of = args.as_of or payload.get("as_of") or ""
    if not as_of:
        raise SystemExit("as_of 필요 (--as-of 또는 입력 JSON 의 as_of)")
    report = build_allocation_dryrun(
        as_of=as_of,
        regime=payload.get("regime", {}),
        available_cash=int(payload.get("available_cash", 0)),
        holdings=payload.get("holdings", []),
        strategies=payload.get("strategies", []),
        source=payload.get("source", ""),
    )
    json_path, md_path = generate_report_files(report, Path(args.output_root))
    log.info("allocation dry-run 생성: %s / %s", json_path, md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
