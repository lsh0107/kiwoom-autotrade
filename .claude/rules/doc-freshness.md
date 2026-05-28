# Document Freshness Rules

> 문서 vs 코드 충돌 시 **코드 우선**. 같은 PR 에서 문서 동기화.

## 핵심 규칙

1. 문서를 읽고 코드 작업에 인용할 때, 문서가 현재 코드 / 정책과 충돌하면 **코드를 우선**한다.
2. 코드 변경으로 active 문서가 어긋나면 같은 PR 에서 문서 동기화. 별도 PR 로 미루지 않는다.
3. "역사적 가치는 있지만 현 정책과 다른 문서" 는 삭제하지 말고 **"Historical" 섹션으로 낮춤**.
4. 새 정책 / 게이트 / 안전 규칙 도입 시 `CLAUDE.md` Current Status 표 + 해당 rule 파일 + 관련 design doc 을 함께 갱신.

## active 문서 (변경 시 즉시 갱신 대상)

- `CLAUDE.md` (루트 인덱스)
- `.claude/rules/python.md` / `frontend.md` / `airflow.md` / `trading.md`
- `.claude/rules/github-workflow.md` / `post-merge-rebuild.md`
- `.claude/rules/agent-roles.md` / `agent-logging.md`
- `.claude/rules/doc-lifecycle.md` / `prompting-guide.md`
- `.claude/rules/escalation.md` / `testing.md` / `security.md` / `doc-freshness.md` (신규)
- `docs/ai-hedge/PR_E_DESIGN.md` / `PROPOSAL_QUALITY_ROADMAP.md` / `AI_HEDGE_FUND_INTEGRATION_HANDOFF.md`
- 활성 ADR / architecture / design 문서

## reference 문서 (변경 적음)

- 완료된 PR 의 회고 / Phase 보고서
- 과거 buglog / 회의록 (필요 시 Historical 섹션으로 흡수)

## 인용 시 신선도 체크

코드 변경의 근거로 문서를 인용할 때:
- 문서의 마지막 갱신 일자 / 관련 PR 번호 확인
- 현재 코드 / 정책과 일치하는지 확인
- 충돌 발견 시: 코드 우선 + 같은 PR 에서 문서 갱신 (별도 PR 로 미루지 않음)

## 문서 갱신 트리거

| 이벤트 | 갱신 대상 |
|---|---|
| 새 안전 게이트 도입 | `CLAUDE.md` Current Status + `.claude/rules/security.md` (또는 관련 rule) + `docs/ai-hedge/PR_E_DESIGN.md` |
| 새 정책 (e.g. fail-fast endpoint) | `.claude/rules/security.md` + `.claude/rules/testing.md` (테스트 요구) |
| AI hedge ingestion 정책 변경 | `docs/ai-hedge/*.md` + `.claude/rules/escalation.md` |
| Workflow / 머지 절차 변경 | `.claude/rules/github-workflow.md` + `.claude/rules/post-merge-rebuild.md` |
| 작업 종료 (PR 머지 / 세션) | `.claude/memory/sessions/YYYY-MM/YYYY-MM-DD.md` (append) |

## 참조

- 문서 생명주기: `.claude/rules/doc-lifecycle.md`
- 에이전트 로깅: `.claude/rules/agent-logging.md`
