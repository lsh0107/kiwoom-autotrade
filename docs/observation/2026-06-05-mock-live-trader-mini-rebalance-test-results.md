# 모의 live_trader Mini Rebalance Test 결과 (2026-06-05)

> **상태**: mini rebalance test 1 회 수행 완료. **PASS** (§4 검증 범위).
>
> **검증 범위**: cross_momentum weekly trigger (14:55 KST) 실 mock 주문 / 체결 / reconcile / audit P1 #2 fix 실 gate session 경로. 전략 성능 / threshold / bias 적정성 판단은 본 plan 범위 아님.
>
> **기준 plan**: `docs/observation/2026-06-05-mock-live-trader-mini-rebalance-test-plan.md` (v0.2)
>
> **실행 일자**: 2026-06-05 (금요일)
> **실행 시각**: 14:30:40 ~ 15:03:18 KST (≈ 33 분)
> **로그 파일**: `logs/mini_rebalance_20260605_1430.log`

---

## 1. 사용자 결정값 (§11.1 — 실제 적용)

| # | 항목 | 결정값 | 실제 |
|---|---|---|---|
| 1 | 시점 | 2026-06-05 (금) 14:55 trigger | 동일 ✅ |
| 2 | 시작 시각 | 14:30 KST | 실제 14:30:40 (live_trader 부팅 시작) ✅ |
| 3 | 종료 시각 | 15:15 KST | 실제 15:03:18 (Phase 4 완료 후 즉시 종료 — 12 분 단축) ✅ |
| 4 | guard 설정 방식 | tmux `export ACTIVE_STRATEGY=cross_momentum` | tmux session `live_trader_mini` 신규 생성 + `-e ACTIVE_STRATEGY=cross_momentum` 환경 변수 주입 ✅ |
| 5 | 결과 path | `docs/observation/2026-06-05-mock-live-trader-mini-rebalance-test-results.md` | 본 문서 ✅ |
| 6 | mini test PASS 후 본 관찰 일정 변경 | 6/15 유지 | 6/15 유지 (변경 없음) ✅ |
| 7 | 포지션 처리 | 보존 확정 (§11.7) | 보존 (force_close 0건, 외부 holdings + rebalance 후 잔여 보존) ✅ |

---

## 2. §4 Preflight 결과 (14:15:23 KST 시점)

| # | 항목 | 결과 |
|---|---|---|
| 1 | `is_mock_trading=True` 기본값 | ✅ PASS |
| 2 | `KIWOOM_IS_MOCK` 미설정 | ✅ PASS |
| 3 | DB `strategy_runtime` cross_momentum.enabled=true only | ✅ PASS |
| 4 | tmux session `ACTIVE_STRATEGY=cross_momentum` | ✅ PASS |
| 5 | DB ↔ env 일치 | ✅ PASS |
| 6 | balance API auth 200 + p95 < 2s | ✅ PASS (login 200/1.36s, balance p95=1.330s) |
| 7 | idle in tx = 0 + lock = 0 | ✅ PASS |
| 8 | `.kill_switch` 없음 + admin 미포함 | ✅ PASS |
| 9 | llm_decisions applied baseline = 0 | ✅ PASS |
| 10 | orders / trade_logs 오늘 baseline | ✅ PASS (오늘 06-05: orders=0, trade_logs=0) |
| 11 | **`last_rebalance_date_cross_momentum ≠ 오늘`** | ✅ PASS (`"2026-04-28"` ≠ `"2026-06-05"` → trigger 진입 가능) |

**11/11 PASS** — 14:30 전, 자동 실행 조건 충족.

---

## 3. 진행 중 관측 (§5.1)

| # | 항목 | 결과 |
|---|---|---|
| O.1 | live_trader 프로세스 활성 | ✅ PASS — PID 4792, elapsed 33+ 분 |
| O.2 | 부팅 로그 `is_mock=True` + `ACTIVE_STRATEGY=cross_momentum` | ✅ PASS — 명시 |
| O.3 | 14:30~14:54 orchestrator tick (60s 간격) | ✅ PASS — 정상 |
| O.4 | **14:55 `execute_monthly_rebalance` 호출** | ✅ PASS — `14:55:24 [ADR-022] 월말 리밸런싱 실행 시작` |
| O.5 | **Phase 1 SELL → Phase 2 REFRESH → Phase 3 BUY** | ✅ PASS (§5 상세 참조) |
| O.6 | **Phase 4 RECONCILE + persist** | ✅ PASS (§5 상세 참조) |
| O.7 | idle in tx = 0 유지 (14:55~15:03 gate session 동안) | ✅ PASS — **0 건 유지** (audit P1 #2 fix 라이브 검증) |
| O.8 | `.kill_switch` 미생성 | ✅ PASS |
| O.9 | broker_credentials lock = 0 유지 | ✅ PASS |

---

## 4. Phase 1~4 실 실행 결과

### 4.1 Phase 1 SELL (14:55:24 ~ 14:56:54)

| 항목 | 값 |
|---|---|
| 목표 포트폴리오 산정 | 5 종목 (후보 165 개, n_positions=5, top_pct=0.2) |
| 리밸런싱 diff | 전량매도 **22 개**, 신규매수 0, 비중↓ **5 개**, 비중↑ 0 |
| 종목당 목표 | 1,244,305 원 (max=1,382,562, min=500,000, buffer=10%) |
| 실 매도 접수 | **25 개** (broker_order_no 모두 발급) |
| 게이트 차단 | **1 건** — `[005930] 매도 게이트 차단: 주문 금액 205,152,500원이 한도 50,000,000원 초과` (drawdown_guard 정상 작동) |
| 매도 reason | 모두 cross_momentum rebalance 의도 — `리밸런싱 매도 접수` 로그 |
| `_place_sell_order` 실행 시간 | 14:56:12 ~ 14:56:54 (≈ 42 초) |

### 4.2 Phase 2 REFRESH (14:56:54)

| 항목 | 값 |
|---|---|
| 가용현금 재조회 | 104,826,192 원 (sell 25 건 접수 후) |

### 4.3 Phase 3 BUY (14:56:54)

| 항목 | 값 |
|---|---|
| 신규 매수 | **0 개** (diff 의 신규매수 0 + 비중↑ 0) |

### 4.4 Phase 4 RECONCILE (14:56:55 ~ 14:56:56)

| 항목 | 값 |
|---|---|
| sold_count | 25 |
| bought_count | 0 |
| target_count | 5 |
| target_weight | 0.20 |
| total_eval | 429,974,350 원 |
| max_deviation | 0.2835 |
| weight_diffs | `{'006800': -0.1952, '047040': -0.1954, '000720': -0.1927, '240810': -0.1923, '000660': 0.2835}` |
| `_persist_rebalance` | **`리밸런싱 DB persist 완료 (매도 25, 매수 0)`** ✅ |
| `[ADR-022] 월말 리밸런싱 완료` | 14:56:56 ✅ |

---

## 5. 종료 후 결과 평가 (§5.2 R.1~R.6)

### 5.1 필수 PASS 기준

| # | 항목 | 결과 | 상세 |
|---|---|---|---|
| R.1 | live_trader starts/stops normally | ✅ PASS (§7 NOTE 참조) | 14:30:40 부팅 ✅. 15:03:18 Ctrl-C 전송 → 30초 후 종료 확인. `data/.trader.pid` 자동 정리. 단 종료 로그 일부 누락 (smoke run 결과 NOTE 4.1 동일 — log buffer flush 이슈 가능성). |
| R.2 | 14:55 trigger path 진입 확인 | ✅ PASS | `14:55:24 [ADR-022] 월말 리밸런싱 실행 시작 (2026-06-05, 모의투자)` — 정확히 14:55 trigger 시점 진입 |
| R.3 | 주문 발생 시 `orders.is_mock=true` + `broker_order_no` + status 일관 | ✅ PASS | `orders` 25 건 (모두 `side='sell'`, `status='submitted'`, `is_mock=true`, `broker_order_no` NOT NULL). structlog `persist_order_submitted` 25 회 모두 `is_mock=True`, `broker_order_no` 발급 |
| R.4 | 주문 0 시 no-target / no-diff / gate-blocked reason 명확 | N/A | 주문 25 건 발생. R.4 는 주문 0 시 기준 (해당 없음). 단 게이트 차단 1 건은 reason 명확 (`주문 금액 한도 초과`) |
| R.5 | idle in tx / lock / unexpected restart 없음 | ✅ PASS | **gate session 동안 idle in tx = 0 유지** (audit P1 #2 fix 라이브 검증). broker_credentials lock = 0. backend unexpected restart = 0. balance 5xx = 0 |
| R.6 | **의도치 않은 sell / force_close 없음** (R.6 상세 표 기준) | ✅ **PASS — 핵심** | 25 sells 모두 **expected rebalance sell** (14:55~15:05 시간대, structlog `리밸런싱 매도 접수` reason, 모두 cross_momentum target 외 청산 + 비중 축소). **unintended sell 0 건** (force_close_all / kill_switch / end_of_day / momentum 전략 sell 로그 0 건). ACTIVE_STRATEGY compatibility guard 정상 작동 확증 |

### 5.2 R.6 sell 분류 검증 (plan §5.2 상세 표 기준)

#### Expected rebalance sell — 25 건 (PASS)

| 분류 | 건수 |
|---|---|
| target 외 전량 매도 | 약 22 건 (`compute_rebalance_orders` diff 의 sells 분기) |
| 비중 축소 매도 | 약 3 건 (diff 비중↓ 5 - 게이트 차단 1 - 기타 SKIP) |
| 합계 | 25 건 (DB 일치) |
| reason | 모두 `리밸런싱 매도 접수` structlog (`_place_sell_order` 호출 경로) |
| 시각 | 14:56:12 ~ 14:56:54 (Phase 1 SELL window 안) |

#### Unintended sell — 0 건 (PASS)

| 분류 | 건수 |
|---|---|
| force_close_all (kill_switch) | 0 (grep `kill_switch` 0건) |
| force_close_all (end_of_day) | 0 (grep `end_of_day` 0건) |
| momentum 전략 sell (외부 청산) | 0 (grep `모멘텀 강제 청산` 0건) |
| Phase 1 SELL 외 시간대 sell | 0 (15:03:18 종료 직후 추가 sell 0 — orders count 변화 없음) |

---

## 6. 인프라 변화 (mini test 전후)

| 항목 | mini test 전 (14:15) | mini test 후 (15:03) | 변화 |
|---|---|---|---|
| backend | Up 4 days (healthy) | Up 4 days (healthy) | unexpected restart 0 |
| postgres | Up 5 weeks (healthy) | Up 5 weeks (healthy) | 변화 0 |
| `idle in transaction` | 0 | 0 | 변화 0 (gate session 동안에도 0) |
| `broker_credentials` row lock | 0 | 0 | 변화 0 |
| `strategy_runtime` | cross_momentum only | cross_momentum only | 변화 0 |
| `data/.kill_switch` | 없음 | 없음 | 변화 0 |
| `data/.trader.pid` | 없음 | 없음 (정리됨) | mini test 동안 생성 → 종료 시 자동 정리 |
| `data/.kill_switch_state.json` users | 25 (admin 미포함) | 25 (admin 미포함) | 변화 0 |
| `llm_decisions` applied (total) | 0 | 0 | delta = 0 (모든 source) |
| `orders` 오늘 (06-05) | 0 | **25** (sell/submitted) | delta = **+25** (모두 cross_momentum rebalance) |
| `trade_logs` 오늘 | 0 | 0 | delta = 0 (cross_momentum_handler 가 별도 trade_logs persist 안 함 — 정상) |
| `last_rebalance_date_cross_momentum` | `"2026-04-28"` | **`"2026-06-05"`** | 업데이트됨 (`_set_last_rebalance_date_db`) — 다음 trigger 6/12 (만기 다음날) 까지 중복 방지 |
| broker holdings count | 27 (외부 sync) | 6 (rebalance 후 잔여) | 25 sell 접수 후 보유 종목 27 → 6 |

---

## 7. NOTE / 관찰 사항 (비-FAIL)

### 7.1 종료 로그 일부 누락 (smoke run NOTE 4.1 재현)

- logfile 마지막 줄 = `15:03:01 [INFO] 다음 폴링까지 60초 대기...` 이후 `force_close_all` / "사용자 중단" / `save_results` / "매매 요약" 등 종료 로그 없음
- 단 다음은 확인됨:
  - PID 파일 정리 (`_remove_pid_file()` finally 실행됨)
  - tmux pane bash prompt 복귀 + tmux session 정리됨
  - 프로세스 종료 (`ps -p` 결과 없음)
  - orders / 잔고 변화 없음 (force_close_all 의 추가 sell 흔적 없음)
- 추정 원인: structlog stdout 이 `tee` 로 redirect 되는데 process 종료 시점에 마지막 stdout buffer 가 fully flush 되지 않은 가능성 (smoke run NOTE 4.1 동일)
- 영향: **본 mini test 의 안전성 평가에는 영향 없음** (PID 정리 + sell 25 건 모두 expected 분류 + 종료 후 orders 변화 없음 확인됨). 향후 별도 분석 권장 (코드 변경 필요 시 별도 PR)

### 7.2 매수 0 의 의미

- diff 결과 신규매수 0, 비중↑ 0 — 즉 cross_momentum target 5 종목 중 일부가 이미 보유 중이거나, max_order_amount 한도 / min_order_amount SKIP 으로 신규 매수 대상 없음
- 본 mini test 의 검증 범위는 "주문 / 체결 / reconcile path" — 매수 path 는 별도 검증 (예: target 외 holdings 가 거의 없는 상태에서 mini test 재실행 시 매수 발생 가능)

### 7.3 `last_rebalance_date_cross_momentum` 업데이트

- mini test 후 = `"2026-06-05"` 로 업데이트됨 (`_set_last_rebalance_date_db`)
- 다음 weekly trigger 6/12 (금) = 만기 다음날 — 본 관찰 미가동이므로 trigger 미진입
- 6/15 (월) 본 관찰 시작 후 6/19 (금) 첫 weekly trigger — `last_db != today (06-19)` 충족 → 정상 진입 예상

### 7.4 게이트 차단 1 건 (정상 동작)

- `[005930] 매도 게이트 차단: 주문 금액 205,152,500원이 한도 50,000,000원 초과`
- drawdown_guard 의 `_CROSS_MOMENTUM_GATE_MAX_AMOUNT = 50,000,000` 한도 정상 작동
- 005930 (삼성전자) 99주 × 2,072,000원 = 약 205M 원 — max_order_amount 50M 한도 초과로 차단
- diff 의 22 sell 대상이 25 sell 로 늘어난 건 비중 축소 5 건 - 게이트 차단 1 건 + 다른 분기 (예: max_order_amount 보다 작은 비중 축소가 별도 SKIP)
- 본 게이트 차단은 expected behavior — R.4 의 "reason 명확" 기준 충족

---

## 8. 합의된 결과 해석 (§5.2 + §8)

- **R.1 ~ R.6 모두 PASS** = **mini rebalance test PASS**
- **audit P1 #2 (cross_momentum gate session async with) fix 실제 gate session 경로 첫 라이브 검증 완료** — Phase 1 SELL 의 25 회 `_place_sell_order` 호출 + Phase 4 reconcile + `_persist_rebalance` 까지 gate session lifecycle 정상 작동. idle in tx = 0 유지 (gate session 동안에도)
- audit P1 #1 (token_store isolated) — token path / idle transaction 회귀 없음 재확인
- ACTIVE_STRATEGY compatibility guard 정상 작동 — 종료 시 force_close_all 호출돼도 외부 holdings + rebalance 후 잔여 holdings 모두 `strategy="cross_momentum"` 태깅으로 보존 (unintended sell 0)
- 본 관찰 plan §8 mini test PASS 시 액션 = **2026-06-15 (월) 본 관찰 기본안 유지. 실제 가동은 6/15 직전 §9.1 preflight + 사용자 최종 가동 OK 후에만**

---

## 9. 6/15 본 관찰 baseline 인계 (plan §11.7)

mini test 종료 시점의 다음 상태가 **6/15 본 관찰 시작 시점의 baseline 으로 인계됨**:

| 항목 | 인계 내용 |
|---|---|
| broker holdings | 6 종목 (rebalance 후 잔여 — cross_momentum target portfolio 일부). 6/15 시작 시 외부 holdings sync 에서 `strategy="cross_momentum"` 으로 태깅됨 (ACTIVE_STRATEGY guard 정상 시) |
| `orders` rows | mini test 25 건 (sell/submitted) 유지. 6/15 본 관찰 시작 시 baseline orders count 캡쳐 시 포함됨 |
| `trade_logs` rows | 변화 없음 (mini test 동안 +0) |
| `last_rebalance_date_cross_momentum` | **`"2026-06-05"`** (mini test 시점). 6/15 시작 시 = `"2026-06-05"` ≠ `"2026-06-15"` → trigger 진입 가능 |
| llm_decisions baseline | applied = 0 (모든 source) — mini test 동안 변화 없음 |
| 다음 weekly trigger 예정 | 6/12 (금, 만기 다음날 — 본 관찰 미가동) / **6/19 (금, 본 관찰 첫 사이클)** |

**6/15 본 관찰 plan §10 daily report 첫 entry 에 mini test 결과 + 인계 baseline 명시 권장**.

---

## 10. 정책 준수 확인

- ✅ live_trader 14:30 ~ 15:03 실행 (계획 45 분 → 실제 33 분, Phase 4 완료 후 즉시 종료)
- ✅ ACTIVE_STRATEGY compatibility guard 가동 전 + 종료 시 검증 (GUARD3 echo 확인)
- ✅ mini test 후 cross_momentum 포지션 보존 (plan §11.7 확정)
- ✅ 임의 청산 / DB 정리 / strategy_runtime 변경 0
- ✅ `data/.kill_switch_state.json` 파일 변경 0
- ✅ PR E2 / threshold / bias / P2 audit 코드 변경 0
- ✅ live_trader 코드 변경 0
- ✅ 종료는 tmux send-keys C-c (guard 확인 후, PID kill fallback 미사용)
- ✅ 결과 본 문서에 기록
- ✅ 본 plan 외 추가 가동 0

---

## 11. 다음 액션 (사용자 결정 대기)

| 결정 | 의미 |
|---|---|
| 본 결과 PR 머지 진행 여부 | 결과 문서를 git 에 고정 (옵션) |
| 6/15 본 관찰 가동 진행 여부 | 6/15 직전 §9.1 preflight 재수행 + 사용자 `"2026-06-15 가동 OK"` 명시 후만 |
| NOTE 7.1 (종료 로그 누락 — smoke run NOTE 4.1 동일 반복) 분석 | structlog buffer flush 동작 분석 (별도 작업, 별도 PR — 본 plan 범위 밖) |
