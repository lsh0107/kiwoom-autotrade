# 아키텍처 결정 기록

## ADR-001: 키움 REST API 사용
- **일자**: 2026-03-03
- **결정**: 키움증권 REST API (한국투자증권 OpenAPI 기반) 사용
- **이유**: Mac/Windows 크로스플랫폼 지원, OCX 대신 REST 사용으로 플랫폼 독립
- **영향**: HTS 없이도 자동매매 가능

## ADR-002: Python 3.12 + Poetry + 비동기 아키텍처
- **일자**: 2026-03-03 (3.12/Poetry 확정: 2026-03-04)
- **결정**: Python 3.12 / Poetry / httpx async
- **이유**: 빠른 개발, 풍부한 금융 라이브러리 생태계, 비동기로 API 호출 효율화, 3.12 에러 메시지/성능 개선
- **영향**: asyncio 기반 설계 필요

## ADR-003: 멀티유저 지원 (초대 기반)
- **일자**: 2026-03-04
- **결정**: 초대 코드 기반 가입, 사용자별 API 키/전략/주문 완전 격리
- **이유**: 가족 공유 필요, 오픈 가입은 보안 위험. 각자 본인 키움 계좌 사용으로 자연스러운 격리
- **대안**: 단일 사용자 → 확장성 부족

## ADR-004: 프로세스 분리 (FastAPI + Trading Engine)
- **일자**: 2026-03-04
- **결정**: FastAPI(웹 API/WebSocket)와 Trading Engine(매매 엔진)을 별도 프로세스로 실행
- **이유**: 웹 요청이 매매 로직을 블로킹하지 않도록 격리. 독립 재시작 가능
- **대안**: 단일 프로세스 → 웹 장애 시 매매도 중단

## ADR-005: 메시지 큐 전략 (asyncio.Queue -> Redis Streams)
- **일자**: 2026-03-04
- **결정**: Phase 1 asyncio.Queue, Phase 2 Redis Streams. Kafka 불사용
- **이유**: API 제한(~20/sec)이 병목이므로 Kafka(100만+/sec)는 과잉. asyncio.Queue로 시작하고 프로세스간 통신 필요시 Redis Streams로 전환
- **대안**: Kafka → 리소스 과잉, 운영 복잡도 증가

## ADR-006: 배포 방식 (로컬 Mac Docker + Cloudflare Tunnel)
- **일자**: 2026-03-04
- **결정**: 로컬 Mac (Apple Silicon) + Docker Compose + Cloudflare Tunnel ($0/월)
- **이유**: Oracle Cloud ARM은 VM 회수 위험, 네트워크 불안정. 로컬 Mac은 안정적이고 Cloudflare Tunnel로 외부 접근 + SSL 자동 처리
- **대안**: Oracle Cloud ARM → 무료지만 회수 위험, keepalive 필요

## ADR-007: 인증 (JWT httpOnly cookie + 초대 코드)
- **일자**: 2026-03-04
- **결정**: JWT를 httpOnly cookie로 전달 + Refresh Token + 초대 코드 기반 가입
- **이유**: httpOnly cookie는 XSS로부터 토큰 보호. SameSite=Lax로 CSRF 방지. 초대 코드로 비인가 가입 차단
- **대안**: Bearer token → XSS에 취약 (localStorage 저장 시)

## ADR-008: 3단계 보안 (Claude 훅 -> pre-commit -> GitHub Actions)
- **일자**: 2026-03-04
- **결정**: 3단계 방어 — Claude Code 훅(시크릿 감지) → pre-commit(gitleaks/bandit) → GitHub Actions(SAST/CVE)
- **이유**: 금융 거래 시스템이므로 다층 보안 필수. 개발 시점부터 배포까지 전 구간 커버
- **대안**: 단일 단계 → 누락 위험

## ADR-009: 브랜치 전략 (claude -> feat/* -> dev -> main)
- **일자**: 2026-03-04
- **결정**: claude(base) → feat/*(기능) → dev(PR 머지) → main(PR 머지, 배포)
- **이유**: claude 브랜치에서 AI 작업, feat/*로 기능 분리, dev에서 통합 테스트, main은 안정 배포만
- **대안**: trunk-based → 소규모 프로젝트에 과잉은 아니지만 안전한 단계별 머지 선호

## ADR-010: 데이터 파이프라인 + AI 매매 확장 설계
- **일자**: 2026-03-04
- **결정**: src/data/ (데이터 파이프라인) + src/ai/ (AI 매매) 모듈 설계. Phase 4-5로 분리, 시기 유동적
- **이유**: 사용자가 데이터 엔지니어이고 향후 AI 기사 분석 기반 자동매매를 원함. 데이터 파이프라인(Phase 4)만 먼저 해도 백테스트/분석에 충분한 가치
- **대안**: Phase 1부터 AI 포함 → 범위 과대, MVP 지연

## ADR-011: 패키지 관리 Poetry / 린터 Ruff / mypy 점진적 strict
- **일자**: 2026-03-04
- **결정**: Poetry(lock 기반 재현), Ruff(all-in-one 린터+포매터), mypy 점진적 strict(SQLAlchemy 모듈 예외)
- **이유**: Poetry는 안정적 의존성 관리, Ruff는 black+isort+flake8 대체로 빠름, mypy strict는 SQLAlchemy async와 충돌 많아 점진적 적용
- **대안**: uv → 빠르지만 아직 성숙도 부족, black+isort → Ruff가 상위호환
