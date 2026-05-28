# Escalation Policy

> 자율 결정 vs 사용자 확인 필수.

## 사용자 확인 필수 (MUST ASK)

| 액션 | 이유 |
|---|---|
| 실거래 전환 (`is_mock_trading=False`) | 자금 영향, 비가역적 |
| 주문 로직 / `live_trader` / `live_trader_*` 소비 로직 변경 | 실거래 영향 직결 |
| AI hedge live consumption 시작 (PR E2 코드 진입) | lab observation §5 미충족 시 위험만 증가 |
| broker / order / cancel / modify API 호출 추가 | 신규 외부 호출 경로 |
| `alembic upgrade` 적용 | 데이터/스키마 변경 비가역 |
| `dev → main` 머지 (코드 변경 포함) | prod 영향 직결 |
| secrets / `.env` / `settings.local.json` / 토큰 변경 | 서비스 중단 / 보안 |
| `force push`, `git rebase -i`, history rewriting | 비가역 |
| 데이터 삭제 / 대량 수정 | 비가역 |
| `gh pr merge --admin` bypass | 정책 우회 |

## 자율 결정 가능

| 액션 | 조건 |
|---|---|
| 문서 수정 / 생성 | `.claude/`, `docs/`, CLAUDE.md 등 |
| `feature/*` / `fix/*` / `docs/*` / `chore/*` 브랜치 생성 | 로컬 |
| lint / format / `uv run pytest` / `pre-commit run` | 자동 수정 or 읽기 전용 |
| read-only QA (status / logs / DB select) | write 없음 |
| mock / read-only pipeline 실행 | 기본 모의투자 + 외부 write 없음 |
| `git commit` (feature 브랜치) | 로컬 변경 |
| `git push` (feature 브랜치) | PR 대기 |
| `feat → dev` PR 생성 / 머지 | CI green + 사용자 review OK (코드) / CI green (문서) |
| `dev → main` PR **문서/CI/docs only** 머지 | CI green + diff 가 문서/설정만 |

## 리뷰 게이트

코드 변경 PR (`.py` / `.ts` / `.tsx` / `.sql` / `alembic/*` / `scripts/*.py`) 은:
1. `pre-commit run --all-files` 통과
2. PR 본문에 변경 의도 / 테스트 결과 / 안전 영향 명시
3. GitHub Actions CI 통과 (Pytest 85%+ / Ruff / Secret Detection / TruffleHog / Bandit / CodeQL)
4. 사용자 review OK 후 머지

trading / order / reconcile / security / auth 변경은 추가로:
- 변경 의도 + 위험 영향 (체결 정합성 / 자금 / 권한) PR 본문에 명시
- 회귀 테스트 (상태 전이 / 권한 매트릭스) 동반
- 리뷰 결과 우선순위: P0 (수정 필수) / P1 (가급적 수정) / P2 (메모)

## 외부 API 호출

- 신규 외부 HTTP 호출 추가 시 timeout 명시 + 실패 매핑 (5xx) 정의 필수.
- balance / order / account API 는 fail-fast (`/api/v1/account/balance` PR #482 모델 참조).
- 자격 증명 / 토큰을 argv 로 자식 프로세스에 전달하지 않음 — env / keychain 사용.

## 외부 / 다른 repo

- `../ai-hedge-fund-lab/` 의 read-only HTTP 호출은 본 repo 가 받는 측. 별도 작업 없음.
- 본 repo 의 작업이 `../ai-hedge-fund-lab/` 의 코드/문서를 변경하지 않음 — 사용자 명시 외.

## 참조

- 브랜치/PR 절차: `.claude/rules/github-workflow.md`
- 테스트 범위: `.claude/rules/testing.md`
- 보안 정책: `.claude/rules/security.md`
- 머지 후 재빌드: `.claude/rules/post-merge-rebuild.md`
