# 모의 live_trader Mini Rebalance Test 계획 (v0.2)

> **상태**: 사용자 1차 리뷰 반영 (preflight #11 last_rebalance_date / §3 14:30 vs 14:55 정정 / R.6 sell 분리 / §11.7 포지션 보존 확정). **사용자 결정**: 오늘 (2026-06-05) A안 진행 가능. 14:30 전에 preflight 11항 + last_rebalance_date PASS 시 실행. 14:30 넘기거나 preflight FAIL 시 오늘 강행 금지.
>
> **변경 이력**:
> - v0.1 (2026-06-05 11:24) — 초안.
> - v0.2 (2026-06-05) — 사용자 1차 리뷰 반영. (1) §4 preflight #11 신규 = `last_rebalance_date_cross_momentum` 조회 — 값이 오늘이면 중복 실행 skip 상태 → mini test 중단. (2) §3 14:30 = signal trigger 아닌 boot/stabilization window 정정. 실 trigger 진입 = 14:55 `current_hhmm == "1455"` + trigger date 동시 충족. (3) §5.2 R.6 sell 검증 분리 — expected rebalance sell vs unintended sell (force_close/kill/end_of_day/momentum 전략 sell). sell row 존재 자체는 FAIL 아님. (4) §11.7 mini test 후 cross_momentum 포지션 보존 확정 (사용자 명시) — 임의 청산 / DB 정리 금지. 6/15 본 관찰 baseline 으로 인계 명시.
>
> **기준 문서**:
> - `docs/observation/2026-06-01-mock-live-trader-observation-plan.md` (v0.8)
> - `docs/observation/2026-06-01-mock-live-trader-checklist.md` (v0.5)
> - `docs/observation/2026-06-01-mock-live-trader-smoke-run-plan.md` (v0.4) — 본 plan 의 선행 검증
> - `docs/observation/2026-06-04-mock-live-trader-smoke-run-results.md` — A안 PASS 결과
>
> **본 plan 의 위치**: smoke run plan §2.5 에서 분리된 mini rebalance test. cross_momentum weekly trigger 일 (매주 금요일 14:55) 의 실제 mock 주문 / 체결 / reconcile path 1 회 확인. 6/15 본 관찰 가동 일정과 **별개**.
>
> **작성일**: 2026-06-05

---

## 0. P0 안전 가드 — ACTIVE_STRATEGY compatibility guard (smoke run plan §0 동일)

`scripts/live_trader.py` 의 ACTIVE_STRATEGY 잔존 env 분기 + KeyboardInterrupt 경로의 force_close_all 위험은 mini rebalance test 에서도 **동일**. 본 plan 동안 `ACTIVE_STRATEGY=cross_momentum` compatibility guard 필수.

| 파일 / 라인 | 동작 |
|---|---|
| `scripts/live_trader.py:3385-3390` | `ACTIVE_STRATEGY != CROSS_MOMENTUM` → 외부 holdings `strategy="momentum"` 태깅 |
| `scripts/live_trader.py:3650-3652` | `except KeyboardInterrupt: force_close_all(force_all=True)` |
| `scripts/live_trader.py:2289-2302` | `force_close_all` force_all=True → `strategy=="cross_momentum"` 만 보존 |

### Compatibility guard

tmux session 안에서 `export ACTIVE_STRATEGY=cross_momentum` 명시. §4 preflight 에서 DB ↔ env 일치 검증. 불일치 시 가동 금지.

### Mini rebalance test 특화 위험

smoke run 과 달리 mini rebalance test 는 14:55 trigger 에서 **실제 mock 매수/매도 주문 발사**. 따라서:

- guard 정상이면 외부 holdings 보존 + cross_momentum rebalance 만 발생 (정상)
- **guard 부재 시 외부 holdings 청산 위험 + cross_momentum rebalance 의 매도가 strategy="momentum" 태깅 → 의도와 다른 sell path**
- audit P1 #2 fix 의 실제 gate session 경로 (`execute_monthly_rebalance` → `async with async_session_factory()`) 가 본 test 에서 처음 exercised 됨

---

## 1. 목적 (명시 — 사용자 결정)

본 mini rebalance test 는 **cross_momentum weekly trigger 에서 실제 mock 주문 / 체결 / reconcile path 가 살아 있는지** 확인만 한다. **전략 성능 / threshold 적정성 / signal 분포 판단 / bias 변경 결정은 본 plan 의 범위 아니다**.

### 다루는 것 (smoke run plan §1 대비 확장)

- 14:55 trigger 의 `check_monthly_rebalance` → `execute_monthly_rebalance` 호출 path
- universe 12-1 momentum 신호 산정 (`compute_target_portfolio`)
- `compute_rebalance_orders` 의 diff 계산
- 실제 매수 / 매도 주문 (mock) 발사 + 게이트 통과 / 차단 분기
- `orders.status` 전이 (`created → submitted → accepted → filled` 또는 `rejected`)
- Phase 2 balance refresh + Phase 3 매수 + Phase 4 reconcile
- audit P1 #2 fix 의 실제 gate session lifecycle (async with 종료 보장)
- `_persist_rebalance` / `persist_order_submitted` 실제 호출
- broker_order_no 생성 + DB persist

### 다루지 않는 것 (FAIL 처리 금지)

- 전략 성능 / 수익률 / signal confidence 분포 판단
- threshold (top_pct / cash_buffer_pct / max_order_amount_pct) 적정성
- 게이트 차단이 적절한지 vs 과한지 평가
- 신규 종목 진입 vs 기존 보유 청산 비율 평가
- T+2 settlement (mock 기본 OFF)
- PR E2 / bias 소비
- 15 영업일 장기 안정성

---

## 2. 시점 후보 (사용자 결정)

오늘 = 2026-06-05 (금) 11:21 KST. weekly trigger 일 = 매주 금요일 14:55 KST.

| 후보 | 만기 영향 | 본 관찰 일정 영향 | 평가 |
|---|---|---|---|
| **A. 2026-06-05 (금) 오늘 14:55** | 6/11 만기 직전 주의 금요일 — 약한 변동성 가능 (직전은 6/01 = 4 영업일 전) | 본 관찰 6/15 시작 전 mini test 1회 — 본 관찰 시작 전 검증 완료 | ⭐ 시간 여유 충분 (T-3h 34m). 즉시 가동 가능. 만기 영향 보통. |
| B. 2026-06-12 (금) 14:55 | **만기 다음날 + weekly trigger** = 만기 잔존 변동성 + trigger 동시 | 본 관찰 6/15 시작 직전 — mini test 가 본 관찰 직전에 위치 | ⚠️ 만기 영향 직격 — 권장 안 함 |
| C. 2026-06-19 (금) 14:55 | 만기 영향 회피 (6/11 만기 + 1 주 후) | 본 관찰 6/15 시작 후 첫 weekly trigger — mini test 가 본 관찰 첫 사이클 = 별도 진행 의미 약함 | 본 관찰 자연 관측과 중복 |
| D. 진행 안 함 | — | 보수적 경로 — 6/15 본 관찰 시작 후 6/19 자연 관측 | 사용자 직전 결정과 일치 (mini test 보류) |

### 리드 권장 (사용자 결정 대상)

| 권장 | 이유 |
|---|---|
| **A. 2026-06-05 (오늘) 14:55** | 시간 여유 충분. 6/15 본 관찰 가동 전에 mini test 가 끝남 → 본 관찰 진입 전 audit P1 #2 fix 의 실제 gate session 경로 검증 완료. 단 6/11 만기 직전 주 변동성 인지 필요. |
| **D. 진행 안 함 (직전 보수적 경로 재확인)** | 사용자 직전 결정 ("보수적 경로 1번") 과 일치. 6/15 본 관찰 후 6/19 자연 관측. |

본 plan 은 **A안 (오늘 14:55) 가정**으로 §3 이후 작성. D 선택 시 본 plan 폐기.

---

## 3. Duration / 시간

> **중요 — 14:30 vs 14:55 의미 정정**:
> - **14:30 KST = signal trigger 아님**. 본 plan 에서 14:30 은 **boot / stabilization window** (live_trader 부팅 + 토큰 발급 + 잔고 조회 + orchestrator tick 안정).
> - **14:55 KST = 실제 trigger 진입 시점**. `cross_momentum_rebalance.py::check_monthly_rebalance` 가 `current_hhmm == REBALANCE_ORDER_HHMM ("1455")` + trigger date 조건을 모두 만족할 때만 `execute_monthly_rebalance` 호출 (`cross_momentum_rebalance.py:62-63`, `check_monthly_rebalance` line 1283-1296).
> - 14:30 ~ 14:54 동안에는 orchestrator tick 이 60 초 간격으로 돌지만 `check_monthly_rebalance` 가 `executed=False` 반환만 (smoke run 동작과 동일). 실제 rebalance 는 14:55 한 번만 trigger.

| 항목 | 값 |
|---|---|
| 시작 시각 | 사용자 결정. 기본안 = **14:30 KST** — **boot / stabilization window** (live_trader 부팅 + 토큰 + orchestrator tick 안정 확인) |
| 종료 시각 | **15:15 KST** (15:05~15:15 Phase 4 reconcile + `_persist_rebalance` 완료 후 종료) |
| 총 가동 | 약 45 분 |
| 14:30~14:54 | 부팅 + orchestrator tick 정상 동작 확인 (smoke run 과 유사) — `check_monthly_rebalance` 가 `current_hhmm != "1455"` 로 `executed=False` 반환만 |
| **14:55** | **실제 trigger 진입** — `check_monthly_rebalance` 가 `current_hhmm == REBALANCE_ORDER_HHMM ("1455")` + weekly trigger date (금요일 영업일) 조건 동시 만족 → `execute_monthly_rebalance` 호출 |
| 14:55~15:05 | Phase 1 SELL → Phase 2 REFRESH → Phase 3 BUY 진행 |
| 15:05~15:15 | Phase 4 RECONCILE + `_persist_rebalance` + DB 확인 |
| 15:15 이후 | tmux send-keys C-c (compatibility guard 확인 후) → graceful stop |

**14:55 trigger 조건 (둘 다 충족 필수)**:
1. `current_hhmm == "1455"` (live_trader 의 tick 시각이 정확히 14:55 도달)
2. `_is_rebalance_trigger_date(today, freq=adapter.params.rebalance_freq)` = True (오늘 = 금요일 영업일 + `cross_momentum.rebalance_freq='weekly'`)

오늘 (2026-06-05 금요일) 은 위 2 조건 모두 충족 예정.

---

## 4. Mini test 전 preflight (사용자 명시 안전조건 10항)

| # | 항목 | 기준 |
|---|---|---|
| 1 | `is_mock_trading=True` 기본값 | `grep is_mock_trading src/config/settings.py` |
| 2 | env `KIWOOM_IS_MOCK` 가 `false` 아님 | `env \| grep KIWOOM_IS_MOCK` (미설정 OK) |
| 3 | DB `strategy_runtime` 의 `cross_momentum.enabled=true` only | 본 plan §9 SQL |
| 4 | **env `ACTIVE_STRATEGY=cross_momentum`** (§0 compatibility guard) | tmux session 안에서 `echo $ACTIVE_STRATEGY` |
| 5 | DB ↔ env ACTIVE_STRATEGY 일치 | 결과 대조. 불일치 시 **FAIL — 가동 금지** |
| 6 | balance API 인증 200 + p95 < 2s | admin 쿠키 후 5 회 호출 |
| 7 | `pg_stat_activity` idle in transaction = 0 + broker_credentials lock = 0 | 본 plan §9 SQL |
| 8 | `data/.kill_switch` 파일 없음 + admin user_id `kill_switch_state.json` 미포함 | `ls -l` + python3 |
| 9 | `llm_decisions` applied baseline 캡쳐 + ai_hedge / PR E2 origin = 0 확인 | 본 plan §9 SQL |
| 10 | **mini test 전 `orders` / `trade_logs` baseline 캡쳐** | 본 plan §9 SQL — mini test 동안 발생할 delta 측정 기준 |
| 11 | **`strategy_config` 의 `last_rebalance_date_cross_momentum` 값이 오늘 (`2026-06-05`) 아님** | DB query: `SELECT value FROM strategy_config WHERE key = 'last_rebalance_date_cross_momentum';` — 값이 `"2026-06-05"` 면 **당일 중복 실행 skip 상태** (`cross_momentum_rebalance.py::execute_monthly_rebalance` line 759-763: `last_db == today` 면 즉시 skip). 이 경우 mini test 14:55 trigger 진입해도 `execute_monthly_rebalance` 가 실 rebalance 를 수행하지 않음 → mini test 의 목적 (실 주문 path 검증) 자체 달성 불가 → **mini test 중단** |

11 항목 모두 PASS 아니면 가동 금지. **특히 #4 / #5 가 PASS 아니면 §0 mock sell 위험 — 절대 가동 금지. #11 FAIL 시 mini test 의미 없음 — 중단.**

추가 권장 (인프라):
- backend / postgres healthy + last restart 시각 기록
- cross_momentum.rebalance_freq = 'weekly' DB 값 재확인 (`strategy_config`)
- backend / live_trader 가 사용하는 동일 DB 인스턴스 확인 (`last_rebalance_date` 가 같은 인스턴스에 저장됨)

---

## 5. 점검 항목 (mini test 진행 중 + 종료 후)

### 5.1 진행 중 관측

| # | 항목 | 확인 방법 |
|---|---|---|
| O.1 | live_trader 프로세스 활성 (`data/.trader.pid`) | `cat data/.trader.pid` + `ps aux \| grep live_trader` |
| O.2 | 부팅 로그 `is_mock=True` + `ACTIVE_STRATEGY=cross_momentum` 명시 | tmux session 또는 logfile head |
| O.3 | 14:30~14:54 orchestrator tick (60 초 간격) 정상 | structlog tail |
| O.4 | **14:55 `check_monthly_rebalance` 호출** | structlog grep `check_monthly_rebalance` 또는 `execute_monthly_rebalance` |
| O.5 | **14:55~15:05 Phase 1 SELL → Phase 2 REFRESH → Phase 3 BUY** | structlog grep `Phase 1 매도 완료`, `Phase 2 잔고 재조회`, `Phase 3 매수 완료` |
| O.6 | **15:05~15:15 Phase 4 RECONCILE + persist** | structlog grep `리밸런스 reconcile`, `리밸런싱 DB persist 완료` |
| O.7 | idle in transaction = 0 유지 (특히 14:55~15:15 gate session 동안) | 본 plan §9 SQL 30 초마다 |
| O.8 | `data/.kill_switch` 미생성 | `ls -l data/.kill_switch` |
| O.9 | broker_credentials row lock = 0 유지 (audit P1 #1/#2 fix 회귀 검증) | 본 plan §9 SQL |

### 5.2 종료 후 결과 평가 — PASS 기준 (사용자 명시)

#### 필수 PASS

| # | 항목 | PASS 기준 |
|---|---|---|
| R.1 | live_trader 정상 종료 (starts/stops normally) | 종료 후 `data/.trader.pid` 미존재 + tmux pane bash prompt 복귀 + force_close_all guard 보존 동작 정상 |
| R.2 | 14:55 trigger path 진입 확인 | structlog 에 `[ADR-022] 월말 리밸런싱 실행 시작` 또는 동등 로그 1 회 이상 |
| R.3 | 주문 발생 시 `orders.is_mock=true` + `broker_order_no` 존재 + status 일관 | 모든 orders rows: `is_mock=true`, `broker_order_no IS NOT NULL`, `status` 가 `submitted/accepted/filled/rejected` 등 정상 enum |
| R.4 | 주문 0 인 경우 no-target / no-diff / gate-blocked reason 명확 | structlog 또는 trade_logs 에 다음 중 하나 명시: `목표 포트폴리오 산정 실패` / `리밸런싱 diff: 전량매도 0, 신규매수 0, 비중↓ 0, 비중↑ 0` / `[%s] 매수 게이트 차단` / `[%s] 매도 게이트 차단` / `현재가 조회 실패` / `min_order_amount 미만 — SKIP` |
| R.5 | idle in transaction / lock / unexpected restart 없음 | smoke run 결과 §3.1 R.7 / R.9 동일 기준 |
| R.6 | **의도치 않은 sell / force_close 없음** (expected rebalance sell 과 분리) | sell rows 가 발생하면 **reason / log / time window** 로 분류 (R.6 상세 표 참조). sell row 존재 자체는 FAIL 아님. |

#### R.6 상세 — sell 분류

본 mini test 의 sell 은 **expected rebalance sell** vs **unintended sell** 로 분리해서 평가. sell row 존재 자체가 FAIL 이 아님.

**Expected rebalance sell (PASS — 정상)**:

| 분류 | 조건 |
|---|---|
| target 외 전량 매도 | `trade_logs.event_type IN ('cross_momentum_rebalance_sell', 'rebalance_sell_full')` 또는 structlog `리밸런싱 매도 접수` + symbol 이 cross_momentum target 외. 시각 14:55~15:05 안. |
| 비중 축소 매도 | structlog `리밸런싱 매도 접수` + 비중 축소 분기 (`compute_rebalance_orders` 의 `adjust_sells`). 시각 14:55~15:05 안. |
| 검증 | `execute_sell` 의 `reason` 컬럼 = `"cross_momentum"` 또는 동등. `force_close_all` 호출 흔적 없음 (`강제 청산` 로그 0건). |

**Unintended sell (FAIL — 즉시 사용자 보고)**:

| 분류 | 조건 |
|---|---|
| force_close_all (kill_switch) | `execute_sell` reason = `"kill_switch"`. `trade_logs.message` 에 `kill_switch` 키워드. mini test 시간 범위 (14:30~15:15) 안에서 1 건이라도 발생 시 FAIL. |
| force_close_all (end_of_day) | `execute_sell` reason = `"end_of_day"`. 본 mini test 시간은 15:35 (`_MARKET_CLOSE`) 이전이므로 발생하면 비정상. 1 건이라도 FAIL. |
| momentum 전략 sell (외부 holdings 청산) | structlog `모멘텀 강제 청산` 로그 또는 sell 의 symbol 이 cross_momentum target 외이면서 strategy=`"momentum"` 태깅. ACTIVE_STRATEGY guard 실패 의심. 1 건이라도 FAIL — §0 guard 실패. |
| Phase 1 SELL 외 시간대 sell | 시각 14:30~14:54 또는 15:15 이후 sell 발생. 의도된 rebalance path 외이므로 FAIL. |

**판정 절차** (mini test 종료 후):

```sql
-- mini test 동안 발생한 모든 sell rows
SELECT submitted_at, symbol, quantity, status, broker_order_no
FROM orders
WHERE side = 'sell'
  AND submitted_at >= TIMESTAMPTZ '2026-06-05 14:30:00+09'
  AND submitted_at <  TIMESTAMPTZ '2026-06-05 15:15:00+09'
  AND is_mock = true
ORDER BY submitted_at;

-- 대응 trade_logs (reason / message)
SELECT created_at, event_type, symbol, message, details
FROM trade_logs
WHERE created_at >= TIMESTAMPTZ '2026-06-05 14:30:00+09'
  AND created_at <  TIMESTAMPTZ '2026-06-05 15:15:00+09'
  AND (event_type LIKE '%sell%' OR event_type LIKE '%close%' OR message LIKE '%kill%' OR message LIKE '%end_of_day%')
ORDER BY created_at;
```

각 sell row 별로 위 표 기준으로 expected / unintended 분류 → unintended 1 건 이상이면 R.6 FAIL.

#### FAIL 아닌 것

- 주문 발생 0 (no-target / no-diff / gate-blocked) — R.4 기준 충족 시 정상
- 체결 일부 실패 (rejected) — broker mock 환경 특성, R.3 status 일관성만 확인
- signal confidence 분포 / threshold 적정성 / 게이트 차단 빈도

---

## 6. 실행 절차 (사용자 OK 후만)

### 6.1 Start (14:30 KST 기본안)

```bash
# 1. compatibility guard 명시 (§0)
tmux new -s live_trader_mini
cd /Users/sanghyuklee/individual/stock/kiwoom-autotrade
export ACTIVE_STRATEGY=cross_momentum
echo "guard: ACTIVE_STRATEGY=$ACTIVE_STRATEGY"

# 2. 사전 확인: §4 preflight 10항 + DB strategy_runtime cross_momentum only

# 3. 실행
uv run python scripts/live_trader.py --auto 2>&1 | tee -a logs/mini_rebalance_$(date +%Y%m%d_%H%M).log
```

부팅 직후 5 분 내 확인 (smoke run plan §6.1 동일):
- `is_mock=True` 라인
- `ACTIVE_STRATEGY=cross_momentum` 라인
- 토큰 발급 1 회
- orchestrator tick 시작

### 6.2 Trigger 진입 모니터링 (14:55 KST)

```bash
# 14:54 직전: 진입 직전 idle in tx + lock + balance 마지막 확인
tmux send-keys -t live_trader_mini "" Enter  # session keep-alive
# DB 점검 별도 실행 (호스트):
docker exec kiwoom-autotrade-postgres-1 sh -c "psql ..."
# 14:55 KST 직후: trigger path 로그 capture
tmux capture-pane -t live_trader_mini -p | tail -50 | grep -E "월말 리밸런싱|Phase|매도 완료|매수 완료"
```

### 6.3 Stop (15:15 KST 도달, smoke run plan §6.2 동일)

> **위험 경고**: `Ctrl-C` = `force_close_all(force_all=True)`. ACTIVE_STRATEGY guard 정상이면 외부 holdings 보존 + cross_momentum 보존. **guard 부재 / 불일치 상태에서 Ctrl-C 절대 금지**.

```bash
# 1. guard 재확인
tmux attach -t live_trader_mini
# ACTIVE_STRATEGY=cross_momentum 확인됐는지 grep / 시각 확인

# 2. guard PASS 확인 후 Ctrl-C
# tmux session 안에서 Ctrl-C → KeyboardInterrupt → force_close_all(force_all=True)
#  → cross_momentum 포지션 보존 (line 2294-2302)
```

종료 후 `data/.trader.pid` 자동 제거 확인 (smoke run plan §6.2 동일).

### 6.4 Stop fallback (시간 제한 / 비상)

smoke run plan §6.3 동일 — `tmux send-keys -t live_trader_mini C-c` 우선, PID kill 은 fallback only.

### 6.5 긴급 중단 (smoke run plan §6.4 동일)

```bash
# 1순위 — guard 무관 즉시 안전
touch data/.kill_switch

# 2순위 — guard 상태 확인
tmux send-keys -t live_trader_mini "echo ACTIVE_STRATEGY=$ACTIVE_STRATEGY" Enter

# 3순위 — guard PASS 확인된 경우만 Ctrl-C
# guard FAIL/확인 불가 시 사용자에게 "mock sell 위험" 즉시 보고
```

---

## 7. 결과 기록 위치

**파일명에 실제 실행 일자 포함**:

`docs/observation/YYYY-MM-DD-mock-live-trader-mini-rebalance-test-results.md`

예: 2026-06-05 실행 시 → `docs/observation/2026-06-05-mock-live-trader-mini-rebalance-test-results.md`

본 plan §5.2 R.1~R.6 표 + 인프라 / orders / trade_logs / llm_decisions delta + Phase 1~4 별 로그 첨부.

본 관찰 plan §10 (관찰 결과 영역) 과 분리. mini test 결과는 본 관찰 plan 의 daily report 가 아님.

---

## 8. Mini test 후 액션

| 결과 | 액션 |
|---|---|
| R.1~R.6 전부 PASS + 주문 발생 | mini test PASS. audit P1 #2 fix 실제 gate session 경로 검증 완료. 본 관찰 plan 의 2026-06-15 (월) 기본안 유지. 실제 가동은 6/15 직전 §9.1 preflight + 사용자 최종 OK 후. |
| R.1~R.6 전부 PASS + 주문 0 (no-target / no-diff / gate-blocked) | mini test 부분 PASS — trigger path 진입 + reason 명확 확인. 단 실제 주문 path 미검증. 본 관찰 6/15 가동 후 6/19 trigger 에서 자연 관측 가능. |
| R.6 FAIL (의도치 않은 sell 발생) | **§0 compatibility guard 실패 의심 — 즉시 사용자 보고**. 본 관찰 6/15 가동 보류. 코드/문서 검토 후 사용자 OK 받고 재시도. |
| R.5 FAIL (idle in tx / lock / restart 발생) | audit P1 #1/#2 fix 회귀 의심. 본 관찰 가동 보류. 별도 audit 후 사용자 OK 후 재시도. |
| R.2 FAIL (14:55 trigger path 진입 안 함) | live_trader / orchestrator / check_monthly_rebalance 환경 점검. 본 관찰 가동 보류. |
| R.3 FAIL (orders.is_mock=false 또는 broker_order_no NULL) | broker / persist 비일관. 즉시 사용자 보고. 본 관찰 가동 보류. |

---

## 9. 본 plan 의 변경 / 폐기

- 본 plan 은 1 회용. mini test 완료 후 결과 문서 (§7) append → 본 관찰 plan 으로 인계.
- D안 (진행 안 함) 선택 시 본 plan 폐기 (untracked 유지 후 사용자 결정 시 삭제).
- 결과 명확한 FAIL 시 본 plan §5 점검 항목 보강 + 재실행 결정 (사용자 OK 후).

---

## 10. 금지 사항 (mini test 동안 / 이후)

- **§0 ACTIVE_STRATEGY compatibility guard 부재 / 불일치 상태에서 가동 금지** (외부 holdings mock sell 위험)
- `kill <PID>` 를 "graceful stop" 으로 부르지 마라 (SIGTERM ≠ KeyboardInterrupt)
- 전략 성능 / threshold / bias 변경 결정 금지
- PR E2 진입 코드 작성 금지
- `data/.kill_switch_state.json` 직접 조작 금지
- `data/.trader.pid` 임의 삭제 금지 (라이브 프로세스 종료 확인 후만)
- live_trader 코드 변경 금지
- mini test 결과 1 회만으로 multi_regime / short_swing 전략 활성화 결정 금지
- mini test 결과 1 회만으로 threshold (top_pct / cash_buffer_pct 등) 변경 금지
- 본 관찰 plan §8.2 가동 기본안 변경 금지 (mini test 결과로 본 plan 갱신 금지)
- 본 plan 외 추가 가동 금지

---

## 11. 미해결 / 사용자 결정 필요

| # | 항목 | 본 plan 가정 | 결정 필요 |
|---|---|---|---|
| 1 | mini test 시점 | A: 2026-06-05 (오늘) 14:55 | A / D (진행 안 함) — B (6/12), C (6/19) 권장 안 함 |
| 2 | 시작 시각 | 14:30 KST (trigger 25 분 전 부팅) | 14:00 / 14:15 / 14:30 / 14:45 |
| 3 | 종료 시각 | 15:15 KST (Phase 4 완료 + DB 확인) | 15:15 / 15:30 / 사용자 명시 |
| 4 | ACTIVE_STRATEGY guard 설정 방식 | tmux session 안 `export` (smoke run §6 동일) | 그대로 / `.env` 임시 / 기타 |
| 5 | 결과 문서 path | `docs/observation/2026-06-05-mock-live-trader-mini-rebalance-test-results.md` | 그대로 / 변경 |
| 6 | mini test PASS 후 본 관찰 일정 변경 여부 | 6/15 기본안 유지 (변경 없음) | 6/15 유지 / 변경 |
| 7 | mini test 후 cross_momentum 포지션 처리 | **보존 (확정)** — §11.7 참조 | (결정 완료 — 사용자 명시) |

### 11.7 mini test 후 cross_momentum 포지션 처리 — 보존 확정 (사용자 명시)

mini test 종료 후 cross_momentum 포지션 처리 = **기본 보존 확정**.

**금지**:
- mini test 종료 후 cross_momentum 포지션 임의 청산 금지
- mini test 결과로 `data/.kill_switch_state.json` 정리 금지
- mini test 결과로 `orders` / `trade_logs` / `llm_decisions` row 임의 삭제 금지
- mini test 결과로 broker 잔고 임의 조작 금지
- mini test 결과로 strategy_runtime / strategy_config 값 변경 금지

**6/15 본 관찰 baseline 인계**:

mini test 종료 시점의 다음 상태가 **6/15 본 관찰 시작 시점의 baseline 으로 인계됨**:

| 항목 | 인계 내용 |
|---|---|
| broker holdings | mini test rebalance 후 보유 종목 (예: cross_momentum target portfolio 의 일부) — 그대로 유지. 6/15 시작 시 외부 holdings sync 에서 `strategy="cross_momentum"` 으로 태깅됨 (ACTIVE_STRATEGY guard 정상 시) |
| `orders` rows | mini test 동안 발생한 buy/sell rows 모두 유지. 6/15 본 관찰 시작 시 baseline applied count + orders count 캡쳐 시 포함됨 |
| `trade_logs` rows | 동일 — 인계 시 baseline 에 포함 |
| `last_rebalance_date_cross_momentum` | mini test 후 = `"2026-06-05"` 로 업데이트됨 (`_set_last_rebalance_date_db`). 6/15 (월) 시작 시 = `"2026-06-05"` 값으로 시작 → 6/19 (금) 첫 trigger 가 자연 발생 (당일 중복 skip 조건 충족 안 됨) |
| llm_decisions baseline | mini test 동안 ai_hedge / PR E2 origin applied = 0 (R.8 PASS 가정). 6/15 baseline 캡쳐 시 같은 0 기대 |

**6/15 본 관찰 plan §10 daily report 첫 entry 에 mini test 결과 + 인계 baseline 명시 권장** (별도 PR 또는 본 plan §10 결과 문서 작성 시 cross-reference).

---

## 12. 다음 작업자 진입점

- 본 plan §11 미해결 항목
- 본 관찰 plan v0.8 (`2026-06-01-mock-live-trader-observation-plan.md`) §8.2 가동 기본안 + §9 실행 절차
- smoke run plan v0.4 (`2026-06-01-mock-live-trader-smoke-run-plan.md`) §0 / §6 / §11.3
- 2026-06-04 smoke run 결과 (`2026-06-04-mock-live-trader-smoke-run-results.md`) §6.5 검증 범위
- `scripts/live_trader.py:92` `_TRADER_USER_ID = uuid.uuid4()` (kill_switch user UUID)
- `scripts/live_trader.py:3385-3390` (ACTIVE_STRATEGY 잔존 분기)
- `scripts/live_trader.py:3650-3652` (KeyboardInterrupt → force_close_all)
- `scripts/live_trader.py:2289-2302` (force_close_all 의 cross_momentum 보존 로직)
- `src/trading/cross_momentum_rebalance.py::execute_monthly_rebalance` (audit P1 #2 fix 적용 경로 — Phase 1 SELL / Phase 2 REFRESH / Phase 3 BUY / Phase 4 RECONCILE)
- `src/trading/cross_momentum_rebalance.py::check_monthly_rebalance` (14:55 trigger 진입 함수)
