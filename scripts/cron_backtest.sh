#!/bin/bash
# 모멘텀 돌파 전략 자동 백테스트 (cron용)
#
# 1. 종목 스크리닝 (52주 신고가 근처 + 거래량 급증)
# 2. 스크리닝 통과 종목 백테스트 실행
#
# cron: 5 9 * * 1-5 (월~금 09:05)

set -euo pipefail

cd "$(dirname "$0")/.."

# cron 환경에서 .env 로드
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

LOG_DIR="docs/backtest-results"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cron_$(date +%Y%m%d).log"

echo "=== cron_backtest.sh 시작: $(date) ===" >> "$LOG_FILE"

# 1. 종목 스크리닝
echo "[1/2] 종목 스크리닝..." >> "$LOG_FILE"
poetry run python scripts/screen_symbols.py --threshold 0.90 --volume-ratio 1.2 >> "$LOG_FILE" 2>&1
SCREEN_EXIT=$?

if [ $SCREEN_EXIT -ne 0 ]; then
    echo "[ERROR] 스크리닝 실패" >> "$LOG_FILE"
    exit 1
fi

# 2. 백테스트 실행 (--auto: 스크리닝 결과 자동 로드)
echo "[2/2] 백테스트 실행..." >> "$LOG_FILE"
poetry run python scripts/run_backtest.py --auto --days 5 >> "$LOG_FILE" 2>&1

echo "=== cron_backtest.sh 완료: $(date) ===" >> "$LOG_FILE"
