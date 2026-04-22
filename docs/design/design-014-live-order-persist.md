# ADR-014: live_trader → orders DB persist 브릿지

| 항목 | 내용 |
|------|------|
| 상태 | 구현 완료 (2026-04-22) |
| 구현 브랜치 | feat/fix-live-trader-order-persist |
| 관련 파일 | `src/trading/live_order_persist.py`, `scripts/live_trader.py` |

## 배경

`scripts/live_trader.py`는 broker 주문 접수 후 in-memory `TradeLog` dataclass에만 기록하며,
`src/models/order.py` 기반 DB `orders` 테이블과 완전히 분리되어 있었다.
2주간 실제 매수 신호가 발생했음에도 `orders` 테이블에 0건이 기록되는 문제 발생.

- `persist` 함수는 `src/trading/order_service.py` (create_order/submit_order)에 이미 존재
- `live_trader`는 `order_service`를 import조차 하지 않음
- API 경로(FastAPI)를 통한 주문만 DB에 기록됨

## 결정

**옵션 A 채택**: persistence adapter 레이어를 live_trader에 그림자처럼 추가.

```
broker.place_order() 성공
    ↓
log.info("[매수/매도 접수]")
    ↓
[NEW] try: async_session_factory → persist_order_submitted() → commit
      except: log.error(무시)   ← DB 장애 시 매매 경로 유지
    ↓
state.trades.append(TradeLog(...))  ← 기존 in-memory 경로 그대로
```

## 대안 비교

| 옵션 | 설명 | 기각 사유 |
|------|------|----------|
| **A (채택)** | persist adapter 레이어, broker 성공 직후 DB insert | 최소 수정, 기존 TradeLog 유지 |
| B | order_service.create_order 직접 호출 | Kill Switch 검증 중복 실행, 비동기 트랜잭션 충돌 위험 |
| C | broker 응답을 백엔드 API로 POST | HTTP hop 추가, 지연 증가, 네트워크 장애 의존성 |

## 트레이드오프

| 관점 | 내용 |
|------|------|
| 장점 | 기존 TradeLog in-memory 경로 100% 유지, DB 장애 시 매매 영향 없음 |
| 장점 | 단일 변수 원칙 — persist만 추가, 매매 로직 미변경 |
| 단점 | order_service의 Kill Switch 검증을 거치지 않음 (live_trader는 자체 drawdown_guard 사용) |
| 단점 | 세션을 별도 생성하므로 트랜잭션이 메인 루프와 분리됨 |

## 구현 세부사항

### 신규 모듈: `src/trading/live_order_persist.py`

| 함수 | 역할 |
|------|------|
| `get_is_mock()` | `KIWOOM_IS_MOCK` env 판정 (기본 True) |
| `resolve_live_trader_user_id(db)` | env UUID → fallback dev@example.com |
| `persist_order_submitted(session, ...)` | SUBMITTED 상태로 insert |
| `persist_order_filled(session, ...)` | FILLED/PARTIAL_FILL 업데이트 |
| `persist_order_failed(session, ...)` | FAILED 업데이트 |
| `reset_cached_user_id()` | 테스트용 캐시 초기화 |

### 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LIVE_TRADER_USER_ID` | 미설정 | 트레이더 사용자 UUID. 미설정 시 dev@example.com fallback |
| `KIWOOM_IS_MOCK` | `true` | orders.is_mock 판정. false이면 실거래 |

### user_id 결정 로직

```
LIVE_TRADER_USER_ID 환경변수 설정?
  ├─ YES: UUID 파싱 성공? → 사용 / 실패 → fallback
  └─ NO: dev@example.com 사용자 DB 조회
           └─ 없으면 RuntimeError (시작 불가)
```

### live_trader.py 수정 포인트

- `execute_buy` line ~755: `log.info("[매수 접수]")` 직후
- `execute_sell` line ~850: `log.info("[매도 접수]")` 직후
- 각각 독립 `try/except` → DB 장애 시 `log.error` 후 계속 진행

## 테스트

`tests/trading/test_live_order_persist.py`:
- `persist_order_submitted` 정상 insert (매수/매도, is_mock)
- `persist_order_filled` FILLED / PARTIAL_FILL 분기
- `persist_order_failed` FAILED 업데이트
- user_id fallback (env UUID, 잘못된 UUID, dev@example.com, 없음 RuntimeError)
- DB 장애 시 `try/except` 패턴 검증 (메인 경로 살아있음)

## 미결 사항

- [ ] 체결 콜백 (WebSocket fill event) 연동: 현재 live_trader에 체결 콜백 미구현.
      추후 `persist_order_filled` 호출 지점 추가 예정.
- [ ] `symbol_name` 필드: live_trader의 `name` 파라미터가 있으나 어댑터 시그니처에 미포함.
      필요 시 `persist_order_submitted`에 `symbol_name` 파라미터 추가.
