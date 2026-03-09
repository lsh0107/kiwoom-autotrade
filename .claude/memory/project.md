# 프로젝트 상태

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
- [x] LLM 자동매매 엔진 (실시간 분석 → 매수/매도 판단 → 주문) ← **Phase 5에서 승격**
- [x] API 라우터 전체 구현 (auth, admin, settings, market, account, orders, bot — 14+ 엔드포인트)
- [x] 커밋 컨벤션 확립 (ADR-015)
- [x] 테스트 커버리지 정책 확립 — 85%+ (ADR-016)
- [x] Dependabot 유지 결정 (ADR-017)
- [x] 브랜치 보호 규칙 강화 (ADR-018) — main/dev 강제 푸시 금지, 필수 체크
- [x] CI/CD 파이프라인 분리 (ADR-019) — PR 게이트(~40s) + 머지 후 SAST
- [x] 테스트 커버리지 85%+ 달성 — 62개 → 278개 테스트
- [x] 에이전트 팀 아키텍처 수립 (ADR-020) — 9개 역할, 보안총괄자 게이트키퍼

### 현재 상태 (2026-03-09 세션 3 종료 기준)
- **테스트**: 379개 통과, 커버리지 87%
- **GitHub Actions**: PR 체크 3개 (~40s) + 머지 후 2개 (SAST)
- **main/dev/claude**: PR #55까지 전부 싱크 완료
- **alembic**: 002_broker_token_cache 마이그레이션 적용 완료 (로컬 DB)
- **Ruff**: 0 errors
- **cron**: 월~금 09:05 자동 실행 등록 (`crontab -l`로 확인)
- **자동매매**: live_trader.py 구현 완료, 다음 거래일 첫 실행 예정

### 다음 세션 시작 순서 (MANDATORY)
1. **거래일 결과 확인**: docs/backtest-results/ 에서 screened/backtest/live JSON 확인
2. **결과 분석**: strategy-momentum.md 결과 테이블 갱신
3. **파라미터 튜닝**: 백테스트 + 모의매매 결과 기반 조정
4. **decisions-pending.md #11~14 확정**

### Phase 2 진행 상태
| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 8 | WebSocket 실시간 시세 | ❌ 미시작 | |
| 9 | 캔들차트 + 호가창 | 🔶 부분 | 호가창 UI 있음, 차트 없음 |
| 10 | 자동매매 엔진 (기본 전략 1개) | ✅ 완료 | 백테스트+스크리닝+라이브트레이더+cron |
| 11 | APScheduler 장 시간 관리 | 🔶 부분 | cron 기반 구현 (APScheduler 미사용) |
| 12 | 텔레그램 알림 | ❌ 미시작 | |
| 13 | 한국 시장 규칙 (T+2, VI, 공휴일) | 🔶 부분 | 가격제한 체크 있음, 공휴일 미체크 |

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
| 스케줄러 | APScheduler |
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
