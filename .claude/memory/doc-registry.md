# 문서 레지스트리

> 설계 문서 + 규칙 문서만 추적. 스크립트/프론트엔드/데이터는 git이 관리.
> **마지막 감사**: 2026-04-28 (ADR-022 추가)

## 설계 문서

| # | 파일 | 목적 | 상태 |
|---|------|------|------|
| 001 | design-001-system-v1.md | Phase 1 시스템 설계 | 보관 |
| 002 | design-002-strategy.md | 전략 v2.0 설계 | 활성 |
| 003 | design-003-risk-management.md | Phase 1 리스크 관리 | 활성 |
| 004 | design-004-infra-eks.md | EKS 인프라 설계 | 활성 (대기) |
| 005 | design-005-data-pipeline.md | Phase 3 데이터 파이프라인 | 활성 (진행 중) |
| 006 | design-006-telegram.md | 텔레그램 양방향 | 활성 (대기) |
| 007 | design-007-websocket.md | WebSocket 전환 | 보관 |
| 008 | design-008-llm-db-context.md | LLM DB 컨텍스트 동적 투자 결정 | 활성 (Phase A/B/C/D 완료) |
| 009 | docs/design/design-009-market-context-integration.md | MarketContext 수급/테마 통합 (FlowSignal + ThemeBoost) | 활성 — stocks.theme 백필 완료 (PR #321) |
| 010 | docs/design/design-010-llm-decision-integration.md | LLMDecision approved → live_trader 반영 | 활성 — schema 정렬 후속 PR 필요 |
| 011 | docs/design/design-011-daily-candle-caching.md | 일봉 DB 캐싱 | 활성 (완료) |
| 012 | docs/design/design-012-pre-screening-cache.md | 사전 스크리닝 캐시 | 활성 — DAG unpause 완료 (PR #320) |
| 013 | docs/design/design-013-multi-regime-strategy.md | 다중 레짐 전략 (Pullback/Range) | 활성 — PR 1~9 완료, 배선 완성 (PR #334). walk-forward 검증 대기 |
| 014 | docs/design/design-014-live-order-persist.md | live_trader DB persist 브릿지 (ADR-014) | 활성 — shadow write 완료 (PR #322) |
| 015 | docs/design/design-015-backtest-engine-integrity.md | 백테스트 엔진 무결성 4종 (look-ahead/slippage/MDD/survivorship) | 활성 — PR #326 머지 완료 |
| 016 | docs/design/design-016-strategy-redesign.md | 5분봉 폐기 + 52주 신고가 일봉 채택 + 20종목 WF 결과 | 활성 — **52주 신고가 폐기 확정** (ADR-018: 20 grid × 20종목 전 조합 0/20) |
| 017 | docs/design/design-017-risk-microstructure.md | 리스크 가드레일(T3) + 마이크로구조(T4) 통합 설계 | 활성 — PR #327/#325 머지 완료 |
| 018 | docs/design/design-018-strategy-rerun.md | 파라미터 재검증 결과 통합 (52주 신고가 폐기) + multi-regime 배선 완성 + 후속 옵션 | 활성 — ADR-019로 옵션 B 실패 확정 |
| 019 | docs/design/design-019-pullback-range-validation.md | Pullback/Range/MR walk-forward (전 전략 0/20 폐기) + 누적 폐기 4건 패턴 + 옵션 A/C/D/E | 활성 — ADR-019 |
| 020 | docs/design/design-020-extended-validation.md | 확장 검증 (KOSPI30+KOSDAQ30 59종목, 3년, 27 combo) — 0/59 폐기, **일봉(daily) timeframe** 폐기 (주봉~월봉은 옵션 (e)로 보존) | 활성 — 2026-04-27 신규 (ADR-020) |
| 021 | docs/design/design-021-cross-sectional-momentum.md | Cross-sectional momentum (172종목, 5년, 8 combo) — V2 기준 1/8 PASS (top20pct_novol_notrend 33%), 모의 진입 후보 | 활성 — 2026-04-27 신규 (ADR-021). ADR-022 어댑터 구현 완료 |
| 022 | docs/design/design-022-cross-momentum-live-adapter.md | Cross-momentum live rebalance 어댑터 — CrossMomentumRebalanceAdapter, 월말 14:55 스케줄러, USE_CROSS_MOMENTUM 환경변수, 안전장치 4종, 미해결 위험 4건 | 활성 — 2026-04-28 신규 (ADR-022). 모의 4주 관찰 대기 |

### 운영 문서

| 파일 | 목적 | 상태 |
|------|------|------|
| docs/operations/strategy-redesign-rollout.md | 전략 롤아웃 체크리스트 (모의→실전 전환) | **ADR-022 구현 완료 → 모의 4주 관찰 대기** (`USE_CROSS_MOMENTUM=true` 설정 후 시작 가능) |

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

## 규칙 문서

| 파일 | 목적 |
|------|------|
| rules/python.md | Python + uv 규칙 |
| rules/airflow.md | Airflow DAG 작성 |
| rules/frontend.md | 프론트엔드 |
| rules/trading.md | 트레이딩 |
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
