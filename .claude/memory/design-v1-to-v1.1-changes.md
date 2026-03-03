# v1 → v1.1 변경 사항 정리

## 1. 메시지 큐: Kafka 제거 → 3단계 접근

### 왜 Kafka가 안 맞는가
- API 제한이 병목: 키움 ~20/sec, KIS 20/sec (모의 5/sec)
- 우리 최대 처리량: ~500 msg/sec
- Kafka 최소 리소스: 8GB RAM + JVM + ZooKeeper
- 24GB 무료 VM에서 1/3을 큐에 쓰면 낭비

### 최적 설계: 단계별 큐 아키텍처

**Phase 1 (MVP)**: asyncio.Queue (내장, 0 오버헤드)
```
[키움 WebSocket] → asyncio.Queue → [전략 엔진] → asyncio.Queue → [주문 실행기]
                                                                      ↓
                                                              asyncio.Queue
                                                                      ↓
                                                          [WebSocket → 브라우저]
```
- 단일 프로세스 내 Producer-Consumer 패턴
- RAM 0MB 추가, 설정 0, 의존성 0
- 단점: 프로세스 크래시 시 큐 내 메시지 유실

**Phase 2 (안정화)**: + SQLite WAL 로깅
```
[주문 실행기] → SQLite (WAL mode) → 주문 이력 영속화
                                   → 크래시 복구 시 미체결 주문 재확인
```
- 여전히 외부 의존성 0 (SQLite는 Python 내장)
- 파일 1개로 백업 간편

**Phase 3 (필요시만)**: + Redis
```
[FastAPI 프로세스 1: API 서버]  ←─ Redis Pub/Sub ──→  [프로세스 2: 트레이딩 엔진]
                                ←─ Redis Cache  ──→  실시간 시세 캐시
```
- 멀티프로세스 통신 필요할 때만
- RAM ~50MB
- 시세 캐시 + Pub/Sub 겸용

---

## 2. 아키텍처 변경: 트레이딩 엔진 분리

### v1 (문제)
```
FastAPI (4 workers)
  ├── REST API
  ├── WebSocket Server
  ├── 자동매매 엔진      ← 웹서버와 같은 프로세스
  └── APScheduler        ← 4 workers에서 4번 실행!
```

### v1.1 (수정)
```
[프로세스 1: FastAPI (1 worker, async)]
  ├── REST API
  ├── WebSocket Server (→ 브라우저)
  └── 상태 조회/제어 API

[프로세스 2: Trading Engine (별도)]
  ├── 키움 WebSocket Client (← 실시간 시세)
  ├── 전략 엔진
  ├── 주문 실행기 (→ 키움 REST API)
  ├── APScheduler (장 시간 관리)
  ├── Kill Switch / Circuit Breaker
  └── asyncio.Queue (내부 이벤트)

[통신: asyncio.Queue (Phase 1) → Redis (Phase 3)]
```

**이유:**
- 웹서버 재시작해도 봇은 계속 실행
- APScheduler 중복 실행 문제 원천 해결
- 웹서버 부하가 트레이딩 지연에 영향 안 줌

---

## 3. 주문 상태 머신 추가

### v1 (문제): 단순 status 문자열
```
PENDING → FILLED (부분 체결? 유령 주문?)
```

### v1.1 (수정): 상태 머신 + 부분 체결
```
                    ┌─────────────┐
                    │   CREATED   │ (DB에 기록)
                    └──────┬──────┘
                           │ submit_to_kiwoom()
                    ┌──────v──────┐
                    │  SUBMITTED  │ (키움에 전송)
                    └──────┬──────┘
                     ┌─────┼─────┐
                     │     │     │
              ┌──────v┐ ┌──v────┐ ┌v─────────┐
              │REJECTED│ │PARTIAL│ │  FILLED  │
              └───────┘ │ FILL  │ └──────────┘
                        └──┬────┘
                           │ (추가 체결)
                    ┌──────v──────┐
                    │   FILLED    │
                    └─────────────┘

별도 전이:
  SUBMITTED → CANCEL_REQUESTED → CANCELLED
  SUBMITTED → EXPIRED (장 마감)
```

### DB 스키마 변경
```sql
CREATE TABLE orders (
    -- 기존 필드 유지 +
    filled_quantity INTEGER DEFAULT 0,     -- 체결 수량
    remaining_quantity INTEGER,            -- 미체결 수량
    average_fill_price INTEGER,            -- 평균 체결가
    kiwoom_order_no VARCHAR(50),           -- 키움 주문번호
    kiwoom_status VARCHAR(20),             -- 키움측 상태 원본
    status VARCHAR(20) NOT NULL            -- 우리 상태 머신
      CHECK (status IN ('CREATED','SUBMITTED','PARTIAL_FILL',
                         'FILLED','REJECTED','CANCEL_REQUESTED',
                         'CANCELLED','EXPIRED','FAILED')),
    idempotency_key UUID UNIQUE,           -- 중복 주문 방지
    error_message TEXT,                    -- 실패 사유
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Kill Switch + Circuit Breaker 추가

### 3단계 안전장치
```
Level 1: 주문별 제한 (매 주문마다)
  - 1회 최대 주문 금액: 100만원
  - 1회 최대 수량: 설정값

Level 2: 전략별 제한 (전략 단위)
  - 전략별 최대 투자금
  - 전략별 최대 손실률 → 초과 시 해당 전략만 중지

Level 3: 글로벌 제한 (시스템 전체)
  - 일일 최대 손실: -3% → 모든 거래 중지
  - 일일 최대 주문 횟수: 100건
  - 1초 내 5건 이상 주문 감지 → 폭주 판단 → 긴급 중지
  - 수동 Kill Switch: API 호출 1번으로 전체 중지
```

### Kill Switch 구현
```python
class KillSwitch:
    def __init__(self):
        self._active = True  # True = 거래 허용
        self._reason = ""

    async def check(self) -> bool:
        """매 주문 전 호출. False면 거래 차단"""
        if not self._active:
            logger.critical(f"Kill Switch 활성: {self._reason}")
            return False
        return True

    async def trigger(self, reason: str):
        """긴급 정지"""
        self._active = False
        self._reason = reason
        await self._cancel_all_pending_orders()
        await self._notify_telegram(f"🚨 긴급 정지: {reason}")
```

---

## 5. 단일 사용자 확정 → 인증 간소화

### v1 (문제): 오픈 회원가입
```
POST /api/auth/register  ← 누구나 가입 가능!
```

### v1.1 (수정): 관리자 1인 고정
```
- 회원가입 엔드포인트 제거
- 초기 세팅 시 CLI로 관리자 계정 1개 생성
- JWT 로그인만 유지
- 추후 필요시 초대 코드 방식 추가

POST /api/auth/login     ← 로그인만 존재
POST /api/auth/refresh   ← 토큰 갱신
GET  /api/auth/me        ← 내 정보
```

### 초기 계정 생성
```bash
# 최초 1회만 실행
python -m src.cli create-admin --email admin@example.com --password ****
```

---

## 6. 한국 시장 규칙 반영

### 6A. 시장 시간 관리
```python
MARKET_SCHEDULE = {
    "pre_market":  ("08:00", "09:00"),   # 동시호가
    "regular":     ("09:00", "15:20"),   # 정규장
    "closing":     ("15:20", "15:30"),   # 장마감 동시호가
    "after_hours": ("15:40", "16:00"),   # 시간외 단일가
    "extended":    ("16:00", "18:00"),   # 시간외 종가
}

# 각 구간별 허용 주문 유형이 다름
ALLOWED_ORDER_TYPES = {
    "pre_market":  ["LIMIT"],
    "regular":     ["LIMIT", "MARKET"],
    "closing":     ["LIMIT"],
    "after_hours": ["AFTER_HOURS"],
    "extended":    ["EXTENDED"],
}
```

### 6B. KRX 공휴일
```python
# 한국거래소 공휴일 (매년 업데이트 필요)
KRX_HOLIDAYS_2026 = [
    "2026-01-01",  # 신정
    "2026-02-16",  # 설날 연휴
    "2026-02-17",
    "2026-02-18",
    "2026-03-01",  # 삼일절
    "2026-05-05",  # 어린이날
    "2026-05-24",  # 부처님오신날
    "2026-06-06",  # 현충일
    "2026-08-15",  # 광복절
    "2026-09-24",  # 추석 연휴
    "2026-09-25",
    "2026-09-26",
    "2026-10-03",  # 개천절
    "2026-10-09",  # 한글날
    "2026-12-25",  # 성탄절
    "2026-12-31",  # 연말
]
```

### 6C. 가격 제한폭 검증
```python
async def validate_order_price(symbol: str, price: int) -> bool:
    """주문 가격이 가격제한폭(±30%) 내인지 검증"""
    prev_close = await get_previous_close(symbol)
    upper_limit = int(prev_close * 1.30)
    lower_limit = int(prev_close * 0.70)
    return lower_limit <= price <= upper_limit
```

### 6D. T+2 결제
```python
# 잔고 조회 시 구분
class AccountBalance:
    total_cash: int           # 총 예수금
    available_cash: int       # 주문 가능 금액 (T+2 반영)
    unsettled_amount: int     # 미결제 금액
    # available_cash = total_cash - unsettled_amount
```

### 6E. VI (변동성 완화장치)
```python
# VI 발동 시 해당 종목 주문 보류
async def handle_vi_event(symbol: str, vi_type: str):
    """VI 발동 시 호출"""
    logger.warning(f"VI 발동: {symbol} ({vi_type})")
    await pause_strategy_for_symbol(symbol)
    # VI 해제 후 전략 재개
```

---

## 7. kiwoom-restful 추상화 레이어

### v1 (문제): 직접 의존
```python
from kiwoom_restful import KiwoomClient  # 라이브러리에 직접 의존
```

### v1.1 (수정): Protocol 기반 추상화
```python
# src/broker/base.py
class BrokerClient(Protocol):
    async def place_order(self, req: OrderRequest) -> OrderResponse: ...
    async def cancel_order(self, order_no: str) -> bool: ...
    async def get_balance(self) -> AccountBalance: ...
    async def get_holdings(self) -> list[Holding]: ...
    async def get_quote(self, symbol: str) -> Quote: ...
    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]: ...

# src/broker/kiwoom.py
class KiwoomBrokerClient:
    """kiwoom-restful 래핑"""
    ...

# src/broker/mock.py
class MockBrokerClient:
    """테스트용 목 클라이언트"""
    ...

# 추후 필요시
# src/broker/kis.py
# class KISBrokerClient: ...
```

**이점:**
- kiwoom-restful이 깨져도 교체 가능
- 테스트 시 MockBrokerClient 사용
- 한투(KIS) 추가 시 같은 인터페이스

---

## 8. Rate Limiter 수정 (무한 재귀 버그 제거)

### v1 (버그)
```python
# 429 응답 시 무한 재귀 → RecursionError
async def call_api(endpoint, params):
    async with limiter:
        resp = await client.get(endpoint, params=params)
        if resp.status_code == 429:
            await asyncio.sleep(1)
            return await call_api(endpoint, params)  # 💥 재귀!
```

### v1.1 (수정)
```python
async def call_api(endpoint, params, max_retries=3):
    for attempt in range(max_retries):
        async with api_limiter:
            resp = await client.get(endpoint, params=params)
            if resp.status_code == 429:
                wait = min(2 ** attempt, 30)  # 1, 2, 4초 (최대 30초)
                logger.warning(f"Rate limited. {wait}초 대기 (시도 {attempt+1}/{max_retries})")
                await asyncio.sleep(wait)
                continue
            return resp
    raise RateLimitExceededError(f"{endpoint} {max_retries}회 재시도 실패")
```

---

## 9. DB 백업 전략 추가

```bash
# cron: 매일 03:00 KST (장 마감 후)
0 3 * * * docker exec postgres pg_dump -U kiwoom kiwoom_trade | gzip > /backup/kiwoom_$(date +\%Y\%m\%d).sql.gz

# Oracle Object Storage에 업로드 (무료 20GB)
0 4 * * * oci os object put --bucket-name backups --file /backup/kiwoom_$(date +\%Y\%m\%d).sql.gz

# 7일 이상 된 로컬 백업 삭제
0 5 * * * find /backup -name "*.sql.gz" -mtime +7 -delete
```

---

## 10. 모니터링 + 알림 (텔레그램)

### 알림 대상
| 이벤트 | 심각도 | 알림 |
|--------|--------|------|
| 주문 체결 | INFO | ✅ 텔레그램 |
| Kill Switch 발동 | CRITICAL | 🚨 텔레그램 |
| 일일 손실 -2% | WARNING | ⚠️ 텔레그램 |
| 키움 WebSocket 끊김 | WARNING | ⚠️ 텔레그램 |
| 토큰 갱신 실패 | CRITICAL | 🚨 텔레그램 |
| 봇 시작/종료 | INFO | ℹ️ 텔레그램 |
| 서버 다운 | CRITICAL | 🚨 UptimeRobot |

### 헬스체크 엔드포인트
```
GET /api/health → {
  "status": "healthy",
  "db": "connected",
  "kiwoom_api": "authenticated",
  "kiwoom_ws": "connected (35/40 symbols)",
  "bot_engine": "running",
  "kill_switch": "inactive",
  "last_heartbeat": "2026-03-03T14:30:00+09:00"
}
```

---

## 11. 테스트 전략

### 모의투자 졸업 기준
1. 모의투자 2주 이상 연속 안정 운영
2. 모든 주문 유형 (매수/매도/취소) 성공 확인
3. WebSocket 재연결 3회 이상 자동 복구 확인
4. Kill Switch 발동 → 전체 중지 확인
5. 프로세스 재시작 후 주문 동기화 확인

### 테스트 종류
- 단위 테스트: 전략 로직, 주문 검증, 가격제한폭
- 통합 테스트: 키움 모의투자 API 실제 호출
- 시나리오 테스트: 부분 체결, VI 발동, 네트워크 끊김

---

## 12. Uvicorn Workers 변경

### v1: 4 workers (APScheduler 중복 실행)
### v1.1: 1 worker + async concurrency

단일 사용자 시스템에서 4 workers는 불필요.
Python asyncio의 동시성으로 충분 (수천 동시 연결 처리 가능).

```python
# uvicorn 실행
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
```

---

## 변경 요약표

| 항목 | v1 | v1.1 | 이유 |
|------|----|----|------|
| 메시지 큐 | 미정 (Kafka 검토) | asyncio.Queue → Redis | API 20/sec 제한, Kafka 8GB 낭비 |
| 프로세스 | FastAPI 1개 (4w) | API + 트레이딩 엔진 분리 | 안정성, 중복 실행 방지 |
| 주문 상태 | 단순 status | 상태 머신 + 부분체결 | 돈 관련 = 정확해야 함 |
| 안전장치 | 금액 상한만 | 3단계 Kill Switch | 봇 폭주 방지 |
| 인증 | 오픈 회원가입 | 관리자 1인 고정 | 보안 |
| 시장 규칙 | 없음 | T+2, 가격제한, VI, 공휴일 | 한국 시장 필수 |
| 키움 클라이언트 | kiwoom-restful 직접 | Protocol 추상화 | 교체 가능성 |
| Rate Limiter | 재귀 호출 | for 루프 + backoff | 버그 수정 |
| DB 백업 | 없음 | 일일 pg_dump → OCI | 데이터 보호 |
| 모니터링 | UptimeRobot만 | + 텔레그램 알림 | 트레이딩 이벤트 |
| Uvicorn | 4 workers | 1 worker (async) | 중복 실행 방지 |
| 테스트 | 없음 | 모의투자 졸업 기준 | 실거래 전 검증 |
