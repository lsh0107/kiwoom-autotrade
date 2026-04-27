# 키움증권 REST API 자동매매 시스템

키움증권 REST API 기반 모의/실투자 자동매매 시스템. 모멘텀 돌파 + 평균회귀 2전략 병행.

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
│   ├── trading/            # 주문 실행 · Kill Switch
│   ├── strategy/           # 매매 전략 (momentum, mean_reversion)
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
├── tests/                  # pytest 테스트 (1,182개, 90.23% 커버리지)
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
# 백엔드 (1,182 tests, 90.23% 커버리지 — CI 실측 기준)
uv run pytest --cov

# Airflow (203 tests collected)
cd airflow && uv run pytest

# 프론트엔드
cd frontend && npx vitest run
```

## 매매 전략

### 52주 신고가 일봉 모멘텀 (현재 사용)

일봉 신고가 돌파 + 거래량 급증 + KOSPI 20MA 상승 필터 조건 시 진입. ATR 기반 동적 손절/익절 + Trailing stop + 최대 10거래일 보유 제한.

- 진입: 당일 종가 > lookback(20)일 최고가 + 거래량 > 20일 평균 × 1.5 + KOSPI 종가 > KOSPI 20MA
- 청산: ATR 1.5× 손절 / ATR 4× 또는 +5% 익절 / Trailing stop (+2% armed) / 최대 10일
- 거래 비용: 슬리피지 0.15% + 수수료 왕복 0.03% + 거래세 0.20% = 왕복 약 0.53%

> 5분봉 단타 전략 폐기 (2026-04-27): T1 엔진 보정 후 슬리피지 0.15% 적용 시 하루 5건 거래 = 월 ~58% 비용 발생 → breakeven 불가. 자세한 근거는 [ADR-016](docs/design/design-016-strategy-redesign.md) 참조.

### Walk-Forward 검증 결과 (20종목, 18개월)

| 기준 | 임계값 | 통과율 |
|------|--------|--------|
| OOS Sharpe | ≥ 1.0 | 10/20 (50%) |
| MDD | ≤ −10% | 3/20 (15%) |
| 승률 | ≥ 35% | 20/20 (100%) |
| Risk-Reward | ≥ 2.0 | 0/20 (0%) |
| **전체** | **모두** | **0/20 → 파라미터 재조정 권고** |

주요 원인: `atr_tp_mult=4.0` + `tp_pct=5%` 조합이 대형주 평균 수익 제한 → RR 최대 1.3.
권고: `atr_tp_mult → 6.0` 재조정 후 재검증 후 모의투자 재개.

### 평균회귀

RSI 과매도(< 40) + 볼린저밴드 하단 돌파 + 거래량 조건 충족 시 진입. RSI 과매수(> 70) 또는 BB 중심선 회귀 시 청산.

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

## 운영 체크리스트

모의투자 재개 및 실전 전환 절차: [docs/operations/strategy-redesign-rollout.md](docs/operations/strategy-redesign-rollout.md)

## 브랜치 전략

```
claude (base) → feat/* (기능 개발) → dev (PR, squash) → main (PR, merge)
```

main, dev 브랜치 보호 활성화. 직접 push 금지, CI 필수 통과.

## 라이선스

MIT License
