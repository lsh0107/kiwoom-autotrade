---
name: design-014-live-order-persist
description: live_trader → orders/trade_logs DB persist 브릿지 (shadow write 패턴)
type: design
status: 활성
created: 2026-04-22
related:
  - src/trading/live_order_persist.py
  - scripts/live_trader.py
  - src/models/order.py
  - src/trading/order_service.py
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-22 | 초안 작성 → 구현 완료 (PR #322). 상태 draft → active. |

# ADR-014: live_trader → orders DB persist 브릿지

| 항목 | 내용 |
|------|------|
| 상태 | 활성 (구현 완료 2026-04-22) |
| 구현 브랜치 | feat/fix-live-trader-order-persist |
| 관련 파일 | `src/trading/live_order_persist.py`, `scripts/live_trader.py` |

## 1. 배경

`scripts/live_trader.py`는 broker 주문 접수 후 in-memory `TradeLog` dataclass에만 기록하며,
`src/models/order.py` 기반 DB `orders` 테이블과 완전히 분리되어 있었다.
2주간 실제 매수 신호가 발생했음에도 `orders` 테이블에 0건이 기록되는 문제 발생.

- `persist` 함수는 `src/trading/order_service.py` (create_order/submit_order)에 이미 존재
- `live_trader`는 `order_service`를 import조차 하지 않음
- API 경로(FastAPI)를 통한 주문만 DB에 기록됨

근본 원인: live_trader는 독립 프로세스(스크립트)로 실행되며 FastAPI 앱의 세션 팩토리와
공유 컨텍스트가 없어 order_service를 자연스럽게 호출할 수 없었다.

## 2. 결정

**옵션 A 채택**: persistence adapter 레이어를 live_trader에 그림자처럼 추가 (shadow write 패턴).

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

### 왜 shadow write를 선택했는가

| 기준 | 근거 |
|------|------|
| **매매 경로 무결성** | DB 장애가 실제 매수/매도 실행에 영향을 주면 안 됨. shadow write는 DB 오류를 `log.error`로만 처리하고 계속 진행. |
| **코드 변경 최소화** | 기존 `TradeLog` in-memory 경로 100% 유지. broker 성공 직후 `try/except` 블록만 삽입 — 회귀 리스크 극소화. |
| **Kill Switch 안전성** | `order_service.create_order`를 직접 호출하면 Kill Switch·DrawdownGuard 검증이 중복 실행됨. live_trader는 자체 `drawdown_guard`를 이미 사용하므로 별도 어댑터가 안전. |
| **트랜잭션 독립성** | live_trader 이벤트 루프와 분리된 세션을 사용해 메인 루프 지연·데드락 방지. |

## 3. 대안 비교

| 옵션 | 설명 | 기각 사유 |
|------|------|----------|
| **A (채택)** | shadow write 어댑터 — broker 성공 직후 DB insert, 실패 시 무시 | 최소 수정, 기존 TradeLog 유지 |
| B | `order_service.create_order` 직접 호출 | Kill Switch 검증 중복 실행, 비동기 트랜잭션 충돌 위험, 코드 변경 범위 큼 |
| C | broker 응답을 백엔드 API로 POST (내부 HTTP) | HTTP hop 추가, 지연 증가, 네트워크 장애 추가 의존성, over-engineering |

### 트레이드오프 요약

| 관점 | 내용 |
|------|------|
| 장점 | 기존 TradeLog in-memory 경로 100% 유지 |
| 장점 | DB 장애 시 매매 경로 무영향 |
| 장점 | 단일 변경 원칙 — persist만 추가, 매매 로직 미변경 |
| 단점 | order_service의 Kill Switch 검증을 거치지 않음 (live_trader는 자체 drawdown_guard 사용) |
| 단점 | 세션을 별도 생성하므로 트랜잭션이 메인 루프와 분리됨 |
| 단점 | DB 0건 이슈 재발 시 어댑터 로그로만 추적 가능 (API 주문 이력과 별도) |

## 4. 구현 세부사항

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

## 5. 장애 시나리오

| 시나리오 | 동작 | 영향 |
|---------|------|------|
| **DB 서버 다운** | `persist_order_submitted` 내 DB 연결 실패 → `except` 캐치 → `log.error` 기록 후 `state.trades.append` 정상 실행 | 매매는 계속. orders 테이블에 미기록. |
| **DB 응답 지연 (타임아웃)** | 세션 타임아웃(기본 SQLAlchemy 30s) → `except` 캐치 | 매매 루프 해당 사이클 지연 가능. 이후 정상화. |
| **user_id fallback 실패 (dev@example.com 없음)** | `resolve_live_trader_user_id`에서 `RuntimeError` 발생 → live_trader 시작 불가 | 시작 전에 실패하므로 운영 중 장애 없음. 사전 점검 필수. |
| **UUID 파싱 오류** (`LIVE_TRADER_USER_ID` 형식 불량) | `ValueError` 캐치 → dev@example.com fallback으로 진행 | 로그에 경고. 잘못된 UUID 설정 시 개발자 계정으로 기록됨. |
| **orders 테이블 스키마 불일치** | `persist_order_submitted` 내 `IntegrityError`/`DataError` → `except` 캐치 | 매매는 계속. orders 기록 실패. 마이그레이션 필요 신호. |
| **DB 복구 후** | 다음 주문부터 자동 기록 재개. 복구 전 주문은 in-memory TradeLog만 존재. | 장애 구간 데이터 복구는 별도 스크립트 필요 (미구현). |

## 6. 테스트

`tests/trading/test_live_order_persist.py`:
- `persist_order_submitted` 정상 insert (매수/매도, is_mock)
- `persist_order_filled` FILLED / PARTIAL_FILL 분기
- `persist_order_failed` FAILED 업데이트
- user_id fallback (env UUID, 잘못된 UUID, dev@example.com, 없음 RuntimeError)
- DB 장애 시 `try/except` 패턴 검증 (메인 경로 살아있음)

## 7. 후속 TODO

| 항목 | 우선순위 | 설명 |
|------|---------|------|
| integration test | 높음 | PostgreSQL 테스트 컨테이너 기반 end-to-end: broker 성공 → orders 행 확인. 현재는 mock DB 단위 테스트만 존재. |
| `LIVE_TRADER_USER_ID` 스토리지 표준화 | 중간 | 운영 환경에서 UUID를 .env에 직접 넣는 것은 관리 불편. Vault/secret manager 또는 strategy_config 테이블에서 조회하는 방안 검토. |
| 체결 콜백 연동 | 중간 | 현재 live_trader에 WebSocket fill event 콜백 미구현. 추후 `persist_order_filled` 호출 지점 추가 필요. |
| `symbol_name` 필드 | 낮음 | live_trader의 `name` 파라미터가 있으나 어댑터 시그니처에 미포함. 필요 시 `persist_order_submitted`에 `symbol_name` 파라미터 추가. |
| 장애 구간 데이터 복구 스크립트 | 낮음 | DB 다운 구간 in-memory TradeLog 기반 소급 insert 스크립트. 현재 미구현. |
