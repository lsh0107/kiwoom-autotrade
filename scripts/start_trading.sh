#!/bin/bash
# 자동매매 시작 스크립트 — 장 시작 전 실행 (08:40 권장)
# 1. 스크리닝 (거래량+가격 기반 종목 선별)
# 2. live_trader --auto 실행 (장 종료까지 자동 운영)

set -e
cd "$(dirname "$0")/.."

LOG_DIR="docs/backtest-results"
mkdir -p "$LOG_DIR"
DATE=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/trading_${DATE}.log"

echo "=== 자동매매 시작: $(date) ===" | tee -a "$LOG_FILE"

# 1. 스크리닝 — 거래량 있는 종목 선별 (threshold=0.70, volume-ratio=0.5, 최소 15개)
echo "[1/2] 종목 스크리닝 시작..." | tee -a "$LOG_FILE"
uv run python scripts/screen_symbols.py \
    --threshold 0.70 \
    --volume-ratio 0.5 \
    --min-stocks 15 \
    2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"

# 2. 자동매매 실행 — WebSocket 모드, 모멘텀 전략
echo "[2/2] 자동매매 시작..." | tee -a "$LOG_FILE"
uv run python scripts/live_trader.py \
    --auto \
    --mode ws \
    --strategy momentum \
    --poll-interval 60 \
    --account-balance 10000000 \
    2>&1 | tee -a "$LOG_FILE"

echo "=== 자동매매 종료: $(date) ===" | tee -a "$LOG_FILE"
