# 키움 REST API 자동매매 시스템

> Python 3.12 / FastAPI + Next.js 16+ / uv / Ruff
> 작업 디렉토리: ~/individual/stock/kiwoom-autotrade

**이 파일은 인덱스(참조 포인터)다. 상세 규칙은 `.claude/rules/*.md`에 작성한다. CLAUDE.md에 구체적 명령어·절차를 직접 넣지 않는다.**

---

## Current Status / 위험 게이트 (반드시 먼저 읽기)

| 항목 | 값 |
|---|---|
| 운영 모드 | 기본 모의투자 (`is_mock_trading=True`) |
| balance API | fail-fast (PR #482/#483) — upstream hang 시 12s 504, broker 오류 502 |
| AI hedge ingestion | `/api/v1/decisions/drafts` 동작 중, `ai_hedge` context auto-approval 제외 (#464) |
| applied 마킹 정책 | 실 universe 반영 / 매수·매도 발생 기준 (#466). 단순 읽기로 applied 처리 금지 |
| AI hedge live consumption | **금지** — PR E2 영역. lab(`../ai-hedge-fund-lab/`) observation §5 충족 + 사용자 OK 후에야 시작 |
| Source of truth | broker holdings + available cash (Kiwoom). DB orders 적분 단독 사용 금지 |
| Fake fallback | balance/order 실패의 가짜 정상값 fallback **금지** |
| 머지 후 재빌드 | `bash scripts/post_merge_rebuild.sh` 표준 절차 |

## 작업 시작 프로토콜 (MANDATORY)

**멀티파일 작업(파일 2개+ 변경)은 반드시:**
1. `TeamCreate` → 팀 생성
2. `TaskCreate` → 작업 분해 (blockedBy 의존성 설정)
3. `Agent(team_name=..., isolation="worktree")` → teammate 투입
4. 단일 파일 수정, 간단한 질의응답만 리드 직접 수행
5. 리더만 Opus, teammate는 Sonnet

**모든 작업 완료 시:**
- `.claude/memory/sessions/YYYY-MM-DD.md`에 세션 로그 append
- `.claude/memory/project.md` 상태 업데이트 (필요시)

## 핵심 규칙

### 코딩
- 백엔드: `.claude/rules/python.md` · `.claude/rules/trading.md`
- 프론트엔드: `.claude/rules/frontend.md`
- 데이터 파이프라인: `.claude/rules/airflow.md`
- type hint 필수, docstring/주석 한글, 변수명 영어

### 보안 → `.claude/rules/security.md` (신규)
- API 키/비밀번호 하드코딩 **금지** (`.env` 사용, argv 노출 금지)
- 기본값 `is_mock_trading=True`, SQL은 ORM만
- 3단계 방어: Claude Hook → pre-commit → GitHub Actions
- 커밋 전: `pre-commit run --all-files`
- 자세한 항목 (외부 API timeout, fake fallback 금지, MOCK_BASE_URL 정책 등): `.claude/rules/security.md`

### Git & GitHub → `.claude/rules/github-workflow.md`
- `claude → feat/* → dev(squash) → main(merge)`
- PR 생성 후 Actions 확인 필수, 통과 전 머지 금지

### 머지 후 재빌드 → `.claude/rules/post-merge-rebuild.md`
- main 머지 + claude sync 직후 `bash scripts/post_merge_rebuild.sh` 실행
- 변경 경로(frontend/* vs src/scripts/alembic/...)별로 영향 컨테이너만 재빌드
- airflow 자동 대상 제외, alembic 마이그레이션 자동 적용 금지

### 테스트 → `.claude/rules/testing.md` (신규)
- 커버리지 **85%+** (미만 시 커밋/PR 금지)
- 코드 변경 후 관련 테스트 + QA 검증 필수
- API/trading/order/reconcile 변경은 상태 전이 + endpoint 테스트
- 자세한 범위 매트릭스: `.claude/rules/testing.md`

### 에스컬레이션 → `.claude/rules/escalation.md` (신규)
- 자율 결정: 문서 수정, 테스트 실행, feature branch, read-only QA, mock pipeline
- 사용자 확인 필수: 실거래 전환, 주문 로직 변경, AI hedge live consumption 시작, broker/order API 추가, alembic apply, dev→main 코드 변경 머지, secrets 변경, force push

### 문서 → `.claude/rules/doc-lifecycle.md` + `.claude/rules/doc-freshness.md` (신규)
- 활성 문서는 변경 시 즉시 갱신
- 결정 변경 시 관련 문서 전부 갱신
- 문서 vs 코드 충돌 시 **코드 우선**, 같은 PR 에서 문서 동기화

### 에이전트 → `.claude/rules/agent-roles.md`
- 서브에이전트(탐색/분석)와 팀 에이전트(구현/테스트) 구분
- 팀: 3~5명, worktree 격리, 1입력 1출력
- 세션 로깅: `.claude/rules/agent-logging.md`

### 프롬프팅 → `.claude/rules/prompting-guide.md`
- 효과적인 명령 패턴, 안티패턴, 컨텍스트 관리 가이드

### 커뮤니케이션
- 한글 대화, 리드가 문서 기반 자율 판단
- 판단 불가능한 것만 에스컬레이션
- 설계 결정에 트레이드오프 근거 필수

## AI hedge integration (현재)

- 양 repo 인계 문서: `docs/ai-hedge/AI_HEDGE_FUND_INTEGRATION_HANDOFF.md`
- PR E1/E2 설계 (main 머지 완료): `docs/ai-hedge/PR_E_DESIGN.md`
- 전체 로드맵: `docs/ai-hedge/PROPOSAL_QUALITY_ROADMAP.md`
- lab repo 위치: `../ai-hedge-fund-lab/`
- 현재 단계: lab observation. **본 repo 에서 AI hedge 결정의 live consumption 코드 시작 금지** (PR E2 미진입).
