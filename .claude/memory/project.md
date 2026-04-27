# 프로젝트 상태

> **마지막 검토**: 2026-04-27
> **상태**: 전략 재설계 T1~T5 완료 — walk-forward 20종목 통과 0/20 → 파라미터 재조정 후 모의투자 재개 대기
> **작업 디렉토리**: `~/individual/stock/kiwoom-autotrade/`

## 전략 재설계 현황 (2026-04-27)

| 태스크 | PR | 내용 | 상태 |
|--------|-----|------|------|
| T1 | #326 | 백테스트 엔진 무결성 4종 (look-ahead/slippage/MDD/survivorship) | ✅ 완료 |
| T2 | #329 | 52주 신고가 일봉 모멘텀 전략 + walk-forward 엔진 | ✅ 완료 |
| T3 | #327 | 리스크 가드레일 (HWM/cooldown/auto kill_switch) | ✅ 완료 |
| T4 | #325 | 마이크로구조 (지정가/점심차단/동적유니버스) | ✅ 완료 |
| T5 | — | walk-forward 20종목 검증 + ADR 3종 문서화 | ✅ 완료 |

**Walk-forward 결과**: 20종목 기준 통과 0/20 (0%)
- 주요 실패: RR ≥ 2.0 기준 전 종목 미달 (최대 1.3)
- 원인: ATR 4x 익절 + +5% 상한 조합이 대형주에서 avg_win 제한
- 다음 단계: atr_tp_mult 6.0으로 상향 + walk-forward 재검증

**전략 상태**: 모의투자 차단 중 (파라미터 재조정 필요)
**ADR 문서**: design-015/016/017 (`docs/design/`)
**운영 체크리스트**: `docs/operations/strategy-redesign-rollout.md`

## 현재 단계: Phase 2 완료 (전략 고도화 + 스윙 인프라)

### 완료
- [x] .claude/ 설정 구성
- [x] 프로젝트 구조 설계
- [x] 증권사 REST API 리서치 (키움 + 한투 + LS증권) -> `.claude/memory/research-broker-api.md`
- [x] 시스템 설계 v1.1 확정 -> `.claude/memory/design-001-system-v1.md`
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
- [x] API 라우터 전체 구현 (auth, admin, settings, market, account, orders, bot, results, realtime, strategy_config, trading, universe, decisions — 13개 라우터, 51 엔드포인트(HTTP 50 + WS 1))
- [x] 커밋 컨벤션 확립 (ADR-015)
- [x] 테스트 커버리지 정책 확립 — 85%+ (ADR-016)
- [x] Dependabot 유지 결정 (ADR-017)
- [x] 브랜치 보호 규칙 강화 (ADR-018) — main/dev 강제 푸시 금지, 필수 체크
- [x] CI/CD 파이프라인 분리 (ADR-019) — PR 게이트(~40s) + 머지 후 SAST
- [x] 테스트 커버리지 85%+ 달성 — 62개 → 278개 테스트
- [x] 에이전트 팀 아키텍처 수립 (ADR-020) — 9개 역할, 보안총괄자 게이트키퍼

### 현재 상태 (2026-04-22 기준)

#### 매수 0건 진단·복구 현황

| PR | 브랜치 | 내용 | 상태 |
|----|--------|------|------|
| #320 | feat/fix-daily-screening-unpause | daily_screening DAG unpause + params 예약어 버그 수정 | open |
| #321 | feat/fix-stocks-theme-backfill | stocks.theme 백필 (매수 0건 근본원인) | open |
| #322 | feat/fix-live-trader-order-persist | orders/trade_logs DB persist 브릿지 (ADR-014) | open |

**단일 근본원인**: `stocks.theme` 100% NULL → ThemeDetector cold 차단 → 매수 신호 99.9996% 차단

**Phase 1 복구**: 위 3 PR 머지로 완료 예정

**Phase 2 미착수**:
- design-013 PR 9: `_assign_symbol_strategies` 가중치 분배
- LLM decision schema → SUPPORTED_DECISION_TYPES 정렬

### 현재 상태 (2026-04-20 기준, 구 버전 참조)
- **테스트**: 1,182개 통과 (백엔드, CI 실측) + 203개 수집 (Airflow 로컬 `pytest --collect-only`), 커버리지 90.23% (CI PR #240 실측)
- **GitHub Actions**: PR 체크 5개 (lint + test + security) + 머지 후 2개 (SAST)
- **main/dev/claude**: dev/claude는 PR #241까지, main은 PR #228까지 — dev→main 배치 병합 대기 (PR #230~#241 미반영)
- **패키지 매니저**: uv (Poetry에서 전환, PEP 621)
- **Airflow**: 3.1.8 (docker-compose, DAG 10개, 수집기 9개, LLM provider 2개(anthropic/openai))
  - DAG: data_collection, llm_briefing, trade_review, param_adjustment, news_collection, macro_weekly, stock_master_sync, analysis, index_collection, rebalance
  - 수집기: dart, ecos, fred, investor_flow, krx, news, overseas, storage, vkospi
  - LLM provider: anthropic, openai (Gemini는 Task T3에서 구현 중 — 아직 제공자 미탑재)
- **Docker**: root docker-compose.yml (postgres+backend+frontend+airflow 통합)
- **작업 디렉토리**: `~/individual/stock/kiwoom-autotrade/` (2026-03-14 이동 완료)
- **cron**: 월~금 08:30 자동 실행 + 공휴일 스킵, KIWOOM_HOME 환경변수 사용
- **인프라 레포**: `~/individual/stock/kiwoom-infra/` 디렉토리 생성 (Phase 3 후 구현)
- **자동매매**: live_trader.py 웹 제어 가능 (ProcessManager + kill_switch 파일 연동)
- **Phase 1 리스크 관리**: ✅ 전체 구현 완료 (PR #125, #129~#134)
- **Phase 2 전략 고도화**: ✅ 전체 완료 (PR #137~#143)
  - ADX 변동성 분류 + 전략별 자금 버킷
  - 스크리닝 보너스 조건 + 장중 동적 유니버스 (10시/11시)
  - 스윙 인프라 — overnight 보유 + 갭 리스크(-3%) + 보유 기간 5일 제한
- **Phase 3 데이터+AI**: 3-DB~3-7 구현 완료, 3-8 텔레그램 양방향 미시작
  - DB: market_data, news_articles, strategy_config, strategy_config_suggestions 테이블
  - Kill Switch: DrawdownGuard(기존) + KillSwitch(soft/hard stop) 분리
  - LLM: Claude→GPT fallback 클라이언트 (provider 2개. Gemini는 Task T3 구현 중)
  - 장전 브리핑 + 장후 리뷰 + 파라미터 자동 조정 제안
  - 전략 설정 API + 프론트엔드 /strategy-config 페이지
  - Airflow 3.x Docker Compose 전면 호환 완료 (PR #183~#184)
  - full-review CRITICAL 전체 완료: B-C01~C04, F-C01~C04, A-C03, D-C01/C02
  - news_collection DAG 버그 수정 (save_news_articles 컬럼 매핑 오류) + 81건 저장 확인
  - decisions-pending.md #21 완료: stocks/stock_relations 테이블 + 마이그레이션 005/006 + stock_master_sync DAG (PR #185/#186)
- **인프라 정리**: Docker Compose 통합 완료
- **전략 v2.0**: 이중 전략(단타/스윙) + 그리드서치 구현 완료
- **프론트엔드**: 10페이지 완료 + 캔들차트 + Bot 웹 제어 + 실시간 로그
- **텔레그램**: 단방향 알림 완료 (매수/매도/요약/에러)
- **스크리닝**: 유니버스 140종목 (PR #234), 테마/섹터 SECTOR_MAP 15테마

### Phase 2 고도화 상태 (정확히)

```
Phase 2: 수급/테마 시그널 — PR #232 병합(모듈+테스트) 완료.
⚠️ scripts/live_trader.py에 FlowSignal/ThemeDetector import 0회,
MarketContext의 get_investor_flow/get_theme_scores 미호출.
실매매 경로 통합은 Task T2-A/B/C/D에서 처리 예정.
```

### 최근 PR 이력 (dev 머지, 2026-04-17~2026-04-20)

| PR | 제목 | 머지 SHA |
|----|------|----------|
| #241 | fix(ci): security.yml action 버전 복구 (@v6 → @v4/@v5) | `e3c615d` |
| #240 | feat(screening): 스크리닝 파라미터 DB 유동화 (threshold/volume_ratio/min_stocks) | `14b715a` |
| #239 | fix(market_context): VKOSPI/KOSPI None 값 방어 | `b485105` |
| #238 | fix(live_trader): 재스크리닝 WS 구독 실패 버그 수정 | `2293546` |
| #237 | fix(compose): airflow-common anchor에 data 볼륨 통합 | `d82ceef` |
| #236 | test(refactor): boilerplate 테스트 48개 축소 (1,201 → 1,153) | `85a9db9` |
| #235 | fix(scripts, trading): UTF-16 서로게이트 페어 교체 + is_cache_stale() 미갱신 오탐 수정 | `6f7dbd3` |
| #234 | feat(screening): 종목 유니버스 55 → 140개 확장 | `8587419` |
| #233 | fix(infra): 로컬 환경 + 봇 프로세스 버그 수정 | `7f14384` |
| #232 | feat(strategy/airflow): Phase2 — 수급 시그널·테마 감지·DAG 확장 | `4295fff` |
| #230 | feat(phase1): 데이터 파이프라인 연결 + 장중 레짐 갱신 | `80f0caa` |

### 최종 목표 & 로드맵

**메인 머지 조건**: 백엔드 완성 + 프론트엔드 완료 + 테스트 85%+

**즉시 — Phase 1 긴급 패치 (완료: 2026-03-13)** ✅
- [x] 대시보드 잔고 0원 버그 수정 3건
- [x] 백테스트 --days 3→60 수정
- [x] CORS 화이트리스트 명시 + CI pytest+ruff 자동화
- [x] 프론트엔드 API 타임아웃 + WebSocket 재연결 로직
- [x] 이중 전략 시스템 (grid_search.py) + 유니버스 66종목 확장
- [x] 모의투자 API 호환 + OrderSide 소문자 통일 + Enum DB 매핑
- [x] 키움 API 버그 4건 + 에러 로깅 강화
- [x] momentum.py 진입 필터 복구 (PR #125)
- [x] volume_ratio 기본값 1.5 복원 (PR #125)
- [x] 단계적 리스크 관리 — 2연패 50% 축소, 3연패 블랙리스트 (PR #131)
- [x] ATR 기반 동적 SL/TP + 변동성 필터 (PR #131)
- [x] 테마별 포지션 제한 — 섹터당 1개 (PR #131)
- [x] kill_switch 통합 — 일간 -2% 매수중단, -3% 전량청산 (PR #131)
- [x] 거래세 0.20% + force_close 15:15 통일 (PR #131, #133)
- [x] WebSocket HTTPS 프로토콜 자동감지 (PR #129)

**단기 — Phase 2 전략 고도화 (1-2주)**
- [x] 변동성 기반 전략 자동 분류 (PR #137)
- [x] ADX 계산기 + 전략 분류 고도화 (PR #137)
- [x] 전략별 자금 버킷 (PR #138)
- [x] 스크리닝 강화 (PR #139)
- [x] 장중 동적 유니버스 (PR #140)
- [x] 스윙 인프라 (PR #142) — overnight 보유 + 갭 리스크(-3%) + 보유 기간 5일 제한

**중기 — Phase 3 데이터+AI 레이어** (오케스트레이터: Airflow 3.1.8, 패키지: uv)
- [x] 3-1: Airflow 로컬 환경 구축 (PR #147)
- [x] 3-2: Tier 1 수집기 — DART, pykrx, FRED, ECOS (PR #147)
- [x] 3-3: 장전 데이터 수집 DAG + overseas + storage (PR #149)
- [x] 3-5: 뉴스 수집 파이프라인 — 네이버 뉴스 + 감성 분류 (PR #149)
- [x] 3-DB: DB 테이블 + 전략 설정 API + Kill Switch 리팩토링 (soft/hard stop)
- [x] 3-4: LLM 브리핑 (Claude→GPT→Gemini fallback)
- [x] 3-6: 장후 매매 리뷰 DAG
- [x] 3-7: 파라미터 자동 조정 제안 (LLM→웹 승인→적용) + 프론트 UI
- [ ] 3-8: 텔레그램 양방향 통신 — design-006-telegram.md

**Phase 3 완료 후 → 인프라 정리**
- [x] Docker Compose 통합 (백엔드 + 프론트 + DB + Airflow)
- [ ] EKS 배포 (kiwoom-infra 레포)
- [ ] CI/CD 연결

**상세 설계**: `design-005-data-pipeline.md`

### Phase 2 진행 상태
| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 8 | WebSocket 실시간 시세 | ✅ 완료 | PR #106~#110, 스펙 준수 재작성 + Contract Test |
| 9 | 캔들차트 + 호가창 | 🔶 부분 | 호가창 UI 있음, recharts 차트 추가됨 |
| 10 | 자동매매 엔진 (2전략 병행) | ✅ 완료 | 모멘텀+평균회귀, 백테스트+스크리닝+cron |
| 11 | APScheduler 장 시간 관리 | 🔶 부분 | cron 기반 구현 (APScheduler 미사용) |
| 12 | 텔레그램 알림 (단방향) | ✅ 완료 | PR #101, 매수/매도/요약/에러 |
| 12b | 텔레그램 양방향 (LLM 연동) | ❌ 미시작 | Phase 2-3, design-006-telegram.md |
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
| Frontend | Next.js 16.1.6 / TypeScript / Tailwind CSS / ShadCN UI |
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
- 시스템 설계: `.claude/memory/design-001-system-v1.md`
- 아키텍처 결정: `.claude/memory/architecture.md`
- 증권사 API 리서치: `.claude/memory/research-broker-api.md`
