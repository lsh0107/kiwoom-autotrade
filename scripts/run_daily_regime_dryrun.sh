#!/usr/bin/env bash
# regime daily dry-run 루틴 (6/15 본 관찰 전까지 매일 실행).
#
# 이미 만든 R3(regime report) + R4(allocation dry-run) 을 실제 데이터로 돌려
# 매일 regime/전략 판단을 갱신한다. **거래 0 / DB write 0 / decision POST 0 /
# broker order 0.** 산출물은 2계층:
#   - private(실계좌 금융정보 포함): outputs/regime/<DATE>/*  → .gitignore (커밋 금지)
#   - public-safe 요약: docs/observation/<DATE>-regime-dryrun-summary.md → 커밋 가능
#
# 입력(lab + kiwoom read-only 로 사전 생성, 본 스크립트의 인자):
#   - R3 입력: regime timeline + proposal overlay JSON (ai-hedge-fund-lab 산출)
#   - R4 입력: regime + strategy_runtime + balance/holdings snapshot JSON
#     (입력 생성 절차는 docs/observation/regime-daily-dryrun-routine.md 참조)
#
# 사용:
#   bash scripts/run_daily_regime_dryrun.sh <DATE> <R3_INPUT_JSON> <R4_INPUT_JSON>
#   예) bash scripts/run_daily_regime_dryrun.sh 2026-06-10 \
#         outputs/regime/2026-06-10/regime_overlay_input.actual.json \
#         outputs/regime/2026-06-10/allocation_input.actual.json
set -euo pipefail

DATE="${1:?DATE (YYYY-MM-DD) 필요}"
R3_INPUT="${2:?R3 input JSON 경로 필요}"
R4_INPUT="${3:?R4 input JSON 경로 필요}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT_DIR="outputs/regime/${DATE}"          # private (gitignored)
SUMMARY_MD="docs/observation/${DATE}-regime-dryrun-summary.md"  # public-safe
PG="kiwoom-autotrade-postgres-1"

psql_one() { docker exec "$PG" psql -U kiwoom -d kiwoom_trade -tAc "$1"; }

echo "[1/6] DB before snapshot (read-only)"
B_ORD=$(psql_one "select count(*) from orders;")
B_TL=$(psql_one "select count(*) from trade_logs;")
B_LLM=$(psql_one "select count(*) from llm_decisions;")
B_EN=$(psql_one "select string_agg(strategy||':'||enabled,',' order by strategy) from strategy_runtime;")

echo "[2/6] R3 regime report (read-only)"
uv run python scripts/regime_report_dryrun.py --input "$R3_INPUT" --as-of "$DATE" --output-root outputs/regime

echo "[3/6] R4 mixed allocation dry-run (read-only)"
uv run python scripts/allocation_dryrun.py --input "$R4_INPUT" --as-of "$DATE" --output-root outputs/regime

echo "[4/6] DB after snapshot + delta 검증"
A_ORD=$(psql_one "select count(*) from orders;")
A_TL=$(psql_one "select count(*) from trade_logs;")
A_LLM=$(psql_one "select count(*) from llm_decisions;")
A_EN=$(psql_one "select string_agg(strategy||':'||enabled,',' order by strategy) from strategy_runtime;")
IDLE=$(psql_one "select count(*) from pg_stat_activity where state='idle in transaction';")

SR_CHANGED=false
[ "$B_EN" != "$A_EN" ] && SR_CHANGED=true
D_ORD=$((A_ORD-B_ORD)); D_TL=$((A_TL-B_TL)); D_LLM=$((A_LLM-B_LLM))

FAIL=0
[ "$D_ORD" -ne 0 ] && { echo "FAIL: orders delta=$D_ORD"; FAIL=1; }
[ "$D_TL" -ne 0 ] && { echo "FAIL: trade_logs delta=$D_TL"; FAIL=1; }
[ "$D_LLM" -ne 0 ] && { echo "FAIL: llm_decisions delta=$D_LLM"; FAIL=1; }
[ "$SR_CHANGED" = true ] && { echo "FAIL: strategy_runtime changed"; FAIL=1; }
[ "$IDLE" -ne 0 ] && { echo "FAIL: idle in transaction=$IDLE"; FAIL=1; }
[ "$FAIL" -ne 0 ] && { echo "안전 검증 실패 — 중단"; exit 1; }

echo "[5/6] db_verify JSON 작성 (private)"
DB_VERIFY="${OUT_DIR}/db_verify.json"
cat > "$DB_VERIFY" <<JSON
{"orders_delta": ${D_ORD}, "trade_logs_delta": ${D_TL}, "llm_decisions_delta": ${D_LLM},
 "strategy_runtime_changed": ${SR_CHANGED}, "idle_in_transaction": ${IDLE},
 "broker_order_calls": 0, "decisions_posts": 0}
JSON

echo "[6/6] public-safe 요약 생성 (금융정보 제외) → ${SUMMARY_MD}"
uv run python scripts/regime_summary_public.py \
  --date "$DATE" \
  --regime-report "${OUT_DIR}/regime_report.json" \
  --allocation "${OUT_DIR}/allocation_dry_run.json" \
  --db-verify "$DB_VERIFY" \
  --out-md "$SUMMARY_MD"

echo "완료: private=${OUT_DIR} (gitignored) / public summary=${SUMMARY_MD}"
echo "  orders Δ${D_ORD} trade_logs Δ${D_TL} llm_decisions Δ${D_LLM} strategy_runtime_changed=${SR_CHANGED} idle=${IDLE}"
echo "  → public summary 만 git add. outputs/regime/<DATE> 는 커밋하지 말 것."
