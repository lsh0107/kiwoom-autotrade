# Design 025 — Multi-Strategy Orchestrator + Budget Allocation

> **Status**: Draft (작성 중)
> **Author**: lead (Claude)
> **Date**: 2026-05-19
> **Supersedes**: ADR-024 (ACTIVE_STRATEGY 단일 enum)

## 배경

현재 구조는 환경변수 `ACTIVE_STRATEGY` 하나로 1개 전략만 활성. 변경 시 backend/live_trader 재시작 필요. 여러 전략 동시 실행 정식 지원 없음.

운영상 요구:
- cross_momentum (weekly 리밸런스) + short_swing (daily scan) 병행
- DB 토글로 즉시 on/off (재시작 없이)
- 전략별 자산 budget 분리 (중복 주문 방지)
- broker holdings/현금이 공통 source of truth (DB 만 보고 발주 금지)

## 설계 결정

### 1. 단일 진실원: DB `strategy_runtime`

env `ACTIVE_STRATEGY` deprecate. 새 테이블:

```sql
CREATE TABLE strategy_runtime (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy VARCHAR(50) UNIQUE NOT NULL,  -- 'cross_momentum', 'short_swing', 'multi_regime'
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    budget_pct NUMERIC(5,4) NOT NULL DEFAULT 0,  -- 0.0 ~ 1.0
    max_order_amount INTEGER NOT NULL DEFAULT 1000000,
    max_daily_orders INTEGER NOT NULL DEFAULT 100,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(50)
);
```

초기 시드:
| strategy | enabled | budget_pct | max_order_amount |
|---|---|---|---|
| cross_momentum | true | 0.6 | 50_000_000 |
| short_swing | false | 0.3 | 5_000_000 |
| multi_regime | false | 0.0 | 1_000_000 |

`reserve_cash_pct` = 1 - sum(enabled budget) (현재는 코드 계산, 별도 row 불필요).

### 2. `StrategyRegistry` + Orchestrator

`scripts/live_trader.py` 의 `if active_strategy == X` 분기 제거. 대신:

```python
class StrategyRegistry:
    async def load_enabled(self, db) -> list[StrategyConfig]:
        """strategy_runtime 에서 enabled=true 전략들 조회"""

    async def is_enabled(self, db, strategy: str) -> bool: ...

class Orchestrator:
    def __init__(self, registry, budget_manager, risk_guard):
        ...

    async def tick(self, current_hhmm, today):
        enabled = await self.registry.load_enabled(self.db)
        for strategy in enabled:
            handler = self._handlers[strategy.strategy]
            # 각 핸들러는 broker holdings/현금 받아서 자체 판단
            holdings, cash = await self.broker_state()
            allowed_budget = self.budget_manager.allowed(strategy, cash)
            await handler(self.db, self.broker, holdings, allowed_budget, today, current_hhmm)
```

기존 `check_monthly_rebalance` / `check_short_swing_entry/exit` 는 handler 로 래핑.

### 3. `BudgetManager` — 전략별 자산 한도

```python
class BudgetManager:
    async def allowed(self, strategy: StrategyConfig, available_cash: int) -> int:
        """해당 전략에 할당된 budget 만큼의 현금 한도."""
        return int(available_cash * float(strategy.budget_pct))
```

각 strategy handler 는 `allowed_budget` 만 사용. 중복 주문 방지.

`max_order_amount` / `max_daily_orders` 는 `run_all_checks` 게이트에 주입.

### 4. broker holdings/cash 공통 source of truth

orchestrator tick 마다 `broker.get_balance()` 1회 호출 → 모든 핸들러에 `holdings_map`, `available_cash` 인자로 전달. DB orders SUM 만으로 발주 결정 금지.

### 5. `/strategy/runtime` API

```
GET  /api/v1/strategy/runtime           → list[StrategyRuntimeView]
POST /api/v1/strategy/runtime/{strategy} { enabled, budget_pct, max_order_amount, ... }
```

UI 토글에 사용. 변경 즉시 반영 (다음 orchestrator tick 부터).

### 6. UI

`/strategy` 또는 `/admin/strategies` 페이지에 각 전략 enabled toggle + budget slider.

### 7. ACTIVE_STRATEGY env deprecate

호환성 유지: env 가 설정돼 있고 DB 가 비어있으면 1회 마이그레이션 (env → strategy_runtime row 생성). 이후 env 무시.

## 마이그레이션 절차

1. Alembic 021: `strategy_runtime` 테이블 + 초기 시드 (cross_momentum enabled=true budget=0.6)
2. orchestrator 코드 머지 (live_trader 분기 제거)
3. budget manager + handler 인터페이스 통일
4. `/strategy/runtime` API + UI
5. env `ACTIVE_STRATEGY` 코드 제거 (config/active_strategy.py 단순화 또는 폐기)

## 단계별 PR

| PR | 내용 | 의존 |
|---|---|---|
| #1 | design-025 + Alembic 021 (strategy_runtime + 시드) | - |
| #2 | orchestrator + StrategyRegistry + BudgetManager (live_trader 리팩토링) | #1 |
| #3 | /strategy/runtime API + 테스트 | #1 |
| #4 | UI: /strategy 페이지 토글/budget 슬라이더 | #3 |
| #5 | ACTIVE_STRATEGY env 코드 제거 + 호환 마이그레이션 | #2,#3 |
| #6 | QA (cross_momentum + short_swing 동시 운영 시나리오) | #5 |

## 회의 / 결정 트레이드오프

- **Q**: short_swing 을 daily 로 운영 시 cross_momentum weekly 리밸런스 일 (금요일) 충돌? 
  - **A**: orchestrator 가 시각별 핸들러 호출. cross_momentum 은 14:55 1회, short_swing 은 9:20~13:00 진입 + 9:20~15:10 청산. 시각 겹침 없음. budget 만 분리하면 OK.

- **Q**: budget_pct 합이 >1.0 인 경우?
  - **A**: 시드/Update 시 sum 검증. >1.0 이면 API 거부.

- **Q**: cross_momentum daily 가능?
  - **A**: 비추천. 12-1mo 신호는 회전율/잡음 문제. 일봉 데이터 매일 갱신 + 리밸런스 weekly 유지.

## 운영 영향

- env `ACTIVE_STRATEGY` 사용자 환경 (`docker-compose.override.yml`) 정리 후속 필요 (사용자 영역).
- 기존 cross_momentum 동작은 PR #2 머지 후에도 호환 (DB strategy_runtime 시드 enabled=true 로 동일 동작).
- short_swing 활성 잠금 메모리 (mock 1주 dry-run 검증 전 운영 잠금) 는 그대로 유지. PR #3 머지 후에도 strategy_runtime.short_swing.enabled=false 로 유지.

## 후속 결정 필요

- short_swing 활성화 (사용자 명시 OK 후)
- multi_regime 활성화 정책
- 실거래 small-real 전환 시 budget_pct 조정 정책
