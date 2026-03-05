# Agent Teams 역할 정의

**온디맨드 투입. 3~5명 실전 운영. 리더만 Opus, 나머지 Sonnet.**

## 역할

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

## 투입 원칙

1. **Worktree 격리**: `Agent(isolation="worktree")` — 파일 충돌 방지
2. **같은 파일 수정 금지** — 충돌 시 리드가 해소
3. **QA 필수** — 코드 변경 후 예외 없이 투입
4. **1입력 1출력** — 각 에이전트에 명확한 입력 → 명확한 산출물
5. **최소 병렬화** — 필요한 만큼만 (3~5명), 전원 투입 X

## 배치 패턴

```
새 기능:  PM → Backend/Frontend(병렬) → QA → Reviewer → PR
버그:    Backend → QA → PR
인프라:  DevSecOps → Security → PR
```

## 투입 시 프롬프트

```
역할: [역할명]
작업: [구체적 내용]
산출물: [기대 출력]
규칙: 작업 완료마다 sessions/YYYY-MM-DD.md에 기록
```

## 보안총괄자

- 자동 승인: pre-commit 통과 + 시크릿 미검출 + CVE 없음
- 에스컬레이션: 모의→실거래 전환, 외부 서비스 연동, 암호화 변경
