# Multi-Strategy Portfolio Controller — 설계 문서

> **상태**: 설계 (PR 0). **코드 구현 없음.** 본 문서는 멀티전략 포트폴리오 운영 구조의 목표 설계와 단계별 로드맵을 정의한다.
>
> **목표**: 단일 전략 선택/폐기가 아니라 **여러 전략을 동시에 운영하는 포트폴리오 구조**. cross_momentum · short_swing · multi_regime · ai_hedge 를 모두 보존하고, 예산·포지션 ownership·매도 권한·시간대를 분리해 서로 간섭하지 않게 한다.
>
> **작성 기준**: 2026-06-08 현재 코드. 인용한 `파일:라인` 은 작성 시점 기준이며, 구현 PR 진입 시 재확인한다 (doc-freshness: 코드 우선).
>
> **안전 원칙 (변경 불가)**: 기본 모의투자, broker holdings = source of truth, fake fallback 금지, AI hedge 는 직접 주문 금지(제안만), 기존 kill switch / risk gate 보존. (`.claude/rules/trading-safety.md`, `.claude/rules/security.md`)

---

## 0. 용어

| 용어 | 의미 |
|---|---|
| 전략(strategy) | cross_momentum / short_swing / multi_regime / ai_hedge 식별자 |
| orchestrator | 매 tick 활성 전략을 dispatch 하는 멀티전략 실행기 (`src/trading/orchestrator.py`) |
| handler | orchestrator 가 전략별로 호출하는 함수 (`src/trading/handlers/*.py`) |
| budget | 전략에 할당된 가용 현금 상한 (`strategy_runtime.budget_pct`) |
| ownership | 어떤 전략이 특정 포지션을 "소유"하는지 (청산 권한 근거) |
| overlay | 직접 주문하지 않고 다른 전략의 매매를 필터/조정하는 계층 (ai_hedge) |

---

## 1. 현재 코드 구조 조사

### 1.1 strategy_runtime 스키마

`src/models/strategy_runtime.py:14-81`

| 컬럼 | 타입 | 기본값 | 비고 |
|---|---|---|---|
| id | UUID | gen_random_uuid() | PK |
| strategy | String(50) | — | **unique** 인덱스 |
| enabled | Boolean | False | 매 tick 조회 |
| budget_pct | Numeric(5,4) | 0 | 전략 자산 비율 0.0~1.0 |
| max_order_amount | Integer | 1_000_000 | 1회 주문 상한(원) |
| max_daily_orders | Integer | 100 | 일일 주문 상한 |
| updated_at | DateTime(tz) | now() | |
| updated_by | String(50) | NULL | 변경 주체 |

초기 시드 (`alembic/versions/021_strategy_runtime_table.py:31-75`): `cross_momentum(enabled=True, 0.60)`, `short_swing(False, 0.30)`, `multi_regime(False, 0.00)`.

> **관찰**: 전략별 enabled/budget_pct/max_order_amount/max_daily_orders 는 이미 DB 로 분리되어 있다. **risk_weight, daily_loss_limit, 시간대, 우선순위, ownership 정책** 은 없다.

### 1.2 live_trader orchestrator 구조

- 진입점: `scripts/live_trader.py` (약 3700줄), `main()` (≈ 2928-3700).
- 폴링 루프: `run_trading_loop()` (≈ 2191-2267), 간격 `POLL_INTERVAL_SEC = 60` (≈ :94). 60초 대기 중 1초 단위 kill_switch 체크 (≈ 2262-2267).
- orchestrator 준비: `_ensure_orchestrator()` (≈ 2113-2185) — `StrategyRegistry` + `BudgetManager` + handlers 등록.
- handler 등록 (≈ 2175-2184): `{"cross_momentum": cm_handle, "short_swing": ss_handle}`. **multi_regime 미등록.**
- 핵심 dispatch: `Orchestrator.tick()` `src/trading/orchestrator.py:50-112`
  - `registry.load_enabled(db)` → enabled 전략 목록 (TTL 5초 캐시).
  - `client.get_balance()` **1회** → `holdings_map`, `available_cash` (전략 간 공유).
  - 전략별 `allowed_budget = budget.allowed_cash()`, `max_order = budget.max_order_amount()` 계산 후 handler 호출.
  - handler 시그니처: `handler(db, client, holdings_map, available_cash, allowed_budget, max_order_amount, today, current_hhmm)`.
  - handler 예외는 `{"error": True}` 로 격리 (한 전략 실패가 다른 전략 중단 안 시킴).

`BudgetManager` `src/trading/budget_manager.py:20-90`: `allowed_cash = budget_pct × available_cash`, `max_order_amount = runtime.max_order_amount`.
`StrategyRegistry` `src/trading/strategy_registry.py:19-70`: `load_enabled()` (TTL 5초), `is_enabled()`.

### 1.3 cross_momentum handler

- handler: `src/trading/handlers/cross_momentum_handler.py:21-74`. `load_rebalance_params(db)` → `check_monthly_rebalance()` → `allowed_budget` 로 현금 제한.
- 조정자: `src/trading/cross_momentum_rebalance.py`.
  - 트리거: 현재 live path 는 `check_monthly_rebalance()` 가 `current_hhmm == "1455"` 일 때 `execute_monthly_rebalance()` 를 호출하면서 **target 산정과 주문 실행이 14:55에 함께 진행**된다. 상수 `REBALANCE_SIGNAL_HHMM = "1430"` 이 존재하나 **현재 live_trader/orchestrator handler 경로에서 별도 14:30 signal phase 로 exercise 되지는 않는다** (코드상 잔존 상수). `rebalance_freq="monthly"` → 마지막 영업일 / `"weekly"` → 금요일(휴장 시 목요일). `_is_rebalance_trigger_date()` (≈ :1252-1286).
  - 4-Phase `compute_rebalance_orders()` (≈ :440-578): Phase 1 SELL(전량매도+비중↓) → Phase 2 REFRESH(매도 후 balance 재조회) → Phase 3 BUY(신규+비중↑) → Phase 4 RECONCILE(비중 차이 로그).
  - 사이징: `investable = available_cash × (1 − cash_buffer_pct=0.10)`, `cash_per_position = investable ÷ n_positions(5)`, 종목당 `min(cash_per_position, available_cash × max_order_amount_pct=0.20)`, `min_order_amount=500k` 미만 SKIP.
  - T+2 결제 잠금 (ADR-023): `available_cash = max(0, total_cash − Σ T2PendingSettlement.sell_amount)`.
  - `last_rebalance_date` 저장: strategy_config KV (당일 중복 방지).
- **포지션 모델 없음** — rebalance 는 broker holdings 대비 diff 로만 동작.

### 1.4 short_swing entry/exit/scheduler

- handler: `src/trading/handlers/short_swing_handler.py:34-87`. 시간대 상수: entry `0920~1300`, exit `0920~1510`, cancel `1520`(이전엔 30분 threshold), reconcile 매 cycle.
- entry: `src/trading/short_swing.py` `run_entry_check()`. 신규매수 금지 9조건(비활성/시간외/kill_switch/max_positions=5/max_daily_new=2/현금부족/갭상승 0.08/당일상승 0.15/중복보유). 신호 = `price > prev_day_high AND price ≥ intraday_vwap AND 갭/상승 임계 이하`.
- exit: `src/trading/short_swing_exit.py` `run_exit_check()`. 우선순위: kill_switch → MA20 이탈 우선청산 → stop_loss(-0.02) → take_profit(0.04) → trailing(arm +0.03, stop -0.015) → max_holding_days(7) → MA20 후보 마킹.
- reconcile: `src/trading/short_swing_reconciler.py` — PENDING_ENTRY↔OPEN, CLOSING↔CLOSED/OPEN 전이, broker 실수량 검증.
- 포지션: `ShortSwingPosition` (§1.8).

> **결함 (핵심)**: `short_swing_handler.handle()` 는 `allowed_budget`, `available_cash`, `max_order_amount`, `holdings_map` 을 **전부 `# noqa: ARG001` 로 미사용** 처리한다 (`short_swing_handler.py:38-57`). docstring 명시: "미사용, 기존 함수가 params로 제어". 즉 short_swing 은 orchestrator 가 계산한 budget 을 **버리고**, 자체적으로 `available_cash × (1 − cash_buffer_pct=0.15)` 전액을 슬롯 분배에 사용한다. → **전략별 예산 격리가 실제로는 작동하지 않는다.** cross_momentum 은 `allowed_budget` 을 받지만, short_swing 과 동시 활성 시 둘 다 같은 전체 현금을 보고 경쟁한다.

### 1.5 multi_regime 실행 경로

- orchestrator **미통합**. `ACTIVE_STRATEGY="multi_regime"` 일 때만 레거시 `poll_cycle()` (`scripts/live_trader.py` ≈ 2234-2250) 로 실행.
- WebSocket 기본 + 60초 REST fallback. 종목별 변동성 기반 momentum/mean_reversion 분배, MarketStyle 기반 가중치 (design-013).
- 포지션: 메모리 기반 (DB positions 테이블 없음).
- 현재 enabled=False (시드).

### 1.6 ai_hedge decision draft / llm_decisions 적용 경로

- ingestion: `POST /api/v1/decisions/drafts` `src/api/v1/decisions.py:130-165`. `decision_type ∈ {universe_adjust, symbol_bias, strategy_param_hint}`. symbol_bias 의 `bias ∈ {block_buy, boost_buy, review_sell, block_sell}` (`decisions.py:65`). pending 상태로 `LLMDecision` 저장.

> **bias 현재/미래 상태 (중요)**: 현재 kiwoom API validator 가 허용하는 bias 는 정확히 `{block_buy, boost_buy, review_sell, block_sell}` 4개다 (`decisions.py:65`). **`boost_sell` 은 현재 whitelist 에 없어 수집조차 불가**하다 (PR E 설계상 도입 예정이나 API whitelist 추가 전까지 draft 로 받을 수 없음). 그리고 **현재 실제로 소비되는 것은 `block_buy` 뿐**이며 `boost_buy/review_sell/block_sell` 은 저장·로드만 되고 미소비다. 즉 본 문서에서 "block_buy/boost_buy/review_sell/boost_sell" 을 언급할 때 이는 **ai_hedge overlay 의 목표 어휘(future)** 이지 현재 가능한 기능이 아니다. 구현·소비 시점은 `docs/ai-hedge/PR_E_DESIGN.md` PR E2 + (boost_sell 의 경우) API whitelist 추가가 선행 조건이다.
- 적용: `src/trading/llm_decision_loader.py`
  - `apply_universe_decisions()` (:53-107) — **현재 universe_adjust.exclude + symbol_bias.block_buy 만** 처리 (symbols 에서 제외). boost_buy/review_sell/block_sell 은 로드만, 미소비 (PR E2 대기, :65-66 주석).
  - `mark_decisions_applied()` (:307-338) — approved → applied + applied_at.
  - `determine_applied_decision_ids()` (:530-604) — symbols 변화(universe/block_buy) 기준만 applied 판정 (#466).
- auto-approval 제외 (#464): `src/trading/llm_auto_approval.py:34` `MANUAL_REVIEW_CONTEXT_SOURCES = {"ai_hedge"}` — ai_hedge context 는 자동 승인 제외, 사용자 manual approve 만.
- live 소비: `scripts/live_trader.py:3157` `symbols = apply_universe_decisions(symbols, _llm_decisions)`. feature flag `use_llm_decisions` 기본 **False** (≈ 3099-3104).
- 설계 문서: `docs/ai-hedge/PR_E_DESIGN.md` (PR E1 lab regime+bias → PR E2 kiwoom loader, flag OFF 기본), `PROPOSAL_QUALITY_ROADMAP.md`.

> **관찰**: ai_hedge 는 이미 "직접 주문 금지, 제안만" 계약을 코드로 강제 중 (`/decisions` 승인 → 기존 live_trader 경로). 단 block_buy 외 action 은 미구현. **block_sell / review_sell 로 인한 자동 매도 경로는 존재하지 않음** (안전).

### 1.7 force_close_all / kill_switch / order persistence

- `force_close_all(force_all)` `scripts/live_trader.py:2270-2319`:
  - cross_momentum: **항상 보존** (force_all=True 라도).
  - momentum: force_all=False 보존, True 청산.
  - swing: force_all=False 보존, True 청산.
  - 호출: Ctrl-C/Exception(≈3652/3655, **force_all=True**), kill_switch 감지(≈2265, True), drawdown RED(≈2428/2637, True), 15:15 FORCE_CLOSE_HHMM(≈2309, **False = momentum 만**).
- kill_switch: `KILL_SWITCH_FILE = data/.kill_switch` (≈:139), `check_web_kill_switch()` (≈659-665). 루프에서 감지 시 `force_close_all(force_all=True)`. **전역 only — 전략별 구분 없음.** `.kill_switch_state.json` 은 사용자 목록.
- Ctrl-C: `:3650-3661` → `force_close_all(force_all=True)` → PID 정리. **종료 시 momentum/swing 포지션이 의도치 않게 청산될 수 있음** (cross_momentum 만 안전).
- persistence: `src/trading/live_order_persist.py:89-148` `persist_order_submitted(..., strategy, is_mock, user_id)`. broker `place_order()` → DB flush/commit. **DB 실패는 무시(try/except)** — broker 가 진실원이므로 매매는 진행되나 추적성 저하.

### 1.8 DB 모델 요약 (멀티전략 관점)

| 모델 | 파일 | strategy 식별 | 비고 |
|---|---|---|---|
| orders | `src/models/order.py:34-80` | `strategy_id`(FK strategies, nullable) + `reason`(Text) | OrderStatus 9값, OrderSide buy/sell, is_mock, broker_order_no |
| trade_logs | `src/models/trade_log.py:11-42` | `strategy_id`(FK) + details JSON | event_type 인덱스 |
| llm_decisions | `src/models/llm_decision.py:13-47` | context_source(ai_hedge) | status pending→approved→applied→evaluated, action 은 content JSON |
| ShortSwingPosition | `src/models/short_swing.py:104-177` | **strategy 필드 없음** (short_swing 전용) | partial unique `(symbol) WHERE status='open'` |
| strategy_runtime | `src/models/strategy_runtime.py:14-81` | strategy(unique) | enabled/budget/limit |

> **관찰**: 포지션 ownership 의 단일 진실원이 없다. orders 는 `strategy_id`(거의 NULL, reason 문자열로 추적) + `reason`, short_swing 만 별도 포지션 테이블, cross_momentum/multi_regime 은 broker holdings/메모리. **전략별 보유 구분은 현재 broker holdings 에 "어느 전략이 샀는지" 정보가 없어 사실상 reason/별도테이블/추정에 의존.**

### 1.9 ACTIVE_STRATEGY legacy 잔존 위치

`src/config/active_strategy.py:32-42` `get_active_strategy()` (enum CROSS_MOMENTUM/MULTI_REGIME/SHORT_SWING/NONE). 사용처:

| 위치(≈) | 역할 | 멀티전략 충돌 |
|---|---|---|
| `live_trader.py:3021` | 부팅 로그 | 무해 |
| `live_trader.py:2137-2172` | DB 비면 env 로 strategy_runtime seed | seed 후 불필요 |
| `live_trader.py:2236-2247` | MULTI_REGIME → poll_cycle, else orchestrator | **단일 전략 분기** |
| `live_trader.py:3599-3604` | `≠ MULTI_REGIME` → WS 차단, polling 강제 | 모드 결정이 단일 전략에 종속 |
| `live_trader.py:3441-3443` | MULTI_REGIME 전용 갭리스크/보유손절 | 다른 전략 SKIP |

> **관찰**: ACTIVE_STRATEGY 는 "하나의 전략만 돈다"는 가정을 강제한다. orchestrator(DB enabled 기반)와 공존하나, 실행 모드(WS vs polling)와 multi_regime 경로가 여전히 env 단일 값에 묶여 있다. **멀티전략의 가장 큰 legacy 장애물.**

---

## 2. 목표 구조

1. **동시 활성**: 여러 전략을 `strategy_runtime.enabled=true` 로 동시에 켤 수 있다. orchestrator 가 enabled 전부를 매 tick dispatch (이미 구조 존재, multi_regime 미등록 + short_swing budget 미적용이 장애).
2. **예산 분리**: 전략별 `budget_pct`(현금 비율), `max_order_amount`, **`risk_weight`(신규)**, **`daily_loss_limit`(신규)** 를 독립 적용. 모든 handler 가 `allowed_budget` 을 **실제로 사용**.
3. **포지션 ownership 명확화**: 모든 포지션/주문이 정확히 한 전략에 귀속. broker holdings 를 전략별로 매핑하는 ownership 레이어 도입.
4. **임의 청산 금지**: 한 전략은 자기 ownership 포지션만 청산 가능. 타 전략 포지션 매도 시도는 차단.
5. **시간대 충돌 방지**: 전략별 실행 시간대 + 동일 tick 내 주문 우선순위/lock.
6. **ai_hedge overlay**: 초기에는 주문하지 않고 filter/decision overlay 로만. 목표 어휘는 `block_buy / boost_buy / review_sell / boost_sell` 제안 생성 → 다른 전략의 매수 후보/사이징 조정. **단 §1.6 참조 — 현재 validator 허용 bias 는 `{block_buy, boost_buy, review_sell, block_sell}` 이고 `boost_sell` 은 미허용(수집 불가), 현재 소비는 `block_buy` 뿐.** review_sell/boost_sell 은 어떤 경우에도 자동 매도 금지.

설계 비목표(non-goal): 전략 알고리즘 자체 변경, 실거래 전환, ai_hedge 자동 주문, multi_regime 신규 알고리즘.

---

## 3. 전략별 역할 정의

| 전략 | 역할 | 시간대 | 포지션 성격 | 현재 상태 |
|---|---|---|---|---|
| cross_momentum | 금요일/월말 14:55 리밸런스 | 14:55 (target 산정+주문 함께) | 장기/중기 | orchestrator 등록, budget 적용 ✅ |
| short_swing | 매일 장중 후보 진입/청산 | entry 09:20~13:00, exit 09:20~15:10, cancel 15:20 | 단기(수일) | orchestrator 등록, **budget 미적용** ⚠️ |
| multi_regime | 시장 국면 기반 (별도 활성 전까지 보류/제한 실험) | polling | 동적 | **orchestrator 미통합** ⚠️ |
| ai_hedge | overlay 제안만 생성. 현재 validator: `block_buy/boost_buy/review_sell/block_sell` (boost_sell 미허용·수집불가) | 비실시간 (decision) | 없음 (overlay) | **현재 block_buy 만 소비**, 나머지 미구현 |

multi_regime 단기 방침: orchestrator 미통합 상태 유지하되, 멀티전략에서는 **enabled=false 유지(보류)** 를 기본으로 한다. 활성화는 별도 설계(ownership/budget 통합 + handler 등록)를 PR 로 분리.

---

## 4. 예산 분리 설계

### 4.1 allocation 방식

- 기준: **총 계좌 평가액(total equity) = available_cash + Σ holdings 평가액**. 현금만 기준으로 하면 이미 매수된 전략의 비중이 과소평가됨.
- 예시 배분: cross_momentum 50%, short_swing 30%, reserve 20% (reserve 는 어느 전략도 못 쓰는 완충).
- 전략별 가용 예산: `strategy_equity_budget = total_equity × budget_pct`. 전략이 **추가로 매수 가능한 현금** = `max(0, strategy_equity_budget − 해당 전략 현재 보유 평가액 − 해당 전략 미체결 매수 notional)`.

### 4.2 strategy_runtime 충분성 검토 + 확장안

현재 충분: `budget_pct`, `max_order_amount`, `max_daily_orders`.
부족 → 확장 제안 (PR 2):

| 신규 컬럼 | 타입 | 용도 |
|---|---|---|
| risk_weight | Numeric(5,4) | 사이징/리스크 게이트 가중 (budget 과 분리된 위험 한도) |
| daily_loss_limit | Integer (원) NULL | 전략별 일일 실현손실 한도. 초과 시 해당 전략만 신규매수 중단 |
| max_notional | Integer (원) NULL | 전략 총 보유 notional 상한 (budget_pct 보완) |
| priority | SmallInt | 동일 tick 주문/현금 경합 시 우선순위 (낮을수록 먼저) |
| entry_window | String(9) NULL | "0920-1300" 형식 진입 허용 시간대 (옵션, 핸들러 하드코딩 대체) |

> 위 컬럼은 전부 nullable/기본값 두어 기존 동작 보존. budget_pct 합 ≤ 1.0 검증은 이미 존재 (`strategy_runtime.py` PATCH, 합 검증 :85-91).

### 4.3 전략별 available_cash 계산

```
total_equity = balance.available_cash + Σ(holding.eval_amount)
for s in enabled:
    s_equity_budget = total_equity × s.budget_pct
    s_held_value    = Σ(eval_amount of holdings owned by s)      # §5 ownership
    s_pending_buy   = Σ(notional of open BUY orders reason=s)
    s_buyable_cash  = max(0, s_equity_budget − s_held_value − s_pending_buy)
    # 추가로 계좌 전체 available_cash 와 reserve 로 한 번 더 clamp
    s_buyable_cash  = min(s_buyable_cash, available_cash × (1 − reserve_pct))
```

- 미체결 주문 반영: orders 에서 `status ∈ {submitted, accepted, partial_fill}` 이고 `side=buy` 인 row 의 `(quantity−filled_quantity) × price` 합.
- 보유 평가액 반영: broker holdings × ownership 매핑.
- T+2 결제 잠금(ADR-023)은 계좌 전체 available_cash 단에서 이미 차감되므로 그대로 활용.

> **핵심 변경 요구**: §1.4 결함 해소 — short_swing handler 가 `allowed_budget`(= `s_buyable_cash`) 을 실제로 사용하도록 사이징 진입점을 수정해야 한다 (PR 2/3). cross_momentum 도 `allowed_budget` 을 위 식 기반 값으로 받도록 BudgetManager 확장.

---

## 5. 종목 충돌 규칙

### 5.1 ownership 원칙

- 모든 신규 매수 주문은 `reason` 또는 `strategy_id` 로 전략을 태깅한다 (이미 orders 에 존재). broker holdings 에는 전략 정보가 없으므로 **ownership 매핑 테이블/뷰**가 필요 (§8).
- 한 종목은 원칙적으로 **한 전략이 ownership**. 동일 symbol 을 두 전략이 동시에 보유하면 청산 권한/손익 귀속이 모호해짐.

> **Phase 1 정책 (명시)**: 본 컨트롤러의 **Phase 1 은 same-symbol exclusive — 한 종목은 한 전략만 ownership** 한다 (보수적 기본값). 이는 "전략 폐기"가 아니라 전략 보존을 전제로 한 충돌 회피 규칙이다. **동일 종목을 복수 전략이 각자 sleeve 로 보유하는 virtual sleeve / 복수 ownership 모델은 Phase 1 범위 밖이며 별도 설계 PR 로 분리**한다. Phase 1 에서 종목이 겹치면 ownership 우선순위(예: cross_momentum > short_swing)로 한 전략이 양보(SKIP)한다.

### 5.2 충돌 규칙

| 상황 | 규칙 |
|---|---|
| 다른 전략이 이미 ownership 한 종목을 신규 전략이 매수하려 함 | **차단** (기본). 동일 symbol 중복 매수 불허. 예외는 명시적 플래그(향후). |
| long-term(cross_momentum) 보유 종목에 short_swing 진입 신호 | short_swing 진입 **SKIP** (cross_momentum ownership 우선). |
| short_swing 이 cross_momentum 보유 종목을 매도하려 함 | **금지** (§6 sell authority). |
| ai_hedge `block_buy` 가 있는 종목 | 모든 전략 신규 매수 **차단** (이미 universe 제외로 구현, `apply_universe_decisions`). |
| ai_hedge `review_sell` | **자동 매도 금지.** 사용자 확인 또는 별도 flag 필요. 신규 매수만 보수화(후보 가중 하향)하는 overlay 로 한정. (현재 미소비) |
| ai_hedge `boost_buy` | 사이징 가중치만 조정(매수 boost는 후보 우선순위↑). 자동 신규 매도 생성 금지. (현재 미소비) |
| ai_hedge `boost_sell` | **현재 validator 미허용 — 수집 불가** (§1.6). 향후 도입 시에도 자동 매도 금지, 매도 임계 보수화 overlay 로만. |

> cross_momentum 은 rebalance 특성상 같은 종목을 target 으로 보유할 수 있다. short_swing 의 단기 신호가 같은 종목에 겹치면 cross_momentum ownership 을 존중해 short_swing 이 양보(SKIP)하는 것을 기본으로 한다.

---

## 6. sell authority 규칙

1. **자기 ownership 만 청산**: 각 전략 handler 의 매도 경로는 ownership 이 자기 전략인 포지션만 대상으로 한다. ownership 판정은 §8 매핑 기준.
2. **force_close_all 의 전략별 규칙 명확화** (`live_trader.py:2270-2319` 확장):
   - cross_momentum: 현행 유지 (항상 보존).
   - short_swing: ownership 포지션만, 그리고 `force_all=True`(kill_switch/치명 종료) 일 때만 청산. 정상 종료(Ctrl-C)에서는 **보존**으로 변경 권고.
   - multi_regime: 활성 시 동일 원칙.
   - 어떤 경우에도 **타 전략 ownership 포지션은 청산 대상에서 제외**.
3. **kill_switch 계층화**: 전역 `.kill_switch`(전체 중단) 유지 + 전략별 중단 도입. 후보: `strategy_runtime.enabled=false` 를 "신규매수 중단" 신호로, 전략별 kill 은 `data/.kill_switch_<strategy>` 또는 runtime 컬럼. 전역 kill 은 모든 신규매수 중단 + (정책에 따라) 보존/청산.
4. **Ctrl-C 안전화**: 현재 Ctrl-C → `force_close_all(force_all=True)` 가 momentum/swing 을 청산. 멀티전략에서는 **정상 종료 시 청산하지 않음**을 기본으로 하고, 청산이 필요하면 명시적 kill_switch 경로로만. → ACTIVE_STRATEGY legacy 제거(§1.9)와 함께 종료 핸들러의 force_all 의미를 재정의.
5. **ACTIVE_STRATEGY 제거/대체 방향 (제거는 PR 5+)**: 실행 모드(WS vs polling)와 multi_regime 분기를 env 단일 값 대신 (a) 전략별 capability(WS 지원 여부) + (b) strategy_runtime enabled 조합으로 결정. multi_regime 만 WS 가 필요하면 "multi_regime enabled 시 WS, 아니면 polling" 으로 치환. **단 이 제거/대체는 본 절의 방향 제시일 뿐, 실제 코드 변경은 budget(PR 2)·ownership·sell authority(PR 3) 완료 후 PR 5+ 로 미룬다. 현재 `ACTIVE_STRATEGY=cross_momentum` 은 6/15 본 관찰에서 검증된 compatibility guard 이므로 그 전에 건드리지 않는다.**

---

## 7. 주문 스케줄 / 시간 충돌

### 7.1 시간대

| 전략 | 시간대 |
|---|---|
| cross_momentum | 14:55 target 산정+주문 함께 (금/월말). 14:30 signal 상수는 live 경로 미사용 |
| short_swing | entry 09:20~13:00, exit 09:20~15:10, cancel 15:20 |
| multi_regime | polling 기반 (활성 시 상시) — 충돌 위험 큼 |

### 7.2 충돌/우선순위

- 동일 tick 에서 여러 전략이 주문을 낼 수 있다 (예: 14:55 에 short_swing exit + cross_momentum rebalance). orchestrator 는 현재 enabled 순서대로 직렬 dispatch — 충돌은 budget/현금 경합으로 나타남.
- 우선순위: `strategy_runtime.priority`(§4.2) 로 dispatch 순서 결정. 현금 경합 시 우선순위 높은 전략이 먼저 budget 소진.
- lock/queue: 같은 종목에 대해 동일 tick 내 복수 전략 주문이 겹치지 않도록 §5 ownership 으로 사전 차단(같은 종목은 한 전략만). 별도 분산 lock 은 단일 프로세스 직렬 실행이라 현재 불필요.

### 7.3 idempotency

- 주문 중복 방지 key 설계: `(strategy, symbol, side, trade_date, intent_bucket)`. 예) cross_momentum 의 당일 리밸런스는 `last_rebalance_date` 로 이미 1일 1회 보장. short_swing 은 포지션 partial unique index `(symbol) WHERE status='open'` 로 중복 진입 방지.
- 신규: orders 에 idempotency key 컬럼(또는 reason 규약) 추가해 재시작/중복 tick 시 동일 intent 재주문 차단 (PR 3 검토). broker_order_no 는 사후 식별자라 사전 중복 방지엔 부적합.

---

## 8. 상태 / DB 모델 영향

| 대상 | 현재 | 영향 / 제안 |
|---|---|---|
| strategy_runtime | enabled/budget_pct/max_order_amount/max_daily_orders | §4.2 컬럼 확장 (risk_weight, daily_loss_limit, max_notional, priority, entry_window) |
| 포지션 ownership | short_swing 만 테이블, cross_momentum/multi_regime 없음 | **ownership 단일 진실원 필요.** 옵션 A: 범용 `strategy_positions(strategy, symbol, qty, avg_price, owner)` 뷰/테이블. 옵션 B: broker holdings + orders.reason 집계로 파생 뷰. 우선 B(파생) 로 시작, 부족 시 A. |
| orders | strategy_id(nullable, 거의 NULL) + reason | 모든 주문에 strategy 태깅 강제 (reason 규약 표준화 또는 strategy_id 채우기). is_mock/broker_order_no 정합 유지 |
| llm_decisions | status/applied, context_source=ai_hedge | 전략별 적용 범위 표기 필요 — 어떤 전략의 universe/사이징에 영향 주는지 content 에 `target_strategy` 추가 검토 |
| trade_logs | strategy_id FK + details | 전략별 추적 가능 (이미 충분). reconcile_source 같은 details 규약 유지 |

> ownership 파생 뷰(옵션 B) 예: `각 symbol 의 ownership = 가장 최근 FILLED BUY 주문의 strategy`. 단 cross_momentum 의 외부 sync holdings 처럼 주문 이력이 없는 보유는 별도 규칙(기본 ownership=cross_momentum 또는 unowned) 필요 → 설계 시 명시.

---

## 9. API / UI 영향

현재: `src/api/v1/strategy_runtime.py` `GET /strategy/runtime`, `PATCH /strategy/runtime/{strategy}` (enabled/budget_pct/max_*, budget 합 ≤ 1.0 검증). 프론트: `strategy-runtime-panel.tsx`(다중 토글+budget 존재), `strategy/page.tsx`(현재 단일 active 표시), `decisions/page.tsx`(5단계 상태). **전략별 positions/orders/trades 필터 API 부재, portfolio view 부재.**

제안:
- 전략별 enabled toggle / budget 설정: 기존 PATCH 확장 (신규 컬럼 포함).
- 신규 API: `GET /api/v1/strategy/{strategy}/positions|orders|trades` (ownership/strategy_id 필터).
- strategy dashboard 를 **portfolio view** 로: "현재 active 1개" 가 아니라 enabled 전략 전부 + 전략별 budget 사용률/보유/손익 카드.
- ai_hedge decision 이 **어느 전략에 영향**을 주는지 표시 (target_strategy + 영향 받은 universe/사이징).

---

## 10. 단계별 PR 로드맵

| PR | 범위 | 산출물 | 위험 | 게이트 |
|---|---|---|---|---|
| **PR 0** | 본 설계 문서 | `docs/design/multi-strategy-portfolio-controller.md` | 없음 | 문서 리뷰 |
| **PR 1** | ACTIVE_STRATEGY legacy **audit + 회귀 테스트 + 제거 계획** (제거 X) | legacy 사용처 인벤토리(§1.9) + 실행모드/multi_regime 분기 대체안 + 현재 동작 고정 회귀 테스트 + 단계적 제거 계획 문서. **코드 제거는 본 PR 에서 하지 않음.** | 낮음 (조사/테스트) | 회귀 테스트 green, 6/15 관찰 경로 무변경 확인 |
| **PR 2a** | **short_swing allowed_budget 실사용 (최소 변경)** | `short_swing_handler` → entry sizing 에 `allowed_budget` 주입. schema 변경 없이 budget 격리부터 확보 | 중 (자금 사이징) | budget 격리 단위 테스트, cross_momentum+short_swing 동시활성 dry-run |
| **PR 2b** | strategy_runtime/budget model 확장 | §4.2 컬럼(risk_weight/daily_loss_limit/max_notional/priority/entry_window) + alembic up/down + BudgetManager 확장 | 중 (스키마/자금) | 마이그레이션 up/down + budget 회귀 |
| **PR 3** | ownership / sell authority 강화 | §5/§6/§8 ownership 매핑(파생 뷰, **Phase 1 same-symbol exclusive**) + force_close_all 전략별 규칙 + kill_switch 계층화 + Ctrl-C 보존화 + idempotency | **높음** (체결/청산/권한) | 상태전이 테스트, 권한 매트릭스, 의도치않은 sell 0 검증 |
| **PR 4** | cross_momentum + short_swing 병행 dry | 두 전략 동시 enabled mock 운영 + budget/ownership/시간충돌 관측 결과 문서 | 중 (관측) | mock 1주 dry-run, baseline clean |
| **PR 5+ (별도)** | ACTIVE_STRATEGY 실제 제거/대체 | PR 1 계획 기반, **budget/ownership/sell authority(PR 2~3) 완료 후** | 중~높음 | 회귀 + 종료/모드 전환 검증 |

### 로드맵 원칙

- 각 PR 은 `claude → feat/* → dev(squash) → main(merge)` (`.claude/rules/github-workflow.md`), CI green + 사용자 review 후 머지.
- **PR 1 은 ACTIVE_STRATEGY 를 제거하지 않는다.** 현재 `ACTIVE_STRATEGY=cross_momentum` 은 여전히 compatibility guard 역할(실행모드 결정 + multi_regime 분기 + mini test 에서 검증된 가드)을 한다. **6/15 본 관찰 안정성을 건드리지 않도록**, 실제 제거/대체는 budget(PR 2)·ownership·sell authority(PR 3) 가 자리잡은 뒤 PR 5+ 로 분리한다. PR 1 은 audit·회귀 테스트·제거 계획까지만.
- **budget 격리는 schema 대형 확장(PR 2b)보다 먼저 PR 2a(allowed_budget 최소 주입)로 쪼갠다.** 그래야 cross_momentum+short_swing 일일매매 병행 검증으로 빨리 진입할 수 있다. risk_weight/daily_loss_limit 등은 이후 PR 2b.
- ownership 은 **Phase 1 same-symbol exclusive** 만 구현 (한 종목 한 전략). virtual sleeve/복수 ownership 은 별도 설계 PR.
- ai_hedge bias 소비(boost_buy/review_sell)의 live consumption 은 본 로드맵 범위 밖 — `docs/ai-hedge/PR_E_DESIGN.md` PR E2 (lab observation §5 + 사용자 OK 후) 로 분리. **boost_sell 은 API whitelist 추가가 선행**돼야 수집 가능. 본 컨트롤러는 그 전까지 **block_buy(universe 제외) overlay 만** 사용.
- multi_regime orchestrator 통합은 PR 4 이후 별도 PR (ownership/budget 통합 + handler 등록).

---

## 부록 A. 핵심 결함/위험 요약

| # | 결함 | 위치 | 영향 | 해소 PR |
|---|---|---|---|---|
| 1 | short_swing 이 allowed_budget 미사용 (전체 현금 사용) | `short_swing_handler.py:38-57` | 예산 격리 무효 — 동시 활성 시 현금 경합 | **PR 2a** (최소 주입) |
| 2 | 포지션 ownership 단일 진실원 부재 | §1.8 | 청산 권한/손익 귀속 모호 | PR 3 |
| 3 | Ctrl-C → force_close_all(force_all=True) 가 swing/momentum 청산 | `live_trader.py:3650-3661` | 정상 종료 시 의도치 않은 매도 | PR 3 |
| 4 | kill_switch 전역 only | `live_trader.py:139,659-665` | 전략별 중단 불가 | PR 3 |
| 5 | ACTIVE_STRATEGY 가 실행모드/분기 단일화 (단, 현재 compatibility guard 역할 有) | §1.9 | 멀티전략 동시운영 장애. **단 6/15 관찰 가드라 즉시 제거 금지** | PR 1 audit / **PR 5+ 제거** |
| 6 | multi_regime orchestrator 미통합 | `live_trader.py:2234-2250` | 멀티전략 포트폴리오에서 제외됨 | PR 4 이후 |
| 7 | ai_hedge boost_buy/review_sell 미소비, boost_sell 미허용(수집불가) | `llm_decision_loader.py:65-66`, `decisions.py:65` | overlay 효과 제한 (현재 block_buy만) | PR E2 (+ boost_sell 은 API whitelist 선행) |
