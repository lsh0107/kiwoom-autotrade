# 문서 레지스트리

> 설계 문서 + 규칙 문서만 추적. 스크립트/프론트엔드/데이터는 git이 관리.
> **마지막 감사**: 2026-03-22

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
