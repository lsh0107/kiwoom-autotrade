# 키움 자동매매 시스템 설계 v1.1 (최종)

> v1 전문가 리뷰(6.5/10) 피드백 전체 반영. 멀티유저(가족 포함) 지원.

---

## 1. 시스템 개요

키움증권 REST API 기반 자동/수동 트레이딩 웹 애플리케이션.
- 크로스플랫폼 (Mac/Windows/모바일 브라우저)
- 멀티유저 (초대 기반, 가족 공유 가능)
- 완전 무료 배포 ($0/월)
- 각 사용자가 본인 키움 계좌 + API 키로 독립 운영

### 핵심 기능 2가지
1. **자동 트레이드 봇**: 전략 기반 자동 매매 (사용자별 독립 실행)
2. **수동 트레이드**: 웹 UI에서 직접 주문/조회/관리

---

## 2. 아키텍처

```
┌──────────────────────────────────────────┐
│  Vercel (무료)                            │
│  Next.js 14+ / Tailwind / ShadCN UI      │
│                                           │
│  ├── 로그인 / 초대 가입                    │
│  ├── 대시보드 (포트폴리오, 수익률)          │
│  ├── 수동 트레이드 (주문/취소/호가/차트)     │
│  ├── 자동봇 관리 (전략 설정/시작/중지)       │
│  └── 설정 (API 키 등록, 모의/실거래 전환)    │
└──────────┬───────────────────────────────┘
           │ HTTPS (REST) / WSS (실시간)
           │ httpOnly Cookie (JWT)
           v
┌──────────────────────────────────────────┐
│  Oracle Cloud ARM (무료 4코어/24GB)       │
│  Ubuntu 22.04 + Docker Compose            │
│                                           │
│  ┌─ Nginx (리버스 프록시 + Let's Encrypt) │
│  │                                        │
│  ├─ [프로세스 1] FastAPI (1 worker async) │
│  │  ├── REST API /api/v1/*                │
│  │  ├── WebSocket Server (→ 브라우저)      │
│  │  ├── Auth (JWT, 초대 기반 가입)         │
│  │  ├── 사용자별 데이터 격리               │
│  │  └── 헬스체크 /api/health              │
│  │                                        │
│  ├─ [프로세스 2] Trading Engine            │
│  │  ├── 사용자별 키움 API 클라이언트       │
│  │  │   (User A → 키움 API with A의 키)   │
│  │  │   (User B → 키움 API with B의 키)   │
│  │  ├── 사용자별 전략 엔진                 │
│  │  ├── 사용자별 WebSocket Client (시세)   │
│  │  ├── 주문 실행기 + 상태 머신            │
│  │  ├── APScheduler (장 시간 관리)         │
│  │  ├── Kill Switch / Circuit Breaker      │
│  │  └── asyncio.Queue (내부 이벤트)        │
│  │                                        │
│  ├─ PostgreSQL 16 (Docker)                │
│  │  └── 사용자별 데이터 (user_id FK)       │
│  │                                        │
│  └─ Redis (Phase 2, 프로세스간 통신)       │
│                                           │
│  ┌─ Cron Jobs                             │
│  │  ├── 03:00 pg_dump → OCI Object Store  │
│  │  └── keepalive (VM 회수 방지)           │
│  └────────────────────────────────────────┘
└──────────┬───────────────────────────────┘
           │ HTTPS / WSS (사용자별 API 키)
           v
┌──────────────────────────────────────────┐
│  키움증권 REST API                        │
│  openapi.kiwoom.com                       │
│  ├── REST: ~20/sec (사용자별 독립)        │
│  └── WebSocket: 40종목/연결 (사용자별)     │
└──────────────────────────────────────────┘
```

---

## 3. 멀티유저 설계

### 3A. 사용자 모델
```
관리자 (나) ──── 초대 코드 발급
                    │
         ┌──────────┼──────────┐
         v          v          v
      사용자 A   사용자 B   사용자 C
      (본인 키움) (본인 키움) (본인 키움)
      (본인 전략) (본인 전략) (본인 전략)
      (본인 주문) (본인 주문) (본인 주문)
```

### 3B. 격리 원칙
| 항목 | 격리 방식 |
|------|----------|
| 키움 API 키 | 사용자별 암호화 저장, 각자 본인 키 사용 |
| 주문/거래 | 모든 쿼리에 `WHERE user_id = :current_user` |
| 전략 | 사용자별 독립 실행, 다른 사용자 전략 접근 불가 |
| Rate Limit | 키움 API 키별로 분리 (자연스럽게 격리) |
| WebSocket | 사용자별 키움 WS 연결 (40종목 × 사용자 수) |
| Kill Switch | 사용자별 독립 (A 중지해도 B는 계속) |
| 포트폴리오 | 사용자별 독립 조회/스냅샷 |

### 3C. 리소스 예상 (Oracle ARM 4코어/24GB 기준)
| 사용자 수 | 키움 WS 연결 | RAM 예상 | CPU | 판정 |
|-----------|-------------|---------|-----|------|
| 1명 | 1 | ~500MB | 여유 | 충분 |
| 3명 (가족) | 3 | ~1.5GB | 여유 | 충분 |
| 5명 | 5 | ~2.5GB | 여유 | 충분 |
| 10명 | 10 | ~5GB | 보통 | 가능 |
| 20명+ | 20+ | ~10GB+ | 주의 | 한계 근접 |

→ 가족 단위(3-5명)는 전혀 문제 없음.

---

## 4. 기술 스택

| 계층 | 기술 | 선택 이유 |
|------|------|----------|
| **Frontend** | Next.js 14+ / TypeScript | Vercel 네이티브, SSR, App Router |
| **UI** | Tailwind CSS + ShadCN UI | 빠른 개발, 일관된 디자인 |
| **차트** | Lightweight Charts (TradingView) | 무료, 경량, 캔들차트 |
| **Backend** | FastAPI / Python 3.11+ | 비동기, WebSocket, 타입 안전 |
| **ASGI** | Uvicorn (1 worker, async) | 단일 프로세스, 중복 실행 방지 |
| **ORM** | SQLAlchemy 2.0 (async) | 타입 안전, 비동기 |
| **DB** | PostgreSQL 16 (Docker) | JSON, 안정성, 무료 |
| **캐시** | Redis (Phase 2) | 시세 캐시, 프로세스간 통신 |
| **HTTP** | httpx (async) | 비동기 HTTP |
| **키움 API** | kiwoom-restful (Protocol 래핑) | 교체 가능한 추상화 |
| **인증** | JWT (httpOnly cookie) + 초대 코드 | 보안, CSRF 방지 |
| **스케줄러** | APScheduler | 장 시간 관리 |
| **Rate Limit** | aiolimiter | 비동기, 경량 |
| **알림** | Telegram Bot | 체결/장애 실시간 |
| **배포** | Oracle ARM + Vercel | $0/월 |
| **SSL** | Let's Encrypt | 무료 |
| **CI/CD** | GitHub Actions | 무료 |
| **로깅** | structlog (JSON) | 감사 추적 |

---

## 5. 메시지 큐: 단계별 접근 (Kafka 불필요)

| Phase | 방식 | RAM | 시점 |
|-------|------|-----|------|
| **1 (MVP)** | `asyncio.Queue` | 0 MB | 지금 |
| **2 (안정화)** | + SQLite/PostgreSQL 로깅 | 0 MB | 봇 안정 후 |
| **3 (필요시)** | + Redis Pub/Sub | 50 MB | 프로세스간 통신 필요시 |

API 제한(20/sec)이 병목이므로 Kafka(100만+/sec)는 불필요.

---

## 6. DB 스키마

### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    display_name VARCHAR(50),
    role VARCHAR(10) DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    is_active BOOLEAN DEFAULT TRUE,
    totp_secret VARCHAR(32),                -- 2FA (선택)
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### invites
```sql
CREATE TABLE invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) UNIQUE NOT NULL,
    created_by UUID REFERENCES users(id),
    used_by UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### broker_credentials
```sql
CREATE TABLE broker_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) UNIQUE,
    broker VARCHAR(20) DEFAULT 'kiwoom',
    app_key_enc TEXT NOT NULL,              -- AES-256 암호화
    app_secret_enc TEXT NOT NULL,           -- AES-256 암호화
    account_no VARCHAR(20) NOT NULL,
    account_product_code VARCHAR(5) DEFAULT '01',
    is_mock_trading BOOLEAN DEFAULT TRUE,
    ip_whitelist TEXT,                      -- 키움 등록된 IP
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### orders
```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    symbol_name VARCHAR(50),
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(15) NOT NULL CHECK (order_type IN (
        'LIMIT', 'MARKET', 'AFTER_HOURS', 'EXTENDED'
    )),
    quantity INTEGER NOT NULL,
    price INTEGER,                           -- 원 단위 (정수)
    filled_quantity INTEGER DEFAULT 0,
    remaining_quantity INTEGER,
    average_fill_price INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'CREATED' CHECK (status IN (
        'CREATED', 'SUBMITTED', 'PARTIAL_FILL',
        'FILLED', 'REJECTED', 'CANCEL_REQUESTED',
        'CANCELLED', 'EXPIRED', 'FAILED'
    )),
    kiwoom_order_no VARCHAR(50),
    kiwoom_status VARCHAR(20),
    idempotency_key UUID UNIQUE,
    is_auto BOOLEAN DEFAULT FALSE,
    strategy_id UUID REFERENCES strategies(id),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ
);

CREATE INDEX idx_orders_user_status ON orders(user_id, status);
CREATE INDEX idx_orders_user_created ON orders(user_id, created_at DESC);
```

### strategies
```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    max_investment INTEGER NOT NULL,         -- 최대 투자금
    max_loss_pct DECIMAL(5,2) DEFAULT 3.00,  -- 최대 손실률 %
    max_order_amount INTEGER DEFAULT 1000000, -- 1회 최대 금액
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### portfolio_snapshots
```sql
CREATE TABLE portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    total_value INTEGER NOT NULL,
    cash INTEGER NOT NULL,
    available_cash INTEGER NOT NULL,         -- T+2 반영
    unsettled_amount INTEGER DEFAULT 0,
    holdings JSONB NOT NULL,
    daily_pnl INTEGER,
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_snapshots_user_date ON portfolio_snapshots(user_id, snapshot_at DESC);
```

### trade_logs (감사 추적)
```sql
CREATE TABLE trade_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) NOT NULL,
    action VARCHAR(30) NOT NULL,             -- ORDER_PLACED, ORDER_FILLED, KILL_SWITCH, etc.
    detail JSONB NOT NULL,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trade_logs_user_date ON trade_logs(user_id, created_at DESC);
```

---

## 7. 주문 상태 머신

```
                    ┌─────────────┐
                    │   CREATED   │  DB에 기록
                    └──────┬──────┘
                           │ submit_to_kiwoom()
                    ┌──────v──────┐
               ┌────│  SUBMITTED  │────┐
               │    └──────┬──────┘    │
               │           │           │
        ┌──────v──┐  ┌─────v────┐  ┌───v──────┐
        │ REJECTED│  │ PARTIAL  │  │  FILLED  │
        └─────────┘  │  FILL   │  └──────────┘
                     └────┬────┘
                          │ 추가 체결
                   ┌──────v──────┐
                   │   FILLED    │
                   └─────────────┘

  SUBMITTED ──→ CANCEL_REQUESTED ──→ CANCELLED
  SUBMITTED ──→ EXPIRED (장 마감 시 자동)
  * ──→ FAILED (시스템 오류)
```

---

## 8. Kill Switch + Circuit Breaker (사용자별 독립)

```
Level 1: 주문별 (매 주문)
  ├── 1회 최대 금액 초과? → 차단
  ├── 가격제한폭(±30%) 밖? → 차단
  └── 시장 시간 외? → 차단

Level 2: 전략별 (전략 단위)
  ├── 전략 최대 투자금 초과? → 해당 전략 중지
  └── 전략 최대 손실률 초과? → 해당 전략 중지

Level 3: 글로벌 (사용자 단위)
  ├── 일일 손실 -3%? → 해당 사용자 전체 중지
  ├── 일일 주문 100건 초과? → 중지
  ├── 1초 내 5건 이상? → 폭주 감지 → 긴급 중지
  └── 수동 Kill Switch → 즉시 전체 중지 + 미체결 취소

모든 Kill Switch 발동 → 텔레그램 알림
```

---

## 9. 한국 시장 규칙

### 시장 시간
| 구간 | 시간 | 허용 주문 |
|------|------|----------|
| 프리마켓 (동시호가) | 08:00-09:00 | 지정가만 |
| 정규장 | 09:00-15:20 | 지정가, 시장가 |
| 장마감 동시호가 | 15:20-15:30 | 지정가만 |
| 시간외 단일가 | 15:40-16:00 | 시간외가 |
| 시간외 종가 | 16:00-18:00 | 종가매매 |

### 필수 검증
- 가격제한폭: 전일 종가 ±30%
- T+2 결제: 매도 대금 2영업일 후 사용 가능
- VI 발동: 해당 종목 주문 보류, 해제 후 재개
- KRX 공휴일: 별도 캘린더 관리 (매년 업데이트)

---

## 10. API 엔드포인트

### 인증
| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/auth/register | 초대 코드 기반 가입 |
| POST | /api/v1/auth/login | 로그인 (JWT → httpOnly cookie) |
| POST | /api/v1/auth/refresh | 토큰 갱신 |
| POST | /api/v1/auth/logout | 로그아웃 |
| GET | /api/v1/auth/me | 내 정보 |

### 관리자
| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/admin/invites | 초대 코드 발급 |
| GET | /api/v1/admin/invites | 초대 코드 목록 |
| GET | /api/v1/admin/users | 사용자 목록 |
| PATCH | /api/v1/admin/users/{id} | 사용자 활성/비활성 |

### 설정 (사용자별)
| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/settings/broker | 키움 API 키 등록 |
| PUT | /api/v1/settings/broker | 키움 API 키 수정 |
| GET | /api/v1/settings/broker | 등록 상태 확인 (키 마스킹) |
| PUT | /api/v1/settings/trading | 거래 설정 (모의/실거래 등) |

### 계좌
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/v1/account/balance | 잔고 (T+2 반영) |
| GET | /api/v1/account/holdings | 보유 종목 |
| GET | /api/v1/account/history | 거래 내역 |

### 주문 (수동)
| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/orders | 주문 (멱등성 키 필수) |
| DELETE | /api/v1/orders/{id} | 주문 취소 |
| GET | /api/v1/orders | 주문 목록 (필터링) |
| GET | /api/v1/orders/{id} | 주문 상세 |

### 시세
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/v1/market/quote/{symbol} | 현재가 |
| GET | /api/v1/market/orderbook/{symbol} | 호가 |
| GET | /api/v1/market/chart/{symbol} | 차트 (캔들) |
| GET | /api/v1/market/search?q= | 종목 검색 |

### 자동매매
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/v1/bot/strategies | 내 전략 목록 |
| POST | /api/v1/bot/strategies | 전략 생성 |
| PUT | /api/v1/bot/strategies/{id} | 전략 수정 |
| POST | /api/v1/bot/strategies/{id}/start | 시작 |
| POST | /api/v1/bot/strategies/{id}/stop | 중지 |
| POST | /api/v1/bot/kill-switch | 긴급 전체 중지 |
| GET | /api/v1/bot/status | 봇 상태 |
| GET | /api/v1/bot/logs | 실행 로그 |

### WebSocket
| Path | 설명 |
|------|------|
| /ws/market/{symbol} | 실시간 시세 |
| /ws/orders | 주문 체결 알림 (사용자별) |
| /ws/bot | 봇 상태 (사용자별) |

### 헬스체크
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/health | 시스템 상태 |

---

## 11. 프론트엔드 페이지 구조

```
/login                      # 로그인
/register?code=ABC123       # 초대 가입
│
├── /dashboard              # 메인 대시보드
│   ├── 포트폴리오 요약 (총자산, 수익률)
│   ├── 보유 종목 테이블
│   ├── 일일 P&L 차트
│   └── 최근 거래/알림
│
├── /trade                  # 수동 트레이드
│   ├── 종목 검색
│   ├── 실시간 캔들차트 (Lightweight Charts)
│   ├── 호가창
│   ├── 주문 폼 (매수/매도, 지정가/시장가)
│   └── 미체결 주문 (취소 가능)
│
├── /bot                    # 자동매매
│   ├── 전략 목록 (활성/비활성 토글)
│   ├── 전략 생성/편집 폼
│   ├── 봇 실행 로그 (실시간)
│   ├── 성과 분석 (전략별)
│   └── Kill Switch 버튼 🔴
│
├── /history                # 이력
│   ├── 전체 주문 내역 (필터/검색)
│   ├── 일별 수익률
│   └── 월별 리포트
│
└── /settings               # 설정
    ├── 키움 API 키 등록/수정
    ├── 모의투자 ↔ 실거래 전환 (2중 확인)
    ├── 텔레그램 알림 설정
    ├── 2FA 설정 (선택)
    └── 계정 정보
```

---

## 12. 보안 체크리스트

- [ ] JWT: httpOnly cookie, 30분 만료
- [ ] Refresh token: 7일 만료, 자동 회전
- [ ] 초대 기반 가입 (오픈 가입 없음)
- [ ] 키움 API 키: AES-256 암호화, 키는 Oracle Cloud Vault
- [ ] 사용자 데이터 격리 (모든 쿼리 user_id 필터)
- [ ] CORS: Vercel 도메인만 허용
- [ ] HTTPS 강제 (Nginx 301 redirect)
- [ ] Rate limiting: 자체 API (로그인 5/min, 일반 60/min)
- [ ] SQL injection 방지 (SQLAlchemy ORM)
- [ ] XSS 방지 (Next.js 기본 이스케이핑)
- [ ] CSRF: SameSite=Lax cookie + Origin 검증
- [ ] 로그인 실패 5회 → 계정 잠금 15분
- [ ] 모든 주문 감사 로그 (trade_logs)
- [ ] 실거래 전환 시 2중 확인 (비밀번호 재입력)

---

## 13. 배포 ($0/월)

| 서비스 | 용도 | 비용 |
|--------|------|------|
| Oracle Cloud ARM | Backend + DB + Bot (4코어/24GB) | $0 |
| Vercel Hobby | Frontend (Next.js) | $0 |
| Let's Encrypt | SSL | $0 |
| GitHub Actions | CI/CD | $0 |
| Cloudflare | DNS | $0 |
| UptimeRobot | 서버 모니터링 | $0 |
| Telegram Bot | 거래 알림 | $0 |

### Docker Compose
```yaml
services:
  api:
    build: ./backend
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
    env_file: .env
    depends_on: [db]
    restart: unless-stopped

  trading-engine:
    build: ./backend
    command: python -m src.engine.main
    env_file: .env
    depends_on: [db]
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    volumes: ["pgdata:/var/lib/postgresql/data"]
    environment:
      POSTGRES_DB: kiwoom_trade
      POSTGRES_USER: kiwoom
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./certbot:/etc/letsencrypt
    depends_on: [api]
    restart: unless-stopped

volumes:
  pgdata:
```

---

## 14. 모니터링 + 알림

### 텔레그램 알림 (사용자별)
| 이벤트 | 심각도 |
|--------|--------|
| 주문 체결 | INFO |
| 부분 체결 | INFO |
| 주문 실패/거부 | WARNING |
| Kill Switch 발동 | CRITICAL |
| 일일 손실 -2% 경고 | WARNING |
| 키움 WebSocket 끊김 | WARNING |
| 토큰 갱신 실패 | CRITICAL |
| 봇 시작/종료 | INFO |

### 헬스체크
```json
GET /api/health
{
  "status": "healthy",
  "db": "connected",
  "active_users": 3,
  "bot_engines": {
    "user_a": { "status": "running", "strategies": 2, "ws": "connected" },
    "user_b": { "status": "running", "strategies": 1, "ws": "connected" }
  },
  "uptime": "3d 14h 22m"
}
```

---

## 15. Broker 추상화 (kiwoom-restful 교체 대비)

```python
# src/broker/base.py
class BrokerClient(Protocol):
    async def authenticate(self) -> str: ...
    async def place_order(self, req: OrderRequest) -> OrderResponse: ...
    async def cancel_order(self, order_no: str) -> bool: ...
    async def get_balance(self) -> AccountBalance: ...
    async def get_holdings(self) -> list[Holding]: ...
    async def get_quote(self, symbol: str) -> Quote: ...
    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]: ...

# src/broker/kiwoom.py - kiwoom-restful 래핑
# src/broker/mock.py   - 테스트용
# src/broker/kis.py    - 한투 (추후)
```

---

## 16. 구현 우선순위

### Phase 1: MVP (3-4주)
1. 프로젝트 세팅 (FastAPI + Docker + PostgreSQL)
2. 사용자 인증 (JWT + 초대 가입)
3. 키움 API 인증/토큰 관리 (BrokerClient 추상화)
4. 시세 조회 (REST)
5. 주문 실행 (매수/매도/취소, 상태 머신)
6. Next.js 기본 UI (로그인, 대시보드, 주문)
7. Kill Switch 기본 구현

### Phase 2: 실시간 + 자동매매 (3-4주)
8. WebSocket 실시간 시세
9. 캔들차트 + 호가창
10. 자동매매 엔진 (기본 전략 1개)
11. APScheduler 장 시간 관리
12. 텔레그램 알림
13. 한국 시장 규칙 (T+2, 가격제한, VI, 공휴일)

### Phase 3: 배포 + 고도화 (2-3주)
14. Oracle Cloud ARM 배포
15. CI/CD (GitHub Actions)
16. DB 백업 자동화
17. 전략 관리 UI
18. 포트폴리오 분석/리포트
19. 모의투자 졸업 테스트

---

## 17. 전제 조건
- [x] 키움증권 모의투자 가입 완료
- [ ] 키움 REST API 앱 등록 (AppKey/AppSecret)
- [ ] Oracle Cloud 계정 생성 + ARM VM 프로비저닝
- [ ] 도메인 구매 (선택)
- [ ] 텔레그램 봇 생성
