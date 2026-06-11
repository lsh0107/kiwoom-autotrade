# 키움증권 REST API 자동매매 시스템

키움증권 REST API 기반 모의/실투자 자동매매 시스템. Cross-sectional momentum 주간 리밸런스 (ADR-021~024, design-025 멀티전략 오케스트레이터).

## 기술 스택

| 계층 | 기술 |
|------|------|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL |
| Frontend | Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · shadcn/ui |
| 인증 | JWT httpOnly cookie + Refresh Token + 초대 코드 |
| 브로커 | 키움증권 REST API (BrokerClient Protocol 추상화) |
| AI | Anthropic Claude · OpenAI GPT (shadow mode) |
| 스케줄러 | cron (월~금 08:30, 공휴일 스킵) |
| CI/CD | GitHub Actions (Secret Detection · CodeQL · Bandit · Dependency Audit) |
| 배포 | 로컬 Mac (Apple Silicon) + Cloudflare Tunnel |

## 프로젝트 구조

```
├── src/                    # Python 백엔드
│   ├── api/v1/             # REST API 엔드포인트 (auth, orders, market, bot, ...)
│   ├── broker/             # 키움증권 API 클라이언트
│   ├── trading/            # 주문 실행 · Kill Switch · Cross-momentum 리밸런스
│   ├── config/             # ACTIVE_STRATEGY enum (ADR-024) · 설정
│   ├── strategy/           # 매매 전략 (cross-sectional momentum)
│   ├── backtest/           # 백테스트 엔진
│   ├── ai/                 # LLM 기반 신호 분석
│   └── models/             # SQLAlchemy ORM
├── frontend/               # Next.js 프론트엔드
│   ├── src/app/            # App Router (dashboard, trade, bot, results, strategy, settings)
│   ├── src/components/     # UI 컴포넌트 (shadcn/ui)
│   └── src/hooks/          # React Query 훅
├── scripts/                # 운영 스크립트
│   ├── live_trader.py      # 실시간 자동매매 실행기
│   ├── run_backtest.py     # 백테스트 러너
│   ├── screen_symbols.py   # 종목 스크리닝
│   └── cron_backtest.sh    # 크론 자동 실행
├── tests/                  # pytest 테스트 (1,874개, 커버리지 85%+ CI 강제)
└── alembic/                # DB 마이그레이션
```

## 개발 환경

### 필수 요구사항

- Python 3.12+
- uv (패키지 매니저)
- PostgreSQL 17
- Node.js 25+ (프론트엔드)

### 설치

```bash
# uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치
uv sync

# Airflow 포함 전체 설치
uv sync --all-groups

# 환경변수
cp .env.example .env
# .env 편집

# DB 마이그레이션
uv run alembic upgrade head

# 서버 실행
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

### 테스트

```bash
# 백엔드 (1,874 tests, 커버리지 85%+ CI 강제)
uv run pytest --cov

# Airflow (203 tests collected)
cd airflow && uv run pytest

# 프론트엔드
cd frontend && npx vitest run
```

## 매매 전략

### Cross-sectional momentum (현재 활성, ADR-021/022/023)

KOSPI/KOSDAQ 172종목 풀에서 모멘텀 상위 종목을 리밸런스 (현재 설정: weekly — 매주 금요일 14:55, `strategy_config.cross_momentum.rebalance_freq`. monthly 옵션 보존). V2 walk-forward 백테스트 1/8 PASS 카드 (`top20pct_novol_notrend`, 5년 33%) 채택.

- 진입/청산: 리밸런스 시 신규 편입 종목은 시장가 진입, 제외 종목은 시장가 청산
- T+2 결제: 메모리 큐로 결제 대기 시뮬 (실거래 시 D+2 현금 반영)
- KRX 캘린더: 2025~2027년 정규 공휴일 + 임시공휴일 사전 등록
- Rate limit 백오프: pykrx 일봉 DB 캐싱 + 재시도 백오프

### 활성 전략 선택 (design-025 — DB `strategy_runtime` 단일 진실원)

활성 전략은 **DB `strategy_runtime` 테이블**이 단일 진실원이다 (design-025 Orchestrator). env `ACTIVE_STRATEGY`는 deprecated legacy fallback (DB가 비어있을 때 1회 seed 용도, ADR-024 호환).

| 전략 | 현재 상태 (2026-06-11) |
|----|------|
| `cross_momentum` | **enabled** (budget_pct 0.6) — weekly 리밸런스, 6/15 본 관찰 예정 |
| `short_swing` | disabled (budget_pct 0.3) — 실활성은 PR 2b/3 (total-equity budget, ownership/sell authority) 이후 |
| `multi_regime` | disabled — ADR-019/020 폐기, legacy poll_cycle 경로만 잔존 (orchestrator 미통합) |

default tick 매매 + 폐기된 5분봉 polling은 가드로 차단.

### 폐기된 전략 (참조)

- 5분봉 단타 모멘텀 — [ADR-016](docs/design/design-016-strategy-redesign.md) (왕복비용 0.53% × 일 5거래 = 일 -2.65% 비용)
- 52주 신고가 일봉 모멘텀 — [ADR-018](docs/design/design-018-strategy-rerun.md) (20 grid × 20종목 0/20)
- Pullback / Range / Mean Reversion 일봉 multi-regime — [ADR-019](docs/design/design-019-pullback-range-validation.md), [ADR-020](docs/design/design-020-extended-validation.md) (59종목·3년 0/59)

## 백테스트 엔진 (ADR-015)

[`src/backtest/daily_engine.py`](src/backtest/daily_engine.py) — 4종 무결성 보장:

- **Look-ahead bias 제거**: 신호 계산에 당일 이전 데이터(`prior_daily`)만 사용. 체결은 익일 시가.
- **슬리피지 0.15% 기본값**: KOSPI 대형주 스프레드 + 시장충격 보수적 추정.
- **MDD equity curve 기반**: 미실현 손익 포함 일별 평가액으로 산출.
- **Survivorship bias 경고**: pykrx는 현재 상장 종목만 제공 — WARN 로그 자동 출력.

자세한 근거: [ADR-015](docs/design/design-015-backtest-engine-integrity.md)

## 안전장치 및 리스크 가드레일 (ADR-017)

- **HWM Drawdown Guard**: 당일 최고 평가액 대비 −5% → 신규 매수 중단, −7% → 전량 청산
- **Auto Kill Switch**: 동일 종목 3회 연속 손절 / 10분 PnL −1.5% / 일일 주문 40건 초과 → SOFT_STOP
- **상태 영속화**: `.kill_switch_state.json` — 서버 재시작 후에도 상태 유지
- **모의투자 기본값**: `is_mock_trading=True`
- **주문 확인 다이얼로그**: 가격·수량·총금액 확인 후 실행
- **3단계 보안**: Claude Hook → pre-commit → GitHub Actions

자세한 설계: [ADR-017](docs/design/design-017-risk-microstructure.md)

## 마이크로구조 (ADR-017)

- **지정가 주문 우선**: 1호가 기준 지정가 제출 → 호가 조회 실패 시 시장가 fallback
- **점심 시간대 차단**: 11:30~13:00 신규 진입 차단 (저유동성 슬리피지 증가 구간)
- **동적 유니버스 필터**: 거래대금 · 스프레드 · 당일 변동폭 실시간 필터링

## ADR 인덱스

| 번호 | 문서 | 주제 |
|------|------|------|
| 009 | [design-009](docs/design/design-009-market-context-integration.md) | MarketContext 수급/테마 통합 |
| 010 | [design-010](docs/design/design-010-llm-decision-integration.md) | LLM Decision live_trader 반영 |
| 011 | [design-011](docs/design/design-011-daily-candle-caching.md) | 일봉 DB 캐싱 |
| 012 | [design-012](docs/design/design-012-pre-screening-cache.md) | 사전 스크리닝 캐시 |
| 013 | [design-013](docs/design/design-013-multi-regime-strategy.md) | 다중 레짐 전략 (Pullback/Range) |
| 014 | [design-014](docs/design/design-014-live-order-persist.md) | live_trader DB persist 브릿지 |
| 015 | [design-015](docs/design/design-015-backtest-engine-integrity.md) | 백테스트 엔진 무결성 4종 |
| 016 | [design-016](docs/design/design-016-strategy-redesign.md) | 전략 재설계 + walk-forward 결과 |
| 017 | [design-017](docs/design/design-017-risk-microstructure.md) | 리스크 가드레일 + 마이크로구조 |
| 018 | [design-018](docs/design/design-018-strategy-rerun.md) | 52주 신고가 파라미터 재검증 (400 시나리오 폐기) |
| 019 | [design-019](docs/design/design-019-pullback-range-validation.md) | Pullback/Range/MR walk-forward (20종목 0/20 폐기) |
| 020 | [design-020](docs/design/design-020-extended-validation.md) | 확장 검증 (59종목·3년·27 combo) → **일봉(daily) timeframe** Pullback/Range/MR 폐기 (주봉~월봉은 보존) |
| 021 | [design-021](docs/design/design-021-cross-sectional-momentum.md) | Cross-sectional momentum (172종목·5년·8 combo) → V2 기준 **PASS** (top20pct_novol_notrend 33%) |
| 022 | [design-022](docs/design/design-022-cross-momentum-live-adapter.md) | Cross-momentum live rebalance 어댑터 — CrossMomentumRebalanceAdapter, 월말 14:55 스케줄러 |
| 023 | [design-023](docs/design/design-023-cross-momentum-hardening.md) | Cross-momentum 견고화 — rate limit 백오프 (DB 캐싱 + pykrx retry), T+2 결제 시뮬 (메모리 큐), KRX 공휴일 캘린더 (2025~2027) |
| 024 | [design-024](docs/design/design-024-strategy-enum-consolidation.md) | ACTIVE_STRATEGY enum 통합 (USE_MULTI_REGIME / USE_CROSS_MOMENTUM 두 boolean 폐기) + default poll_cycle 가드 |
| 025 | [design-025](docs/design/design-025-multi-strategy-orchestrator.md) | 멀티전략 오케스트레이터 — DB `strategy_runtime` 다중 토글 + StrategyRegistry/BudgetManager/handler dispatch |
| — | [multi-strategy-portfolio-controller](docs/design/multi-strategy-portfolio-controller.md) | 4전략 동시운영 포트폴리오 설계 (PR 0 — 로드맵: PR 1 감사 / 2a budget 주입 완료, 2b/3 은 6/15 후) |
| — | [active-strategy-legacy-audit](docs/design/active-strategy-legacy-audit.md) | env ACTIVE_STRATEGY 의존성 인벤토리 + 회귀 테스트 (제거는 보류) |

## 운영 체크리스트

**전략 검증 현황 (2026-06-11)**: 누적 폐기 5건. **ADR-021 cross-sectional momentum V2 PASS → 모의 운영 중** (weekly, DB `strategy_runtime` enabled). 한국장 **regime R-series** (5-label scorer → overlay → read-only report → mixed allocation dry-run) + bias vocabulary alignment main 고정 — 매일 regime daily dry-run 운영 ([루틴](docs/observation/regime-daily-dryrun-routine.md)). **모의 live_trader 본 관찰 2026-06-15 시작 예정** — 기준 문서: [observation plan v0.10](docs/observation/2026-06-01-mock-live-trader-observation-plan.md) (6/11 사전 smoke run PASS with NOTE). 실전 전환은 본 관찰 통과 + 사용자 명시적 승인 필수.

모의투자 재개 및 실전 전환 절차: [docs/operations/strategy-redesign-rollout.md](docs/operations/strategy-redesign-rollout.md)

## 브랜치 전략

```
claude (base) → feat/* (기능 개발) → dev (PR, squash) → main (PR, merge)
```

main, dev 브랜치 보호 활성화. 직접 push 금지, CI 필수 통과.

## 라이선스

MIT License
