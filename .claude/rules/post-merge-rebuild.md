# 머지 후 자동 재빌드

main 머지 + 메인 worktree `claude` sync 직후 변경 경로 기반으로 **backend/frontend 컨테이너만** 재빌드한다. airflow 는 자동 대상에서 제외한다.

## 트리거

- main 머지 → 메인 worktree (`kiwoom-autotrade/`) 에서 `claude` ← `origin/main` merge + push 완료 시.
- **dev 머지만 한 경우 트리거 안 함** — 라이브 컨테이너는 main 기준.

## 도구

`scripts/post_merge_rebuild.sh` 가 단일 진입점.

```bash
bash scripts/post_merge_rebuild.sh                # HEAD~1..HEAD (기본)
bash scripts/post_merge_rebuild.sh REF_BEFORE     # REF_BEFORE..HEAD
bash scripts/post_merge_rebuild.sh REF_BEFORE REF_AFTER
DRY_RUN=1 bash scripts/post_merge_rebuild.sh      # 변경 감지 + 계획만 출력
```

## 경로 → 서비스 매핑

| 변경 경로 | 재빌드 대상 |
|---|---|
| `frontend/*` | `frontend` 컨테이너 |
| `src/*`, `scripts/*`, `alembic/*`, `pyproject.toml`, `uv.lock`, `Dockerfile.backend` | `backend` 컨테이너 |
| `airflow/*` | 감지만 (자동 재빌드 X) |
| `alembic/versions/*` | 추가 경고 (마이그레이션 자동 적용 금지) |

변경 없는 서비스는 손대지 않는다.

## 절차 (Claude 표준)

1. main 머지 직후 메인 worktree 에서:
   ```bash
   cd /Users/sanghyuklee/individual/stock/kiwoom-autotrade
   git checkout claude
   git fetch origin main
   git merge origin/main
   git push origin claude   # env 토큰 사용
   ```
2. `bash scripts/post_merge_rebuild.sh` 실행.
3. 마이그레이션 감지되면 자동 적용 금지 — 사용자 확인 후 수동 실행.
4. HTTP probe 로 라이브 응답 확인 (백엔드 `/api/v1/...`, 프론트 `/decisions` 등 변경 경로에 맞춰 1회).

## 정책

- airflow: 컨테이너 다수 + 재시작 비용 큼 → 자동 대상 제외. 사용자가 명시적으로 요청할 때만 처리.
- alembic 마이그레이션: 데이터 영향 → 자동 적용 금지. 항상 사용자 승인.
- 빌드 시 env (`POSTGRES_PASSWORD` 등) 누락 시 스크립트가 기본값 주입 — 운영 시크릿이 아니라 compose 인터폴레이션 용도.

## 회피하지 말 것

- 변경 경로가 명백히 frontend 만이라도 backend 까지 같이 재빌드 — 불필요한 다운타임 발생. 스크립트가 자동 감지하므로 수동 override 금지.
- pre-existing 변경(예: 이전 머지 잔존 diff) 와 섞이지 않도록 항상 정확한 REF 범위로 호출.
