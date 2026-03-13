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
├── tests/                  # pytest 테스트 (791개, 93%+ 커버리지)
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
# 백엔드
uv run pytest --cov

# 프론트엔드
cd frontend && npx vitest run
```

## 매매 전략

### 모멘텀 돌파

52주 고점 대비 현재가가 임계치(70%) 이상이고 거래량이 급증한 종목에 진입. 손절/익절/강제청산(14:30) 조건으로 청산.

### 평균회귀

RSI 과매도(< 40) + 볼린저밴드 하단 돌파 + 거래량 조건 충족 시 진입. RSI 과매수(> 70) 또는 BB 중심선 회귀 시 청산.

## 안전장치

- **Kill Switch 3단계**: 주문별(-2%) → 전략별(-3%) → 사용자별(-4%) 자동 차단
- **모의투자 기본값**: `is_mock_trading=True`
- **주문 확인 다이얼로그**: 가격·수량·총금액 확인 후 실행
- **3단계 보안**: Claude Hook → pre-commit → GitHub Actions

## 브랜치 전략

```
claude (base) → feat/* (기능 개발) → dev (PR, squash) → main (PR, merge)
```

main, dev 브랜치 보호 활성화. 직접 push 금지, CI 필수 통과.

## 라이선스

MIT License
