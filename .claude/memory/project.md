# 프로젝트 상태

> **마지막 검토**: 2026-03-12
> **상태**: Phase 1 MVP 운영 중, 백엔드 완성 단계

## 현재 단계: Phase 1 (MVP 백엔드 구현 완료, 테스트 85%+ 달성)

### 완료
- [x] .claude/ 설정 구성
- [x] 프로젝트 구조 설계
- [x] 증권사 REST API 리서치 (키움 + 한투 + LS증권) -> `.claude/memory/research-broker-api.md`
- [x] 시스템 설계 v1.1 확정 -> `.claude/memory/design-v1.1.md`
- [x] 아키텍처 결정 기록 (ADR-001~020) -> `.claude/memory/architecture.md`
- [x] 보안 3단계 방어 구축 (Claude 훅 + pre-commit + GitHub Actions)
- [x] 브랜치 전략 확정 (claude -> feat/* -> dev(PR) -> main(PR))
- [x] 프로젝트 디렉토리 구조 생성 (src/, tests/, scripts/, alembic/, frontend/)
- [x] 보안 훅 검증 및 수정 (시크릿 패턴 강화, .env 읽기 차단, NotebookEdit 추가)
- [x] 활동 로깅 훅 추가 (PostToolUse, 민감정보 마스킹)
- [x] .env.example 모의/실투자 분리 키 반영
- [x] .gitignore 보강 (Node.js, Docker, 활동로그, poetry.lock 커밋)
- [x] FastAPI 앱 기본 세팅 + DB 연결
- [x] 사용자 인증 (JWT httpOnly cookie + 초대 기반 가입)
- [x] 키움 모의투자 API 연동 (인증/토큰 관리, BrokerClient Protocol 추상화)
- [x] 시세 조회 (REST) — 현재가, 호가
- [x] 주문 실행 (매수/매도/취소, 상태 머신 9개 상태)
- [x] Kill Switch 기본 구현 (3단계: 주문별/전략별/사용자별)
- [x] LLM 자동매매 엔진 구현 (ai/engine.py — AIEngine 클래스, 분석·시그널·주문 파이프라인) ← **Phase 5에서 승격**, bot.py API 연동은 단기 TODO
- [x] API 라우터 전체 구현 (auth, admin, settings, market, account, orders, bot, results, realtime — 9개 라우터, 14+ 엔드포인트)
- [x] 커밋 컨벤션 확립 (ADR-015)
- [x] 테스트 커버리지 정책 확립 — 85%+ (ADR-016)
- [x] Dependabot 유지 결정 (ADR-017)
- [x] 브랜치 보호 규칙 강화 (ADR-018) — main/dev 강제 푸시 금지, 필수 체크
- [x] CI/CD 파이프라인 분리 (ADR-019) — PR 게이트(~40s) + 머지 후 SAST
- [x] 테스트 커버리지 85%+ 달성 — 62개 → 278개 테스트
- [x] 에이전트 팀 아키텍처 수립 (ADR-020) — 9개 역할, 보안총괄자 게이트키퍼

### 현재 상태 (2026-03-12 세션 20 종료 기준)
- **테스트**: 689개 통과, 커버리지 94.06%
- **GitHub Actions**: PR 체크 4개 (lint + test + security) + 머지 후 2개 (SAST)
- **main/dev/claude**: PR #112까지 싱크 완료
- **alembic**: 002_broker_token_cache 마이그레이션 적용 완료 (로컬 DB)
- **Ruff**: 0 errors
- **cron**: 월~금 08:30 자동 실행 + 공휴일 스킵
- **자동매매**: live_trader.py 운영 중 (모멘텀 + 평균회귀 2전략 병행, WebSocket 모드 기본)
- **프론트엔드**: 7페이지 완료 + 실시간 시세 UI + API 타임아웃(10s) + WS 재연결(exp backoff)
- **텔레그램**: 단방향 알림 완료 (매수/매도/요약/에러)
- **WebSocket**: 4단계 전체 완료 + 키움 스펙 준수 재작성 (PR #110, Contract Test 22개)
- **Contract Test**: fixture 13개 + contract test 22개 (tests/fixtures/kiwoom/websocket/)
- **버그 수정**: 대시보드 잔고 0원 근본 원인 3건 수정 (return_code 에러 감지, 토큰 8005 재시도, kt00018 기반 금액 계산), 백테스트 --days 3→60
- **보안 강화**: CORS allow_methods/allow_headers 화이트리스트 명시
- **CI 강화**: test.yml 추가 (ruff lint/format + pytest --cov-fail-under=85)

### 최종 목표 & 로드맵

**메인 머지 조건**: 백엔드 완성 + 프론트엔드 완료 + 테스트 85%+

**즉시 (목표: 3/12 목요일)**
- [x] 대시보드 잔고 0원 버그 수정 3건 (return_code 감지, 토큰 8005 재시도, kt00018 기반 금액 계산)
- [x] 백테스트 --days 3→60 수정 (기술지표 계산 불가 해결)
- [x] CORS 화이트리스트 명시 (보안 강화)
- [x] CI pytest+ruff 자동화 추가 (test.yml)
- [x] 프론트엔드 API 타임아웃 + WebSocket 재연결 로직
- [ ] 크론 정상 동작 확인 (08:30 자동 실행 + 텔레그램 알림 수신)

**단기 (이번 주)**
- [ ] auth.py 핵심 경로 100%
- [ ] ai/engine.py → bot.py API 연동 (LLM 전략 활성화)
- [ ] ai/engine.py 테스트 85%+ (현재 coverage omit 처리)
- [ ] volume_ratio Grade A/B 분리 로깅
- [ ] WebSocket 전환 후 텔레그램 알림 정상 동작 확인

**중기 (1-2주)**
- [ ] LLM shadow mode
- [ ] 동일 종목 중복 보유 금지

**장기 (모의투자 중반 이후)**
- [ ] 텔레그램 양방향 통신 (사용자 → LLM → 전략 수정 → 매매) — design-telegram-bidirectional.md
- [ ] 트레일링 스탑
- [ ] 종목 유니버스 동적 업데이트

### Phase 2 진행 상태
| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 8 | WebSocket 실시간 시세 | ✅ 완료 | PR #106~#110, 스펙 준수 재작성 + Contract Test |
| 9 | 캔들차트 + 호가창 | 🔶 부분 | 호가창 UI 있음, recharts 차트 추가됨 |
| 10 | 자동매매 엔진 (2전략 병행) | ✅ 완료 | 모멘텀+평균회귀, 백테스트+스크리닝+cron |
| 11 | APScheduler 장 시간 관리 | 🔶 부분 | cron 기반 구현 (APScheduler 미사용) |
| 12 | 텔레그램 알림 (단방향) | ✅ 완료 | PR #101, 매수/매도/요약/에러 |
| 12b | 텔레그램 양방향 (LLM 연동) | ❌ 미시작 | Phase 2-3, design-telegram-bidirectional.md |
| 13 | 한국 시장 규칙 (T+2, VI, 공휴일) | ✅ 완료 | 가격제한 체크 + 공휴일 스킵 |

### Phase 2 외 완료된 추가 작업 (Phase 1 → 2 전환 중)
- [x] ADR-022: 사용자별 DB 자격증명 기반 KiwoomClient 전환 (PR #42)
- [x] 주문 API KiwoomClient 실제 브로커 연동 (PR #46)
- [x] 키움 API 파싱 버그 5건 수정 (PR #48) — 모의투자 실계좌 정상 동작 확인
- [x] Settings UX: API 키 삭제, 중복 등록 방지, created_at 노출 (PR #49)
- [x] 에러 처리 일관성: HTTPException→AppError 통일, 에러 타입별 UI 안내 (PR #51)
- [x] 토큰 DB 캐시: 동시 요청 레이스 컨디션(BrokerAuthError) 해결, Double-Check Locking (PR #52)
- [x] NO_CREDENTIALS 에러 코드: API 키 미등록 시 정확한 메시지 표시 (PR #52)
- [x] Enter 키 중복 요청 방어 (PR #52)
- [x] 프론트엔드 인증 미들웨어 + 전 페이지 UX (PR #38, #40)

### 기술 스택 (확정)
| 계층 | 기술 |
|------|------|
| Backend | FastAPI / Python 3.12 (Uvicorn 1 worker async) |
| Frontend | Next.js 14+ / TypeScript / Tailwind CSS / ShadCN UI |
| DB | PostgreSQL 17 (로컬 Homebrew) |
| ORM | SQLAlchemy 2.0 (async) |
| HTTP | httpx (async) |
| 키움 API | BrokerClient Protocol 래핑 |
| 인증 | JWT httpOnly cookie + Refresh Token + 초대 코드 |
| 스케줄러 | cron (현재) / APScheduler (향후 통합 예정) |
| 알림 | Telegram Bot |
| 메시지 큐 | Phase 1: asyncio.Queue -> Phase 2: Redis Streams |
| 배포 | 로컬 Mac (Apple Silicon) + Cloudflare Tunnel |
| SSL | Cloudflare Tunnel (자동) |
| CI/CD | GitHub Actions |
| 로깅 | structlog (JSON) |

### 배포 방식
- **개발**: PostgreSQL 로컬 (Homebrew), Python/Next.js 네이티브
- **프로덕션**: 로컬 Mac (Apple Silicon) + Docker Compose
- **외부 접근**: Cloudflare Tunnel (HTTPS 자동, $0/월)
- **비용**: $0/월

### 브랜치 전략
```
claude (base) -> feat/* (기능 개발) -> dev (PR 머지) -> main (PR 머지, 배포)
```

### 참조 문서
- 시스템 설계: `.claude/memory/design-v1.1.md`
- 아키텍처 결정: `.claude/memory/architecture.md`
- 증권사 API 리서치: `.claude/memory/research-broker-api.md`
