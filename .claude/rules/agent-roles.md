# 에이전트 시스템 가이드

Claude Code에는 두 가지 에이전트 시스템이 있다. 용도와 동작 방식이 완전히 다르다.

| 구분 | 서브에이전트 | 팀 에이전트 |
|------|-------------|------------|
| 호출 | `Agent(subagent_type=...)` | `TeamCreate` + `Agent(team_name=...)` |
| 세션 | 리드 컨텍스트 내 일회성 | 독립 세션 (별도 context window) |
| 격리 | 없음 | worktree 격리 |
| 소통 | 결과 반환 후 종료 | `SendMessage`로 양방향 |
| 모델 | 타입별 상이 | 리드 Opus, 팀원 Sonnet |
| 용도 | 탐색, 분석, 계획 | 구현, 테스트, 리뷰 |

---

## 1. 서브에이전트 (Subagents)

리드가 직접 호출하는 일회성 에이전트. 팀 없이도 사용 가능. 결과를 리드에게 반환하고 종료된다.
**주 용도**: context window 절약 (탐색 결과가 리드 컨텍스트를 오염시키지 않음)

| 타입 | 모델 | 도구 | 용도 |
|------|------|------|------|
| `Explore` | Haiku | 읽기 전용 (Read, Grep, Glob, WebFetch 등) | 빠른 코드 탐색, 키워드 검색 |
| `Plan` | Opus (inherit) | 읽기 전용 | 설계 계획, 아키텍처 분석 |
| `general-purpose` | Opus (inherit) | 모든 도구 (Agent 제외) | 복잡한 멀티스텝 작업 |
| `claude-code-guide` | Opus (inherit) | 읽기 + WebFetch/WebSearch | Claude Code 자체 기능 조사 |

### 사용 예시

```
# 코드 탐색 (Haiku — 빠르고 저렴)
Agent(subagent_type="Explore", prompt="backend/app/api/ 디렉토리에서 인증 관련 엔드포인트 목록 조사")

# 설계 계획 (Opus — 깊은 분석)
Agent(subagent_type="Plan", prompt="키움 API 주문 모듈의 에러 핸들링 개선 계획 수립")
```

### 사용 기준
- 단순 탐색/검색 → `Explore` (Haiku, 저비용)
- 3회 이상 Grep/Glob이 필요한 넓은 탐색 → `Explore`
- 설계 분석, 의사결정 → `Plan`
- 복잡한 단발성 작업 → `general-purpose`

---

## 2. 팀 에이전트 (Team Agents)

독립 세션을 가진 팀원. 멀티파일 작업(2개+ 파일 변경) 시 필수.

### 생성 흐름
```
TeamCreate → TaskCreate (blockedBy 의존성) → Agent(team_name=..., name="backend", isolation="worktree")
```

### 역할

| # | 역할 | 코드명 | 투입 조건 |
|---|------|--------|----------|
| 0 | **리드** | `lead` | 항상. 조율 + 사용자 소통 |
| 1 | **백엔드** | `backend` | Python/FastAPI 구현, 버그 수정 |
| 2 | **프론트엔드** | `frontend` | Next.js/TypeScript UI |
| 3 | **QA** | `qa` | **모든 코드 변경 후 필수** |
| 4 | **DevSecOps** | `devsecops` | CI/CD, Docker, 보안 검사 |
| 5 | **문서작성자** | `docs` | ADR, 규칙 문서 |
| 6 | **PM** | `pm` | Phase 기획, 범위 결정 |
| 7 | **보안총괄자** | `security` | 보안 변경 게이트키퍼 |
| 8 | **코드리뷰어** | `reviewer` | PR 전 코드 리뷰 |

### 투입 원칙

1. **Worktree 격리**: `Agent(isolation="worktree")` -- 파일 충돌 방지
2. **같은 파일 수정 금지** -- 충돌 시 리드가 해소
3. **QA 필수** -- 코드 변경 후 예외 없이 투입
4. **1입력 1출력** -- 각 에이전트에 명확한 입력, 명확한 산출물
5. **최소 병렬화** -- 필요한 만큼만 (3~5명), 전원 투입 X

### 투입 시 프롬프트

```
역할: [역할명]
작업: [구체적 내용]
산출물: [기대 출력]
규칙: 작업 완료마다 sessions/YYYY-MM-DD.md에 기록
```

---

## 3. 배치 패턴

### 팀 에이전트 배치
```
새 기능:  PM → Backend/Frontend(병렬) → QA → Reviewer → PR
버그:    Backend → QA → PR
인프라:  DevSecOps → Security → PR
```

### 서브에이전트 활용
```
코드 탐색:      Explore로 조사 → 리드가 직접 수정
설계 검토:      Plan으로 분석 → 리드가 판단
단일 파일 수정:  리드가 직접 수행 (팀 불필요)
```

### 혼합 사용
```
복잡 기능:  Explore(조사) → Plan(설계) → TeamCreate → Backend/Frontend → QA → PR
```

---

## 4. 보안총괄자

- 자동 승인: pre-commit 통과 + 시크릿 미검출 + CVE 없음
- 에스컬레이션: 모의->실거래 전환, 외부 서비스 연동, 암호화 변경

---

## 5. 커스텀 에이전트

`.claude/agents/*.md` 파일로 커스텀 에이전트 정의 가능. 현재 미사용이나 반복 패턴 발생 시 확장 예정.
