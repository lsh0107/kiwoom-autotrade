# 2026-03 세션 로그 요약

> 압축본. 21개 일별 파일을 통합. 시각별 verbose 작업 로그·자가 점검 루프·중복 entry 제거.

## 주요 마일스톤

- **03-03**: .claude/ 초기 구성, GitHub 레포 생성 (lsh0107/kiwoom-autotrade public), 웹/API/Rate Limit/배포 리서치, 설계 v1 → 전문가 리뷰 6.5/10 → v1.1 확정, 3단계 보안 자동화, 브랜치 전략 (claude→feat/*→dev→main) 확정
- **03-04**: Critical/Warning 일괄 수정 (3개 병렬 에이전트), Python 3.12 + Poetry + Ruff + VSCode 환경, 데이터 파이프라인/AI 매매(Phase 4-5) 설계, Phase 1 백엔드 MVP 거의 완료 (FastAPI + 인증 + 키움 API + 주문 + Kill Switch + LLM 엔진), 테스트 278개 통과 커버리지 85%
- **03-05**: Agent Teams 활성화, 문서 생명주기 규칙 수립, **키움 REST API PDF (528p) → 207 API 자동 인덱싱** (`docs/kiwoom-rest-api/`), **KIS→키움 REST API 마이그레이션 (ADR-021)**, ADR-022 자격증명 DI 패턴 (환경변수→DB)
- **03-06**: Hooks 새 API 전환, Phase 1 프론트엔드 초기화 (Next.js 16 + ShadCN 13컴포넌트 + 인증 layout), 다중 활성 자격증명 latest 우선 반환 패치, 프론트 API 연결 디버깅 (KiwoomClient 인자 불일치, 빈 문자열 int 파싱)
- **03-07~09**: 토큰 DB 캐시 + Double-Check Locking (`token_store.py`), 모의투자 라이브 테스트 8건 → 파싱 버그 5건 수정 (종목코드 6자리, 가격 abs(), 호가 필드명, ka10086 페이징 등), **모멘텀 돌파 전략 설계 + 백테스트 엔진 (`src/backtest/`)** + 데이터 수집 모듈, 379 tests / 87% coverage
- **03-10**: 종목 스크리닝 + cron 자동 백테스트 + live_trader.py (모의 자동매매) + 한국 공휴일 모듈, 대시보드 shadcn 패턴 재작성, recharts 차트, 매매결과 페이지, rate limit 근본 수정 (credential별 10초 캐시), 429 자동 재시도 (지수 백오프)
- **03-11**: 분산 투자 파라미터 확대 (max_positions 3→5, max_position_pct 0.15→0.10), 4명 전문가 토론회로 다음 단계 결정, **P0 Critical 버그 수정**: volume 비교 로직 오류 (5분봉 vs 일평균 → 5분봉 누적+time_ratio), 주문 status 불일치 "success"→"submitted", Kill Switch FORCE_CLOSE 매도 차단, 평균회귀 청산 로직 구현 + 파라미터 완화, 프론트엔드 안정화 (Vitest 스모크 9건 + CORS rewrites + 무한 리다이렉트 + AlertDialog), README + MIT 라이선스, **텔레그램 알림 연동** (562 tests, 91.72%), WebSocket 마이그레이션 4단계 설계
- **03-12**: WebSocket 4단계 전체 구현 (KiwoomWebSocket + FastAPI /ws/market + 프론트 useRealtime), 키움 WS 스펙 준수 재작성 (포트 10000, LOGIN 패킷, flat JSON, values 숫자코드) + Contract Test 22 + fixture 13개, project-evaluation 6태스크 (대시보드 0원 버그, 백테스트 --days 60, CORS 화이트리스트, CI pytest+ruff, 프론트 타임아웃+WS 재연결), **잔고 조회 3건 버그 수정** (return_code 에러 감지, 토큰 8005 재시도, kt00018 prsm_dpst_aset_amt), 689 tests 94%
- **03-13**: 키움 REST API 문서 기준 4건 버그 (trde_tp 2바이트 코드, kt00001→kt00004→kt00001 최종, qry_tp, KST→UTC), 토큰 자동 갱신 / Lock 메모리 누수 / 주문체결 DB 연동, 핫픽스 다발 (Enum DB 매핑, OrderSide 대소문자), **단타/스윙 이중 전략 + 그리드 서치** (ATR% > 2% → 단타, R:R 3:1 → 1:2, 트레일링 스톱), 진입 필터 미적용 치명적 버그, **Phase 1 리스크 관리 6개 이슈 토론** (ATR 바닥 0.5% + ATR%<0.35% 진입 스킵 / R:R 1:2 (3.0×ATR) / 단계적 블랙리스트 / force_close 15:15 통일 / risk_scale 복구 안 함 / 거래비용 0.21%→0.23%)
- **03-14**: Phase 2 (ADX 변동성 분류 + 자금 버킷 + 스크리닝 + 동적 유니버스 + 스윙 인프라 overnight + 갭 리스크), Phase 3 데이터+AI 설계 + **Airflow 3.1.8** 도입 + Tier 1 수집기 (DART, pykrx, FRED, ECOS), **Poetry → uv 마이그레이션 (ADR-024)**, include/→plugins/, 디렉토리 이동 ~/projects → ~/individual/stock, **Phase 3-DB~3-7 구현** (DB 테이블 4개 + Kill Switch 리팩토링 (drawdown_guard 분리 + 신규 KillSwitch soft/hard_stop) + LLM 클라이언트 + 장전 브리핑 + 장후 리뷰 + 파라미터 자동 조정 + 전략 설정 UI), **Docker Compose 통합** + 캔들차트 + Bot 웹 제어, 코드 리뷰 CRITICAL 5/HIGH 13 수정, 연속 매매 모드, 876+138 = 1,014 tests
- **03-17~18**: 매매 -4.62% 원인 진단 (WS _ensure_token 오타 → 폴링 폴백, 시간 필터 HH:MM 슬라이싱, exit 로그 부재, C-RISK-01 drawdown 미실현 손익 누락, C-RISK-02 KillSwitch 영속화 부재, ATR 동적 손절 비활성화 버그), full-review TOP 10, 전문가 토론 4명, **Layer 0 VKOSPI 레짐 판단** (AGGRESSIVE/NEUTRAL/DEFENSIVE/CRISIS + 확증 기간 3일), Layer 1 월봉 12이평 추세 DAG, Layer 2 파라미터 개선, 레짐별 자본 배분
- **03-19~20**: **자동매매 16일 중단 원인**: 환경설정 파일 33번 줄 NAVER_CLIENT_SECRET 등호 누락 → source 실패 → set -euo pipefail로 로그도 안 만들고 종료. cron_backtest.sh에서 live_trader 제거 (ProcessManager 단일 진입점), **Docker→host DB 연결** (localhost→host.docker.internal), **Airflow 3.x 데이터 수집 파이프라인 전체 구동** (api-server, dag-processor, EXECUTION_API_SERVER_URL, AIRFLOW JWT_SECRET 공유), full-review CRITICAL B/F 수정, news_collection 필드 매핑 수정, design-005/architecture 검토 + 갱신 (cron UTC↔KST 정정)
- **03-21**: 종목 DB 정규화 + 연관종목 모델링 (#21) — Stock/StockRelation 모델, alembic 005/006, stock_master_sync DAG (매월 1일 pykrx)
- **03-22**: **문서-코드 전수조사** 37건 (CRITICAL 3 + HIGH 8 + MEDIUM 16 + LOW 10) → CRITICAL 3건 (monthly_signals alembic, RegisterRequest nickname, rebalance.py short_circuit) + HIGH 8건 + MEDIUM/LOW 다수 수정. M-07/M-10/M-14 사용자 결정 대기
- **03-23**: Airflow 로그인 (SimpleAuthManager 비밀번호 파일 named volume), LLMBriefing/TradeReview 모델 + 마이그레이션 008, **design-008 LLM DB 컨텍스트 설계** (4단계 시간별 데이터 흐름, plugins/context/ 토큰 예산 ~15K, llm_decisions 테이블, 야간 수집 yfinance, VIX 기반 리스크 모드)
- **03-25**: M-07 skip (멀티스레드 시 처리), M-10 Phase B 추가, **M-14 mypy hook 추가** (38 타입 에러 18파일 수정), design-008 **Phase A/B/C/D 전체 완료** (DB 컨텍스트 빌더, 야간 해외지수 10종 수집 DAG, llm_decisions 모델 + 야간 분석 DAG + 프론트 LLM 결정 페이지 + 텔레그램 알림)
- **03-28**: param_tuner UUID 버그 (id 누락), dart 테스트 mock 오류, **전문가 5인 토론으로 전략 파라미터 전면 재조정** — 모멘텀 SL/TP -0.5%/1.5% → -1.0%/2.5% + trailing -0.8% 활성화 + volume 1.5→0.7 + entry 09:05~14:00, 평균회귀 RSI 40→35 + BB 1.5→2.0 + SL/TP -1.5/1.5 → -2.5/2.5, 신뢰도 0.7→0.65, MAX_ORDER 100만→150만, AGGRESSIVE/DEFENSIVE 자본 배분 재조정

## 머지된 PR / ADR

### 누적 PR (대표 PR 위주)

| PR | 내용 |
|---|---|
| #1~2 | 03-04 전체 문서 배포 |
| #18~19 | 테스트 커버리지 85% |
| #28~29 | KIS→키움 마이그레이션 |
| #30 abandoned → #42~45 | ADR-022 자격증명 DI 재작업 + 대시보드 multiple results 버그 |
| #46~51 | 모의투자 라이브 버그 5건 + 에러 핸들링 |
| #52~53 | 토큰 DB 캐시 + 백테스트 엔진 |
| #54~55 | 자동 백테스트 + 자동매매 + cron |
| #56 | 프론트엔드 dashboard 재작성 |
| #66~67 | 분산 투자 파라미터 |
| #68~69 | 커버리지 정확도 (omit) |
| #79~83 | P0/P1 버그 수정 + 평균회귀 청산 + 전략 흐름도 |
| #92~100 | UX + AlertDialog + middleware + README + MIT |
| #101~105 | 텔레그램 + 프론트 규칙 |
| #106~109 | WebSocket 4단계 |
| #110~112 | WS 키움 스펙 준수 + 잔고 0원 버그 |
| #113~120 | 키움 API 4건 버그 + Enum + 로깅 |
| #121~134 | 단타/스윙 이중 전략 + Phase 1 리스크 관리 |
| #137~167 | Phase 2 + Phase 3 DB+LLM+UI + Docker Compose + 연속매매 |
| #168~175 | 매매 로직 6건 + full-review + C-RISK + 테스트 보강 |
| #181~184 | full-review CRITICAL B/F + Airflow 3.x 구동 |
| #185~186 | 종목 DB 정규화 |
| #187 (대규모) | 전수조사 수정 |
| #189~190 | param_tuner UUID + dart mock |

### ADR 추가

- **ADR-021**: KIS → 키움 REST API 마이그레이션 (전부 POST, api-id, KRX:종목코드)
- **ADR-022**: 자격증명 DI 패턴 (환경변수 → DB)
- **ADR-023**: Airflow 3.1.8 도입
- **ADR-024**: Poetry → uv 마이그레이션 (PEP 621)
- (architecture 내부) ADR-015~020: 커밋 컨벤션, 테스트 85% 정책, Dependabot, CI 분리, Agent Teams 아키텍처
- **design-001~007 순번화**: design-v1.1.md → design-001-system-v1.md 등, MEMORY.md 최소화, doc-registry.md 신설
- **design-008 LLM DB 컨텍스트**: 4단계 시간별 데이터 흐름, llm_decisions 테이블

## 핵심 의사결정

1. **인프라**: 무료 배포 = 로컬 Mac Docker + Cloudflare Tunnel (Oracle 폐기). FastAPI + Next.js. 멀티유저(가족). 키움 REST API + WebSocket. asyncio.Queue → Redis Streams 단계적 (Kafka 불필요).
2. **DB 정책**: SQLAlchemy 범용 타입 (UUID/JSON), PostgreSQL 종속 안 함. Alembic 마이그레이션에서만 dialect 지정.
3. **보안 3단계**: Claude Hook → pre-commit (gitleaks/bandit/detect-private-key) → GitHub Actions (Secret/TruffleHog/SAST/CodeQL/Dependency). PR 게이트와 머지 후 분석 분리. 브랜치 보호 강화 (enforce_admins, strict, required_conversation_resolution).
4. **테스트 정책**: 커버리지 85% 미만 PR 금지. ai/engine, broker/base, config/scheduler는 omit. mypy pre-commit hook 추가.
5. **에이전트 운영**: 서브에이전트(일회성)+팀 에이전트(독립 worktree) 구분. 멀티파일 작업은 팀 필수. QA 코드 변경 후 필수 투입. 9-10 역할 + 보안총괄자 게이트키퍼.
6. **전략**:
   - 모멘텀 돌파 (52주 신고가 95%+, 거래량 1.5×, R:R 1:2, ATR 동적 손절, trailing) + 평균회귀 (RSI/BB) 이중 전략
   - 단타/스윙 그리드 서치, ATR%>2% 단타 / ≤2% 스윙
   - **Layer 0 VKOSPI 레짐 판단** (AGGRESSIVE/NEUTRAL/DEFENSIVE/CRISIS, 확증 3일)
   - force_close 15:15 통일, 단계적 블랙리스트 (1패 무변경 / 2패 50% 축소 / 3패 당일 블랙)
   - risk_scale 복구 안 함 (의도적, 다음날 자동 리셋)
   - max_positions 5/전략, 합산 8 소프트캡, max_position_pct 0.10
7. **Kill Switch 분리**: 기존 → DrawdownGuard로 rename. 신규 KillSwitch (soft_stop=매수중단 / hard_stop=전량청산+중단). 파일 영속화 (`data/.kill_switch_state.json`), atomic write.
8. **Phase 3 LLM 인프라**: Airflow 3.1.8 + plugins/ + LocalExecutor + Asset 트리거. LLM provider Claude → GPT → Gemini fallback. LLM 제안 → 웹 승인 → strategy_config 반영 (자동 적용 X). 전략 파라미터 DB(strategy_config) 로드.
9. **GitHub 워크플로우**: claude→feat/*→dev(squash)→main(merge commit). MCP 토큰 URL 임베드로 PeterCplat→lsh0107 push 우회. dev→main release PR 표준화.

## 실수 + 교훈

- **잘못된 시작점**: 키움 결정인데 KIS API로 처음 구현 → 3월 5일 마이그레이션. PDF 인덱싱 후 발견.
- **세션 16/18 폴링부터 만든 오판**: WebSocket 문서 제공받았는데 폴링으로 구현 → WS 마이그레이션 4단계 추가 작업.
- **kt00001/04/05/18 필드 혼동 다회**: 모의/실 미지원 + qry_tp 누락 → 여러 핫픽스. 모의는 kt00001 + entr 필드로 최종 확정.
- **OrderSide/OrderStatus 대소문자 불일치**: BUY vs buy, name vs value → InvalidTextRepresentationError. SQLAlchemy Enum values_callable로 해소.
- **agent isolation=worktree 미작동**: 일부 팀원이 메인 repo에 작업, 브랜치 격리 실패 → cherry-pick 또는 통합 PR로 해결.
- **에이전트 완료 보고 신뢰 실패**: design-013 PR 7이 완료라 했지만 실제로 _assign_symbol_strategies 가중치 분배 미구현 → USE_MULTI_REGIME=true 활성화해도 효과 0. 04-22에 PR 9으로 보강.
- **환경설정 33줄 등호 누락 → 16일간 자동매매 중단**: NAVER_CLIENT_SECRET 값에 = 없어 source 실패 → set -euo pipefail 로그도 못 만들고 종료. 3-19에 복구. cron live_trader 제거 (ProcessManager 단일 진입점).
- **rate limit 진단 오해**: get_balance가 토큰+잔고+예수금 3건×React 더블 마운트=6건 → 초당 5건 초과. credential별 10초 캐시로 해결 + 프론트 GET 10초 TTL 이중 방어.
- **volume 비교 근본 오류**: 5분봉 거래량 vs 일평균 거래량 비교 (117배 차이) → 거래 발생 물리적 불가능. 5분봉 누적 + time_ratio (elapsed/390) × avg_volume(20일) × volume_ratio.
- **백테스트 매매 0건**: 삼성전자 등 대형주는 52주 신고가 95% 조건 미달. 스크리닝 종목 풀 확장(140) + 조건 완화 필요.
- **drawdown 미실현 손익 누락 (C-RISK-01)**: cash만 보면 보유 종목 평가손익 안 잡힘. calc_portfolio_value 헬퍼로 미실현 포함.
- **KillSwitch 인메모리 영속화 부재 (C-RISK-02)**: 컨테이너 재시작 시 상태 소실. 파일 영속화 + atomic write.
- **잔고 0원 표시 (3건)**: return_code 에러 감지 미흡 / 토큰 8005 재시도 부재 / entr에 D+2 미결제 포함 → 이중 계산. kt00018 prsm_dpst_aset_amt 정확 사용.
- **테스트 가짜 통과 + assert_called_once 남용**: 호출만 검증, 동작 검증 안 됨. 반환값 + 상태 기반 검증으로 재작성.

## 미해결 / 후속 (3월 기준)

- 3-8 텔레그램 양방향 통신 (`design-006`) 미시작
- EKS 배포 (kiwoom-infra 레포 분리) 미시작
- AIRFLOW_JWT_SECRET 환경설정 명시
- broker/token_store.py race condition 검토 (M-07, 멀티스레드 전환 시)
- t2_pending, sentiment_score 컬럼 사용 (Phase B 예정)
- 4월에 추가: MeanReversion 백테스트 엔진 + 슬리피지 모델 + DB config 자동 로드
