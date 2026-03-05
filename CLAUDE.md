# 키움 REST API 자동매매 시스템

> Python 3.12 / FastAPI + Next.js 14+ / Poetry / Ruff
> 작업 디렉토리: ~/individual

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
- `.claude/rules/python.md` · `.claude/rules/trading.md` 참조
- type hint 필수, docstring 한글, 변수명 영어 snake_case

### 보안 (최우선 — 금융 거래 시스템)
- API 키/비밀번호 하드코딩 **금지** (`.env` 사용)
- 기본값 `is_mock_trading=True`, SQL은 ORM만
- 3단계 방어: Claude Hook → pre-commit → GitHub Actions
- 커밋 전: `pre-commit run --all-files`

### 브랜치
```
claude(base) → feat/* → dev(PR, squash) → main(PR, merge)
```
main/dev 직접 push 금지

### 커밋
- `feat(모듈): 한글 설명` (feat/fix/refactor/test/docs/chore/ci)
- `git add .` 금지, Co-Authored-By 금지

### 테스트
- 커버리지 **85%+** (미만 시 커밋/PR 금지)
- 코드 변경 후 QA 검증 필수

### 에이전트 팀 → `.claude/rules/agent-roles.md`
- 3~5명 실전 투입, worktree 격리, 1입력 1출력

### 문서 → `.claude/rules/doc-lifecycle.md`
- 활성 문서는 변경 시 즉시 갱신
- 결정 변경 시 관련 문서 전부 갱신

### 커뮤니케이션
- 한글 대화, 리드가 문서 기반 자율 판단
- 판단 불가능한 것만 에스컬레이션
- 설계 결정에 트레이드오프 근거 필수
