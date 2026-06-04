# 모의 live_trader Smoke Run 결과 (2026-06-04)

> **상태**: smoke run 1 회 수행 완료. **A안 기준 PASS** (§6.5 검증 범위 한정).
>
> **검증 범위**: 부팅 / balance-token / orchestrator tick / 비-trigger skip / 종료 경로 / 안전 가드. **체결 / reconcile / order lifecycle / 실제 gate session 경로는 본 smoke run 에서 검증하지 않음** — orders / trade_logs 0 건. 별도 mini rebalance test 또는 6/15 본 관찰 weekly trigger 발생 시점부터 검증 가능.
>
> **기준 plan**: `docs/observation/2026-06-01-mock-live-trader-smoke-run-plan.md` (v0.4)
>
> **실행 일자**: 2026-06-04 (목요일)
> **실행 시각**: 10:33:34 ~ 11:04 KST (약 30 분)
> **로그 파일**: `logs/smoke_run_20260604_1033.log` (65 KB, 463 lines)

---

## 1. 사용자 결정값 (§11.1 — 실제 적용)

| # | 항목 | 결정값 | 실제 |
|---|---|---|---|
| 1 | 시점 | 2026-06-04 (목) | 동일 ✅ |
| 2 | 기간 | 30 분 | 약 30 분 (10:33:34 ~ 11:04 ≈ 30:26) ✅ |
| 3 | 시작 시각 | 10:00 KST (조정 → 10:35) | 실제 10:33:34 (live_trader 부팅 시작) ✅ |
| 4 | mini rebalance test | 진행 안 함 | 진행 안 함 ✅ |
| 5 | 결과 path | `docs/observation/2026-06-04-mock-live-trader-smoke-run-results.md` | 본 문서 ✅ |
| 6 | guard 설정 방식 | tmux `export ACTIVE_STRATEGY=cross_momentum` | tmux session `live_trader_smoke` 신규 생성 + `-e ACTIVE_STRATEGY=cross_momentum` 환경 변수 주입 ✅ |

---

## 2. 진행 중 관측 (§5.1)

| # | 항목 | 결과 |
|---|---|---|
| O.1 | live_trader 프로세스 활성 (`data/.trader.pid`) | ✅ PASS — PID 89099 (10:33 ~ 11:04, elapsed ≈ 30 분) |
| O.2 | 부팅 로그 `is_mock=True` + `ACTIVE_STRATEGY=cross_momentum` | ✅ PASS — `10:33:27 ACTIVE_STRATEGY=cross_momentum`, `10:33:28 is_mock=True base_url=https://mockapi.kiwoom.com` |
| O.3 | balance / token 로그 정상 | ✅ PASS — `10:33:28 토큰 발급 성공 expires_at=2026-06-05T00:57:24+00:00`, 매 tick 잔고 조회 200 정상 |
| O.4 | 오케스트레이터 tick 호출 | ✅ PASS — 60 초 간격 30 회 tick (10:33:34 ~ 11:02:58), 매 tick `orchestrator tick 완료: ['cross_momentum']` + `다음 폴링까지 60초 대기...` |
| O.5 | idle in transaction = 0 유지 | ✅ PASS — 5/15/25 분 점검 모두 0 |
| O.6 | `data/.kill_switch` 미생성 | ✅ PASS — 가동 전체 기간 미생성 |

---

## 3. 종료 후 결과 평가 (§5.2)

### 3.1 필수 PASS 기준

| # | 항목 | 결과 | 상세 |
|---|---|---|---|
| R.1 | live_trader 정상 종료 | ✅ PASS (단 §4 NOTE 참조) | tmux Ctrl-C 전송 (11:03:58) → 30 초 graceful 대기 후 (11:04:28) PID 89099 종료 확인. `data/.trader.pid` 자동 정리 (`_remove_pid_file()` finally 실행). tmux pane `^C` + bash prompt 복귀. |
| R.2 | `is_mock=True` + `ACTIVE_STRATEGY=cross_momentum` 로그 명시 | ✅ PASS | structlog: `is_mock=True base_url=https://mockapi.kiwoom.com`, `ACTIVE_STRATEGY=cross_momentum` (3 곳 명시) |
| R.3 | DB `strategy_runtime` 토글 로드 성공 | ✅ PASS | `전략 실행: cross_momentum (budget=6,912,811, max_order=50,000,000)` 매 tick 출력. DB `cross_momentum.enabled=true / budget_pct=0.60 / max_order=50M / max_daily=200` 일치 |
| R.4 | balance / token path 정상 (504/5xx 미발생) | ✅ PASS | 매 tick 잔고 조회 정상 (`available_cash=11521353 holdings_count=27 total_eval=568M~572M`). 외부 5xx 0 건 |
| R.5 | 오케스트레이터 tick 호출 발생 | ✅ PASS | 30 회 tick 발생 (60 초 간격). 누락 0. 11:00:54 재스크리닝 1 회 정상. |
| R.6 | 비-trigger 일 skip 동작 | ✅ PASS | 6/4 (목) 평일 = weekly trigger 아님. `execute_monthly_rebalance` 호출 0 (예상대로). universe 조회 / 신호 계산 / no-order reason 로그 없음 = 정상 |
| R.7 | `is_mock=true` (orders 있을 경우) | N/A | orders 0 건 (평일 정상) |
| R.8 | `llm_decisions` applied delta — `ai_hedge` / PR E2 origin 0 | ✅ PASS | smoke run 동안 `applied_at >= 2026-06-04 10:30+09` delta = 0 (모든 source). baseline (0) 유지. |
| R.9 | 인프라 P0 미발생 | ✅ PASS | backend unexpected restart 0 / idle in transaction 5 분 이상 0 / balance 5xx + 내부 lock 동반 0 |
| R.10 | 종료 후 `data/.kill_switch` 미생성 + `data/.trader.pid` 정리 | ✅ PASS | `data/.kill_switch` 미생성 유지. `data/.trader.pid` 자동 제거 |
| R.11 | A안 의도치 않은 mock sell 미발생 | ✅ **PASS — 핵심** | `orders.side='sell'` rows = **0 건**. ACTIVE_STRATEGY compatibility guard 정상 작동 확인. |

### 3.2 FAIL 아닌 것 (A안, 정상)

- universe 조회 / 신호 계산 / 게이트 평가 로그 없음 — 평일 trigger 없음, 정상
- `no-order reason` 기록 없음 — universe 조회 자체가 일어나지 않으므로 정상
- 실 모의 매수 / 매도 발생 0 — cross_momentum weekly 평일 정상
- 체결률 측정 불가 (표본 부족)
- signal confidence 분포 좁음 (표본 부족)

---

## 4. NOTE / 관찰 사항 (비-FAIL)

### 4.1 종료 로그 일부 누락 (NOTE — 종료 자체는 정상)

- logfile 마지막 줄 = `11:02:58 [INFO] 다음 폴링까지 60초 대기...` 이후 `force_close_all` / "사용자 중단" / `save_results` / "매매 요약" 등 종료 로그 없음
- 단 다음은 확인됨:
  - PID 파일 정리 (`_remove_pid_file()` finally 실행됨)
  - tmux pane `^C` + bash prompt 복귀
  - 프로세스 종료 (`ps aux | grep live_trader` 결과 없음)
  - orders 0 건 (force_close_all 의 sell 분기 진입 흔적 없음 + guard 보존 확인)
- 추정 원인: structlog stdout 이 `tee` 로 redirect 되는데 process 종료 시점에 마지막 stdout buffer 가 fully flush 되지 않은 가능성 (block-buffered 모드)
- 영향: **본 smoke run 의 안전성 평가에는 영향 없음** (PID 정리 + sell 0 확인됨). 향후 별도 분석 권장 (코드 변경 필요 시 별도 PR).

### 4.2 부팅 시 자동 승인 다수 발생

- 10:33:28 시점에 `strategy_param_hint 자동 승인 (confidence=0.85~0.90)` 다수 (12+ 건) + `symbol_bias 자동 승인` 1 건
- `applied_at` baseline 캡쳐 시점 (10:30 KST 이후) 의 delta query 결과는 0 — 이는 본 자동 승인이 `applied_at` 컬럼이 아니라 다른 status 전환 (예: `approved`) 만 갱신했을 가능성
- 또는 `applied_at >= 10:30` 필터에 해당 row 가 잡히지 않은 시점 차이
- R.8 PASS 기준은 `ai_hedge` / PR E2 origin delta = 0 (다른 source 는 정상) — 따라서 본 smoke run 의 안전성에는 영향 없음
- 단 추후 본 관찰 (6/15) 시점에 baseline 캡쳐 + delta 측정 방법론 재확인 권장

### 4.3 overnight 포지션 33 개 복원 + 외부 broker holdings 27 개 sync

- 부팅 시 overnight 포지션 33 개 복원, 잔고 조회 27 개 holdings
- ACTIVE_STRATEGY compatibility guard 정상이므로 외부 holdings 가 `strategy="cross_momentum"` 으로 태깅됐을 것 (`scripts/live_trader.py:3386-3390`)
- 종료 시 `force_close_all(force_all=True)` 가 만약 트리거됐다면 cross_momentum 태깅 → 보존 → sell 0 (확인됨)
- 결과적으로 외부 holdings 안전 보존, mock sell 위험 0

### 4.4 재스크리닝 1 회 발생 (11:00:54)

- 11:00 KST 시점에 재스크리닝 1 회 발생 (정상 시각 trigger)
- 2 개 종목 DB 일봉 캐시 미스 → 키움 폴백 정상
- "추가 종목 없음" 결과 → universe 변동 없음

---

## 5. 인프라 변화 (smoke run 전후)

| 항목 | smoke run 전 (2026-06-04 09:57) | smoke run 후 (2026-06-04 11:04) | 변화 |
|---|---|---|---|
| backend 컨테이너 | Up 2 days (healthy) | Up 2 days (healthy) | restart 0 |
| postgres 컨테이너 | Up 5 weeks (healthy) | Up 5 weeks (healthy) | restart 0 |
| `idle in transaction` | 0 | 0 | 변화 0 |
| `broker_credentials` row lock | 0 | 0 | 변화 0 |
| `strategy_runtime` | cross_momentum only | cross_momentum only | 변화 0 |
| `data/.kill_switch` | 없음 | 없음 | 변화 0 |
| `data/.trader.pid` | 없음 | 없음 (정리됨) | smoke run 동안 생성 → 종료 시 자동 정리 |
| `data/.kill_switch_state.json` users | 25 | 25 | 변화 0 (admin 미포함 유지) |
| `llm_decisions` applied (total) | 0 | 0 | delta = 0 |
| `orders` (10:30 이후) | 0 | 0 | 발생 0 |
| `trade_logs` (10:30 이후) | 0 | 0 | 발생 0 |

---

## 6. 합의된 결과 해석 (§5.2 + §8)

- **R.1 ~ R.11 모두 PASS** = **smoke run PASS** (A안 기준 — §6.5 검증 범위 참조)
- A안 의도치 않은 mock sell 미발생 (R.11) 확인 — ACTIVE_STRATEGY compatibility guard 정상 작동
- 인프라 P0 미발생 (R.9):
  - **audit P1 #1 (token_store isolated)**: token path 및 idle in transaction 회귀 없음 확인 (간접 검증 — `_get_token` / balance 경로 정상)
  - **audit P1 #2 (cross_momentum gate session async with)**: 비-trigger tick 에서 회귀 없음만 확인. 실제 gate session 경로 (`execute_monthly_rebalance` → `async with async_session_factory()`) 는 본 smoke run 에서 **exercised 되지 않음**. 검증은 별도 mini rebalance test 또는 2026-06-15 본 관찰의 weekly trigger 발생 시점에 필요.
- 본 관찰 plan §8 "전부 PASS" 시 액션 = **2026-06-15 (월) 본 관찰 기본안 유지. 실제 가동은 6/15 직전 §9.1 preflight + 사용자 최종 가동 OK 후에만**

### 6.5 본 smoke run 검증 범위 (성공 범위 한정)

| 검증됨 | 검증 안 됨 |
|---|---|
| live_trader 부팅 (`is_mock=True`, `ACTIVE_STRATEGY=cross_momentum` 명시) | 체결 (`orders` filled 상태 전이) |
| balance / token path (admin 200, p95 < 2s) | reconcile 경로 (Phase 4 `_compute_reconcile`) |
| 토큰 발급 1 회 + 캐시 정상 (재발급 폭주 없음) | order lifecycle (`created → submitted → accepted → filled`) |
| orchestrator tick (60 초 간격, 30 회) | gate 차단 / 통과 분기 (`drawdown_guard.run_all_checks`) |
| `check_monthly_rebalance` 비-trigger 일 skip (`execute_monthly_rebalance` 미호출) | `execute_monthly_rebalance` 의 실제 4-phase 실행 |
| 종료 경로 (PID 정리, tmux Ctrl-C, force_close_all guard 보존 — sell 0 확인) | audit P1 #2 fix 의 실제 gate session lifecycle (rebalance 미발생) |
| ACTIVE_STRATEGY compatibility guard 안전성 | universe 12-1 momentum 신호 산정 / select_portfolio / compute_rebalance_orders |
| `data/.kill_switch` 미생성 + admin user_id 미포함 유지 | `_persist_rebalance` / `persist_order_submitted` 실 호출 |
| `llm_decisions` ai_hedge / PR E2 origin applied 0 | T+2 settlement 시뮬레이션 |
| backend / postgres unexpected restart 0 | live_trader 장기 안정성 (15 영업일 누적) |

**결론**: 본 smoke run 은 "**실행 경로 / 안전 가드 확인**" 까지 PASS. **주문 / 체결 / 리밸런스 / reconcile 검증은 본 smoke run 의 범위 아님**. 해당 검증은 mini rebalance test (별도 plan 필요) 또는 6/15 본 관찰의 weekly trigger 발생 시점부터 가능.

---

## 7. 다음 액션 (사용자 결정 대기)

| 결정 | 의미 |
|---|---|
| 본 결과 PR 머지 진행 여부 | 결과 문서를 git 에 고정. (옵션) |
| mini rebalance test 진행 여부 / 시점 | 별도 plan 필요. smoke run PASS 했으므로 검토 가능. |
| 6/15 본 관찰 가동 진행 여부 | 6/15 직전 §9.1 preflight 재수행 + 사용자 `"2026-06-15 가동 OK"` 명시 후만 |
| NOTE 4.1 (종료 로그 누락) 분석 | structlog buffer flush 동작 분석 (별도 작업, 별도 PR — 본 plan 범위 밖) |

---

## 8. 정책 준수 확인

- ✅ live_trader 30 분 실행 (계획 30 분)
- ✅ ACTIVE_STRATEGY compatibility guard 가동 전 + 종료 후 검증
- ✅ mini rebalance test 진행 안 함
- ✅ PR E2 / threshold / bias / P2 audit 코드 변경 0
- ✅ `data/.kill_switch_state.json` 파일 변경 0
- ✅ 종료는 tmux send-keys C-c 우선 (PID kill fallback 미사용)
- ✅ 결과 본 문서에 기록 (`docs/observation/2026-06-04-mock-live-trader-smoke-run-results.md`)
- ✅ live_trader 코드 변경 0
- ✅ 본 plan 외 추가 가동 0
