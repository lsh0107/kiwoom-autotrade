# Deep Work Protocol

> "완료"는 작업 수행이 아니라 검증 완료를 의미한다. 검증하지 않은 작업은 "구현 완료, 검증 대기"라고 보고한다.

고위험 / 멀티파일 / 거래 / 인증 / DB / PR 머지 작업은 바로 구현하지 않는다. 반드시 아래 순서를 따른다.

## 적용 대상

- trading / order / cancel / reconcile / live_trader 변경
- auth / permission / token / credential 변경
- account / balance / broker API 변경
- DB schema / alembic / 데이터 정합성 변경
- AI hedge ingestion / applied / auto-approval / live consumption 변경
- main 머지 / post-merge rebuild / 운영 QA
- 2개 이상 파일을 바꾸는 작업

## 1. Scope Restatement

작업 시작 전 3줄 이하로 다음을 명시한다.

- 사용자의 요청을 재정의한다.
- 현재 repo / branch / 영향 범위를 확인한다.
- 이번 작업에서 하지 않을 것을 명시한다.

## 2. Preflight

구현 전 반드시 확인한다.

- `git status` 로 기존 변경 / untracked / branch 확인
- 관련 문서: `CLAUDE.md`, `.claude/rules/*`, 관련 `docs/*`
- 기존 구현 위치와 호출 경로
- 테스트 / QA 방법
- 사용자 확인이 필요한지 (`.claude/rules/escalation.md`)

경로를 추측하지 않는다. `pwd`, git root, 실제 파일 존재를 확인한다.

## 3. Implementation Plan

작업 전 짧게 정리한다.

- 변경 파일 후보
- 데이터 / 상태 전이 / 외부 API 영향
- 실패 시 중단 기준
- 필요한 테스트
- 문서 동기화 필요 여부

## 4. Two-Pass Requirement

Trading / order / auth / DB 작업은 2-pass mandatory.

1. 구현
2. 독립 self-review

self-review 질문:

- 이 변경이 실제 주문 / 잔고 / 체결 / 권한 상태를 바꾸는가?
- mock 결과를 live 결과처럼 말하고 있지 않은가?
- DB 상태와 broker 상태가 어긋날 때 어떻게 동작하는가?
- 실패 시 fake success / fake fallback 이 생기지 않는가?
- timeout / retry / 중복 실행 시 안전한가?
- 권한 없는 사용자나 다른 사용자의 데이터에 영향이 없는가?

## 5. Self Review Before Reporting Done

완료 보고 전 반드시 확인한다.

- `git diff`
- 변경 파일 목록
- 의도치 않은 파일 변경 여부
- 테스트 / lint / CI 결과
- 문서 동기화 필요 여부
- 사용자 요청 중 누락된 항목 여부
- 남은 위험 / 검증 한계

## 6. Done Definition

작업 유형별 완료 기준:

| 유형 | 완료 기준 |
|---|---|
| 코드 변경 | 관련 테스트 + lint/format + diff review |
| 문서 변경 | diff review + 링크/경로 검증 |
| PR 작업 | base/head 확인 + CI 확인 + merge target 확인 |
| 운영 QA | 실제 실행 결과 + 실패/한계 명시 |
| post-merge | claude sync + `post_merge_rebuild.sh` + HTTP probe |

## 금지

- 확인하지 않은 것을 "완료"라고 말하지 않는다.
- CI pending 상태에서 "통과"라고 말하지 않는다.
- mock 검증을 live 검증처럼 표현하지 않는다.
- 사용자 원본 파일을 덮어쓰기 전 diff / 범위 확인 없이 수정하지 않는다.
- 권한 / 계정 / branch 상태를 추측하지 않는다.
- PR E2 / live consumption 을 observation gate 없이 시작하지 않는다.

## Claude Code 적용 지점

Claude Code 는 프로젝트 `CLAUDE.md` 를 shared project memory 로 읽고, 프로젝트별 subagent 는 `.claude/agents/`, 커스텀 slash command 는 `.claude/commands/`, hook 은 `.claude/settings.json` 에 둘 수 있다.

현재 적용:

- 본 규칙은 `CLAUDE.md` 에서 직접 참조한다.
- 완료 전 수동 self-review 명령: `/deep-check` (`.claude/commands/deep-check.md`).

추후 강제화 후보:

- `Stop` hook 으로 "검증 없는 완료 보고" 차단.
- `PreToolUse` hook 으로 `git add .`, secrets 파일, 위험 명령 차단.
- trading / auth / DB 변경용 project subagent 를 `.claude/agents/` 에 정의해 리뷰를 분리.
