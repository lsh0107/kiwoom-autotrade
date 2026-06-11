# 문서 레지스트리

> 설계 문서 + 규칙 문서만 추적. 스크립트/프론트엔드/데이터는 git이 관리.
> **마지막 감사**: 2026-06-11 (전수 감사 — design-025/멀티전략/observation 문서 추가, 3월 문서군 Historical 강등, design-024 파일명 링크 정정)

## 설계 문서

| # | 파일 | 목적 | 상태 |
|---|------|------|------|
| 001 | design-001-system-v1.md | Phase 1 시스템 설계 | 보관 |
| 002 | design-002-strategy.md | 전략 v2.0 설계 | **Historical** (2026-06-11 — cross_momentum 채택으로 대체) |
| 003 | design-003-risk-management.md | Phase 1 리스크 관리 | **Historical** (2026-06-11 — 현행은 design-017/kill_switch) |
| 004 | design-004-infra-eks.md | EKS 인프라 설계 | **Historical** (로컬 Mac+Cloudflare 운영 중, EKS 미진행) |
| 005 | design-005-data-pipeline.md | Phase 3 데이터 파이프라인 | **Historical** (Airflow 운영분은 rules/airflow.md) |
| 006 | design-006-telegram.md | 텔레그램 양방향 | **Historical** (구현 완료) |
| 007 | design-007-websocket.md | WebSocket 전환 | 보관 |
| 008 | design-008-llm-db-context.md | LLM DB 컨텍스트 동적 투자 결정 | **Historical** (Phase A/B/C/D 완료) |
| 009 | docs/design/design-009-market-context-integration.md | MarketContext 수급/테마 통합 (FlowSignal + ThemeBoost) | 활성 — stocks.theme 백필 완료 (PR #321) |
| 010 | docs/design/design-010-llm-decision-integration.md | LLMDecision approved → live_trader 반영 | 구현 완료 — schema 후속은 bias vocab alignment (#535/#536) 로 해소 |
| 011 | docs/design/design-011-daily-candle-caching.md | 일봉 DB 캐싱 | 활성 (완료) |
| 012 | docs/design/design-012-pre-screening-cache.md | 사전 스크리닝 캐시 | 활성 — DAG unpause 완료 (PR #320) |
| 013 | docs/design/design-013-multi-regime-strategy.md | 다중 레짐 전략 (Pullback/Range) | **보관(deprecated)** — PR 4(Pullback) ADR-019 폐기, PR 5(Range) ADR-020 폐기. USE_MULTI_REGIME → ActiveStrategy.MULTI_REGIME (ADR-024) |
| 014 | docs/design/design-014-live-order-persist.md | live_trader DB persist 브릿지 (ADR-014) | 활성 — shadow write 완료 (PR #322) |
| 015 | docs/design/design-015-backtest-engine-integrity.md | 백테스트 엔진 무결성 4종 (look-ahead/slippage/MDD/survivorship) | 활성 — PR #326 머지 완료 |
| 016 | docs/design/design-016-strategy-redesign.md | 5분봉 폐기 + 52주 신고가 일봉 채택 + 20종목 WF 결과 | 활성 — **52주 신고가 폐기 확정** (ADR-018: 20 grid × 20종목 전 조합 0/20) |
| 017 | docs/design/design-017-risk-microstructure.md | 리스크 가드레일(T3) + 마이크로구조(T4) 통합 설계 | 활성 — PR #327/#325 머지 완료 |
| 018 | docs/design/design-018-strategy-rerun.md | 파라미터 재검증 결과 통합 (52주 신고가 폐기) + multi-regime 배선 완성 + 후속 옵션 | 활성 — ADR-019로 옵션 B 실패 확정 |
| 019 | docs/design/design-019-pullback-range-validation.md | Pullback/Range/MR walk-forward (전 전략 0/20 폐기) + 누적 폐기 4건 패턴 + 옵션 A/C/D/E | 활성 — ADR-019 |
| 020 | docs/design/design-020-extended-validation.md | 확장 검증 (KOSPI30+KOSDAQ30 59종목, 3년, 27 combo) — 0/59 폐기, **일봉(daily) timeframe** 폐기 (주봉~월봉은 옵션 (e)로 보존) | 활성 — 2026-04-27 신규 (ADR-020) |
| 021 | docs/design/design-021-cross-sectional-momentum.md | Cross-sectional momentum (172종목, 5년, 8 combo) — V2 기준 1/8 PASS (top20pct_novol_notrend 33%), 모의 진입 후보 | 활성 — 2026-04-27 신규 (ADR-021). ADR-022 어댑터 구현 완료 |
| 022 | docs/design/design-022-cross-momentum-live-adapter.md | Cross-momentum live rebalance 어댑터 — CrossMomentumRebalanceAdapter, 월말 14:55 스케줄러, `ACTIVE_STRATEGY=cross_momentum` (구 USE_CROSS_MOMENTUM 폐기, ADR-024), 안전장치 4종, 미해결 위험 4건 | 활성 — 2026-04-28 신규 (ADR-022). ADR-023 견고화 완료 |
| 023 | docs/design/design-023-cross-momentum-hardening.md | ADR-022 미해결 위험 3건 해소 — rate limit 백오프 (DB 캐싱 + pykrx retry), T+2 결제 시뮬 (메모리 큐), KRX 공휴일 캘린더 (2025~2027) | 활성 — 2026-04-28 신규 (ADR-023). 모의 4주 관찰 시작 가능 (`ACTIVE_STRATEGY=cross_momentum`, ADR-024) |
| 024 | docs/design/design-024-strategy-enum-consolidation.md | ACTIVE_STRATEGY enum 단일화 — USE_CROSS_MOMENTUM/USE_MULTI_REGIME 환경변수 폐기, enum 기반 전략 선택 | 구현 완료 (ADR-024). env 는 design-025 로 deprecated legacy fallback |
| 025 | docs/design/design-025-multi-strategy-orchestrator.md | 멀티전략 오케스트레이터 — DB `strategy_runtime` 단일 진실원, StrategyRegistry/BudgetManager/handler dispatch | **활성** — 머지 완료, cross_momentum 단독 enabled 운영 중 |
| — | docs/design/multi-strategy-portfolio-controller.md | 4전략 동시운영 포트폴리오 설계 (PR 0) — 로드맵: PR 1 감사·2a budget 주입 완료, **2b/3 은 6/15 본 관찰 후** | **활성** |
| — | docs/design/active-strategy-legacy-audit.md | env ACTIVE_STRATEGY 의존성 인벤토리 + 회귀 테스트 (제거 보류) | 활성 (PR 1) |
| — | docs/design/multi-strategy-pr2b-budget-model.md | PR 2b total-equity budget 설계 초안 | **DRAFT — 미커밋 보류** (로컬 untracked, 구현은 6/15 후) |
| — | docs/design/SHORT_SWING_STRATEGY_DESIGN.md | short_swing 전략 설계 (PR 1~5 + HOTFIX 구현 완료) | 구현 완료 — 실활성은 운영 잠금 (PR 2b/3 후) |

### 운영 문서

| 파일 | 목적 | 상태 |
|------|------|------|
| docs/operations/strategy-redesign-rollout.md | 전략 롤아웃 체크리스트 (모의→실전 전환) | ADR-023 완료 — 모의 운영 중. 본 관찰 2026-06-15 예정 |

### 관찰/운영 문서 (2026-06 신규)

| 파일 | 목적 | 상태 |
|------|------|------|
| docs/observation/2026-06-01-mock-live-trader-observation-plan.md | **모의 live_trader 관찰 기준 문서 (v0.10)** — 본 관찰 6/15 시작 예정, §11 smoke run(6/11 PASS with NOTE), §11.8 mini trigger smoke | **활성 (기준)** |
| docs/observation/2026-06-01-mock-live-trader-checklist.md | 가동 전 8항목 체크리스트 | 활성 |
| docs/observation/regime-daily-dryrun-routine.md | regime daily dry-run 루틴 (2계층 출력, outputs/regime 커밋 금지) | **활성 — 매일 실행** |
| docs/observation/&lt;DATE&gt;-regime-dryrun-summary.md | 일별 public-safe regime 요약 (6/9: risk_off 88 → 6/10: 93 → 6/11: 94) | 기록 (append) |
| docs/ai-hedge/PR_E_DESIGN.md 외 2종 | AI hedge 통합 설계/로드맵/인계 | 활성 |
| docs/audit/2026-06-01-async-transaction-audit.md | async tx leak 감사 (P1 해소 완료) | 참조 |

### 교차 참조

- design-009 ↔ design-013: ThemeBoost/FlowSignal은 design-009에서 배선, design-013 MarketStyle과 직교
- design-011 ↔ design-012: 012는 011 DailyCandle 테이블에 의존
- design-012 ↔ design-013: 013 거래량 override는 012 스크리닝 캐시 종목에 적용
- design-014 ↔ design-010: 014는 live_trader orders persist, 010은 LLM decision 소비 — 모두 live_trader 확장 라인
- design-015 ↔ design-016: 015 엔진 보정 후 016 전략 재측정 — 순서 의존성
- design-016 ↔ design-017: 016 전략 신호 → 017 리스크 가드레일 게이트 통과 후 체결
- design-016 ↔ operations/strategy-redesign-rollout: 016 결과 기반 롤아웃 조건 정의
- design-018 ↔ design-016: 018은 016 폐기 확정 + 후속 전략 방향 결정
- design-018 ↔ design-013: 018은 013 배선 완성 확인 + walk-forward 검증 방향 제시
- design-018 ↔ operations/strategy-redesign-rollout: 018 §5 옵션 B/A/C → rollout 1단계 진행 방향
- design-019 ↔ design-018: 019는 018 옵션 B 실패 확정 + 옵션 A/C/D/E 트레이드오프
- design-019 ↔ design-013: 019 결과로 USE_MULTI_REGIME 계속 비활성화
- design-019 ↔ operations/strategy-redesign-rollout: 019 §8 권고 → rollout 옵션 A 1순위 전환
- design-020 ↔ design-019: 020은 019 신호 희소성 가설 기각 + **일봉(daily) timeframe** 폐기 확정 (주봉~월봉은 옵션 (e)로 보존)
- design-020 ↔ design-013: 020 결과로 USE_MULTI_REGIME 계속 비활성화
- design-020 ↔ operations/strategy-redesign-rollout: 020 §6 결정 → rollout 옵션 A 폐기, 후속 방향 미결정
- design-021 ↔ design-020: 021은 020 폐기 이후 직교 카테고리(monthly cross-sectional) 검증 → V2 기준 PASS
- design-021 ↔ design-015: 021 cross-momentum 백테스트도 015 엔진 무결성 기준 동일 적용
- design-021 ↔ operations/strategy-redesign-rollout: 021 §9 PASS → rollout 모의 재개 조건 갱신 (ADR-022 + 4주)
- design-022 ↔ design-021: 022는 021 PASS 이후 live_trader 통합 어댑터 구현
- design-022 ↔ design-014: 022 주문 DB persist는 014 live_order_persist 재사용
- design-022 ↔ design-013: 022 USE_CROSS_MOMENTUM과 013 USE_MULTI_REGIME 상호배타 (동시 ON → exit(1))
- design-022 ↔ operations/strategy-redesign-rollout: 022 구현 완료 → rollout 2단계 모의 시작 가능
- design-023 ↔ design-022: 023은 022 미해결 위험 4건 중 3건 해소 (#1 rate limit, #2 T+2, #4 공휴일)
- design-023 ↔ design-021: 023 모의 4주 관찰 기준은 021 §7 V2 기준과 동일
- design-023 ↔ design-011: 023 DB 우선 조회는 011 daily_candle_store 테이블에 의존
- design-023 ↔ operations/strategy-redesign-rollout: 023 견고화 완료 → rollout 모의 진입 선언
- design-024 ↔ design-022: 024로 USE_CROSS_MOMENTUM/USE_MULTI_REGIME 폐기, validate_cross_momentum_exclusivity 삭제
- design-024 ↔ design-013: 024로 USE_MULTI_REGIME → ActiveStrategy.MULTI_REGIME enum 통합
- design-024 ↔ design-023: 024로 USE_CROSS_MOMENTUM=true 설정 방식 → ACTIVE_STRATEGY=cross_momentum으로 대체

## 규칙 문서

| 파일 | 목적 |
|------|------|
| rules/python.md | Python + uv 규칙 |
| rules/airflow.md | Airflow DAG 작성 |
| rules/frontend.md | 프론트엔드 |
| rules/trading.md | 트레이딩 |
| rules/security.md | 보안 (시크릿/fail-fast/fake fallback 금지) |
| rules/testing.md | 테스트 (커버리지 85%+, 범위 매트릭스) |
| rules/escalation.md | 자율 vs 사용자 확인 |
| rules/deep-work.md | 고위험 작업 프로토콜 |
| rules/doc-freshness.md | 문서 신선도 (코드 우선) |
| rules/post-merge-rebuild.md | 머지 후 재빌드 |
| rules/agent-roles.md | 에이전트 시스템 |
| rules/agent-logging.md | 세션 로깅 |
| rules/doc-lifecycle.md | 문서 갱신 규칙 |
| rules/github-workflow.md | Git/PR |
| rules/prompting-guide.md | 프롬프팅 |

## 참조/리서치

| 파일 | 목적 |
|------|------|
| research-broker-api.md | 증권사 API 리서치 |
| research-data-sources-phase3.md | Phase 3 데이터 소스 |
| research-market-analysis-2026-03.md | 시장 분석 |
| research-rate-limits-and-queues.md | 레이트 리밋/큐 |

## 보관

| 파일 | 보관일 | 사유 |
|------|--------|------|
| design-001-system-v1.md | 2026-03-14 | design-002로 대체 |
| design-007-websocket.md | 2026-03-14 | 전환 완료 |
| bug-dashboard-balance-zero.md | 2026-03-14 | 버그 수정 완료 |
| design-002~006/008 (memory) | 2026-06-11 | Historical 강등 — 초기 설계 스냅샷 (헤더 표기) |
| research-*.md 4종, full-analysis-2026-03-10.md, strategy-momentum.md, feedback_parallel_agents.md | 2026-06-11 | Historical 강등 — 3월 리서치/구전략 스냅샷 |
| last-session.md | 2026-06-11 | DEPRECATED — sessions/YYYY-MM/ 일별 로그가 대체 |
