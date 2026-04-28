---
name: design-023-cross-momentum-hardening
description: ADR-022 미해결 위험 4건 중 3건 해소 — rate limit 백오프 (DB 캐싱 + pykrx retry), T+2 결제 시뮬레이션 (메모리 큐), KRX 공휴일 캘린더 (2025~2027). ADR-023 견고화 완료, 모의 4주 관찰 시작 가능.
type: design
status: "활성 — 견고화 완료, 모의 4주 관찰 시작 가능"
created: 2026-04-28
depends_on:
  - design-021-cross-sectional-momentum
  - design-022-cross-momentum-live-adapter
  - design-011-daily-candle-caching
related:
  - src/utils/krx_calendar.py
  - src/trading/cross_momentum_rebalance.py
  - data/krx_holidays.json
  - scripts/live_trader.py
---

# ADR-023: Cross-Momentum 견고화 — Rate Limit · T+2 · 공휴일

## 상태 이력

| 날짜 | 상태 | 사유 |
|------|------|------|
| 2026-04-28 | 신규 — 구현 완료 | ADR-022 미해결 위험 4건 중 3건 해소 (commit 36098b9) |
| 2026-04-28 | 견고화 완료 | 1871 회귀 PASS, krx_calendar 100%, rebalance 87%. 모의 시작 가능 |

---

## §1. 배경

ADR-022는 `USE_CROSS_MOMENTUM=true` 플래그로 모의투자 시작이 가능한 상태로 마무리됐으나, §9에서 **미해결 위험 4건**을 명시했다.

| # | 위험 | 심각도 |
|---|------|--------|
| 1 | 키움 rate limit — 200종목 pykrx 일봉 수집 시 초과 가능 | 중 |
| 2 | T+2 결제 — 실거래 시 매도 대금 즉시 미반영, 매수 현금 부족 가능 | 높음 |
| 3 | quantity=0 전량매도 키움 API 지원 여부 미확인 | 중 |
| 4 | 공휴일 처리 — 주말만 제외, 임시공휴일·대체공휴일 미반영 | 중 |

본 ADR(ADR-023)은 위험 **#1, #2, #4** 3건을 해소한다. 위험 #3은 PR #350/#351 hotfix에서 별도 처리 완료.

---

## §2. 위험 #1 해소: Rate Limit — DB 캐싱 + pykrx 백오프

### 문제

`compute_rebalance_orders` 내부에서 200종목 일봉을 매번 pykrx로 호출 → 분당 요청 제한 초과 시 빈 데이터프레임 반환 → 잘못된 리밸런싱 실행.

### 해결 설계

```
daily_candle_store (DB, design-011)
    ↓ 조회 → missing symbol 목록 추출
pykrx fetch (missing만, 배치 처리)
    ↓ retry on failure (backoff)
daily_candle_store UPSERT
```

#### 구현 세부

- **DB 우선 조회**: `daily_candle_store` 테이블에서 해당 날짜 일봉 존재 여부 확인 → 존재하면 pykrx 생략
- **`_fetch_pykrx_with_backoff`**: 3회 retry, sleep = 0.5 × 2^attempt (0.5s → 1.0s → 2.0s)
- missing만 fetch → API 호출 최소화 (200종목 전체 → 실제로는 신규 종목만)

#### 트레이드오프

| 방식 | 장점 | 단점 |
|------|------|------|
| DB 캐싱 우선 | API 호출 최소화, rate limit 회피 | DB 최신성 의존 (DAG 실패 시 stale 가능) |
| 매번 pykrx | 항상 최신 | rate limit 위험, 느림 |
| **채택: DB 우선 + missing만 backoff** | 최소 호출 + 안전 fallback | 구현 복잡도 소폭 증가 |

---

## §3. 위험 #2 해소: T+2 Cash Flow 시뮬레이션

### 문제

한국 주식은 매도 후 T+2 영업일에 결제된다. 현재 코드는 매도 즉시 현금을 가용으로 처리 → 실전 모드에서 매도 당일 매수 시 증거금 부족 주문 실패 가능.

### 해결 설계

```python
@dataclass
class T2PendingSettlement:
    symbol: str
    sell_amount: float       # 매도 대금 (세금/수수료 차감 전)
    sell_date: date          # 매도 체결일
    settle_date: date        # T+2 결제일 (krx_calendar 기준)
```

#### 모의 vs 실전 동작 차이

| 구분 | 동작 |
|------|------|
| 모의 (`t2_settlement=False`, 기본값) | 매도 대금 즉시 현금 반영 (백테스트와 동일) |
| 실전 (`t2_settlement=True`) | 매도 대금 → `t2_pending` 큐 적재, `settle_date` 도래 시 현금 반영 |

#### settle_date 산정

```python
settle_date = add_business_days(sell_date, 2)  # krx_calendar 기준
```

- `add_business_days(date, n)`: 공휴일·주말 건너뜀, `krx_holidays.json` 참조
- 예시: 금요일 매도 → settle_date = 다음 주 화요일 (공휴일 끼면 수요일)

#### `compute_rebalance_orders` 시그니처 확장

```python
def compute_rebalance_orders(
    target_symbols: list[str],
    current_positions: dict[str, int],
    available_cash: float,
    price_map: dict[str, float],
    params: RebalanceParams,
    t2_pending: list[T2PendingSettlement] | None = None,  # 추가
) -> RebalanceOrders:
```

- `t2_pending`이 있으면 `settle_date <= today`인 항목의 `sell_amount`를 `available_cash`에 가산
- `t2_settlement=False`(모의)이면 `t2_pending=None` 그대로, 즉시 반영

#### 1차 구현 제약 (follow-up TODO)

현재는 **메모리 큐**만 구현. 서버 재기동 시 `t2_pending` 큐 손실 → DB 영속화가 별도 follow-up으로 필요 (§7 참조).

---

## §4. 위험 #4 해소: KRX 공휴일 캘린더

### 문제

기존 `_is_last_trading_day_of_month`는 주말만 제외하고 KRX 공휴일(설날·추석·대체공휴일 등)을 미반영 → 공휴일 직전 마지막 영업일을 마지막 거래일로 잘못 판정하는 시나리오 존재.

### 해결 설계

#### `data/krx_holidays.json`

- 2025~2027년 KRX 공휴일 정적 데이터 (대체공휴일 포함)
- 형식: `{"holidays": ["2025-01-01", "2025-01-28", ...]}`
- **매년 12월 갱신 절차** (§7 참조)

#### `src/utils/krx_calendar.py` API

| 함수 | 설명 |
|------|------|
| `is_business_day(date)` | 주말·공휴일 아닌 날 → True |
| `previous_business_day(date)` | 해당 날짜 이전 가장 최근 영업일 |
| `next_business_day(date)` | 해당 날짜 이후 가장 최근 영업일 |
| `is_last_business_day_of_month(date)` | 월의 마지막 영업일 여부 |
| `add_business_days(date, n)` | n 영업일 후 날짜 (T+2 산정에 사용) |

#### 기존 코드 교체

```python
# 이전: 주말만 제외
def _is_last_trading_day_of_month(self, date: date) -> bool:
    ...  # weekday() < 5 체크

# 이후: krx_calendar 호출
from src.utils.krx_calendar import is_last_business_day_of_month

def _is_last_trading_day_of_month(self, date: date) -> bool:
    return is_last_business_day_of_month(date)
```

---

## §5. 백테스트와 실전 모드의 Cash Flow 차이

백테스트(`portfolio_engine.py`)는 매도 후 동일 시뮬레이션 스텝 내 현금을 즉시 가용으로 처리한다. 이는 **동기 가정**으로, 백테스트 성과와 실전 성과 사이에 체계적 편차를 만들 수 있다.

| 구분 | Cash Flow 처리 |
|------|---------------|
| 백테스트 | 매도 즉시 현금 반영 (동기, 단순화) |
| 실전 (`t2_settlement=False`) | 매도 즉시 현금 반영 (모의는 동일) |
| 실전 (`t2_settlement=True`) | 매도 후 T+2 결제 대기 (비동기, 현실 반영) |

**의미**: 모의투자 4주 기간 동안은 `t2_settlement=False` 기본값으로 백테스트와 동일 조건으로 관찰. 실전 전환 시 `t2_settlement=True`로 변경하여 현실적인 cash flow 시뮬레이션 적용.

---

## §6. 테스트 결과

| 구분 | 결과 |
|------|------|
| 신규 테스트: `tests/utils/test_krx_calendar.py` | 18 PASS (커버리지 100%) |
| 신규 테스트: `tests/trading/test_cross_momentum_rebalance_t2.py` | 18 PASS (커버리지 87%) |
| 회귀 전체 | 1871 PASS |
| commit | 36098b9 |

---

## §7. Follow-up TODO

| 우선순위 | 항목 | 설명 |
|----------|------|------|
| 높음 | **t2_pending DB 영속화** | 현재 메모리 큐 → 재기동 시 손실. PostgreSQL `t2_pending_settlements` 테이블 + Alembic 마이그레이션으로 영속화 필요 |
| 중 | **매년 12월 공휴일 캘린더 갱신** | `data/krx_holidays.json`에 다음 해 공휴일 추가. KRX 공식 공시 기준 (매년 11~12월 발표). Alembic 아닌 수동 JSON 편집 |
| 낮음 | **임시공휴일 자동 동기화** | 정부 임시공휴일 지정은 사전 예고가 짧음. Airflow DAG + KRX/공공데이터포털 API로 자동 갱신 검토 (Phase 3) |

---

## §8. 모의 진입 가능 선언

ADR-022 미해결 위험 4건이 모두 처리됐다 (#3은 PR #350/#351, #1/#2/#4는 본 ADR).

**`USE_CROSS_MOMENTUM=true` 설정 후 모의 4주 관찰 즉시 시작 가능.**

단, 다음 조건은 모의 기간 이후 실전 전환 시 별도 판단:

- `t2_settlement=True` 활성화 (실전 전환 전 테스트)
- `t2_pending` DB 영속화 완료
- 모의 4주 관찰 기준 전부 충족 (ADR-022 §7 참조)
- 사용자 명시적 승인

---

## §9. 교차 참조

- design-022 §9: 미해결 위험 4건 원문 (본 ADR이 해소)
- design-021 §7: 모의 4주 관찰 기준 (OOS Sharpe ≥ 1.0, MDD ≥ -25%, IR ≥ 0.3)
- design-011: `daily_candle_store` DB 캐싱 설계 (§2 DB 우선 조회 의존)
- docs/operations/strategy-redesign-rollout.md: 모의 진입 절차 + 운영 체크리스트
