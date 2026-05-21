#!/usr/bin/env bash
# main 머지 + 메인 worktree claude sync 직후 변경 경로 기반으로
# backend/frontend 컨테이너만 재빌드한다.
#
# 정책:
#   - frontend/*                                      → frontend 재빌드
#   - src/*, scripts/*, alembic/*, pyproject.toml,    → backend 재빌드
#     uv.lock, Dockerfile.backend
#   - airflow/*                                       → 감지만 (자동 재빌드 X)
#   - alembic/versions/*                              → 마이그레이션 감지 시 경고만,
#                                                       자동 적용 금지 (사용자 승인 필요)
#
# 사용:
#   bash scripts/post_merge_rebuild.sh                # 기본 HEAD~1..HEAD
#   bash scripts/post_merge_rebuild.sh REF_BEFORE     # REF_BEFORE..HEAD
#   bash scripts/post_merge_rebuild.sh REF_BEFORE REF_AFTER
#   DRY_RUN=1 bash scripts/post_merge_rebuild.sh      # 변경 감지 + 액션 계획만 출력

set -euo pipefail

REF_BEFORE="${1:-HEAD~1}"
REF_AFTER="${2:-HEAD}"
DRY_RUN="${DRY_RUN:-0}"

cd "$(git rev-parse --show-toplevel)"

# macOS 기본 bash 3.2 호환 (mapfile 미지원)
CHANGED=()
while IFS= read -r _line; do
  CHANGED+=("$_line")
done < <(git diff --name-only "$REF_BEFORE" "$REF_AFTER")

if [[ ${#CHANGED[@]} -eq 0 ]]; then
  echo "변경 파일 없음 ($REF_BEFORE..$REF_AFTER) — 재빌드 불필요."
  exit 0
fi

NEED_BACKEND=0
NEED_FRONTEND=0
NEED_AIRFLOW=0
MIGRATIONS_DETECTED=0

for f in "${CHANGED[@]}"; do
  case "$f" in
    frontend/*)
      NEED_FRONTEND=1
      ;;
    src/*|scripts/*|alembic/*|pyproject.toml|uv.lock|Dockerfile.backend)
      NEED_BACKEND=1
      ;;
    airflow/*)
      NEED_AIRFLOW=1
      ;;
  esac
  if [[ "$f" == alembic/versions/* ]]; then
    MIGRATIONS_DETECTED=1
  fi
done

echo "변경 파일 ${#CHANGED[@]}개 ($REF_BEFORE..$REF_AFTER)"
[[ $NEED_BACKEND  -eq 1 ]] && echo "  → backend 재빌드 필요"
[[ $NEED_FRONTEND -eq 1 ]] && echo "  → frontend 재빌드 필요"
[[ $NEED_AIRFLOW  -eq 1 ]] && echo "  → airflow 변경 감지 (자동 재빌드 안 함, 사용자 확인 필요)"

if [[ $MIGRATIONS_DETECTED -eq 1 ]]; then
  echo ""
  echo "[!] alembic/versions/ 신규 마이그레이션 감지."
  echo "    이 스크립트는 마이그레이션을 자동 적용하지 않는다 — 사용자 확인 후 수동 실행 필요."
  echo "    재빌드 후 'docker compose exec backend uv run alembic upgrade head' 등으로 직접 적용."
fi

if [[ $NEED_BACKEND -eq 0 && $NEED_FRONTEND -eq 0 ]]; then
  echo ""
  echo "재빌드 대상 컨테이너 없음 — 종료."
  exit 0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo ""
  echo "DRY_RUN=1 — 실제 재빌드는 건너뛴다."
  exit 0
fi

# docker compose 가 요구하는 필수 env 기본값 주입 (운영 시크릿이 아니라
# compose 인터폴레이션용 임시 값. 실제 컨테이너는 기존 값 유지.)
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-password}"
export AIRFLOW_DB_USER="${AIRFLOW_DB_USER:-airflow}"
export AIRFLOW_DB_PASSWORD="${AIRFLOW_DB_PASSWORD:-changeme}"

if [[ $NEED_BACKEND -eq 1 ]]; then
  echo ""
  echo "=== backend rebuild ==="
  docker compose build backend
  echo "=== backend recreate ==="
  docker compose up -d --no-deps backend
fi

if [[ $NEED_FRONTEND -eq 1 ]]; then
  echo ""
  echo "=== frontend rebuild ==="
  docker compose build frontend
  echo "=== frontend recreate ==="
  docker compose up -d --no-deps frontend
fi

echo ""
echo "=== 헬스 (after 6s) ==="
sleep 6
if [[ $NEED_BACKEND -eq 1 ]]; then
  docker ps --filter name=kiwoom-autotrade-backend --format "table {{.Names}}\t{{.Status}}"
fi
if [[ $NEED_FRONTEND -eq 1 ]]; then
  docker ps --filter name=kiwoom-autotrade-frontend --format "table {{.Names}}\t{{.Status}}"
fi

echo ""
echo "완료."
