#!/bin/bash
# 모멘텀 돌파 전략 자동 실행 (cron용)
#
# 1. 종목 스크리닝 (52주 신고가 근처 + 거래량 급증)
# 2. 백테스트 실행 (백그라운드)
# 3. 모의투자 자동매매 실행 (포그라운드, 15:35 자동 종료)
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

# 0. 공휴일 체크
if ! python3 scripts/korean_holidays.py --check-today >> "$LOG_FILE" 2>&1; then
    echo "[SKIP] 공휴일 — 실행 중단" >> "$LOG_FILE"
    echo "=== cron_backtest.sh 종료 (공휴일): $(date) ===" >> "$LOG_FILE"
    exit 0
fi

# 1. 종목 스크리닝
echo "[1/3] 종목 스크리닝..." >> "$LOG_FILE"
poetry run python scripts/screen_symbols.py --threshold 0.75 --volume-ratio 0.8 >> "$LOG_FILE" 2>&1
SCREEN_EXIT=$?

if [ $SCREEN_EXIT -ne 0 ]; then
    echo "[ERROR] 스크리닝 실패" >> "$LOG_FILE"
    exit 1
fi

# 스크리닝 후 쿨다운 (레이트 리밋 회복)
echo "[WAIT] 스크리닝 완료, 10초 쿨다운..." >> "$LOG_FILE"
sleep 10

# 2. 백테스트 (백그라운드 — 결과는 JSON으로 저장됨)
echo "[2/3] 백테스트 실행 (백그라운드)..." >> "$LOG_FILE"
poetry run python scripts/run_backtest.py --auto --days 3 >> "$LOG_FILE" 2>&1 &
BACKTEST_PID=$!

# 3. 모의투자 자동매매 (포그라운드 — 15:35 자동 종료)
echo "[3/3] 모의투자 자동매매 시작..." >> "$LOG_FILE"
poetry run python scripts/live_trader.py --auto >> "$LOG_FILE" 2>&1

# 백테스트 완료 대기
wait $BACKTEST_PID 2>/dev/null

echo "=== cron_backtest.sh 완료: $(date) ===" >> "$LOG_FILE"
