#!/bin/bash
# Claude Code PostToolUse Hook: 모든 파일 변경 활동 기록
# Write/Edit/Bash/NotebookEdit 도구 사용 후 자동 호출
#
# 새 Hook API (2026):
#   입력: stdin JSON { tool_name, tool_input: {...}, ... }

INPUT=$(cat)

# tool_name을 JSON stdin에서 추출
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")

SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/.claude/memory/activity"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"
TIMESTAMP=$(date +"%H:%M:%S")

# 로그 디렉토리 생성
mkdir -p "$LOG_DIR"

# Write/Edit/NotebookEdit: 파일 변경 기록
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "NotebookEdit" ]]; then
  FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin).get('tool_input', {})
print(d.get('file_path', d.get('notebook_path', '')))
" 2>/dev/null || echo "unknown")
  echo "[$TIMESTAMP] $TOOL_NAME: $FILE_PATH" >> "$LOG_FILE"
fi

# Bash: 실행된 명령 기록 (민감 정보 마스킹)
if [[ "$TOOL_NAME" == "Bash" ]]; then
  COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json, re
cmd = json.load(sys.stdin).get('tool_input', {}).get('command', '')[:200]
# 민감 정보 마스킹
cmd = re.sub(r'(password|secret|key|token|bearer|authorization)[=: ]+\S+', r'\1=***REDACTED***', cmd, flags=re.IGNORECASE)
cmd = re.sub(r'(postgres|mysql|mongodb)(\+\w+)?://\S+:\S+@', r'\1://***:***@', cmd, flags=re.IGNORECASE)
print(cmd)
" 2>/dev/null || echo "unknown")
  echo "[$TIMESTAMP] Bash: $COMMAND" >> "$LOG_FILE"
fi

exit 0
