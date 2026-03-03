# 키움 자동매매 시스템 설계 v1

## 1. 시스템 개요

키움증권 REST API를 활용한 자동/수동 트레이딩 웹 애플리케이션.
Mac/Windows 크로스플랫폼, 완전 무료 배포.

### 두 가지 핵심 기능
1. **자동 트레이드 봇**: 전략 기반 자동 매매 (스케줄러 + 전략 엔진)
2. **수동 트레이드**: 웹 UI에서 직접 주문/조회/관리

---

## 2. 아키텍처

```
┌──────────────────────────────────────┐
│  Vercel (무료)                        │
│  Next.js 14+ / Tailwind / ShadCN UI  │
│                                       │
│  ├── 대시보드 (포트폴리오, 수익률)      │
│  ├── 수동 트레이드 UI (주문/취소)       │
│  ├── 자동봇 관리 (전략 설정/시작/중지)   │
│  ├── 실시간 시세 차트                   │
│  └── 로그인 (JWT)                      │
└──────────┬───────────────────────────┘
           │ HTTPS (REST) / WSS (실시간)
           v
┌──────────────────────────────────────┐
│  Oracle Cloud ARM VM (무료)           │
│  4 OCPU Ampere A1 / 24GB RAM         │
│  Ubuntu + Docker Compose              │
│                                       │
│  ┌─ Nginx (리버스 프록시 + SSL)       │
│  │                                    │
│  ├─ FastAPI Backend (uvicorn)         │
│  │  ├── REST API (주문/조회/계좌)      │
│  │  ├── WebSocket Server (→ 브라우저)  │
│  │  ├── Auth (JWT + OAuth2)           │
│  │  ├── Rate Limiter (aiolimiter)     │
│  │  └── Background Tasks              │
│  │      ├── 자동매매 엔진              │
│  │      ├── 스케줄러 (APScheduler)     │
│  │      └── WebSocket Client (← 키움) │
│  │                                    │
│  ├─ PostgreSQL (Docker)               │
│  │  ├── 주문 이력                      │
│  │  ├── 포트폴리오 스냅샷              │
│  │  ├── 전략 설정                      │
│  │  └── 사용자 계정                    │
│  │                                    │
│  └─ Redis (Docker, Phase 2)           │
│     ├── 실시간 시세 캐시               │
│     └── Pub/Sub (내부 이벤트)          │
└──────────┬───────────────────────────┘
           │ HTTPS / WSS
           v
┌──────────────────────────────────────┐
│  키움증권 REST API                    │
│  openapi.kiwoom.com                   │
│                                       │
│  ├── REST: 주문/조회/계좌 (~20/sec)   │
│  └── WebSocket: 실시간 시세 (40종목)   │
└──────────────────────────────────────┘
```

---

## 3. 기술 스택

| 계층 | 기술 | 선택 이유 |
|------|------|----------|
| **Frontend** | Next.js 14+ / TypeScript | Vercel 네이티브, SSR, App Router |
| **UI** | Tailwind CSS + ShadCN UI | 빠른 개발, 일관된 디자인 |
| **차트** | Lightweight Charts (TradingView) | 무료, 경량, 캔들차트 |
| **Backend** | FastAPI / Python 3.11+ | 비동기, WebSocket 네이티브, 타입 안전 |
| **ASGI** | Uvicorn (4 workers) | 고성능 비동기 서버 |
| **ORM** | SQLAlchemy 2.0 (async) | 타입 안전, 비동기 지원 |
| **DB** | PostgreSQL 16 (Docker) | 안정성, JSON 지원, 무료 |
| **캐시** | Redis (Phase 2) | 시세 캐시, Pub/Sub |
| **HTTP** | httpx (async) | 비동기 HTTP 클라이언트 |
| **키움 API** | kiwoom-restful | 공식 라이브러리, 자동 rate limit |
| **인증** | JWT (PyJWT) + OAuth2 | FastAPI 네이티브 지원 |
| **스케줄러** | APScheduler | 장 운영시간 자동 관리 |
| **Rate Limit** | aiolimiter | 비동기 네이티브, 경량 |
| **배포 BE** | Oracle Cloud ARM (Always Free) | 4코어/24GB, 영구 무료 |
| **배포 FE** | Vercel (Hobby) | Next.js 최적, 무료 |
| **SSL** | Let's Encrypt + Certbot | 무료 SSL |
| **CI/CD** | GitHub Actions | 무료, 자동 배포 |

---

## 4. 메시지 큐: Kafka vs 대안

### 결론: Kafka는 과도함 (Overkill)

| 지표 | 우리 시스템 | Kafka 설계 목표 |
|------|-----------|----------------|
| 처리량 | ~500 msg/sec | 1,000,000+ msg/sec |
| 소비 RAM | 0 MB (in-process) | 1-8 GB |
| 프로세스 | 단일 | 분산 멀티노드 |
| 사용자 | 1명 | 수천-수만 |

### 단계별 접근

| Phase | 큐 방식 | 시점 | 이유 |
|-------|--------|------|------|
| **1 (MVP)** | `asyncio.Queue` | 지금 | 의존성 0, 오버헤드 0, 충분한 성능 |
| **2 (안정화)** | + SQLite 로깅 | 봇 안정 후 | 주문 이력 영속화, 크래시 복구 |
| **3 (필요시)** | + Redis Streams | 멀티프로세스 필요시 | 프로세스간 통신, 시세 캐시 |
| **4 (거의 불필요)** | Kafka | 기관급 스케일 | 현실적으로 불필요 |

---

## 5. Rate Limit 전략

### 키움 REST API 제한

| 항목 | 제한 | 안전 마진 |
|------|------|----------|
| REST API | ~20/sec | 15/sec 사용 |
| WebSocket 구독 | 40종목/연결 | 35종목 사용 |
| Access Token | 24시간 유효 | 6시간마다 갱신 |

### 구현 방식

```python
from aiolimiter import AsyncLimiter

# 안전 마진 적용
api_limiter = AsyncLimiter(15, 1)  # 15 req/sec (공식 ~20)

async def call_kiwoom_api(endpoint, params):
    async with api_limiter:
        response = await client.get(endpoint, params=params)
        if response.status_code == 429:  # Rate limited
            await asyncio.sleep(1)
            return await call_kiwoom_api(endpoint, params)
        return response
```

---

## 6. 데이터 흐름

### 자동 트레이드
```
[APScheduler: 09:00 장 시작]
    → [전략 엔진: 조건 평가]
    → [asyncio.Queue: 매매 신호]
    → [주문 실행기: 키움 API 호출]
    → [DB: 주문 이력 저장]
    → [WebSocket → 브라우저: 실시간 알림]
```

### 수동 트레이드
```
[브라우저: 주문 입력]
    → [FastAPI: 주문 검증 + 안전장치]
    → [키움 API: 주문 실행]
    → [DB: 주문 이력 저장]
    → [WebSocket → 브라우저: 체결 알림]
```

### 실시간 시세
```
[키움 WebSocket → FastAPI WebSocket Client]
    → [asyncio.Queue: 시세 버퍼]
    → [FastAPI WebSocket Server → 브라우저]
    → [Lightweight Charts: 차트 업데이트]
```

---

## 7. DB 스키마 (핵심)

### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    kiwoom_app_key_enc TEXT,        -- 암호화 저장
    kiwoom_app_secret_enc TEXT,     -- 암호화 저장
    kiwoom_account_no VARCHAR(20),
    is_mock_trading BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### orders
```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) NOT NULL,        -- BUY / SELL
    order_type VARCHAR(10) NOT NULL, -- LIMIT / MARKET
    quantity INTEGER NOT NULL,
    price INTEGER,                   -- 원 단위 (정수)
    status VARCHAR(20) NOT NULL,     -- PENDING/FILLED/CANCELLED/FAILED
    kiwoom_order_id VARCHAR(50),
    is_auto BOOLEAN DEFAULT FALSE,   -- 자동매매 여부
    strategy_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ
);
```

### strategies
```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,       -- 전략 유형
    config JSONB NOT NULL,           -- 전략 파라미터
    is_active BOOLEAN DEFAULT FALSE,
    max_investment INTEGER,          -- 최대 투자금
    max_loss_pct DECIMAL(5,2),       -- 최대 손실률
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### portfolio_snapshots
```sql
CREATE TABLE portfolio_snapshots (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    total_value INTEGER NOT NULL,
    cash INTEGER NOT NULL,
    holdings JSONB NOT NULL,         -- {symbol: {qty, avg_price, current_price}}
    daily_pnl INTEGER,
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 8. API 엔드포인트 설계

### 인증
| Method | Path | 설명 |
|--------|------|------|
| POST | /api/auth/register | 회원가입 |
| POST | /api/auth/login | 로그인 (JWT 발급) |
| POST | /api/auth/refresh | 토큰 갱신 |
| GET | /api/auth/me | 내 정보 |

### 계좌
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/account/balance | 잔고 조회 |
| GET | /api/account/holdings | 보유 종목 |
| GET | /api/account/history | 거래 내역 |

### 주문 (수동)
| Method | Path | 설명 |
|--------|------|------|
| POST | /api/orders | 주문 실행 |
| DELETE | /api/orders/{id} | 주문 취소 |
| GET | /api/orders | 주문 목록 |
| GET | /api/orders/{id} | 주문 상세 |

### 시세
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/market/quote/{symbol} | 현재가 |
| GET | /api/market/orderbook/{symbol} | 호가 |
| GET | /api/market/chart/{symbol} | 차트 데이터 |
| GET | /api/market/search?q= | 종목 검색 |

### 자동매매
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/bot/strategies | 전략 목록 |
| POST | /api/bot/strategies | 전략 생성 |
| PUT | /api/bot/strategies/{id} | 전략 수정 |
| POST | /api/bot/strategies/{id}/start | 전략 시작 |
| POST | /api/bot/strategies/{id}/stop | 전략 중지 |
| GET | /api/bot/status | 봇 상태 |
| GET | /api/bot/logs | 봇 실행 로그 |

### WebSocket
| Path | 설명 |
|------|------|
| /ws/market/{symbol} | 실시간 시세 |
| /ws/orders | 주문 체결 알림 |
| /ws/bot | 봇 상태 업데이트 |

---

## 9. 프론트엔드 페이지 구조

```
/ (로그인)
├── /dashboard              # 메인 대시보드
│   ├── 포트폴리오 요약 카드
│   ├── 일일 수익률 차트
│   ├── 보유 종목 테이블
│   └── 최근 거래 내역
├── /trade                  # 수동 트레이드
│   ├── 종목 검색
│   ├── 실시간 차트 (캔들)
│   ├── 호가창
│   ├── 주문 폼 (매수/매도)
│   └── 미체결 주문 목록
├── /bot                    # 자동매매 관리
│   ├── 전략 목록 (활성/비활성)
│   ├── 전략 생성/편집
│   ├── 봇 실행 로그
│   └── 성과 분석
├── /history                # 거래 이력
│   ├── 전체 주문 내역
│   ├── 일별 수익률
│   └── 전략별 성과
└── /settings               # 설정
    ├── API 키 관리
    ├── 모의/실거래 전환
    ├── 알림 설정
    └── 계정 관리
```

---

## 10. 배포 구성

### 비용: $0/월

| 서비스 | 용도 | 비용 |
|--------|------|------|
| Oracle Cloud ARM | Backend + DB + Bot | $0 (Always Free) |
| Vercel Hobby | Frontend | $0 |
| Let's Encrypt | SSL | $0 |
| GitHub Actions | CI/CD | $0 |
| Cloudflare DNS | DNS + CDN | $0 |
| UptimeRobot | 모니터링 | $0 |

### Docker Compose (Backend)
```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
    depends_on: [db]

  db:
    image: postgres:16-alpine
    volumes: ["pgdata:/var/lib/postgresql/data"]
    environment:
      - POSTGRES_DB=kiwoom_trade

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes: ["./nginx.conf:/etc/nginx/conf.d/default.conf"]
    depends_on: [api]

volumes:
  pgdata:
```

---

## 11. 보안 체크리스트

- [ ] JWT access token 만료: 30분
- [ ] Refresh token 만료: 7일
- [ ] 키움 API 키는 AES-256으로 암호화 저장
- [ ] 모든 주문에 금액/수량 상한 적용
- [ ] 모의투자 기본값 (실거래 전환 시 2중 확인)
- [ ] CORS: Vercel 도메인만 허용
- [ ] Rate limiting: 자체 API도 적용
- [ ] HTTPS 강제 (HTTP → 301 redirect)
- [ ] SQL injection 방지 (SQLAlchemy ORM)
- [ ] XSS 방지 (Next.js 기본 이스케이핑)

---

## 12. 구현 우선순위

### Phase 1: MVP (2-3주)
1. FastAPI 프로젝트 세팅 + Docker
2. 키움 API 인증/토큰 관리
3. 시세 조회 (REST)
4. 기본 주문 실행 (매수/매도)
5. 간단한 Next.js 대시보드
6. JWT 로그인

### Phase 2: 실시간 + 자동매매 (2-3주)
7. WebSocket 실시간 시세
8. 캔들 차트
9. 호가창
10. 자동매매 엔진 (기본 전략)
11. APScheduler 장 시간 관리

### Phase 3: 고도화 (2-3주)
12. 전략 관리 UI
13. 포트폴리오 분석/리포트
14. Oracle Cloud 배포
15. CI/CD 파이프라인
16. 알림 시스템 (Telegram)

---

## 13. 전제 조건
- [x] 키움증권 모의투자 가입 완료
- [ ] 키움 REST API 앱 등록 (AppKey/AppSecret 발급)
- [ ] Oracle Cloud 계정 생성
- [ ] 도메인 구매 (선택, Cloudflare 무료 DNS)
