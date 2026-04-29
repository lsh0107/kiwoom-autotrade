---
name: design-022-cross-momentum-live-adapter
description: ADR-021 PASS 이후 Cross-sectional momentum 전략을 live_trader에 통합하기 위한 월별 리밸런싱 어댑터 설계 + 구현 완료. CrossMomentumRebalanceAdapter, RebalanceParams/Orders, 스케줄러 통합(14:55), ACTIVE_STRATEGY=cross_momentum (구 USE_CROSS_MOMENTUM 환경변수는 ADR-024로 폐기), 안전장치 4종.
type: design
status: "활성 — 어댑터 구현 완료, 모의 4주 관찰 대기"
created: 2026-04-27
updated: 2026-04-28
depends_on:
  - design-013-multi-regime-strategy
  - design-014-live-order-persist
  - design-015-backtest-engine-integrity
  - design-021-cross-sectional-momentum
related:
  - src/strategy/cross_momentum_universe.py
  - src/trading/cross_momentum_rebalance.py
  - scripts/live_trader.py
---

# ADR-022: Cross-Momentum Live Rebalance 어댑터

## 상태 이력

| 날짜 | 상태 | 사유 |
|------|------|------|
| 2026-04-27 | 신규 — 설계 시작 | ADR-021 PASS, live_trader 통합 어댑터 필요 |
| 2026-04-28 | 구현 완료 | 21 신규 + 611 회귀 PASS, 커버리지 85.05% |
| 2026-04-28 | 모의 4주 관찰 대기 | `ACTIVE_STRATEGY=cross_momentum` 설정 시 시작 가능 (구 `USE_CROSS_MOMENTUM` 환경변수는 ADR-024로 폐기) |
| 2026-04-29 | ADR-024 반영 | `USE_CROSS_MOMENTUM`/`USE_MULTI_REGIME` → `ACTIVE_STRATEGY` enum 단일화. `validate_cross_momentum_exclusivity` 삭제됨. |

---

## §1. 배경

ADR-021에서 Cross-sectional momentum (top20pct_novol_notrend)이 V2 기준 PASS 판정을 받았다 (2/6 윈도우 = 33%, OOS Sharpe 1.22·3.24, IR 1.37·1.75). 모의 진입 후보 확정.

그러나 기존 live_trader.py는 단일 종목 시그널 기반 주문 구조다. Cross-momentum은 **포트폴리오 월별 리밸런싱** 방식 — 상위 20% 모멘텀 종목 40개를 유지하고, 매월 마지막 거래일에 target vs 현재 포지션 diff를 계산해 매도·매수 순서로 주문한다.

이 차이를 bridge하기 위한 전용 어댑터가 필요하다. 기존 `_assign_symbol_strategies` 경로(multi-regime)를 우회하고, 월말 스케줄러 독립 등록으로 동작한다.

---

## §2. 핵심 설계 결정

| # | 결정 | 선택 | 근거 |
|---|------|------|------|
| 1 | 유니버스 관리 | **동결 200종목** (KOSPI100+KOSDAQ100) | 백테스트와 동일 조건 유지. 운영 중 종목 추가/제거 없음 |
| 2 | 리밸런싱 주기 | **월 1회, 마지막 거래일** | ADR-021 설계 그대로. 일봉 모멘텀 score로 순위 산정 |
| 3 | 보유 종목 수 + sizing | **top 20% = 40종목**, equal-weight | 백테스트와 동일 조건. position 당 현금 균등 배분 |
| 4 | 어댑터 클래스 | `CrossMomentumRebalanceAdapter` | live_trader 내부에서 `_check_monthly_rebalance(state)` 훅으로 호출 |
| 5 | 스케줄러 통합 | `current_hhmm == "14:55"` + 마지막 거래일 | 14:30 ranking 산정 → 14:55 주문 (시장가 매도 선행, 매수 후행) |
| 6 | 마지막 거래일 판정 | 월 마지막 주말 제외 날 비교 | 공휴일 미반영 — 미해결 위험 §9.4 참조 |
| 7 | live_order_persist 통합 | 기존 `_persist_order` 재사용 | ADR-014 orders 테이블 shadow write |
| 8 | ~~USE_CROSS_MOMENTUM / USE_MULTI_REGIME 상호배타~~ → **ACTIVE_STRATEGY enum 단일화** | ADR-024: `ACTIVE_STRATEGY` enum으로 전략 선택 단일화 | `validate_cross_momentum_exclusivity` 함수 삭제됨 (ADR-024). 전략 충돌은 enum 레벨에서 원천 차단. |

---

## §3. 어댑터 인터페이스

### 파일 위치

- `src/strategy/cross_momentum_universe.py` — 동결 유니버스 200종목
- `src/trading/cross_momentum_rebalance.py` — 어댑터 본체

### RebalanceParams

```python
@dataclass
class RebalanceParams:
    formation_months: int = 12    # 모멘텀 측정 기간 (12개월)
    skip_months: int = 1          # 최근 1개월 skip (단기 반전 제거)
    top_pct: float = 0.20         # 상위 20% 선택
    universe: list[str] = field(  # 동결 200종목
        default_factory=lambda: CROSS_MOMENTUM_UNIVERSE
    )
```

### RebalanceOrders

```python
@dataclass
class RebalanceOrders:
    sells: list[str]              # 매도 대상 종목 코드
    buys: list[str]               # 매수 대상 종목 코드
    target_symbols: list[str]     # 목표 보유 40종목
    cash_per_position: int        # 종목당 배분 현금 (원)
```

### CrossMomentumRebalanceAdapter 공개 API

| 메서드 | 역할 |
|--------|------|
| `compute_target_portfolio(params)` | 유니버스 일봉 수집 → 모멘텀 score → top 40 선택 |
| `compute_rebalance_orders(target, current_holdings, cash)` | target vs 현재 diff → sells / buys 산출 |
| `execute_monthly_rebalance(state)` | 매도 주문 → 매수 주문 → DB persist |

### 내부 헬퍼

- `_score_and_select(params)` — formation 기간 수익률 계산 + vol/trend 필터 비적용 (top20pct_novol_notrend)
- `check_monthly_rebalance(state)` — live_trader 훅 진입점
- ~~`validate_cross_momentum_exclusivity()`~~ — **ADR-024로 삭제됨** (USE_MULTI_REGIME 동시 감지 로직은 ACTIVE_STRATEGY enum 단일화로 대체)

### 의존성 다이어그램

```
CrossMomentumRebalanceAdapter
    ├── KiwoomClient               # 키움 REST API (주문 + 잔고 조회)
    ├── DailyCandleStore           # ADR-011 일봉 DB (pykrx 캐시)
    ├── LiveOrderPersist           # ADR-014 orders 테이블
    └── cross_momentum.compute_momentum_score  # ADR-021 전략 로직
```

---

## §4. 데이터 흐름

```
매월 마지막 거래일
│
├── 14:30  ranking 산정
│           ├── 유니버스 200종목 일봉 수집 (DailyCandleStore)
│           ├── formation 12개월 수익률 계산
│           ├── skip 1개월 제외
│           ├── top 20% = 40종목 선택
│           └── target_symbols 확정
│
├── 14:55  주문 실행
│           ├── 현재 보유 종목 조회 (KiwoomClient.get_holdings)
│           ├── diff 계산 → sells / buys
│           ├── 매도 주문 (시장가) — 현금 확보 선행
│           ├── 잔고 새로고침
│           ├── 매수 주문 (시장가) — cash_per_position 균등 배분
│           └── orders DB persist (LiveOrderPersist)
│
└── 익일    결과 확인 (로그 + dashboard)
```

---

## §5. 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| ~~`USE_CROSS_MOMENTUM`~~ | — | **ADR-024로 폐기** → `ACTIVE_STRATEGY=cross_momentum` 사용 |
| ~~`USE_MULTI_REGIME`~~ | — | **ADR-024로 폐기** → `ACTIVE_STRATEGY=multi_regime` 사용 |
| `ACTIVE_STRATEGY` | `none` | `cross_momentum` 설정 시 어댑터 활성화 + 월말 스케줄러 등록 |
| `MAX_ORDER_AMOUNT_KRW` | `5000000` | 종목당 최대 주문 금액 (5,000,000원) |

활성화 방법:

```bash
# .env에서 전략 설정 (ADR-024: USE_CROSS_MOMENTUM 폐기됨)
ACTIVE_STRATEGY=cross_momentum

# live_trader 재기동 (is_mock_trading=True 확인 필수)
bash scripts/start_trading.sh
```

---

## §6. 안전장치

| 안전장치 | 동작 |
|----------|------|
| 종목당 주문 한도 | `MAX_ORDER_AMOUNT_KRW` 초과 시 수량 하향 조정 (기본 5,000,000원) |
| 가격제한폭 초과 SKIP | 상/하한가 도달 종목 주문 생략 (체결 불가) |
| 시장 운영시간 검증 | 09:00~15:30 외 리밸런싱 SKIP |
| cooldown 우회 | 월 리밸런싱 시 종목당 cooldown 예외 허용 |
| 모의투자 강제 | `is_mock_trading=True` 기본값 유지 — 실전 전환은 명시적 변수 변경 필수 |
| ~~USE_MULTI_REGIME 상호배타~~ | **ADR-024로 대체** — `ACTIVE_STRATEGY` enum 단일화로 충돌 원천 차단. `validate_cross_momentum_exclusivity` 삭제됨. |

---

## §7. 모의 4주 관찰 기준

**실전 전환 전 필수 조건** (모두 충족 시만 검토):

| 지표 | 기준값 | 근거 |
|------|--------|------|
| 4주 누적 수익률 | **양수** | 절대 손실 없음 |
| OOS Sharpe (관찰 4주 기준) | **≥ 1.0** | ADR-021 V2 PASS 기준과 일치 |
| 최대 낙폭 (MDD) | **≥ -25%** | ADR-021 V2 기준 |
| IR (관찰 기간) | **≥ 0.3** | 한국 long-only 실증 기준 |
| 이상 거래 | **0건** | kill_switch 미발동 + 가격제한폭 SKIP 0건 |
| API 연결 안정성 | **접속 오류 0회** | 키움 REST 안정성 |

> **주의**: 위 기준은 필요조건이지 충분조건이 아님. 실전 전환은 사용자 명시적 승인 필수.

---

## §8. 실전 전환 절차

모의 4주 관찰 기준 통과 후:

1. **1개월 소액 실전** — 총 투자금 1,000만원 한도 (`MAX_ORDER_AMOUNT_KRW` 조정)
2. **1개월 소액 결과 검토** — 모의 대비 성과 비율 ≥ 50%
3. **점진적 증액** — 사용자 결정

```bash
# 실전 전환 (명시적 변경 필요 — 기본값 절대 변경 금지)
# .env
is_mock_trading=False        # 반드시 명시적으로 변경
MAX_ORDER_AMOUNT_KRW=200000  # 소액 테스트 시 낮게 설정

# 전환 전 확인
grep -E "(is_mock_trading|USE_CROSS_MOMENTUM|MAX_ORDER)" .env
```

**중단 기준** (아래 중 하나 발생 시 즉시 모의 복귀):

- 실전 누적 수익률 < OOS 기대수익률의 50%
- MDD > 백테스트 OOS MDD × 1.5
- API 연결 장애 3회 이상
- kill_switch HARD_STOP 1회

---

## §9. 미해결 위험

> backend 구현팀 보고 기반 (2026-04-28). 실전 전환 전 해결 필요.

| # | 위험 | 영향도 | 해소 방안 |
|---|------|--------|-----------|
| 1 | 키움 rate limit (200종목 pykrx 일봉 수집) | 중 | 수집 후 DB 캐시 확인, 실패 종목 재시도 로직 추가 필요 |
| 2 | T+2 결제 (매도 대금 즉시 미반영) | 높음 | 모의 환경에선 즉시 반영이나 실거래 시 매수 가용현금 부족 가능. 실전 전환 시 buffer 확보 필수 |
| 3 | 전량 매도 quantity=0 키움 API 지원 여부 | 중 | 수량이 0이 되는 엣지 케이스 키움 API 명세 확인 필요 |
| 4 | 공휴일 처리 (현재 주말만 제외) | 낮음 | 임시공휴일(석가탄신일, 대체공휴일 등) 미반영 → 공휴일 주문 미발생 (SKIP 안전) |

---

## §10. 교차 참조

- **ADR-021** (`design-021-cross-sectional-momentum.md`): 이 어댑터의 전략 근거 — top20pct_novol_notrend V2 PASS 결과
- **ADR-014** (`design-014-live-order-persist.md`): orders 테이블 persist — 어댑터 주문 DB 기록 경로
- **ADR-013** (`design-013-multi-regime-strategy.md`): multi-regime 배선 — ADR-024로 ACTIVE_STRATEGY enum 통합, USE_CROSS_MOMENTUM/USE_MULTI_REGIME 폐기
- **ADR-024** (`design-024-active-strategy-enum.md`): ACTIVE_STRATEGY enum 단일화 — USE_CROSS_MOMENTUM/USE_MULTI_REGIME 환경변수 폐기 + validate_cross_momentum_exclusivity 삭제
- **ADR-015** (`design-015-backtest-engine-integrity.md`): 백테스트 엔진 integrity 기준 — 어댑터 ranking 산정에도 동일 기준 적용
- **operations/strategy-redesign-rollout.md**: 모의→실전 전환 절차 + 4주 관찰 체크리스트
