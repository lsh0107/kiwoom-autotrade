# 문서 레지스트리 (Document Registry)

> **목적**: 프로젝트 문서의 생성/삭제/변경을 추적. 모든 문서는 이 인덱스에 등록되어야 한다.
> **마지막 감사**: 2026-03-13 세션 21 (docs 에이전트)
> **갱신 규칙**: 문서 생성/삭제/상태 변경 시 즉시 이 파일 업데이트

## 추적 규칙

1. **생성 시**: 이 레지스트리에 추가 + 관련 섹션에 등록
2. **삭제 시**: 삭제 이력 섹션으로 이동 (날짜 + 삭제 사유)
3. **상태 변경 시**: 상태 컬럼 갱신 + 최종검증일 갱신
4. **감사 주기**: 주 1회 (금요일) 전체 문서 ↔ 코드 일치 확인

---

## 활성 문서 (Active — 변경 시 즉시 갱신)

| 파일 | 목적 | 최종검증일 | 상태 | 관련 코드 |
|------|------|-----------|------|----------|
| `CLAUDE.md` | 프로젝트 규칙 인덱스 | 2026-03-11 | ✅ 정상 | 전체 |
| `README.md` | 프로젝트 소개 (공개 레포) | 2026-03-11 | ✅ 신규 | 전체 |
| `.claude/memory/project.md` | 프로젝트 상태 추적 | 2026-03-13 | ✅ 갱신됨 | 전체 |
| `.claude/memory/architecture.md` | ADR 아키텍처 결정 | 2026-03-11 | ✅ 정상 | 전체 |
| `.claude/memory/decisions-pending.md` | 미결정 사항 추적 | 2026-03-13 | ✅ 갱신됨 | 미결정 4건 (#11,12,14,15) |
| `.claude/memory/strategy-momentum.md` | 전략 상세 (모멘텀+평균회귀) | 2026-03-11 | ✅ 갱신됨 | `src/strategy/`, 파라미터 반영 완료 |
| `.claude/memory/doc-registry.md` | 문서 인덱스 (이 파일) | 2026-03-13 | ✅ 갱신됨 | — |

## 규칙 문서 (Rules — 워크플로우 기준)

| 파일 | 목적 | 최종검증일 | 상태 |
|------|------|-----------|------|
| `.claude/rules/agent-roles.md` | 에이전트 시스템 가이드 | 2026-03-11 | ✅ 정상 |
| `.claude/rules/agent-logging.md` | 작업 기록 규칙 | 2026-03-11 | ✅ 정상 |
| `.claude/rules/doc-lifecycle.md` | 문서 생명주기 규칙 | 2026-03-11 | ✅ 정상 |
| `.claude/rules/github-workflow.md` | Git/PR 워크플로우 | 2026-03-11 | ✅ 정상 |
| `.claude/rules/prompting-guide.md` | 프롬프팅 가이드 | 2026-03-11 | ✅ 정상 |
| `.claude/rules/python.md` | Python 코딩 규칙 | 2026-03-11 | ✅ 정상 |
| `.claude/rules/trading.md` | 트레이딩 규칙 | 2026-03-11 | ✅ 정상 |

## 참조 문서 (Reference — 상단에 결정 반영 노트)

| 파일 | 목적 | 최종검증일 | 상태 | 비고 |
|------|------|-----------|------|------|
| `.claude/memory/design-v1.1.md` | 시스템 설계 기준 | 2026-03-13 | ⚠️ 부분불일치 | 프로세스 다이어그램(ADR-004), 16D AI 구조 갱신됨 |
| `.claude/memory/design-websocket-migration.md` | WebSocket 전환 설계 | 2026-03-11 | ✅ 설계 완료 | Phase 2 |
| `.claude/memory/design-telegram-bidirectional.md` | 텔레그램 양방향 설계 | 2026-03-11 | ✅ 설계 초안 | Phase 2-3, decisions-pending #15 |
| `.claude/memory/research-broker-api.md` | 증권사 API 리서치 | 2026-03-05 | ✅ 정상 | 참조용, 변경 없음 |
| `docs/kiwoom-rest-api/*.md` | 키움 API 레퍼런스 (17개) | 2026-03-05 | ✅ 정상 | 참조용 |
| `docs/kiwoom-rest-api/live-test-results.json` | 라이브 API 테스트 결과 | 2026-03-09 | ✅ 정상 | — |

## 기록 문서 (Archive — append only)

| 파일 | 목적 | 최종검증일 |
|------|------|-----------|
| `.claude/memory/sessions/2026-03-04.md` | 세션 1 — 프로젝트 셋업 | 2026-03-04 |
| `.claude/memory/sessions/2026-03-05.md` | 세션 2-3 — 보안/테스트 | 2026-03-05 |
| `.claude/memory/sessions/2026-03-06.md` | 세션 4-5 — API 통합 | 2026-03-06 |
| `.claude/memory/sessions/2026-03-07.md` | 세션 6 — 주문/토큰 | 2026-03-07 |
| `.claude/memory/sessions/2026-03-09.md` | 세션 7-8 — 백테스트/전략 | 2026-03-09 |
| `.claude/memory/sessions/2026-03-10.md` | 세션 — 분석/배포 | 2026-03-10 |
| `.claude/memory/sessions/2026-03-11.md` | 세션 9-15 — 감사/버그수정/프론트 안정화 | 2026-03-11 |
| `.claude/memory/sessions/2026-03-12.md` | 세션 16-20 — WebSocket 재작성/버그수정/PR #112 | 2026-03-12 |

## 백테스트/운영 결과 (Data)

| 파일 | 생성일 | 비고 |
|------|--------|------|
| `docs/backtest-results/backtest_20260309_*.json` | 2026-03-09 | 초기 백테스트 |
| `docs/backtest-results/screened_20260310_*.json` | 2026-03-10 | 종목 스크리닝 |
| `docs/backtest-results/live_20260310_*.json` | 2026-03-10 | 라이브 거래 로그 |
| `docs/backtest-results/*.log` | 2026-03-10+ | 실행 로그 |

## 스크립트 (Scripts)

| 파일 | 목적 | 최종검증일 | 상태 |
|------|------|-----------|------|
| `scripts/cron_backtest.sh` | 일일 자동 백테스트+매매 | 2026-03-11 | ✅ 커밋됨 (PR #82) |
| `scripts/live_trader.py` | 라이브 트레이더 | 2026-03-11 | ✅ 커밋됨 (MR params, time_ratio) |
| `scripts/run_backtest.py` | 백테스트 실행 | 2026-03-09 | ✅ 정상 |
| `scripts/screen_symbols.py` | 종목 스크리닝 | 2026-03-09 | ✅ 정상 |
| `scripts/korean_holidays.py` | 공휴일 체크 | 2026-03-09 | ✅ 정상 |
| `scripts/test_kiwoom_live.py` | 키움 API 연결 테스트 | 2026-03-09 | ✅ 정상 |

## 프론트엔드 주요 파일 (Frontend)

| 파일 | 목적 | 추가일 | 비고 |
|------|------|--------|------|
| `frontend/next.config.ts` | API rewrites 프록시 | 2026-03-11 | PR #88 |
| `frontend/vitest.config.ts` | 스모크 테스트 설정 | 2026-03-11 | PR #86 |
| `frontend/__tests__/smoke/pages.test.tsx` | 6페이지 스모크 테스트 | 2026-03-11 | PR #86 |
| `frontend/src/app/(authenticated)/strategy/page.tsx` | 전략 흐름도 페이지 | 2026-03-11 | PR #82 |
| `frontend/src/components/strategy/*.tsx` | 전략 흐름도 컴포넌트 3개 | 2026-03-11 | PR #82 |
| `frontend/src/components/ui/alert-dialog.tsx` | 주문 확인 다이얼로그 | 2026-03-11 | PR #92 |

---

## 삭제 이력

| 파일 | 삭제일 | 사유 |
|------|--------|------|
| `.claude/commands/plan.md` | 2026-03-09 | dev 머지 시 삭제됨 (커스텀 커맨드 → 빌트인 사용) |
| `.claude/commands/review.md` | 2026-03-09 | dev 머지 시 삭제됨 |
| `.claude/commands/save-memory.md` | 2026-03-09 | dev 머지 시 삭제됨 |

---

## 감사 체크리스트

매주 금요일 또는 Phase 전환 시:
- [ ] 활성 문서 ↔ 현재 코드/설계 일치?
- [ ] 새 파일 생성됐는데 레지스트리 미등록?
- [ ] 삭제된 파일이 레지스트리에 남아있나?
- [ ] ⚠️ 표시 문서 갱신 완료?
- [ ] 세션 로그 빠짐 없는가?
