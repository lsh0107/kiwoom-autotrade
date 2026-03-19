#!/bin/bash
# Claude Code PreToolUse Hook: 보안 파일 쓰기 및 시크릿 감지
# Write/Edit/Bash/Read/NotebookEdit 도구 실행 전 자동 호출
#
# 새 Hook API (2026):
#   입력: stdin JSON { tool_name, tool_input: {...}, ... }
#   차단: stderr 메시지 + exit 2
#   허용: exit 0

INPUT=$(cat)

# tool_name을 JSON stdin에서 추출
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")

# ── Write/Edit/NotebookEdit 도구: 파일 + 내용 검사 ─────────
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "NotebookEdit" ]]; then
  FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin).get('tool_input', {})
print(d.get('file_path', d.get('notebook_path', '')))
" 2>/dev/null || echo "")

  # 1) 보안 파일 직접 쓰기 차단 (.env, .env.*, .pem, .key 등)
  BASENAME=$(basename "$FILE_PATH" 2>/dev/null || echo "")
  if echo "$BASENAME" | grep -qiE '^\.env($|\.)'; then
    echo "보안 파일 직접 쓰기 차단: $FILE_PATH. 사용자가 직접 편집해야 합니다." >&2
    exit 2
  fi
  if echo "$BASENAME" | grep -qiE '\.(pem|key|secret|p12|pfx|jks|crt|cer)$'; then
    echo "보안 파일 직접 쓰기 차단: $FILE_PATH" >&2
    exit 2
  fi

  # 2) 파일 내용에서 시크릿 패턴 감지
  CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin).get('tool_input', {})
print(d.get('content', d.get('new_string', d.get('new_source', ''))))
" 2>/dev/null || echo "")

  if [ -n "$CONTENT" ]; then
    DETECTED=$(echo "$CONTENT" | python3 -c "
import sys, re

text = sys.stdin.read()
patterns = [
    # AWS
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
    # OpenAI
    (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI/Stripe Secret Key'),
    # GitHub
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Personal Token'),
    (r'github_pat_[a-zA-Z0-9_]{82}', 'GitHub Fine-grained Token'),
    (r'gh[ops]_[a-zA-Z0-9]{36}', 'GitHub OAuth/App Token'),
    # SSH/RSA Private Key
    (r'-----BEGIN\s+(RSA\s+|EC\s+)?PRIVATE\s+KEY', 'Private Key'),
    # Slack
    (r'xox[bpsa]-[a-zA-Z0-9-]+', 'Slack Token'),
    # Google
    (r'AIza[0-9A-Za-z_-]{35}', 'Google API Key'),
    # Telegram Bot Token
    (r'[0-9]+:AA[0-9A-Za-z_-]{33}', 'Telegram Bot Token'),
    # DB Connection String
    (r'(?:postgres|mysql|mongodb)(?:ql)?://[^\\s\"]+:[^\\s\"]+@', 'DB Connection String'),
    # JWT Token (하드코딩)
    (r'eyJ[a-zA-Z0-9_-]*\\.eyJ[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*', 'JWT Token'),
    # 하드코딩된 API 키/시크릿 (변수 대입)
    (r'(?:app_?(?:key|secret)|api_?(?:key|secret|token)|password|passwd|secret_?key)\s*[=:]\s*[\"\\'][^\"\\'\\s]{8,}', 'Hardcoded Secret'),
    # Bearer 토큰 하드코딩
    (r'[\"\\']Bearer\s+[a-zA-Z0-9._-]{20,}[\"\\']', 'Hardcoded Bearer Token'),
    # Base64로 보이는 긴 시크릿 대입
    (r'(?:KEY|SECRET|TOKEN|PASSWORD)\s*=\s*[\"\\'][A-Za-z0-9+/=_-]{20,}[\"\\']', 'Hardcoded Credential'),
]

for pattern, name in patterns:
    if re.search(pattern, text, re.IGNORECASE):
        print(name)
        sys.exit(0)

sys.exit(1)
" 2>/dev/null) || true

    if [ -n "$DETECTED" ]; then
      echo "시크릿 패턴 감지 ($DETECTED). 환경변수(.env)를 사용하세요." >&2
      exit 2
    fi
  fi
fi

# ── Bash 도구: 위험 명령 감지 ──────────────────────────────
if [[ "$TOOL_NAME" == "Bash" ]]; then
  COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

  # .env 파일 읽기/접근 시도 차단
  # 1) 파일을 인자로 받는 모든 명령 + .env 조합
  # 2) 리다이렉션으로 읽기 (< .env)
  # 3) source / . (dot) 실행
  if echo "$COMMAND" | grep -qiE '\b(cat|head|tail|less|more|vi|vim|nano|code|sed|awk|grep|egrep|fgrep|rg|ripgrep|strings|xxd|hexdump|cut|wc|tr|od|sort|uniq|python[23]?|python|ruby|node|perl|bat|open|source)\b[^|&;]*\.env\b' || \
     echo "$COMMAND" | grep -qiE '<\s*\.env\b' || \
     echo "$COMMAND" | grep -qiE '(^|;|&&|\|\|)\s*\.\s+\.env\b'; then
    echo ".env 파일 직접 접근 차단. 보안 파일은 사용자가 직접 관리합니다." >&2
    exit 2
  fi
fi

# ── Read 도구: .env 읽기 차단 ──────────────────────────────
if [[ "$TOOL_NAME" == "Read" ]]; then
  FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")
  BASENAME=$(basename "$FILE_PATH" 2>/dev/null || echo "")

  if echo "$BASENAME" | grep -qiE '^\.env($|\.)'; then
    echo ".env 파일 읽기 차단: $FILE_PATH" >&2
    exit 2
  fi
fi

exit 0
