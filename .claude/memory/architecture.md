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

## ADR-012: LLM 자동매매를 Phase 1으로 승격 (ADR-010 개정)
- **일자**: 2026-03-04
- **결정**: LLM 기반 자동매매를 Phase 5에서 Phase 1으로 승격. ADR-010의 "Phase 1부터 AI 포함 → 범위 과대" 판단을 개정
- **이유**: 사용자가 LLM 실시간 분석 → 자동 매수/매도를 핵심 기능으로 요청. 범위를 "LLM 투자 판단 → 주문 실행"으로 한정하여 MVP 지연 최소화. 데이터 파이프라인(Phase 4)과 ML 모델(Phase 5)은 여전히 후순위
- **범위 제한**: Phase 1에서는 LLM API 호출 → 시세/공시 분석 → 매매 시그널 생성까지만. 자체 ML 모델 학습, 뉴스 크롤링 파이프라인 등은 Phase 4-5 유지
- **대안**: 원래 계획대로 Phase 5 → 사용자의 핵심 니즈를 너무 늦게 구현

## ADR-013: 기술 스택 선택 근거
- **일자**: 2026-03-04
- **상태**: 확정
- **결정**: 아래 기술 스택을 프로젝트 전반에 걸쳐 사용
- **근거**: 각 도구/라이브러리 선택의 핵심 이유를 정리

| 기술 | 선택 이유 |
|------|-----------|
| **Python 3.12** | PEP 669 저비용 모니터링으로 런타임 성능 개선, PEP 695 `type` 구문으로 type hint 완성도 향상, 에러 메시지 개선(디버깅 생산성), f-string 개선, LTS 안정성 확보 |
| **FastAPI** | 비동기 네이티브(ASGI)로 금융 API 저레이턴시 처리, Pydantic 통합으로 요청/응답 자동 검증, 자동 OpenAPI 문서 생성, 타입 안전성 극대화 |
| **SQLAlchemy 2.0 async** | ORM + 타입 안전성(mapped_column), async session으로 DB I/O 블로킹 방지, PostgreSQL JSONB 네이티브 지원, 다중 DB 호환(테스트 SQLite ↔ 프로덕션 PostgreSQL) |
| **asyncpg** | PostgreSQL async 드라이버 중 최고 성능(C 확장 기반), SQLAlchemy 2.0 async 공식 지원 드라이버, prepared statement 캐싱 |
| **PostgreSQL** | JSONB(전략 config, 거래 상세 저장), UUID 네이티브 타입, ACID 트랜잭션으로 금융 데이터 무결성 보장, 파티셔닝(시계열 거래 데이터) |
| **httpx** | async/sync 듀얼 모드 지원, requests 호환 API(마이그레이션 용이), HTTP/2 지원, respx로 테스트 mock 용이 |
| **Pydantic v2** | Rust 코어(pydantic-core)로 v1 대비 5~50배 성능, 입력 검증 + JSON 직렬화 통합, FastAPI 네이티브 통합, EmailStr 등 금융 도메인 검증 타입 |
| **structlog** | 구조화된 JSON 로깅(ELK/Loki 연동 용이), 비동기 지원(ainfo/awarning), 컨텍스트 바인딩(user_id, order_id 추적), 감사 추적(audit trail) 필수 |
| **Poetry** | lock 파일 기반 재현 가능한 빌드, 그룹별 의존성 분리(dev/prod), pyproject.toml 단일 설정 파일로 관리 통합 |
| **Ruff** | Rust 기반 초고속(flake8+isort+black 올인원 대체), pyproject.toml 통합 설정, 300+ 린트 규칙, 포매터 내장 |
| **APScheduler** | 장 시간 기반 cron 스케줄링(09:00 장 시작, 15:30 장 마감), asyncio 네이티브 지원, 단일 프로세스 내 통합(별도 Celery 불필요) |
| **bcrypt (직접)** | passlib이 bcrypt 5.0+과 호환 깨짐(`__about__` 제거), bcrypt 직접 사용으로 의존성 단순화, 비밀번호 해싱 성능 동일 |
| **python-jose** | JWT 생성/검증 표준 구현, cryptography 백엔드로 보안 강화, httpOnly cookie 기반 인증과 조합 |
| **Fernet (cryptography)** | AES-256-CBC 대칭 암호화, 브로커 API 키/시크릿 DB 저장 시 암호화, 키 관리 단순(단일 FERNET_KEY), 타임스탬프 기반 만료 지원 |
| **aiolimiter** | 비동기 토큰 버킷 레이트 리미터, 키움 API 호출 제한 준수(모의 5/s, 실거래 20/s), asyncio.Lock 기반 경합 방지 |
| **SQLite (테스트)** | 인메모리(`sqlite+aiosqlite://`)로 테스트 초고속, 외부 DB 의존성 없이 CI 실행, aiosqlite로 async 호환, 범용 타입으로 PostgreSQL과 코드 공유 |
| **respx** | httpx 전용 mock 라이브러리, 키움 API 응답 시뮬레이션, 네트워크 격리 테스트로 외부 의존 제거, 패턴 매칭 라우팅 |

## ADR-014: 설계 논의 — 반대 의견 및 근거 기록
- **일자**: 2026-03-04
- **상태**: 확정
- **목적**: 사용자 제안에 대해 다른 방향을 권고한 경우, 그 근거와 레퍼런스를 기록

### 논의 1: "멀티프로세싱을 쓰면 안 되나?" (asyncio vs multiprocessing)

- **사용자 의견**: I/O 작업에 비동기 처리, CPU 바운드에는 멀티프로세싱을 쓰면 되지 않나?
- **권고**: 현재 MVP에서는 단일 프로세스 asyncio만으로 충분. 멀티프로세싱 불필요.
- **이유**:
  1. **현재 작업 100%가 I/O 바운드**: DB 쿼리(asyncpg), 키움 API(httpx), LLM API(httpx) — 모두 네트워크 대기. CPU 연산 병목 없음
  2. **키움 API 자체가 병목**: 모의투자 5req/s, 실거래 20req/s 제한. 아무리 프로세스를 늘려도 API 레이트 리밋이 상한
  3. **공유 상태 복잡도**: 멀티프로세싱은 Kill Switch 상태, 포지션 상태 등 공유 데이터 관리가 어려움 (IPC, 락, 직렬화 필요)
  4. **APScheduler 중복 실행**: 여러 프로세스에서 스케줄러가 동시에 돌면 동일 주문이 중복 실행됨
- **사용자 의견이 맞는 시점**: Phase 2에서 ML 모델 학습, 대량 백테스트 등 CPU 바운드 작업이 생기면 `ProcessPoolExecutor` 또는 별도 프로세스 분리 필요
- **레퍼런스**:
  - [Python asyncio docs — "asyncio is used as a foundation for multiple Python asynchronous frameworks that provide high-performance network and web-servers"](https://docs.python.org/3.12/library/asyncio.html)
  - [FastAPI Concurrency — "if your application doesn't need to communicate with anything else and wait for it to respond, use normal def"](https://fastapi.tiangolo.com/async/#very-technical-details)
  - [uvicorn 공식 — "For production deployment, use --workers for multiprocess scaling"](https://www.uvicorn.org/deployment/)
  - yfinance 같은 동기 라이브러리는 `asyncio.to_thread()`로 감싸면 이벤트 루프 블로킹 없이 동작 ([Python docs run_in_executor](https://docs.python.org/3.12/library/asyncio-eventloop.html#asyncio.loop.run_in_executor))

### 논의 2: "ORM 대신 커넥션을 연 이유가 있나?"

- **사용자 의견**: conftest.py에서 `engine.begin() as conn` + `conn.run_sync()`를 사용하는데, ORM 세션으로 통일해야 하지 않나?
- **권고**: DDL(create_all/drop_all)은 ORM 세션이 아니라 커넥션/엔진 레벨 작업이므로 현재 방식이 올바름
- **이유**:
  1. `Base.metadata.create_all()`은 **MetaData 레벨** 작업 — ORM 세션(Unit of Work 패턴)이 아닌 DDL 명령 직접 실행
  2. SQLAlchemy async에서 DDL은 `run_sync()` 래퍼가 필수 — 동기 API를 async 커넥션 안에서 실행
  3. 실제 데이터 CRUD는 모두 `db` fixture (ORM 세션)을 사용하므로 ORM 원칙 준수
- **사용자 의견이 맞는 시점**: 만약 Alembic 마이그레이션으로 테이블을 생성한다면 커넥션 직접 사용을 피할 수 있음. 하지만 인메모리 SQLite 테스트에서는 create_all이 표준 패턴
- **레퍼런스**:
  - [SQLAlchemy 2.0 async docs — "create_all() method is a sync API, use run_sync()"](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#synopsis-core)
  - [SQLAlchemy MetaData.create_all — "issues CREATE statements for all tables... this is a DDL operation"](https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.MetaData.create_all)
  - [pytest-asyncio SQLAlchemy example — 공식 예제에서도 engine.begin() + run_sync 사용](https://github.com/sqlalchemy/sqlalchemy/blob/main/examples/asyncio/async_orm.py)

### 논의 3: "PostgreSQL 종속 타입 vs 범용 타입"

- **사용자 의견**: 로컬 백엔드(SQLite 테스트)와 Docker PostgreSQL 프로덕션이 호환되어야 한다
- **권고 수정**: 사용자 의견이 올바름. `postgresql.UUID` → `sqlalchemy.Uuid`, `JSONB` → `JSON`으로 변경
- **이유**:
  1. `sqlalchemy.dialects.postgresql.UUID`는 SQLite에서 CHAR(32)로 자동 fallback되지만, 명시적으로 범용 `sqlalchemy.Uuid`를 쓰는 것이 의도가 명확
  2. `JSONB`는 SQLite에서 지원 안 됨 → monkey-patch 필요했으나, `JSON`으로 바꾸면 패치 불필요
  3. 프로덕션에서 JSONB 성능이 필요하면 Alembic 마이그레이션에서 컬럼 타입만 지정하면 됨 (ORM 코드 변경 없음)
- **원래 접근이 틀렸던 이유**: `postgresql.JSONB`를 ORM에 하드코딩하면 모든 테스트 환경에서 monkey-patch가 필요해지고, CI에서도 PostgreSQL이 필요해질 수 있음. 추상화 레이어를 깨는 것
- **레퍼런스**:
  - [SQLAlchemy 2.0 Uuid type — "generic UUID type, selects an appropriate implementation for the backend in use"](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Uuid)
  - [SQLAlchemy JSON vs JSONB — "JSON type provides a generic JSON that works across backends"](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON)

## ADR-015: 커밋 컨벤션 확립
- **일자**: 2026-03-04
- **상태**: 확정
- **결정**: Conventional Commits + 한글 설명 + 논리적 스테이징
- **이유**: GitHub 이력 가독성, 변경사항 추적 용이
- **규칙**:
  - 형식: `feat(모듈): 한글 설명` (타입: feat, fix, refactor, test, docs, chore, ci)
  - `git add .` / `git add -A` 사용 금지 — 논리적 단위로 파일 스테이징
  - Co-Authored-By, Generated with Claude Code 등 자동 생성 문구 삽입 금지
  - 하나의 커밋에 하나의 관심사만 포함

## ADR-016: 테스트 커버리지 정책
- **일자**: 2026-03-04
- **상태**: 확정
- **결정**: 최소 85% 커버리지 유지
- **이유**: 금융 거래 시스템 안정성 보장. 주문/Kill Switch 등 핵심 모듈은 90%+ 권장
- **적용**:
  - 85% 미만이면 커밋/PR 생성 금지
  - 모든 PR에 테스트 포함 필수
  - 미사용/미래 구현 모듈은 커버리지 계산에서 제외 허용
  - QA 에이전트를 항상 활성화하여 테스트 검증

## ADR-017: Dependabot 유지
- **일자**: 2026-03-04
- **상태**: 확정
- **결정**: .github/dependabot.yml 유지
- **이유**: 보안 취약점 자동 감지, pip/github-actions 주간 스캔
- **범위**: pip 의존성 + GitHub Actions 버전 — 주간 자동 PR 생성

## ADR-018: 브랜치 보호 규칙
- **일자**: 2026-03-05
- **상태**: 확정
- **결정**: main/dev 브랜치 강제 푸시 금지, 필수 상태 체크 설정
- **설정**:
  - `allow_force_pushes: false` — 강제 푸시 금지
  - `allow_deletions: false` — 브랜치 삭제 금지
  - `enforce_admins: true` — admin도 규칙 우회 불가
  - `dismiss_stale_reviews: true` — 코드 변경 시 이전 리뷰 무효
  - `required_conversation_resolution: true` — 대화 해결 필수
  - `strict: true` — base와 최신 상태 아니면 머지 불가
- **필수 상태 체크 (PR)**: Secret Detection, TruffleHog Deep Scan, Dependency Audit
- **이유**: 금융 거래 시스템, 보안 사고 방지 최우선

## ADR-019: CI/CD 파이프라인 분리 전략
- **일자**: 2026-03-05
- **상태**: 확정
- **결정**: PR 체크와 머지 후 분석을 분리하여 중복 실행 제거 + 속도 최적화
- **이전 문제**: 동일 체크가 `push`와 `pull_request` 양쪽에서 실행 → 중복
- **새 구조**:

| 단계 | 트리거 | 체크 | 소요 시간 | 목적 |
|------|--------|------|----------|------|
| **PR 게이트** | `pull_request` | Secret Detection | ~10초 | 시크릿 유출 차단 |
| | | TruffleHog Deep Scan | ~10초 | 유효한 키 탐지 |
| | | Dependency Audit | ~40초 | CVE 취약점 차단 |
| **머지 후** | `push` (main/dev) | Bandit SARIF | ~2분 | GitHub Security 탭 업데이트 |
| | | CodeQL Analysis | ~3분 | 심층 SAST 결과 대시보드 |
| **주간** | `schedule` (월 09:00 UTC) | 전체 5개 | - | 정기 전수 스캔 |

- **근거**:
  - PR 체크는 빠른 피드백 필수 (~1분 이내 완료)
  - Bandit/CodeQL은 SARIF 업로드가 목적 → PR 차단용이 아닌 보안 대시보드용
  - 머지된 코드를 또 검사하는 것은 리소스 낭비
  - 실무 기준: CI(PR) = fast gate, CD(merge) = deep analysis
- **레퍼런스**:
  - https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning
  - https://github.blog/developer-skills/github/supercharge-your-ci-cd-pipeline-with-github-actions-best-practices/

## ADR-020: 에이전트 팀 아키텍처
- **일자**: 2026-03-05
- **상태**: 확정
- **결정**: 9개 역할(리드+8에이전트) 온디맨드 팀 구성, 보안총괄자 게이트키퍼 패턴 도입
- **상세**: `.claude/rules/agent-roles.md`

### 왜 9개 역할인가?
- **금융 시스템의 감사 가능성(Auditability)**: 역할 분리 → 누가 무엇을 결정했는지 추적 가능
- **맹점 제거**: 구현자(Backend) ≠ 검증자(QA) ≠ 리뷰어(Reviewer). 같은 에이전트가 구현+테스트하면 동일한 가정을 공유하여 버그를 놓침
- **사용자 부담 최소화**: 보안총괄자가 1차 필터 → 판단 가능한 건 자동 처리 → 사용자에겐 비즈니스 결정만 에스컬레이션

### 트레이드오프
| 장점 | 단점 |
|------|------|
| 역할 명확 → 누락 방지 | 에이전트 수 많음 → spawn 오버헤드 |
| 보안 게이트키퍼 → 사용자 부담 감소 | 보안총괄자 판단 오류 가능성 |
| 병렬 투입 → 속도 향상 | 컨텍스트 분산 → 에이전트 간 정보 공유 비용 |
| QA 분리 → 테스트 품질 향상 | 모든 변경에 QA 필수 → 소규모 수정도 오버헤드 |

### 대안 분석
1. **3~4개 범용 에이전트**: 단순하지만 보안 리뷰 누락 위험. 금융 시스템에서 허용 불가
2. **상시 가동**: 컨텍스트 윈도우 낭비. 온디맨드가 fresh context로 집중도 높음
3. **보안 완전 자동화 (게이트키퍼 없이)**: 판단력 부족. 새로운 유형의 보안 위협에 대응 불가
4. **사용자가 모든 보안 결정**: 사용자 피로도 극대화. "허락해야 할 것"이 너무 많아짐

### 결론
현재 프로젝트 규모(개인~가족)에서 9개 역할은 과도해 보일 수 있으나, 금융 거래 시스템이라는 도메인 특성상 역할 분리의 이점이 오버헤드를 상회한다. 특히 보안총괄자 게이트키퍼는 사용자 경험과 보안의 균형점이다.

## ADR-021: KIS → 키움 REST API 마이그레이션
- **일자**: 2026-03-05
- **상태**: 확정
- **결정**: 한국투자증권(KIS) API 형식으로 임시 구현된 브로커 코드를 실제 키움 REST API 형식으로 전환
- **변경 범위**: constants.py, kiwoom.py, schemas.py, settings.py (전면 재작성), 테스트 전면 재작성
- **이유**:
  - ADR-001에서 키움 REST API 사용이 확정되었으나, 초기 구현 시점에 키움 API 스펙이 없어 KIS API 형식으로 먼저 구현
  - `docs/kiwoom-rest-api/` 레퍼런스(207개 API, 528p PDF 추출)가 완성되어 실제 키움 스펙으로 전환 가능해짐
- **핵심 차이점**:
  | 항목 | KIS (이전) | 키움 (현재) |
  |------|-----------|------------|
  | URL (모의) | `openapivts.koreainvestment.com:29443` | `mockapi.kiwoom.com` |
  | URL (실) | `openapi.koreainvestment.com:9443` | `api.kiwoom.com` |
  | 인증 | `/oauth2/tokenP`, `{appkey, appsecret}` | `/oauth2/token`, `{appkey, secretkey}` |
  | 헤더 | `tr_id`, `appkey`, `appsecret`, `custtype` | `api-id`, `authorization` (2개만) |
  | TR ID | 모의/실 분리 (`VTTC0802U`/`TTTC0802U`) | 동일 (`kt10000`, URL만 다름) |
  | HTTP | GET(시세/잔고) + POST(주문) | 전부 POST |
  | 종목코드 | 6자리 (`005930`) | `KRX:005930` 형식 |
  | 에러 | `rt_cd`, `msg1` | `error_code`, `error_message` |
- **알려진 제한 (Phase 1)**:
  1. `get_quote()` OHLCV 미제공 (ka10007은 종목명+현재가+전일종가만)
  2. 에러 응답 포맷 미검증 (라이브 API 테스트 필요)
  3. 호가 매수호가 필드명 추론 (라이브 검증 필요)
  4. 토큰 `expires_dt` 형식 양쪽 파싱 구현 (검증 필요)
- **대안**: KIS API 유지 → 사용자가 키움 계좌만 보유, KIS 계좌 개설 불필요

## ADR-022: 환경변수 하드코딩 → 사용자별 DB 자격증명 전환
- **일자**: 2026-03-05
- **상태**: 확정
- **결정**: API 라우터(account, market, orders)와 스케줄러에서 환경변수(`settings.kiwoom_app_key` 등) 직접 참조를 제거하고, DB에 저장된 `BrokerCredential`(사용자별 암호화 자격증명)을 FastAPI DI로 주입
- **변경 범위**: deps.py, account.py, market.py, orders.py, scheduler.py
- **이유**:
  - 멀티유저 환경에서 모든 사용자가 동일한 키를 공유하는 구조는 보안/격리 위반
  - ADR-003에서 "사용자별 API 키 완전 격리" 결정했으나 라우터 레벨에서 미적용
  - BrokerCredential 모델, settings CRUD, crypto 유틸은 이미 구현 완료 — 연결만 하면 됨
- **패턴**:
  - `get_broker_credential()` — DB에서 현재 사용자의 활성 자격증명 조회
  - `ActiveBrokerCredential` — FastAPI Annotated 타입 (자동 DI)
  - `_create_kiwoom_client(cred)` — DB 자격증명 → KiwoomClient 팩토리
  - 스케줄러: `strategy.user_id` → `BrokerCredential` 조회 → 클라이언트 생성
- **settings.py 환경변수 프로퍼티**: deprecated 주석 추가, 유지. 라이브 테스트 스크립트에서 사용
- **대안**:
  1. 환경변수 유지 + 사용자별 override → 코드 복잡도 증가, 격리 불완전
  2. 환경변수 완전 제거 → 초기 테스트/셋업 불편. 향후 Phase 2에서 제거 가능
- **트레이드오프**: DB 조회 1회 추가 (매 요청) vs 완전한 사용자 격리. 금융 시스템에서 격리가 우선
