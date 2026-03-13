# WebSocket 실시간 시세 전환 설계

> **상태**: 보관 — WebSocket 전환 완료
> 작성일: 2026-03-11
> 관련: design-001-system-v1.md 섹션 14, Phase 2 항목 #8
>
> **참조 문서 (키움 REST API)**:
> - `docs/kiwoom-rest-api/16-websocket.md` — 실시간 WebSocket API 전체 (23개 TR)
> - `docs/kiwoom-rest-api/01-auth.md` — 인증/토큰 (WebSocket 인증에 동일 토큰 사용)
> - `docs/kiwoom-rest-api/03-order.md` — 주문 API (주문체결 실시간 TR `00`과 연계)
> - `docs/kiwoom-rest-api/05-market.md` — 시세 조회 (REST 폴백 시 사용)
> - `docs/kiwoom-rest-api/README.md` — API 전체 목차

## 배경

현재 `live_trader.py`는 5분 간격 REST 폴링으로 시세를 조회한다.
키움 REST API는 WebSocket 실시간 시세(`/api/dostk/websocket`)를 제공하며, 체결가/호가/주문체결/잔고를 push 방식으로 수신할 수 있다.

**전환 이유**: 5분 지연은 손절/익절 반응에 치명적. 실시간 체결 데이터 기반으로 즉시 반응해야 함.

---

## 아키텍처 변경

```
[현재] live_trader → 5분마다 REST get_quote() → 전략 체크 → 주문

[목표] KiwoomWebSocket → 체결 이벤트 push → 전략 체크 → 주문
       ↓
       FastAPI WebSocket → 프론트엔드 실시간 차트/호가
```

---

## 단계별 구현 계획

### Step 1: WebSocket 클라이언트 (백엔드 코어)

**파일**: `src/broker/realtime.py` (신규)

구현:
- `KiwoomWebSocket` 클래스
  - `connect()` — WebSocket 연결 수립
  - `subscribe(symbols, types)` — 종목 구독 (`trnm: "REG"`)
  - `unsubscribe(symbols)` — 구독 해지 (`trnm: "REMOVE"`)
  - `_on_message(data)` — 수신 메시지 파싱 + 콜백 호출
  - `_reconnect()` — 연결 끊김 시 자동 재연결 (exponential backoff)
  - `close()` — 연결 종료

**파일**: `src/broker/constants.py` (수정)
- `WEBSOCKET_ENDPOINT = "/api/dostk/websocket"`
- `REALTIME_TYPES` dict 추가 (0B, 0C, 0D, 00, 04)

**파일**: `src/broker/schemas.py` (수정)
- `RealtimeTick` dataclass (체결 데이터)
- `RealtimeOrderbook` dataclass (호가 데이터)

**테스트**: `tests/broker/test_realtime.py`
- 구독/해지 메시지 포맷 확인
- 메시지 파싱 테스트
- 재연결 로직 테스트
- 콜백 호출 확인

**산출물**: WebSocket 연결 + 구독 + 메시지 수신이 동작하는 클라이언트

---

### Step 2: live_trader.py 이벤트 기반 전환 (백엔드 통합)

**파일**: `scripts/live_trader.py` (수정)

변경:
- 5분 폴링 루프 → WebSocket 이벤트 루프
- `on_tick(symbol, tick)` 콜백 — 체결 시 전략 체크
- `on_orderbook(symbol, orderbook)` 콜백 — 호가 변동 시 (향후)
- 기존 `poll_cycle()` → `handle_tick()` 로 리팩토링
- 폴링 폴백: WebSocket 연결 실패 시 기존 REST 폴링으로 자동 전환
- 텔레그램 알림 기존대로 유지

구조:
```python
async def main():
    ws = KiwoomWebSocket(client)
    await ws.connect()
    await ws.subscribe(symbols, ["0B"])  # 체결 구독

    ws.on_tick = lambda sym, tick: handle_tick(sym, tick, strategies, state, notifier)

    # 이벤트 루프 (15:35까지)
    await ws.run_until(MARKET_CLOSE_HHMM)

    await force_close_all(client, state)
    await ws.close()
```

**테스트**: `tests/test_live_trader.py` (수정)
- 기존 테스트 유지 (폴백 모드)
- WebSocket 모드 테스트 추가

**산출물**: live_trader가 WebSocket 기반으로 실시간 매매. REST 폴백 유지.

---

### Step 3: FastAPI WebSocket 엔드포인트 (프론트엔드 연동)

**파일**: `src/api/v1/realtime.py` (신규)

구현:
- `GET /api/v1/ws/market` — WebSocket 엔드포인트
- 인증: 연결 시 쿠키/토큰 검증
- 클라이언트가 구독 메시지 전송 → 키움 WebSocket에 전달
- 키움 → FastAPI → 프론트엔드 브릿지

**파일**: `src/main.py` (수정)
- WebSocket 라우터 등록

**테스트**: `tests/api/test_realtime.py`

**산출물**: 프론트엔드에서 WebSocket으로 실시간 시세 수신 가능

---

### Step 4: 프론트엔드 실시간 UI (프론트엔드)

**파일**: `frontend/src/hooks/use-realtime.ts` (신규)
- WebSocket 연결 훅
- 체결가/호가 상태 관리
- 자동 재연결

**파일**: `frontend/src/app/(authenticated)/dashboard/page.tsx` (수정)
- 실시간 가격 업데이트

**파일**: `frontend/src/app/(authenticated)/trade/page.tsx` (수정)
- 실시간 호가창

**테스트**: 스모크 테스트 갱신

**산출물**: 대시보드/매매 페이지에서 실시간 시세 표시

---

## 제약사항

| 항목 | 제한 | 대응 |
|------|------|------|
| 그룹당 종목 수 | 100개 | 현재 30종목이라 충분 |
| 모의투자 | 지원 | mockapi.kiwoom.com 동일 |
| 연결 끊김 | 발생 가능 | 자동 재연결 (exponential backoff) |
| REST 폴백 | 필요 | WebSocket 실패 시 5분 폴링으로 자동 전환 |

## 키움 WebSocket 프로토콜

### 구독 요청
```json
POST /api/dostk/websocket
Headers: { "api-id": "0B", "authorization": "Bearer {token}" }
Body: {
  "trnm": "REG",
  "grp_no": "0000",
  "refresh": "1",
  "data": [
    { "item": "KRX:005930", "type": "0B" },
    { "item": "KRX:000660", "type": "0B" }
  ]
}
```

### 실시간 수신
```json
{ "trnm": "REAL", ... 체결 데이터 필드 }
```

### 구독 해지
```json
Body: { "trnm": "REMOVE", "grp_no": "0000", "data": [...] }
```

## 실시간 데이터 타입

| Type | 이름 | 용도 | Step |
|------|------|------|------|
| `0B` | 주식체결 | 체결가/거래량 — 전략 판단 핵심 | 1 |
| `0D` | 주식호가잔량 | 호가창 — 프론트 실시간 | 3 |
| `00` | 주문체결 | 내 주문 체결 알림 | 2 |
| `04` | 잔고 | 보유종목 실시간 변동 | 2 |
| `0s` | 장시작시간 | 장 시작/종료 감지 | 2 |

---

## PR 전략

| Step | 브랜치 | PR | 의존성 |
|------|--------|-----|--------|
| 1 | `feat/websocket-client` | → dev → main | 없음 |
| 2 | `feat/websocket-live-trader` | → dev → main | Step 1 |
| 3 | `feat/websocket-api` | → dev → main | Step 1 |
| 4 | `feat/websocket-frontend` | → dev → main | Step 3 |

각 Step은 독립 PR로, 테스트 통과 + 커버리지 85%+ 후 main 배포.
