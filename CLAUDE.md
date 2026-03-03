# 키움 REST API 자동매매 시스템

## 프로젝트 개요
- **목표**: Mac/Windows에서 키움증권 REST API를 사용한 자동 투자 및 거래 시스템
- **언어**: Python 3.11+
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

### 2. 코딩 규칙
- Python 코딩 규칙: `.claude/rules/python.md` 참조
- 트레이딩 시스템 규칙: `.claude/rules/trading.md` 참조
- 모든 코드는 type hint 필수
- docstring은 한글로 작성
- 변수/함수명은 영어 snake_case, 주석/문서는 한글

### 3. 보안 규칙
- API 키, 비밀번호는 절대 코드에 하드코딩 금지
- `.env` 파일 사용, `.gitignore`에 반드시 포함
- 실제 거래 관련 코드는 반드시 dry-run/모의투자 모드 기본값

### 4. 커뮤니케이션
- 사용자와의 대화는 한글로
- 코드 내 변수/함수명은 영어
- 커밋 메시지는 한글 (conventional commit 형식)

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
├── pyproject.toml              # 프로젝트 설정 (uv/poetry)
├── src/
│   ├── __init__.py
│   ├── config/                 # 설정 관리
│   ├── api/                    # 키움 REST API 클라이언트
│   ├── strategy/               # 투자 전략
│   ├── trading/                # 주문 실행
│   ├── data/                   # 시세/데이터 수집
│   ├── portfolio/              # 포트폴리오 관리
│   ├── notification/           # 알림 (텔레그램 등)
│   └── utils/                  # 유틸리티
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
