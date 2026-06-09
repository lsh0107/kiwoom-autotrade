"""Korea regime read-only report / dry-run (PR R3).

ai-hedge-fund-lab 이 산출한 regime timeline + proposal overlay dry-run (JSON 계약)
을 받아 kiwoom-autotrade 측 **read-only 보고서**(json + md)를 생성한다.

엄격한 read-only 계약:
    - ``/api/v1/decisions/drafts`` POST **금지**.
    - ``llm_decisions`` insert/update **금지**.
    - ``orders`` / ``trade_logs`` 변경 **금지**.
    - broker order 호출 **금지**.
    - 본 스크립트는 DB 세션도, httpx 클라이언트도 생성하지 않는다. 입력 JSON →
      보고서 파일 생성만.

boost_sell 처리 (R3 범위):
    - vocabulary alignment 는 하지 않는다. lab output 에 ``boost_sell`` 이 있어도
      kiwoom validator 미허용(`src/api/v1/decisions.py:65`) 임을 보고서에 명시한다.
    - kiwoom-compatible view 에서 ``boost_sell`` 은 표시용으로만 두고
      ``unsupported_biases`` / ``boost_sell_kiwoom_compatible=false`` 로 표기한다.
    - ``review_sell`` 은 그대로 표시 가능.
    - 실제 정합은 별도 "bias vocabulary alignment" PR.

입력 JSON 계약 (lab 산출):
    {
      "source": "...",
      "regime_timeline": [
        {"date": "2025-12-01", "regime": "structural_bull", "confidence": 70,
         "flags": ["..."]}, ...   # 과거 6~12개월
      ],
      "overlay_items": [
        {"symbol": "005930", "action": "buy", "action_unchanged": true,
         "confidence_before": 75, "confidence_after": 83,
         "bias_before": "boost_buy", "bias_after": "boost_buy",
         "added_flags": ["REGIME_OVERLAY_STRUCTURAL_BULL_SUPPORT"]}, ...
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("regime_report_dryrun")

# kiwoom validator 허용 bias (src/api/v1/decisions.py:65 와 동기 유지).
# R3 는 import 대신 상수로 둔다 (API 내부 의존/무거운 import 회피, read-only 도구).
_KIWOOM_ALLOWED_BIAS: frozenset[str] = frozenset(
    {"block_buy", "boost_buy", "review_sell", "block_sell"}
)

# regime → 전략별 유불리 해석 (정성, 보고용). 주문 영향 없음.
_STRATEGY_OUTLOOK: dict[str, dict[str, str]] = {
    "structural_bull": {
        "cross_momentum": "favorable (core 추세 유지)",
        "short_swing": "favorable (모멘텀 지속)",
    },
    "bull_overheat": {
        "cross_momentum": "neutral (보유 유지, 추격 자제)",
        "short_swing": "caution (추격매수 위험)",
    },
    "volatile_bull": {
        "cross_momentum": "neutral (보유 유지)",
        "short_swing": "small-size only (변동성 확대)",
    },
    "risk_off": {
        "cross_momentum": "unfavorable (신규매수 제한, 보존)",
        "short_swing": "unfavorable (신규진입 제한, review_sell evidence)",
    },
    "neutral": {
        "cross_momentum": "neutral",
        "short_swing": "neutral",
    },
}


def build_regime_report(
    *,
    as_of: str,
    regime_timeline: list[dict[str, Any]],
    overlay_items: list[dict[str, Any]],
    source: str = "",
) -> dict[str, Any]:
    """read-only regime 보고서 dict 생성 (주문/DB/POST 없음).

    Args:
        as_of: 기준일 (YYYY-MM-DD).
        regime_timeline: 과거~현재 regime 시퀀스 (lab 산출).
        overlay_items: 현재 proposal overlay dry-run 결과 (lab 산출).
        source: 입력 출처 라벨.

    Returns:
        보고서 dict.
    """
    current = regime_timeline[-1] if regime_timeline else None
    timeline_summary = dict(Counter(e.get("regime", "unknown") for e in regime_timeline))

    action_changed = sum(1 for it in overlay_items if not it.get("action_unchanged", True))
    boost_sell_created = sum(
        1
        for it in overlay_items
        if it.get("bias_before") != "boost_sell" and it.get("bias_after") == "boost_sell"
    )

    biases_after = {it.get("bias_after") for it in overlay_items if it.get("bias_after")}
    unsupported = sorted(b for b in biases_after if b not in _KIWOOM_ALLOWED_BIAS)

    current_label = (current or {}).get("regime", "neutral")
    outlook = _STRATEGY_OUTLOOK.get(current_label, _STRATEGY_OUTLOOK["neutral"])

    return {
        "as_of": as_of,
        "source": source,
        "current_regime": current,
        "regime_timeline": regime_timeline,
        "timeline_summary": timeline_summary,
        "strategy_outlook": outlook,
        "overlay_dryrun": {
            "items": overlay_items,
            "proposal_count": len(overlay_items),
            "action_changed_count": action_changed,
            "boost_sell_created_count": boost_sell_created,
        },
        "kiwoom_compat": {
            "allowed_bias": sorted(_KIWOOM_ALLOWED_BIAS),
            "unsupported_biases": unsupported,
            "boost_sell_kiwoom_compatible": "boost_sell" not in unsupported,
            "note": (
                "lab 의 boost_sell 은 kiwoom validator(decisions.py:65) 미허용. "
                "표시용으로만 두며 decision payload 로 전송하지 않는다. "
                "vocabulary alignment 는 별도 PR."
            ),
        },
        "safety": {
            "read_only": True,
            "db_writes": 0,
            "decisions_posts": 0,
            "orders_changed": 0,
            "trade_logs_changed": 0,
            "broker_order_calls": 0,
        },
    }


def to_markdown(report: dict[str, Any]) -> str:
    """보고서 dict → 사람이 읽는 markdown."""
    cur = report.get("current_regime") or {}
    lines: list[str] = []
    lines.append(f"# Korea Regime Report (read-only) — {report['as_of']}")
    lines.append("")
    lines.append(
        f"> source: `{report.get('source', '')}` · **read-only dry-run** "
        "(POST 0 / DB write 0 / orders 0 / trade_logs 0 / broker order 0)"
    )
    lines.append("")
    lines.append("## 현재 regime")
    lines.append("")
    lines.append(f"- **{cur.get('regime', 'n/a')}** (confidence {cur.get('confidence', 'n/a')})")
    if cur.get("flags"):
        lines.append(f"- flags: {', '.join(cur['flags'])}")
    lines.append("")
    lines.append("## 전략 유불리 (정성, 주문 영향 없음)")
    lines.append("")
    for strat, note in report["strategy_outlook"].items():
        lines.append(f"- **{strat}**: {note}")
    lines.append("")
    lines.append("## 최근 regime timeline 요약")
    lines.append("")
    for regime, count in report["timeline_summary"].items():
        lines.append(f"- {regime}: {count}일")
    lines.append("")
    od = report["overlay_dryrun"]
    lines.append("## 현재 proposal overlay dry-run")
    lines.append("")
    lines.append(
        f"- proposal {od['proposal_count']}건 · action 변경 **{od['action_changed_count']}** "
        f"· boost_sell 신규생성 **{od['boost_sell_created_count']}**"
    )
    lines.append("")
    lines.append("| symbol | action | conf before→after | bias before→after | added flags |")
    lines.append("|---|---|---|---|---|")
    for it in od["items"]:
        lines.append(
            f"| {it.get('symbol')} | {it.get('action')} "
            f"| {it.get('confidence_before')}→{it.get('confidence_after')} "
            f"| {it.get('bias_before')}→{it.get('bias_after')} "
            f"| {', '.join(it.get('added_flags', []))} |"
        )
    lines.append("")
    kc = report["kiwoom_compat"]
    lines.append("## kiwoom 호환 view")
    lines.append("")
    lines.append(f"- 허용 bias: {', '.join(kc['allowed_bias'])}")
    lines.append(f"- 미허용(표시용): {', '.join(kc['unsupported_biases']) or '없음'}")
    lines.append(f"- boost_sell kiwoom 호환: **{kc['boost_sell_kiwoom_compatible']}**")
    lines.append(f"- note: {kc['note']}")
    lines.append("")
    return "\n".join(lines)


def generate_report_files(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    """outputs/regime/<as_of>/regime_report.{json,md} 작성. (파일 쓰기만)"""
    out_dir = output_root / report["as_of"]
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "regime_report.json"
    md_path = out_dir / "regime_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Korea regime read-only report / dry-run (POST/DB write 없음)"
    )
    parser.add_argument("--input", required=True, help="lab 산출 regime+overlay JSON 경로")
    parser.add_argument(
        "--output-root", default="outputs/regime", help="출력 루트 (기본 outputs/regime)"
    )
    parser.add_argument("--as-of", default=None, help="기준일 YYYY-MM-DD (기본 입력 JSON 값)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    as_of = args.as_of or payload.get("as_of") or ""
    if not as_of:
        raise SystemExit("as_of 필요 (--as-of 또는 입력 JSON 의 as_of)")
    report = build_regime_report(
        as_of=as_of,
        regime_timeline=payload.get("regime_timeline", []),
        overlay_items=payload.get("overlay_items", []),
        source=payload.get("source", ""),
    )
    json_path, md_path = generate_report_files(report, Path(args.output_root))
    log.info("regime report 생성: %s / %s", json_path, md_path)
    log.info(
        "current=%s action_changed=%s boost_sell_created=%s",
        report["current_regime"],
        report["overlay_dryrun"]["action_changed_count"],
        report["overlay_dryrun"]["boost_sell_created_count"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
