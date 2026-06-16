#!/usr/bin/env bash
# short_swing 모의 mock run (PR B).
#
# 절차:
#   1) preflight (data freshness + DB baseline + mock 확인 + holdings 보존)
#   2) strategy_runtime: short_swing enabled=true 일시 적용 (사용자 GO 후)
#   3) live_trader --auto 시간제한 실행 (기본 30 분)
#   4) Ctrl-C graceful 종료
#   5) strategy_runtime: short_swing enabled=false 자동 복구 (trap)
#   6) 사후 검증 (orders/trade_logs delta + cross_momentum holdings 매도 0)
#
# 안전:
#   - settings.is_mock_trading=False 면 즉시 종료.
#   - data/.kill_switch 존재 시 종료.
#   - cross_momentum 보유 종목 매도 발생 시 FAIL 보고.
#
# 사용:
#   bash scripts/run_short_swing_mock.sh                    # 30 분
#   DURATION_SEC=1800 bash scripts/run_short_swing_mock.sh  # 동일
#   DRY_RUN=1 bash scripts/run_short_swing_mock.sh          # preflight + dry-run 만
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DURATION_SEC="${DURATION_SEC:-1800}"
DRY_RUN="${DRY_RUN:-0}"
PG="kiwoom-autotrade-postgres-1"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TODAY_KST="$(TZ=Asia/Seoul date +%Y-%m-%d)"
LOG_FILE="$LOG_DIR/short_swing_mock_${TODAY_KST}.log"

psql_one() { docker exec "$PG" psql -U kiwoom -d kiwoom_trade -tAc "$1"; }

# ── 0. 환경 확인 ──────────────────────────────────────────────────────────────
echo "[0/6] env 확인"
if [ -f data/.kill_switch ]; then
  echo "FAIL: data/.kill_switch 존재 → 가동 금지"
  exit 1
fi
if [ -f data/.trader.pid ]; then
  echo "WARN: data/.trader.pid 존재 (이전 세션). 사용자 확인 후 수동 정리 필요."
  exit 1
fi

# ── 1. preflight ──────────────────────────────────────────────────────────────
echo "[1/6] preflight: daily_candles freshness"
if ! uv run python scripts/preflight_data_freshness.py; then
  echo "FAIL: data freshness preflight"
  exit 1
fi

echo "[1/6] preflight: strategy_runtime baseline"
BASELINE_RT=$(psql_one "SELECT strategy || ':' || enabled FROM strategy_runtime ORDER BY strategy;")
echo "$BASELINE_RT"
SS_BEFORE=$(psql_one "SELECT enabled FROM strategy_runtime WHERE strategy='short_swing';")
if [ "$SS_BEFORE" != "f" ]; then
  echo "FAIL: short_swing 이 이미 enabled — 사용자 확인 필요"
  exit 1
fi

echo "[1/6] preflight: cross_momentum 보유 스냅샷 (사후 검증용)"
CM_HOLDINGS_BEFORE=$(psql_one "SELECT count(*) FROM short_swing_positions WHERE status='OPEN';")
B_ORD=$(psql_one "SELECT count(*) FROM orders;")
B_TL=$(psql_one "SELECT count(*) FROM trade_logs;")
B_LLM=$(psql_one "SELECT count(*) FROM llm_decisions;")
IDLE_BEFORE=$(psql_one "SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction';")
echo "  orders=$B_ORD trade_logs=$B_TL llm=$B_LLM short_swing_open=$CM_HOLDINGS_BEFORE idle_tx=$IDLE_BEFORE"

echo "[1/6] preflight: dry-run (read-only)"
if ! uv run python scripts/short_swing_dryrun.py; then
  echo "FAIL: short_swing dry-run"
  exit 1
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "DRY_RUN=1 → preflight + dry-run 만 수행, 실가동 skip."
  exit 0
fi

# ── 2. enable + trap 복구 ─────────────────────────────────────────────────────
restore_short_swing() {
  echo "[trap] short_swing enabled=false 복구"
  psql_one "UPDATE strategy_runtime SET enabled=false WHERE strategy='short_swing';" >/dev/null || true
}
trap restore_short_swing EXIT INT TERM

echo "[2/6] short_swing enabled=true 적용"
psql_one "UPDATE strategy_runtime SET enabled=true WHERE strategy='short_swing';" >/dev/null

# ── 3. live_trader 실행 (time-bounded) ────────────────────────────────────────
echo "[3/6] live_trader --auto 시작 (timeout ${DURATION_SEC}s)"
( timeout --signal=INT --kill-after=15s "${DURATION_SEC}s" \
    uv run python scripts/live_trader.py --auto 2>&1 | tee -a "$LOG_FILE" ) || true

# ── 4. 종료 후 stale PID 정리 ─────────────────────────────────────────────────
if [ -f data/.trader.pid ]; then
  PID=$(cat data/.trader.pid)
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "[4/6] stale PID 파일 정리"
    rm -f data/.trader.pid
  fi
fi

# ── 5. 사후 검증 ──────────────────────────────────────────────────────────────
echo "[5/6] post-run 검증"
A_ORD=$(psql_one "SELECT count(*) FROM orders;")
A_TL=$(psql_one "SELECT count(*) FROM trade_logs;")
A_LLM=$(psql_one "SELECT count(*) FROM llm_decisions;")
IDLE_AFTER=$(psql_one "SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction';")

D_ORD=$((A_ORD - B_ORD))
D_TL=$((A_TL - B_TL))
D_LLM=$((A_LLM - B_LLM))
echo "  Δorders=$D_ORD Δtrade_logs=$D_TL Δllm=$D_LLM idle_tx_after=$IDLE_AFTER"

# cross_momentum 보유 종목이 short_swing 신규 매도로 사라진 경우 FAIL
CM_SOLD=$(psql_one "
SELECT count(*) FROM orders
 WHERE created_at > now() - interval '1 hour'
   AND side='SELL'
   AND strategy='short_swing'
   AND symbol IN (
     SELECT DISTINCT symbol FROM short_swing_positions
      WHERE status='OPEN'
        AND created_at < now() - interval '1 day'
   );
")
if [ "$CM_SOLD" -gt 0 ]; then
  echo "FAIL: short_swing 가 24h+ 보유 short_swing 포지션 매도 ($CM_SOLD 건)"
  exit 1
fi

if [ "$D_LLM" -ne 0 ]; then
  echo "WARN: llm_decisions delta=$D_LLM (예상 0)"
fi

# ── 6. 결과 보고 ──────────────────────────────────────────────────────────────
echo "[6/6] 완료. 로그: $LOG_FILE"
echo "  → docs/observation/${TODAY_KST}-short-swing-mock-result.md 에 결과 정리 필요 (PR C)"
