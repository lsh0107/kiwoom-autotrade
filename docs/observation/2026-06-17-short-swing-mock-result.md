# Short Swing Mock Run Result — 2026-06-17 (조건부 PASS, lifecycle 미검증)

> public-safe 요약. 실계좌 금액 / 보유 평가액 / allowed_cash / notional 미포함.
> 비공개 산출물 없음 (이번 run 은 `outputs/short_swing/` 미생성).

## 1. 실행 개요

| 항목 | 값 |
|---|---|
| 일자 | 2026-06-17 (수) |
| 명령 | `bash scripts/run_short_swing_mock.sh` (사용자 명시 GO 후) |
| DURATION_SEC | 1800 (30 분) |
| 실가동 cycle 첫 발동 | 10:52 KST (script 시작 ~10:09 → 초기화/MarketContext 로딩 ~43 분) |
| 종료 | 11:21 KST (timeout SIGINT → graceful shutdown 정상) |
| 사이클 수 | 약 30 (1분 폴링) |
| 시점 regime | bull_overheat (confidence 90, daily dry-run 2026-06-17) |
| PR A2 cutoff | 2026-06-16 (장중 09:43 KST, ready_hhmm=1700 이전) |
| 적용된 안전장치 | PR A (stale guard) + PR A2 (장중 cutoff) + PR B (mock-only + regime overlay) |

## 2. 판정

**조건부 PASS / lifecycle 미검증**

7 / 8 검증 항목 PASS, 1 항목 (lifecycle) 미검증.

| # | 항목 | 결과 | 근거 |
|---|---|---|---|
| 1 | short_swing enabled 토글 복구 (trap) | ✅ PASS | 종료 후 `SELECT enabled WHERE strategy='short_swing'` = `f`. 로그 `[trap] short_swing enabled=false 복구` |
| 2 | stale guard PASS | ✅ PASS | preflight cutoff=2026-06-16, max_date=2026-06-16, coverage=0.938 |
| 3 | bull_overheat 정책 max_new_entries=1 | ✅ PASS | 모든 cycle `regime overlay: regime=bull_overheat allow=True override=1 reason=regime_limit_bull_overheat` |
| 4 | cross_momentum 보유 매도 0 | ✅ PASS (간접) | `Δorders=0` 으로 매도 자체 발생 0. 직접 SQL 검증은 #3 runbook bug 로 미실행 (후속) |
| 5 | orders / trade_logs lifecycle | ❌ 미검증 | `SKIP: 후보 없음` (`short_swing_candidates` total=0) — 진입 발동 자체가 없어 lifecycle 시작 불가 |
| 6 | llm_decisions unexpected consume 0 | ✅ PASS | Δllm=0 (119→119) |
| 7 | idle in transaction 0 | ✅ PASS | 0 (종료 후 즉시 측정) |
| 8 | stale pid / kill_switch 없음 | ✅ PASS | `data/.trader.pid` / `data/.kill_switch` 둘 다 부재 |

## 3. lifecycle 미검증 원인 (blocker)

`short_swing_candidates` 테이블이 비어있음 (total=0). 진입 후보 자체가 없으므로 `run_entry_check` 가 `SKIP: 후보 없음` 으로 매 cycle 반환. 안전장치 + handler 진입 + regime overlay 적용 경로는 정상 작동했으나 **주문 lifecycle (PENDING→SUBMITTED→FILLED + trade_logs) 은 진입 발동 부재로 검증 불가**.

### 적재 경로 (조사 결과)

| 모듈 | 역할 |
|---|---|
| `airflow/dags/postmarket/short_swing_screening.py` | Asset `daily_candle_collection` 트리거. 후보 생성 DAG. |
| `src/screening/short_swing_screener.py::run_short_swing_screening` | 일봉 기반 후보 산출 → `ShortSwingCandidate` insert |
| `airflow/dags/postmarket/daily_candle_collection.py` | 의존 DAG. 장마감 후 일봉 수집 + Asset publish |

### 추정 실패 원인

airflow 4 컨테이너 모두 종료 후 6/17 오전에 재시작 (status "starting/Up under 1m"). 6/16 장마감 시점 (16:00 KST) 에 airflow 가 미가동 → `daily_candle_collection` DAG 미실행 → Asset 미발행 → `short_swing_screening` 미트리거. `catchup=False` 라 자동 backfill 안 됨.

사용자 지시: **DB 임의 후보 적재 금지** (파이프라인 검증이 아니므로).

## 4. 추가 발견 (runbook 버그)

`scripts/run_short_swing_mock.sh` 내 SQL 케이스 오류 3건:

| # | 위치 | 문제 | 수정 |
|---|---|---|---|
| 1 | preflight `short_swing_open` 카운트 | `status='OPEN'` | `status='open'` (enum 소문자) — 이미 로컬 fix |
| 2 | post-run 사후 SQL `side='SELL'` | enum 대문자 오류 | `side='sell'` (필요) |
| 3 | post-run `orders.strategy='short_swing'` | 컬럼 미존재 (실제 `strategy_id` 추정) | 정확한 컬럼 확인 + join 필요 |

세 bug 모두 mock run 자체 안전성에는 영향 없음 (orders Δ=0 확인). post-run 검증 SQL 실패 → 사후 자동 검증 미작동, 수동 SQL 로 대체 수행 (§2 #4 참조).

## 5. 다음 액션 (사용자 결정 필요)

### A. candidate 적재 경로 확인

- airflow `daily_candle_collection` + `short_swing_screening` DAG 의 6/17 장마감 후 자동 실행 여부 확인.
- 자동 실행되면 6/18 (목) 09:20~ mock run 재시도 → lifecycle 검증 가능성.

### B. runbook 보강 (다음 PR — 가칭 PR D)

- preflight 에 `short_swing_candidates` 존재 검사 추가 (예: `latest trade_date >= 직전 영업일` 이면 PASS, 아니면 명확한 skip reason).
- post-run SQL bug fix (`status='open'`, `side='sell'`, strategy 검증 컬럼 정확화).
- 후보 generation step 을 runbook 안에 통합할지 여부 결정 (자동 trigger vs 사용자 수동).

### C. lifecycle 재시도 시점

candidate 적재 정상 작동 확인 후 다음 영업일 mock run.

## 6. 금지 (유지)

- 실거래 전환.
- `is_mock_trading=False` 가동.
- short_swing ownership / sell authority 변경 (PR 3 영역).
- ai_hedge boost_sell / review_sell 자동 매도 연결.
- DB 임의 후보 적재 (`short_swing_candidates` 수동 insert).
- `outputs/regime/` `outputs/short_swing/` 산출물 커밋.

## 7. 참조

- runbook: `docs/observation/2026-06-16-short-swing-mock-runbook.md`
- runbook script: `scripts/run_short_swing_mock.sh`
- PR A: #555/#556 (stale guard)
- PR A2: #561/#562 (cutoff 정책 보정)
- PR B: #557/#558 (mock-only safety + regime overlay)
- regime daily dry-run summary: `docs/observation/2026-06-17-regime-dryrun-summary.md`
