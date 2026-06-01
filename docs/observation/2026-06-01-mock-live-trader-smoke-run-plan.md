# 모의투자 live_trader Smoke Run 계획 (v0.4)

> **상태**: 사용자 결정값 6 항목 입력 완료 (§11.1, 2026-06-01 KST) + 2026-06-01 baseline preflight 결과 기록 (§11.2). **6/04 10:00 KST 직전 §4 preflight 10 항목 재수행 필수** (§11.3). 본 plan 의 PR 머지는 "smoke run 결정값 기록 + 계획 문서 기준 고정" 의미만. **smoke run 자체 실행은 6/04 재preflight 전부 PASS + 사용자 별도 OK 필요**. 6/15 본 관찰 가동도 별도 사용자 OK 필요.
>
> **변경 이력**:
> - v0.1 (2026-06-01) — 초안.
> - v0.2 (2026-06-01) — 사용자 1차 리뷰 반영.
>   - [P0] `scripts/live_trader.py` 잔존 legacy 분기 확인: line 3385 `active_strategy_mode = get_active_strategy()`, line 3386-3390 ACTIVE_STRATEGY != CROSS_MOMENTUM → 외부 보유 `strategy="momentum"` 태깅, line 3650-3652 `except KeyboardInterrupt: await force_close_all(force_all=True)`, line 2289-2302 force_all=True 시 strategy=="cross_momentum" 만 보존. 따라서 ACTIVE_STRATEGY unset + Ctrl-C = 외부 보유종목 mock sell 위험 실재. → smoke run 동안 `ACTIVE_STRATEGY=cross_momentum` compatibility guard 명시.
>   - [P1] 6/4 (목) 은 weekly trigger 일 아님 — `check_monthly_rebalance` 가 trigger date 아니면 `execute_monthly_rebalance` 호출 안 함. PASS 기준에서 universe/signal/no-order reason 필수 제거.
>   - [P1] Stop 절차: Ctrl-C 는 compatibility guard 확인 후에만. `kill <PID>` 는 graceful 아님 — fallback only. tmux send-keys C-c 우선.
>   - [P2] 결과 문서 path 에 실제 실행 일자 포함 (`YYYY-MM-DD-mock-live-trader-smoke-run-results.md`).
>   - [P2] B안 (6/5 금) 은 smoke 가 아니라 **mini rebalance test** 로 분리. 별도 계획 + 별도 체크리스트 필요.
> - v0.3 (2026-06-01) — 사용자 2차 리뷰 반영.
>   - [P1] §6.4 긴급 중단 제목 정정 ("compatibility guard 무관" → "guard 상태에 따라 mock sell 위험이 달라짐") + 절차 1~4 순서 명확화 (1순위: `touch data/.kill_switch` 안전 / 2순위: guard 확인 / 3순위: guard PASS 시 Ctrl-C, FAIL/확인 불가 시 사용자에게 즉시 보고 / 4순위: 사용자 OK 후 fallback).
>   - [P2] §3 cycle 정의 A안 명확화 — "strategy_runtime 조회 → orchestrator.tick → cross_momentum handler 비-trigger executed=False 또는 skip". universe/signal/gate/no-order reason 표현 제거. B안 cycle 정의는 mini rebalance test 문서로 인계.
>   - [P2] §8 PASS 시 "6/15 시작 그대로 진행" → "6/15 본 관찰 기본안 유지. 실제 가동은 6/15 직전 preflight + 사용자 최종 OK 후" 로 완화.
> - v0.4 (2026-06-01) — 사용자 결정값 6 항목 입력 + baseline preflight 기록.
>   - §11.1 결정값 6 항목 (시점 6-04 목 / 기간 30분 / 시작 10:00 KST / mini test 보류 / 결과 path / guard tmux export) 기록.
>   - §11.2 2026-06-01 baseline preflight 결과 (즉시 PASS 8 + DEFERRED 2 — ACTIVE_STRATEGY guard #4/#5 / FAIL 0). 참고용 — 실행 승인 아님.
>   - §11.3 가동 직전 (6/04 10:00 KST) 재preflight + 실행 절차 6 단계 신규. ACTIVE_STRATEGY guard PASS 없이 실행 금지 강조. 재preflight 전부 PASS 여도 사용자 별도 OK 후에만 §6.1 진입.
>   - §11.4 OK 명시 — 6/04 재preflight + 사용자 OK 둘 다 TBD.
>
> **기준 문서**:
> - `docs/observation/2026-06-01-mock-live-trader-observation-plan.md` (v0.8)
> - `docs/observation/2026-06-01-mock-live-trader-checklist.md` (v0.5)
>
> **본 plan 의 위치**: 6/15 본 관찰 (Phase O.1/O.2) 시작 **전** 1 회 수행하는 짧은 실행 경로 확인. 본 관찰 plan 의 §3 기간 / §6 통과 조건 등과 **별개**. 본 관찰 시작일 (2026-06-15 월) 은 그대로 유지.
>
> **작성일**: 2026-06-01

---

## 0. P0 안전 가드 — ACTIVE_STRATEGY compatibility guard (반드시 읽고 시작)

### 문제 (실제 코드 확인)

| 파일 / 라인 | 동작 |
|---|---|
| `scripts/live_trader.py:68` | `from src.config.active_strategy import ActiveStrategy, get_active_strategy` |
| `scripts/live_trader.py:3385` | `active_strategy_mode = get_active_strategy()` — env `ACTIVE_STRATEGY` 기반 |
| `scripts/live_trader.py:3386-3390` | `ACTIVE_STRATEGY != CROSS_MOMENTUM` → 외부 보유종목 `strategy="momentum"` 으로 태깅 |
| `scripts/live_trader.py:3396-3408` | broker `get_balance()` 의 모든 holdings 를 `state.positions` 에 `strategy=external_strategy` 로 등록 |
| `scripts/live_trader.py:3650-3652` | `except KeyboardInterrupt: log.info("사용자 중단 (Ctrl+C)"); await force_close_all(client, state, force_all=True)` |
| `scripts/live_trader.py:2289-2302` `force_close_all` | `force_all=True` 시 `targets = list(state.positions.keys())` → cross_momentum 만 보존, 나머지 = sell 대상 → `execute_sell(...)` 호출 |

### 위험 시나리오

ACTIVE_STRATEGY env 미설정 (= `NONE`) + smoke run 후 Ctrl-C:
1. 부팅 시 외부 broker holdings 가 `strategy="momentum"` 으로 태깅됨
2. Ctrl-C → `force_close_all(force_all=True)` 호출
3. `strategy="momentum"` 포지션 = sell 대상 → 모든 외부 보유종목에 **mock sell 주문 발사**
4. orders / trade_logs / 잔고 / kill_switch 표시 모두 영향 — smoke run 의 "실행 경로 확인" 목적과 정면 충돌

문서상 `ACTIVE_STRATEGY` 는 design-025 이후 legacy fallback 으로 정리됐지만, **`scripts/live_trader.py` 잔존 분기는 아직 env 기반**. DB `strategy_runtime` source of truth 정리와 코드 정리가 분리된 상태.

### Compatibility guard (smoke run 동안 필수)

> **ACTIVE_STRATEGY 는 source of truth 가 아니다. 다만 `scripts/live_trader.py` 내부 잔존 legacy 분기와 종료 시 포지션 보존 경로를 DB 결정값과 정렬하기 위해, smoke run 동안에는 `ACTIVE_STRATEGY=cross_momentum` 을 compatibility guard 로 명시적으로 설정한다.**

설정 방법:

```bash
# tmux 세션 안에서 명시
export ACTIVE_STRATEGY=cross_momentum
uv run python scripts/live_trader.py --auto 2>&1 | tee -a logs/...
```

또는 `.env` 에 임시 추가 (smoke run 종료 후 제거).

§4 preflight 에서 다음 충돌 검증:

| 확인 | 기준 |
|---|---|
| DB `strategy_runtime`: `cross_momentum.enabled=true` only | PASS |
| env `ACTIVE_STRATEGY=cross_momentum` | PASS |
| 둘 다 일치 → compatibility guard OK | PASS |
| DB vs env 불일치 (예: DB cross_momentum + env multi_regime) | **FAIL — smoke run 금지** |

guard 미설정으로 smoke run 시 §6 Stop 절차 사용 금지 (Ctrl-C 위험). 이 경우 §6.4 긴급 중단도 외부 holdings sell 위험 동일.

---

## 1. 목적 (명시)

본 smoke run 은 **live_trader 실행 / 체결 / reconcile 경로가 살아 있는지** 확인만 한다. **전략 성능 / threshold 적정성 / signal 분포 판단은 본 plan 의 범위 아니다**.

### 다루는 것 (A안 — 평일 smoke run)

- live_trader 프로세스 부팅 / DB strategy_runtime 토글 로드 / 브로커 balance / token / 오케스트레이터 tick / 비-trigger 일의 skip 분기 확인
- `is_mock=True` / `ACTIVE_STRATEGY=cross_momentum` compatibility guard 확인 로그
- balance / token / DB session lifecycle 이 audit P1 #1/#2 fix 이후 안정한지
- idle in transaction 유지 / pid 파일 생성·정리

### 다루지 않는 것 (FAIL 처리 금지)

- universe 조회 / 신호 계산 / 게이트 평가 / no-order reason 기록 — `check_monthly_rebalance` 는 `current_hhmm == REBALANCE_ORDER_HHMM("1455")` + trigger date 가 아니면 `execute_monthly_rebalance` 를 호출하지 않음 (`src/trading/cross_momentum_rebalance.py::check_monthly_rebalance`). 따라서 평일 smoke run 에서는 위 로그가 **없을 수 있음 = 정상**.
- 실 모의 매수 / 매도 발생 여부 (cross_momentum weekly 는 금요일 14:55 trigger 만)
- 체결률 / 게이트 차단 횟수 / 신호 confidence 분포
- PR E2 진입 여부
- threshold / bias 적정성

> 위 항목들은 별도 **mini rebalance test** (구 B안 — 본 plan §2.5 참조) 에서 다룬다.

---

## 2. 시점 후보 (사용자 결정)

오늘 = 2026-06-01 (월). 본 관찰 시작 = 2026-06-15 (월). 그 사이 smoke run 1 회.

| 후보 | 평가 |
|---|---|
| 2026-06-02 (화) | 가장 빠름. preflight 직후 + audit PR 머지 24h 이내 → 권장 안 함 |
| **2026-06-04 (목)** ⭐ | preflight 후 3 영업일. 평일 → trigger 없음. 부팅 / 토큰 / balance / 오케스트레이터 tick / 비-trigger skip 분기 확인 깨끗. |
| 2026-06-05 (금) | weekly trigger 일 (14:55 order). 본 plan 범위 밖 → **mini rebalance test** 로 분리 (§2.5). |
| 2026-06-08 (월) | 평일. 6/11 만기 영향권 진입 전 주말 후 첫 영업일. A안 대안 가능. |
| 2026-06-09 (화) | 동일. A안 대안 가능. |
| 2026-06-10 (수) | 만기 (6/11) 직전 — 변동성 가능. |
| 2026-06-11 (목) | 만기일 — smoke run 부적합. |
| 2026-06-12 (금) | 만기 다음날 + weekly trigger — smoke run / mini rebalance test 둘 다 부적합. |

### 리드 권장 (A안 only)

**A. 2026-06-04 (목)** — 평일 smoke run. 부팅 / 토큰 / balance / 오케스트레이터 tick / 비-trigger skip 확인. cross_momentum weekly 라 주문 없음 = 정상. 위험 최소.

대안: 2026-06-08 (월) / 2026-06-09 (화).

→ **사용자 결정 필요**: A안 (smoke run) 시점.

### 2.5 B안 분리 — Mini Rebalance Test (별도 plan 필요)

이전 v0.1 의 B안 (2026-06-05 금) 은 14:55 실제 weekly rebalance 주문 path 를 탄다. 이는 30~60 분 smoke run 보다 blast radius 가 큼:

- `execute_monthly_rebalance` 호출 → universe 12-1 momentum 신호 산정 → 다수 종목 매수 / 매도 주문 실제 발사 (mock)
- 게이트 (drawdown_guard) 통과 시 체결 → orders / trade_logs / 잔고 변화
- audit P1 #2 fix 가 실제 작동하는 첫 라이브 검증 (gate session lifecycle)

따라서 B안 은 **smoke run 이 아니라 mini rebalance test** 로 명칭 분리. 별도 plan 필요:

| 항목 | smoke run (A안) | mini rebalance test (구 B안) |
|---|---|---|
| 목적 | 부팅 / tick / 비-trigger skip 확인 | 실 리밸런스 사이클 1 회 + 체결 path |
| 기간 | 30~60 분 | 14:30 signal ~ 16:00 reconcile 까지 (~ 1.5 h) |
| 주문 발생 | 0 (= 정상) | ≥ 1 (= 의도) |
| blast radius | 최소 | 중간 (잔고 / 게이트 / orders / kill_switch) |
| 본 plan 적용 | ✅ | ❌ — 별도 plan 필요 |

mini rebalance test 는 본 plan 와 별도로 `docs/observation/YYYY-MM-DD-mock-live-trader-mini-rebalance-test-plan.md` (신규) 로 작성. smoke run (A안) PASS 후 사용자 OK 시점에 별도 진행.

본 plan 은 mini rebalance test 를 다루지 않는다.

---

## 3. Duration / cycle

| 항목 | 값 |
|---|---|
| 기간 | **30~60 분** (사용자 결정) |
| 종료 조건 | 시간 도달 또는 사용자가 §6.2 절차 (Ctrl-C — compatibility guard 확인 후) 로 종료 |
| cycle 1 회 정의 (A안 평일) | live_trader main loop 1 회: `strategy_runtime` 조회 → `orchestrator.tick` 호출 → `cross_momentum handler` 가 비-trigger 조건 (`current_hhmm != "1455"` 또는 trigger date 아님) 으로 `executed=False` 반환 또는 skip. **universe 조회 / 신호 계산 / 게이트 평가 / no-order reason 은 본 시점에 발생하지 않으며, 발생 안 함이 정상** (`src/trading/cross_momentum_rebalance.py::check_monthly_rebalance` 참조). |

> mini rebalance test (구 B안 — 6/5 금 14:55 trigger 실행 포함 시나리오) 의 cycle 정의 / 점검 / 결과는 본 plan 의 범위 밖. 별도 `mini-rebalance-test-plan.md` 작성 필요.

---

## 4. Smoke run 전 preflight (5 분)

본 관찰 plan §9.1 의 일부만 즉시 재확인:

| # | 항목 | 기준 |
|---|---|---|
| 1 | `is_mock_trading=True` 기본값 | `grep is_mock_trading src/config/settings.py` |
| 2 | env `KIWOOM_IS_MOCK` 가 `false` 아님 | `env \| grep KIWOOM_IS_MOCK` (미설정 OK) |
| 3 | DB `strategy_runtime` 의 `cross_momentum.enabled=true` only | 본 plan §9 SQL |
| 4 | **env `ACTIVE_STRATEGY=cross_momentum`** (compatibility guard, §0) | `echo $ACTIVE_STRATEGY` |
| 5 | DB strategy_runtime (#3) ↔ env ACTIVE_STRATEGY (#4) 일치 — 둘 다 cross_momentum | 결과 대조. 불일치 시 **FAIL — smoke run 금지** |
| 6 | balance API 인증 200 + p95 < 2s | admin 쿠키 후 5 회 호출 |
| 7 | `pg_stat_activity` idle in transaction = 0 | 본 plan §9 SQL |
| 8 | `data/.kill_switch` 파일 없음 + admin user_id `kill_switch_state.json` 미포함 (또는 NORMAL) | `ls -l data/.kill_switch` + `python3 ...` |
| 9 | backend/postgres healthy | `docker ps` |
| 10 | `llm_decisions` applied baseline 캡쳐 | 본 plan §9 SQL (smoke run 후 delta 비교용) |

10 항목 모두 PASS 아니면 smoke run 가동 금지. **특히 #4 / #5 가 PASS 아니면 §0 mock sell 위험 — 절대 가동 금지.**

---

## 5. 점검 항목 (smoke run 진행 중 + 종료 후)

### 5.1 진행 중 관측

| # | 항목 | 확인 방법 |
|---|---|---|
| O.1 | live_trader 프로세스 활성 | `cat data/.trader.pid` + `ps aux \| grep live_trader` |
| O.2 | 부팅 로그 `is_mock=True` + `ACTIVE_STRATEGY=cross_momentum` 명시 | tmux session 또는 log file head. `log.info("ACTIVE_STRATEGY=%s", get_active_strategy().value)` 참조 (`scripts/live_trader.py:3021`) |
| O.3 | balance / token 로그 정상 | structlog tail |
| O.4 | 오케스트레이터 tick 호출 | structlog tail. 매 tick 마다 `check_monthly_rebalance` 가 호출되고, 비-trigger 일이면 `executed=False` 또는 skip 로그가 남아야 함 (`src/trading/cross_momentum_rebalance.py::check_monthly_rebalance`). |
| O.5 | idle in transaction = 0 유지 | 본 plan §9 SQL 30 초마다 1 회 |
| O.6 | `data/.kill_switch` 파일 미생성 | `ls -l data/.kill_switch` |

### 5.2 종료 후 결과 평가 (A안 — 평일 smoke run)

#### 필수 PASS 기준

| # | 항목 | PASS 기준 |
|---|---|---|
| R.1 | live_trader 정상 종료 | 종료 후 `data/.trader.pid` 파일 미존재 (`scripts/live_trader.py::_remove_pid_file` finally 실행 확인). tmux 세션 정상 종료. |
| R.2 | 부팅 시 `is_mock=True` + `ACTIVE_STRATEGY=cross_momentum` 로그 명시 | structlog grep |
| R.3 | DB `strategy_runtime` 토글 로드 성공 | structlog 또는 부팅 로그에 cross_momentum / multi_regime / short_swing enabled 상태 로그 |
| R.4 | balance / token path 정상 (smoke run 중 504 / 5xx 미발생) | structlog grep / balance 응답 시간 측정값 |
| R.5 | 오케스트레이터 tick 호출 발생 | structlog 에 `check_monthly_rebalance` 호출 1 회 이상 |
| R.6 | 비-trigger 일 skip 동작 | `check_monthly_rebalance` 의 결과가 `False` (executed=False) — universe 조회 / signal 계산 / 게이트 평가 / no-order reason 이 **없을 수 있음 = 정상** |
| R.7 | `is_mock=true` (혹시 발생한 orders / trade_logs 가 있다면) | `orders.is_mock=true`, `trade_logs.is_mock=true` |
| R.8 | `llm_decisions` applied delta — `ai_hedge` / PR E2 origin 0 | smoke run 전 baseline 대비. 다른 source delta 는 정상. |
| R.9 | 인프라 P0 미발생 | backend unexpected restart 0, idle in transaction 5 분 이상 0, balance 5xx + 내부 lock 동반 0 |
| R.10 | 종료 후 `data/.kill_switch` 미생성 + `data/.trader.pid` 정리 | `ls -l data/.kill_switch data/.trader.pid` |
| R.11 | A안 의도치 않은 mock sell 미발생 | smoke run 동안 `orders.side='sell'` rows = 0 (평일 trigger 아님 + compatibility guard 정상 작동). 1 건이라도 발생 시 §0 가드 실패 의심 → 즉시 사용자 보고. |

#### FAIL 아닌 것 (A안)

- universe 조회 / 신호 계산 / 게이트 평가 **로그 없음** — 평일이라 `check_monthly_rebalance` 가 trigger date 아니어서 `execute_monthly_rebalance` 미호출. 정상.
- `no-order reason` 기록 없음 — universe 조회 자체가 일어나지 않으므로 reason 도 없음. **있으면 기록 / 없다고 FAIL 처리 금지.**
- 실 모의 매수 / 매도 발생 0 — cross_momentum weekly 평일 정상.
- 체결률 측정 불가 (표본 부족).
- signal confidence 분포 좁음 (표본 부족).

위 항목들로 "전략 성능 문제" / "live_trader 동작 안 함" 결론 도출 금지.

#### A안 합의된 결과 해석

- R.1 ~ R.11 모두 PASS = **smoke run PASS**. 본 관찰 plan 의 2026-06-15 (월) 시작 그대로 진행.
- R.11 FAIL (sell rows ≥ 1) = **§0 compatibility guard 실패 의심**. 즉시 사용자 보고 + 본 plan 보강 후 재시도.
- R.5 FAIL (tick 호출 0) = live_trader 환경 / DB 토글 / orchestrator path 점검 필요.
- R.9 FAIL (인프라 P0) = 본 관찰 plan 가동 보류. 원인 분석.

---

## 6. Smoke run 실행 절차 (사용자 OK 후만)

### 6.1 Start (§0 + §4 PASS 확인 후만)

```bash
# 1. compatibility guard 명시 (§0)
tmux new -s live_trader_smoke
cd /Users/sanghyuklee/individual/stock/kiwoom-autotrade
export ACTIVE_STRATEGY=cross_momentum   # §0 compatibility guard — 누락 시 가동 금지
echo "guard: ACTIVE_STRATEGY=$ACTIVE_STRATEGY"  # 화면에 명시 출력

# 2. 사전 확인: DB strategy_runtime cross_momentum.enabled=true only (본 plan §9 SQL)
#    + env ACTIVE_STRATEGY=cross_momentum 일치 (§4 #5)
#    위 둘 다 PASS 후에만 실행

# 3. 실행
uv run python scripts/live_trader.py --auto 2>&1 | tee -a logs/smoke_run_$(date +%Y%m%d_%H%M).log
# Ctrl-B D 로 detach (필요 시)
```

부팅 직후 5 분 내 확인:
- `is_mock=True` 라인
- `ACTIVE_STRATEGY=cross_momentum` 라인 (`scripts/live_trader.py:3021`)
- 토큰 발급 1 회 (이후 5 분 전 갱신만)
- 오케스트레이터 tick 시작 로그

### 6.2 Stop (정상) — Ctrl-C 는 compatibility guard 확인 후에만

> **위험 경고**: `Ctrl-C` 는 `scripts/live_trader.py:3650-3652` 의 `except KeyboardInterrupt` 경로 → `force_close_all(force_all=True)` 호출. ACTIVE_STRATEGY compatibility guard (§0) 가 정상이면 외부 보유종목이 `strategy="cross_momentum"` 으로 태깅돼 보존됨. **guard 누락 / 불일치 상태에서 Ctrl-C 사용 절대 금지** — 외부 보유종목 mock sell 위험.

```bash
# 1. compatibility guard 재확인
tmux attach -t live_trader_smoke
# 부팅 로그에서 ACTIVE_STRATEGY=cross_momentum 확인됐는지 다시 grep / 시각 확인

# 2. guard PASS 확인 후 Ctrl-C
# tmux session 안에서 Ctrl-C → KeyboardInterrupt → force_close_all(force_all=True)
#  → cross_momentum 포지션 보존 (line 2294-2302) + 그 외 청산 시도
# guard 정상이면 외부 holdings 모두 cross_momentum 태깅 → 보존 → mock sell 0
```

종료 후 `data/.trader.pid` 자동 제거 확인 (`finally: _remove_pid_file()`, line 3661):

```bash
ls -l data/.trader.pid    # 없으면 정상 정리
```

### 6.3 Stop (시간 제한 도달) — tmux send-keys 우선

`kill <PID>` 는 **graceful stop 아님**. SIGTERM 은 `KeyboardInterrupt` 와 다르고 `try/except/finally` cleanup 보장이 약함. 따라서 시간 제한 도달 시에도 tmux send-keys 로 Ctrl-C 전송 우선.

```bash
# Primary: tmux 세션에 Ctrl-C 신호 전송
tmux send-keys -t live_trader_smoke C-c

# 종료 대기 (10~30 초 graceful cleanup)
sleep 30
ls -l data/.trader.pid 2>&1
ps aux | grep -E "scripts/live_trader\.py" | grep -v grep

# Fallback (정상 종료 실패 시만):
LIVE_PID=$(cat data/.trader.pid 2>/dev/null)
if [ -n "$LIVE_PID" ] && kill -0 "$LIVE_PID" 2>/dev/null; then
    echo "graceful Ctrl-C 실패 — SIGTERM fallback"
    kill "$LIVE_PID"
    sleep 5
    # 그래도 미종료 시 SIGKILL (cleanup 안 됨 인지)
    if kill -0 "$LIVE_PID" 2>/dev/null; then
        echo "SIGTERM 실패 — SIGKILL fallback (cleanup 보장 없음)"
        kill -9 "$LIVE_PID"
    fi
fi
```

### 6.3.1 PID kill fallback 사용 후 stale pid 정리

`kill -9` 또는 SIGTERM 으로 강제 종료한 경우 `_remove_pid_file()` finally 가 실행되지 않아 `data/.trader.pid` 가 stale 로 남을 수 있음. 정리 절차:

```bash
# 1. 라이브 프로세스 실제 종료 확인
ps aux | grep -E "scripts/live_trader\.py" | grep -v grep
# 결과 없어야 함

# 2. stale pid 파일 정리 (사용자 OK 후에만)
ls -l data/.trader.pid
# 결과 있으면 다음 smoke run / 본 관찰 가동 직전 manual 제거:
# rm -f data/.trader.pid   # ← 사용자 OK 후에만
```

`data/.trader.pid` 가 stale 로 남아 있으면 다음 가동 시 `_write_pid_file()` 가 overwrite 하지만, 사용자가 직접 PID 추적할 때 혼동 위험. 제거 권장.

### 6.4 긴급 중단 — guard 상태에 따라 mock sell 위험이 달라짐

본 관찰 plan §9.3 와 절차 동일. 단 §0 compatibility guard 상태에 따라 mock sell 위험이 달라지므로 절차 순서 명확화.

#### 절차

| 순서 | 동작 | 비고 |
|---|---|---|
| 1순위 | `touch data/.kill_switch` — 신규 매수 차단 신호 즉시 생성 | live_trader 가 다음 사이클에서 감지 → "신규 매수 차단 + 보유분 청산 후 종료" 진입. **이 1순위는 guard 상태와 무관하게 즉시 수행 안전**. |
| 2순위 | 가능하면 §0 compatibility guard 상태 확인 | tmux session 부팅 로그 grep `ACTIVE_STRATEGY=cross_momentum` 또는 환경 변수 재확인 (`tmux send-keys -t live_trader_smoke "echo $ACTIVE_STRATEGY" Enter`) |
| 3순위 (guard PASS 경우) | `tmux send-keys -t live_trader_smoke C-c` | guard 정상이면 외부 holdings 가 `strategy="cross_momentum"` 으로 태깅돼 `force_close_all(force_all=True)` 에서도 보존됨 → mock sell 0. |
| 3순위 (guard FAIL / 확인 불가 경우) | **사용자에게 "mock sell 위험 있음" 즉시 보고** | guard 부재 / 불일치 상태에서 Ctrl-C 또는 SIGTERM 발사 시 외부 holdings `strategy="momentum"` 태깅 → `force_close_all` 의 sell 대상. 사용자 결정 전까지 종료 신호 보류. |
| 4순위 (사용자 결정 후) | 사용자가 mock sell 위험 인지 + OK 한 경우만 Ctrl-C / PID kill / SIGTERM fallback | §6.3 fallback 절차 동일. stale pid 정리 §6.3.1. |

```bash
# 1순위 — 즉시 안전, guard 무관
touch data/.kill_switch

# 2순위 — guard 상태 확인 시도
tmux send-keys -t live_trader_smoke "echo ACTIVE_STRATEGY=$ACTIVE_STRATEGY" Enter
# 또는 부팅 로그 grep
grep "ACTIVE_STRATEGY=" logs/smoke_run_*.log | tail -1

# 3순위 — guard PASS 확인된 경우만 Ctrl-C
# tmux send-keys -t live_trader_smoke C-c
```

종료 후 `rm -f data/.kill_switch` 는 **사용자 OK 후에만** (본 관찰 plan §9.3 rollback 정책 동일).

---

## 7. 결과 기록 위치

**파일명에 실제 실행 일자 포함**:

`docs/observation/YYYY-MM-DD-mock-live-trader-smoke-run-results.md`

예: 2026-06-04 실행 시 → `docs/observation/2026-06-04-mock-live-trader-smoke-run-results.md`. plan 작성일 (`2026-06-01`) 이 아니라 **실제 smoke run 실행 일자** 를 prefix 로. 향후 mini rebalance test / 본 관찰 daily report 등 다른 산출물과 시간순 정렬 용이.

본 plan 의 §5.2 R.1~R.11 표를 그대로 채우고 인프라 / orders / trade_logs / llm_decisions delta 첨부.

본 관찰 plan §10 (관찰 결과 영역) 과 분리. smoke run 결과는 본 관찰 plan 의 daily report 가 아님.

---

## 8. Smoke run 후 액션

| 결과 | 액션 |
|---|---|
| §5.2 R.1~R.11 전부 PASS | 본 관찰 plan 의 2026-06-15 (월) 기본안 유지. **실제 가동은 6/15 직전 §9.1 preflight 재확인 + 사용자 최종 가동 OK 후에만**. smoke run 결과 문서 (§7) append + 사용자 리뷰. mini rebalance test 진행 여부 별도 결정. |
| R.11 FAIL (sell rows ≥ 1) | **§0 compatibility guard 실패 의심 — 즉시 사용자 보고**. 본 plan 보강 (가드 강제 절차 / 코드 정정 검토) 후 재시도. 6/15 본 관찰 가동 보류. |
| R.5 FAIL (tick 호출 0) | live_trader 환경 / DB strategy_runtime 토글 / orchestrator path 점검. 6/15 본 관찰 가동 보류. |
| R.7 / R.8 FAIL (is_mock=false / ai_hedge applied delta > 0) | 즉시 사용자 보고. 원인 분석 + 별도 PR 검토. 6/15 시작 연기. |
| R.9 FAIL (인프라 P0) | 본 관찰 plan 가동 보류. 원인 분석 + audit P1 #1/#2 fix 회귀 여부 확인. |

---

## 9. 본 plan 의 변경 / 폐기

- 본 plan 은 1 회용. smoke run 완료 후 결과 문서 (§7) append → 본 관찰 plan 으로 인계.
- 결과가 명확한 FAIL 인 경우 본 plan 의 §5 점검 항목 보강 + 재실행 결정 (사용자 OK 후).

---

## 10. 금지 사항 (smoke run 동안 / 이후)

- **§0 ACTIVE_STRATEGY compatibility guard 부재 / 불일치 상태에서 가동 금지** (외부 holdings mock sell 위험)
- `kill <PID>` 를 "graceful stop" 으로 부르지 마라 — SIGTERM 은 KeyboardInterrupt 와 다르고 cleanup 보장 약함
- 전략 성능 / threshold / bias 변경 결정 금지
- PR E2 진입 코드 작성 금지
- mini rebalance test (구 B안) 를 본 plan 으로 수행 금지 — 별도 plan 필요
- `data/.kill_switch_state.json` 직접 조작 금지
- `data/.trader.pid` 임의 삭제 금지 (라이브 프로세스 종료 확인 후만)
- live_trader 코드 변경 금지
- 본 관찰 plan §8.2 가동 기본안 변경 금지 (smoke run 결과로 본 plan 갱신은 금지 — smoke run 은 "실행 경로 확인" 만)
- smoke run 결과 1 회만으로 multi_regime / short_swing 전략 활성화 결정 금지

---

## 11. 사용자 결정값 입력 영역

### 11.1 사용자 결정값 (2026-06-01 KST 입력)

| # | 항목 | 결정값 |
|---|---|---|
| 1 | smoke run 시점 (A안 only) | **2026-06-04 (목)** |
| 2 | 기간 | **30 분** |
| 3 | 시작 시각 (KST) | **10:00** |
| 4 | mini rebalance test (구 B안) 진행 여부 / 시점 | **smoke run PASS 후 별도 결정. 지금은 진행 안 함** |
| 5 | 결과 문서 path | **`docs/observation/2026-06-04-mock-live-trader-smoke-run-results.md`** |
| 6 | ACTIVE_STRATEGY guard 설정 방식 | **tmux session 안에서 `export ACTIVE_STRATEGY=cross_momentum`** |

### 11.2 2026-06-01 baseline preflight 결과 (참고용 — 실행 승인 아님)

> **본 §11.2 는 2026-06-01 KST 기준 baseline 만**. 결정값 입력 시점에 인프라 상태가 양호한지 확인한 스냅샷. **6/04 10:00 KST 직전 §4 preflight 10 항목 전부 재수행 필수** (§11.3 참조).

| # | 항목 | 2026-06-01 baseline 결과 | 비고 |
|---|---|---|---|
| 1 | `is_mock_trading=True` 기본값 | ✅ PASS | `src/config/settings.py:41` |
| 2 | env `KIWOOM_IS_MOCK` 가 `false` 아님 | ✅ PASS | 미설정 (= 기본값 True) |
| 3 | DB `strategy_runtime` 의 `cross_momentum.enabled=true` only | ✅ PASS | `cross_momentum=t/0.60/50M/200`, `multi_regime=f`, `short_swing=f` |
| 4 | env `ACTIVE_STRATEGY=cross_momentum` (compatibility guard) | ⏸ DEFERRED | 현재 미설정. 6/04 10:00 직전 tmux session 안에서 `export ACTIVE_STRATEGY=cross_momentum` 으로 설정 + 재확인 예정. |
| 5 | DB ↔ env ACTIVE_STRATEGY 일치 | ⏸ DEFERRED | #4 deferred 라 현재 검증 불가. tmux export 후 일치 확인 예정. |
| 6 | balance API 인증 200 + p95 < 2s | ✅ PASS | admin@local.dev 로그인 200/0.658s. balance 5 회: p95 = 1.677s (first) + 0.008~0.017s (cache) |
| 7 | `pg_stat_activity` idle in transaction = 0 | ✅ PASS | idle_in_tx=0, broker_credentials lock=0 |
| 8 | `data/.kill_switch` 파일 없음 + admin user_id `kill_switch_state.json` 미포함 | ✅ PASS | `data/.kill_switch` 없음, `data/.trader.pid` 없음, admin (`0103827d-...`) 미포함 |
| 9 | backend / postgres healthy | ✅ NOTE PASS | backend Up 3 hours (planned restart 13:49 KST audit P1 #2 머지 후), postgres Up 4 weeks |
| 10 | `llm_decisions` applied baseline 캡쳐 | ✅ PASS | **`applied`=0 (모든 source)**. baseline = `{all: 0}` |

**baseline 요약**: 즉시 PASS 8/10, deferred 2/10 (#4, #5 — ACTIVE_STRATEGY guard), FAIL 0.

### 11.3 가동 직전 재수행 + 실행 절차 (2026-06-04 10:00 KST 직전)

> §11.2 는 **6/01 baseline 일 뿐**이다. **6/01 → 6/04 사이 3 영업일 동안 인프라 / DB / strategy_runtime / kill_switch_state.json / 코드 변경 발생 가능 — baseline 그대로 가정 금지**.

#### 6/04 당일 절차 (순서 엄수)

| 순서 | 동작 | PASS 기준 |
|---|---|---|
| 1 | tmux session 생성 (`tmux new -s live_trader_smoke`) | session 진입 |
| 2 | session 안에서 `export ACTIVE_STRATEGY=cross_momentum` | `echo $ACTIVE_STRATEGY` 가 `cross_momentum` 출력 |
| 3 | **§4 preflight 10 항목 전부 재수행** | 10/10 PASS (특히 #4 / #5 가 PASS) |
| 4 | Claude 가 PASS/FAIL 표 보고 | 사용자에게 결과 제출 |
| 5 | **사용자가 `"smoke run 실행 OK"` 별도 명시** | 명시 텍스트 chat 입력 |
| 6 | 사용자 OK 후에만 §6.1 start 절차 진입 | `uv run python scripts/live_trader.py --auto` 실행 |

#### 절대 금지

- 6/04 재preflight 전 live_trader 실행 금지
- 재preflight 결과가 일부 FAIL 인데 실행 진입 금지
- 재preflight 전부 PASS 여도 **사용자가 `"smoke run 실행 OK"` 라고 별도 명시하기 전까지 실행 금지**
- "6/01 baseline 이 PASS 였으니 6/04 도 PASS 일 것이다" 가정 금지
- ACTIVE_STRATEGY guard (#4/#5) PASS 없이 실행 금지 — 외부 holdings mock sell 위험 (§0)

#### 6/04 재preflight 가 FAIL 인 경우

- 즉시 사용자 보고 + 원인 분석
- smoke run 일정 연기 또는 조건 보정 후 재시도 결정 (사용자 OK 후)
- 코드 변경 / DB 조작 / `data/.kill_switch_state.json` 정리 모두 사용자 OK 후

### 11.4 OK 명시

| 항목 | 값 |
|---|---|
| 사용자 결정값 6 항목 (§11.1) | ✅ 입력 완료 (2026-06-01 KST) |
| 2026-06-01 baseline preflight (§11.2) | ✅ 8 PASS / 2 deferred / 0 FAIL |
| **2026-06-04 10:00 KST 직전 §4 preflight 재수행** | ⏸ TBD — 6/04 당일 |
| **사용자 smoke run 실행 OK** | ⏸ TBD — 6/04 재preflight 전부 PASS 후 사용자가 `"smoke run 실행 OK"` 별도 명시 |

**중요**: §11.1 + §11.2 = "결정값 기록 + baseline 인프라 확인" 의미. **실행 승인 아님**. §11.3 절차 (재preflight + 사용자 OK) 가 완료된 뒤에만 §6.1 start.

---

## 12. 다음 작업자 진입점

- 본 plan 의 §11 미해결 항목
- 본 관찰 plan v0.8 (`2026-06-01-mock-live-trader-observation-plan.md`) §9.1 preflight / §9.2 start / §9.3 stop
- 체크리스트 v0.5 (`2026-06-01-mock-live-trader-checklist.md`) §11.2.1 / §11.2.2 PASS 기록
- `scripts/live_trader.py:92` `_TRADER_USER_ID = uuid.uuid4()` (kill_switch user UUID 생성 위치)
- `src/trading/cross_momentum_rebalance.py::execute_monthly_rebalance` (audit P1 #2 fix 적용 경로)
