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

**세션 로그 형식:**
```markdown
### HH:MM - [작업 제목]
- **수행**: 무엇을 했는지
- **변경 파일**: 변경된 파일들
- **결정**: 내린 결정들
- **다음**: 다음에 할 일
```

### 2. 에이전트 작업 기록 (MANDATORY)
**모든 서브에이전트는 작은 덩어리 하나 완료 시마다 반드시 기록해야 한다.**
- 상세 규칙: `.claude/rules/agent-logging.md` 참조
- 서브에이전트 spawn 시 프롬프트에 반드시 포함할 문구:
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
1. **Claude Code 훅** (`.claude/hooks/security-scan.sh`)
   - Write/Edit 시 시크릿 패턴 자동 감지 → 차단
   - 보안 파일(`.env`, `.pem` 등) 직접 쓰기 → 차단
   - git push 전 보안 스캔 리마인더
2. **Pre-commit 훅** (`.pre-commit-config.yaml`)
   - gitleaks: 시크릿/API 키 감지
   - bandit: Python 보안 취약점 (SQL injection, eval, 약한 암호화 등)
   - detect-private-key: 개인키 파일 감지
   - pip-audit: 의존성 CVE 스캔 (push 시)
3. **GitHub Actions** (`.github/workflows/security.yml`)
   - gitleaks + TruffleHog: 시크릿 심층 스캔
   - bandit + CodeQL: Python SAST
   - pip-audit: 의존성 취약점
   - Dependabot: 자동 보안 업데이트 PR

#### git commit/push 전 필수
```bash
pre-commit run --all-files  # 커밋 전 전체 보안 스캔
```

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
```bash
# 작업 시작
git checkout claude
git merge main              # main과 싱크
git checkout -b feat/xxx    # 작업 브랜치 생성

# 작업 완료
git push origin feat/xxx
gh pr create --base dev     # dev로 PR 생성
git checkout claude         # claude로 복귀
```

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

#### 예시
```
feat(auth): 초대 코드 기반 회원가입 구현

- Invite 모델 추가 (code unique, expires_at, used_by)
- 첫 번째 사용자는 초대 없이 ADMIN으로 자동 등록
- 두 번째부터 유효한 초대 코드 필수
- 만료/사용 여부 검증 로직 포함
```

#### 파일 스테이징 규칙
- `git add .` 또는 `git add -A` 사용 금지
- 논리적 단위로 파일을 묶어서 커밋
- 하나의 커밋에 하나의 관심사만 포함
- 예: 모델 변경 → 별도 커밋, 테스트 추가 → 별도 커밋, 설정 변경 → 별도 커밋

### 8. 테스트 정책 (MANDATORY)

- 테스트 커버리지 **85% 이상** 유지 필수
- 85% 미만이면 커밋/PR 생성 금지
- 모든 PR에 테스트 포함 필수
- 미사용/미래 구현 모듈은 커버리지 계산에서 제외 가능
- QA 에이전트를 항상 활성화하여 테스트 검증

### 9. GitHub Actions 확인 (MANDATORY)

- PR 생성 전 로컬 테스트 통과 확인
- PR 머지 전 모든 GitHub Actions 통과 확인
- 머지 후에도 Actions가 실행되면 결과 확인
- Actions 실패 시 즉시 수정

## 프로젝트 구조 (목표)
```
~/individual/
├── CLAUDE.md
├── .claude/                    # Claude Code 설정
│   ├── settings.json
│   ├── commands/               # 슬래시 커맨드
│   ├── rules/                  # 코딩 규칙
│   ├── hooks/                  # 자동화 훅
│   └── memory/                 # 프로젝트 메모리
│       ├── project.md          # 프로젝트 상태
│       ├── architecture.md     # 아키텍처 결정
│       └── sessions/           # 날짜별 세션 로그
├── .env.example                # 환경변수 템플릿
├── .gitignore
├── pyproject.toml              # 프로젝트 설정 (Poetry)
├── src/                        # 백엔드
│   ├── __init__.py
│   ├── config/                 # 설정 관리
│   ├── api/                    # FastAPI 라우터
│   ├── broker/                 # 증권사 API 클라이언트
│   ├── strategy/               # 투자 전략
│   ├── trading/                # 주문 실행
│   ├── data/                   # 데이터 파이프라인 (수집/변환/저장/백테스트)
│   ├── ai/                     # AI 매매 (감성분석/시그널/LLM) [Phase 5]
│   ├── portfolio/              # 포트폴리오 관리
│   ├── notification/           # 알림 (텔레그램)
│   └── utils/                  # 유틸리티
├── frontend/                   # Next.js 프론트엔드
│   ├── src/
│   ├── public/
│   └── package.json
├── tests/                      # 테스트
├── scripts/                    # 실행 스크립트
└── docs/                       # 문서
```

## 작업 흐름
1. 기능 설계 → `/plan` 커맨드 사용
2. 구현 → TDD 방식 권장
3. 코드 리뷰 → `/review` 커맨드 사용
4. 메모리 저장 → 작업 완료 시 자동 (CLAUDE.md 규칙에 따라)

## 사용 가능한 커맨드
- `/save-memory` - 현재 세션 메모리 저장
- `/plan` - 기능/아키텍처 설계
- `/review` - 코드 리뷰
