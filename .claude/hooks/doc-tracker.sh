#!/bin/bash
# Claude Code PostToolUse Hook: 문서 추적 파일 변경 시 갱신 알림
# Write/Edit 도구 사용 후 호출. 변경된 파일이 doc-registry에 추적 중인지 확인.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")

if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin).get('tool_input', {})
print(d.get('file_path', ''))
" 2>/dev/null || echo "")

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# doc-registry 자체 수정이면 스킵
if [[ "$FILE_PATH" == *"doc-registry.md" ]]; then
  exit 0
fi

# 세션 로그, 활동 로그 등 기록 문서는 스킵
if [[ "$FILE_PATH" == *"sessions/"* || "$FILE_PATH" == *"activity/"* ]]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REGISTRY="$SCRIPT_DIR/.claude/memory/doc-registry.md"

if [[ ! -f "$REGISTRY" ]]; then
  exit 0
fi

# 파일 경로에서 프로젝트 루트 제거하여 상대 경로 추출
REL_PATH="${FILE_PATH#$SCRIPT_DIR/}"

# doc-registry에 이 파일(또는 상위 디렉토리)이 추적 중인지 확인
if grep -q "$REL_PATH" "$REGISTRY" 2>/dev/null; then
  echo "{\"message\": \"[doc-tracker] $REL_PATH 는 doc-registry.md에 추적 중인 파일입니다. 변경 내용이 문서와 일치하는지 확인하고, doc-registry.md의 상태/최종검증일을 갱신하세요.\"}"
fi

exit 0
