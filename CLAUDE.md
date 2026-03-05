# 키움 REST API 자동매매 시스템

## 프로젝트 개요
- **목표**: Mac/Windows에서 키움증권 REST API를 사용한 자동 투자 및 거래 시스템
- **백엔드**: Python 3.12 / **프론트엔드**: TypeScript (Next.js 14+)
- **패키지 관리**: Poetry / **린터/포매터**: Ruff
- **작업 디렉토리**: ~/individual

## 핵심 규칙 (MANDATORY)

### 1. 메모리 저장 프로토콜
**메모리는 이 프로젝트 한정. 글로벌 메모리(`~/.claude/projects/*/memory/`) 사용 금지.**
**모든 작업(크건 작건) 완료 시 반드시 실행:**

1. `.claude/memory/sessions/YYYY-MM-DD.md`에 해당 세션 내용 append
   - 수행한 작업 요약
   - 변경된 파일 목록
   - 주요 결정사항
   - 다음 할 일
2. `.claude/memory/project.md`에 프로젝트 상태 업데이트 (필요시)
3. 중요한 아키텍처 결정은 `.claude/memory/architecture.md`에 기록

**세션 로그 형식:** `.claude/rules/agent-logging.md`의 형식을 사용한다.

### 2. 에이전트 작업 기록 (MANDATORY)
**모든 에이전트(Agent Teams teammate)는 작은 덩어리 하나 완료 시마다 반드시 기록해야 한다.**
- 상세 규칙: `.claude/rules/agent-logging.md` 참조
- 에이전트 투입 시 프롬프트에 반드시 포함할 문구:
  > "작업 시작 전 `.claude/rules/agent-logging.md`를 읽고, 작은 덩어리 하나 완료할 때마다 반드시 `.claude/memory/sessions/YYYY-MM-DD.md`에 기록하라. 기록 없이 다음 작업으로 넘어가지 마라."

### 3. 코딩 규칙
- Python 코딩 규칙: `.claude/rules/python.md` 참조
- 트레이딩 시스템 규칙: `.claude/rules/trading.md` 참조
- 모든 코드는 type hint 필수
- docstring은 한글로 작성
- 변수/함수명은 영어 snake_case, 주석/문서는 한글

### 4. 보안 규칙 (최우선)
**이 프로젝트는 실제 금융 거래 시스템. 보안이 가장 중요.**

#### 코드 레벨
- API 키, 비밀번호는 절대 코드에 하드코딩 금지 (`.env` 사용)
- `.env`, `.pem`, `.key`, `.secret` 파일은 `.gitignore`에 포함 + 훅으로 쓰기 차단
- 실제 거래 코드는 반드시 모의투자 모드 기본값 (`is_mock_trading=True`)
- 사용자 입력은 항상 Pydantic으로 검증
- SQL은 반드시 ORM(SQLAlchemy) 사용 (raw SQL 금지)

#### 자동 보안 검사 (3단계 방어)
1. **Claude Code 훅** — `.claude/hooks/security-scan.sh` (시크릿 패턴 감지 + 보안 파일 쓰기 차단)
2. **Pre-commit 훅** — gitleaks, bandit, detect-private-key, pip-audit
3. **GitHub Actions** — gitleaks, TruffleHog, bandit, CodeQL, pip-audit, Dependabot

커밋 전 필수: `pre-commit run --all-files`

### 5. 브랜치 전략 (MANDATORY)
**main/dev 직접 push 절대 금지. 항상 개별 브랜치 → dev → main.**

#### 브랜치 구조
- `main`: 프로덕션 배포 브랜치 (보호됨, 직접 push 금지)
- `dev`: 통합 브랜치 (보호됨, 직접 push 금지)
- `claude`: 작업 베이스 브랜치 (main과 항상 싱크)
- `feat/*`, `fix/*`, `hotfix/*`: 개별 작업 브랜치

#### 작업 흐름
```
1. claude 브랜치에서 시작 (main과 싱크 확인)
2. claude에서 개별 브랜치 생성: git checkout -b feat/xxx
3. 개별 브랜치에서 작업 + 커밋
4. 개별 브랜치 → dev (PR)
5. dev → main (PR)
6. main 머지 후 claude 싱크: git checkout claude && git merge main
7. claude 브랜치로 복귀
```

#### Claude Code 작업 시 필수
시작: `claude → merge main → checkout -b feat/xxx` / 완료: `push → gh pr create --base dev → checkout claude`

### 6. 커뮤니케이션
- 사용자와의 대화는 한글로
- 코드 내 변수/함수명은 영어
- 커밋 메시지는 한글 (conventional commit 형식)

### 7. 커밋 컨벤션 (MANDATORY)

#### 커밋 메시지 형식
- 형식: `feat(모듈): 한글 설명`
- 타입: feat, fix, refactor, test, docs, chore, ci
- 스코프(모듈): auth, broker, trading, ai, api, config, utils, tests, deps 등
- description(본문)은 최대한 자세하게, 읽기 편하게 작성
- Co-Authored-By, Generated with Claude Code 등 자동 생성 문구 삽입 금지

#### 파일 스테이징
- `git add .` / `git add -A` 사용 금지 — 논리적 단위로 묶어서 커밋 (하나의 커밋 = 하나의 관심사)

### 8. 테스트 정책 (MANDATORY)

- 테스트 커버리지 **85% 이상** 유지 필수
- 85% 미만이면 커밋/PR 생성 금지
- 모든 PR에 테스트 포함 필수
- 미사용/미래 구현 모듈은 커버리지 계산에서 제외 가능
- 모든 코드 변경 후 반드시 QA 에이전트 투입하여 테스트 검증

### 9. GitHub Actions 확인 (MANDATORY)

- PR 생성 전 로컬 테스트 통과 확인
- PR 머지 전 모든 GitHub Actions 통과 확인
- 머지 후에도 Actions가 실행되면 결과 확인
- Actions 실패 시 즉시 수정

### 10. 에이전트 팀 (MANDATORY)
**Agent Teams 기반 운영. 각 에이전트는 독립 Claude Code 인스턴스로 실행되며, mailbox/direct message로 통신한다.**
**`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 활성화 필수.**

#### 팀 구성 (10+1 Agent Teams teammates)
| # | 역할 | 투입 시점 |
|---|------|----------|
| 0 | **리드** (메인) | 항상. 조율 + 사용자 커뮤니케이션 + 에스컬레이션 게이트 |
| 1 | **백엔드** | 새 기능 구현, 버그 수정 |
| 2 | **프론트엔드** | UI 개발 |
| 3 | **QA** | **모든 코드 변경 후 반드시 투입** |
| 4 | **DevSecOps** | CI/CD, Docker, 인프라 변경 |
| 5 | **문서작성자** | 아키텍처 결정, 규칙 변경 (병렬 투입) |
| 6 | **기획자/PM** | Phase 기획, 기능 범위 결정 |
| 7 | **보안총괄자** | 보안 관련 변경 게이트키퍼 (리드 게이트 경유) |
| 8 | **코드리뷰어** | PR 전 코드 품질 리뷰 |
| 9 | **DBA** | DB 스키마, 마이그레이션, 쿼리 최적화 |
| 10 | **디자이너** | UI/UX 설계, 컴포넌트 구조 |

- 상세 규칙: `.claude/rules/agent-roles.md` 참조
- 독립 작업은 Agent Teams로 병렬 투입, 의존 작업은 Shared Task List로 순차 관리
- 보안총괄자 → 리드 게이트 → 사용자 (3단계 에스컬레이션)

#### 서브에이전트 (Agent tool) — 별도
리드가 빠른 탐색/분석을 위해 컨텍스트 내에서 일회성으로 호출하는 경량 에이전트.
Agent Teams teammate가 아니며, 결과만 호출자에게 반환된다.
- **Explore**: 코드베이스 탐색, 파일/패턴 검색
- **Plan**: 구현 전략 설계, 아키텍처 분석

### 11. 설계 철학 (MANDATORY)
**정답은 없고 오직 트레이드오프 뿐이다.**

- 모든 설계 결정에 **왜 이것을 선택했는지** + **대안은 무엇이었는지** 기록
- ADR (Architecture Decision Record)에 트레이드오프 근거 필수
- 헷갈리면 사용자를 설득하거나 물어볼 것. 임의로 결정하지 말 것
- 기존 결정 변경 시 원래 결정의 근거를 먼저 확인하고, 왜 바뀌어야 하는지 명시

### 12. 문서 추적 (MANDATORY)
**기록만 하고 버려지는 문서는 절대 허용하지 않는다.**

- 상세 규칙: `.claude/rules/doc-lifecycle.md` 참조
- 모든 `.claude/memory/` 문서는 활성/참조/기록으로 분류
- 활성 문서는 변경 발생 시 즉시 갱신
- 참조 문서는 상단에 "적용된 결정" 노트 필수
- **사용자 토론으로 결정이 변경되면, 관련된 모든 문서를 즉시 갱신**
- 문서작성자는 PR 생성 전 정합성 검증 수행 (doc-lifecycle.md 섹션 4)
- ADR 관련 커밋은 스코프에 ADR 번호 포함: `feat(module, ADR-XXX): 설명`

## 작업 흐름
1. 기능 설계 → `/plan` 커맨드 사용
2. 구현 → TDD 방식 권장
3. 코드 리뷰 → `/review` 커맨드 사용
4. 메모리 저장 → 작업 완료 시 자동 (CLAUDE.md 규칙에 따라)

## 사용 가능한 스킬
- `/save-memory` - 현재 세션 메모리 저장
- `/plan` - 기능/아키텍처 설계
- `/review` - 코드 리뷰
