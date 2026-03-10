#!/bin/bash
# PostToolUse Hook: Python 파일 수정 후 자동 Ruff 포맷
# stdin: JSON { tool_name, tool_input: { file_path: "..." } }

INPUT=$(cat)

FILE=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin).get('tool_input', {})
print(d.get('file_path', ''))
" 2>/dev/null || echo "")

if [[ "$FILE" == *.py ]] && [ -f "$FILE" ]; then
  cd "$(dirname "${BASH_SOURCE[0]}")/../.."
  poetry run ruff check --fix "$FILE" 2>/dev/null
  poetry run ruff format "$FILE" 2>/dev/null
fi

exit 0
