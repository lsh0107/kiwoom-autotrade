#!/bin/bash
# Claude Code PreToolUse Hook: 보안 파일 쓰기 및 시크릿 감지
# git commit/push 전에 자동 실행

INPUT=$(cat)
TOOL_NAME="${CLAUDE_TOOL_NAME:-}"

# Write/Edit 도구일 때: 파일 내용에 시크릿 패턴 감지
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
  FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null)

  # 보안 파일 직접 쓰기 차단
  if echo "$FILE_PATH" | grep -qE '\.(env|pem|key|secret|p12|pfx|jks)$'; then
    echo '{"decision": "block", "reason": "보안 파일 직접 쓰기 차단: '"$FILE_PATH"'"}'
    exit 2
  fi

  # 파일 내용에서 시크릿 패턴 감지
  CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('content', d.get('new_string', '')))
" 2>/dev/null)

  if echo "$CONTENT" | grep -qEi '(AKIA[0-9A-Z]{16}|sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|-----BEGIN (RSA |EC )?PRIVATE KEY|password\s*=\s*["\x27][^"\x27]{8,}|app_?secret\s*=\s*["\x27][^"\x27]+)'; then
    echo '{"decision": "block", "reason": "시크릿/API 키 패턴 감지. 환경변수(.env)를 사용하세요."}'
    exit 2
  fi
fi

# Bash 도구일 때: git push 전 보안 스캔 리마인더
if [[ "$TOOL_NAME" == "Bash" ]]; then
  COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)

  if echo "$COMMAND" | grep -qE '^git push'; then
    echo '{"message": "⚠️ git push 전 보안 체크: pre-commit run --all-files 실행을 권장합니다."}'
  fi
fi

exit 0
