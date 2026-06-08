# ACTIVE_STRATEGY Legacy Audit + 제거 계획 (PR 1)

> **상태**: audit + 회귀 테스트 (PR 1). **실제 제거/대체 코드 변경 없음.**
>
> **상위 설계**: `docs/design/multi-strategy-portfolio-controller.md` (§1.9, §6.5, 로드맵 PR 1 / PR 5+).
> **관련 ADR**: `docs/design/design-024-strategy-enum-consolidation.md` (ADR-024, env 단일 토글), `docs/design/design-025-multi-strategy-orchestrator.md` (DB strategy_runtime 다중 토글).
>
> **작성 기준**: 2026-06-08 현재 코드. `파일:라인` 은 작성 시점.
>
> ⚠️ **제거 금지 (PR 1 범위 외)**: 현재 `ACTIVE_STRATEGY=cross_momentum` 은 **6/15 본 관찰의 compatibility guard** 다 (cross_momentum 포지션을 momentum 손절/강제청산 path 로부터 보호 — 5/5~5/6 사고 재발 방지). 본 PR 은 **인벤토리 + 현재 동작 고정 테스트 + 단계적 제거 계획**까지만. 실제 제거/대체는 budget(PR 2)·ownership·sell authority(PR 3) 완료 후 **PR 5+** 로 분리한다.

---

## 1. 결론 요약

- `ACTIVE_STRATEGY` env 는 ADR-024 의 단일 토글로 도입됐고, design-025 에서 DB `strategy_runtime` 다중 토글로 **점진 전환 중**이다. 두 메커니즘이 **현재 공존**한다.
- DB 기반 가드(`is_strategy_enabled_db`, orchestrator)가 주 경로지만, **live_trader 부팅/실행 모드/안전 분기 일부가 여전히 env `get_active_strategy()` 에 종속**한다 (§3).
- 이 env 종속 분기 중 일부는 **단순 호환(UI status)** 이지만, 일부는 **자금/청산 안전에 직결**(cross_momentum 포지션 보존)된다. 후자를 먼저 DB 기반으로 옮기지 않고 env 를 제거하면 5/5~5/6 사고가 재발할 수 있다.
- 따라서 제거는 **안전 분기 → 모드 분기 → 호환(UI) 순서로 역순 해체**해야 하며, 각 단계 전 characterization 테스트가 선행돼야 한다 (§5).

---

## 2. 사용처 인벤토리 (production code)

`src/` + `scripts/live_trader.py` 만. 문서/테스트/메모리 제외.

### 2.1 resolver (정의)

| 위치 | 내용 | 분류 |
|---|---|---|
| `src/config/active_strategy.py:20-29` | `ActiveStrategy` StrEnum (cross_momentum/multi_regime/short_swing/none) | 정의 |
| `src/config/active_strategy.py:32-42` | `get_active_strategy()` — env 읽기, 잘못된 값/미설정 → NONE | 정의 (env) |
| `src/config/active_strategy.py:45-74` | `is_strategy_enabled_db()` — **DB 우선, row 없거나 실패 시 env fallback** | 정의 (DB+env 가드) |

### 2.2 안전 직결 분기 (제거 시 자금/청산 위험) — **가장 신중**

| 위치(≈) | 동작 | env 제거 시 위험 |
|---|---|---|
| `scripts/live_trader.py:3385-3390` | 외부 sync holdings 의 strategy 태그 = `cross_momentum if ACTIVE==CROSS_MOMENTUM else "momentum"` | cross_momentum 포지션이 "momentum" 으로 태깅되면 momentum 손절 path 가 청산 (5/5~5/6 사고) |
| `scripts/live_trader.py:3432-3444` | 갭 리스크/보유기간 손절을 **MULTI_REGIME 일 때만** 수행, 그 외 SKIP(보존) | cross_momentum/none 에서 손절이 발동하면 부팅 직후 포지션 강제 청산 |
| `scripts/live_trader.py:2270-2319` (force_close_all, §multi-strategy §1.7) | 전략별 보존/청산. cross_momentum 항상 보존 | 본 분기 자체는 strategy 문자열 기반이나, 위 태깅(3385)이 잘못되면 연쇄 영향 |

### 2.3 실행 모드 분기

| 위치(≈) | 동작 | env 제거 시 영향 |
|---|---|---|
| `scripts/live_trader.py:2235-2247` | `MULTI_REGIME` → 레거시 `poll_cycle()`, 그 외 → orchestrator | multi_regime 실행 경로 결정. orchestrator 미통합이라 env 필요 |
| `scripts/live_trader.py:3599-3605` | `mode==ws` 이고 `≠ MULTI_REGIME` → polling 강제 (default tick 매매 차단) | WS 모드 진입 조건. 잘못 풀면 의도치 않은 tick 매매 |
| `scripts/live_trader.py:299, 355, 3229, 3334` | multi_regime 한정 market_style/regime 갱신·집계 분기 | multi_regime 전용 경로 |

### 2.4 부팅 / seed (1회성 마이그레이션)

| 위치(≈) | 동작 |
|---|---|
| `scripts/live_trader.py:3020-3021` | 부팅 시 `ACTIVE_STRATEGY=%s` 로깅 (boolean 상호배타 검증 대체) |
| `scripts/live_trader.py:2134-2173` | `strategy_runtime` 비어있고 env≠NONE 이면 해당 전략 1건 enabled=true seed (budget_pct=1.0, max_order=50M). 기존 row 있으면 enabled=true 전환 |

### 2.5 호환 (UI status) — 제거 영향 낮음

| 위치 | 동작 |
|---|---|
| `src/api/v1/strategy.py:289-310` | `GET /strategy/current` — env 기반 active_strategy + cross_momentum/short_swing detail |
| `src/api/v1/short_swing.py:219-242` | short_swing status 응답에 active_strategy 표시 |
| `src/trading/cross_momentum_rebalance.py:1236-1249` | `_is_cross_momentum_enabled(db)` — db 있으면 `is_strategy_enabled_db`, 없으면 env. (이미 DB 우선 경로 존재) |

### 2.6 이미 DB 기반으로 전환 완료 (env 의존 없음, 참고)

| 위치 | 내용 |
|---|---|
| `src/trading/handlers/cross_momentum_handler.py`, `short_swing_handler.py` | docstring "ACTIVE_STRATEGY env 의존 제거. 내부 가드 DB 기반" |
| `src/trading/short_swing.py:20`, `short_swing_exit.py:21` | `is_strategy_enabled_db` 사용 (DB 우선) |
| `src/trading/orchestrator.py` | `strategy_runtime.enabled` 기반 dispatch (env 무관) |

---

## 3. 현재 동작 계약 (제거 전까지 보존 대상)

`ACTIVE_STRATEGY=cross_momentum` (6/15 본 관찰 설정) 일 때 보장되는 것:

1. **외부/수동 보유 holdings 는 `cross_momentum` 으로 태깅** → momentum 손절 path 진입 안 함 (`live_trader.py:3385-3390`).
2. **갭 리스크/보유기간 손절 SKIP** → 부팅 직후 cross_momentum 포지션 보존 (`live_trader.py:3432-3444`).
3. **WS 모드 우회 → polling 만** → default tick 매매 차단 (`live_trader.py:3599-3605`).
4. **orchestrator 경로 사용** (MULTI_REGIME 아님) → strategy_runtime enabled 전략 dispatch (`live_trader.py:2248-2256`).
5. `strategy_runtime` 비어있으면 env 로 1회 seed (`live_trader.py:2134-2173`).

이 5개는 mini test(2026-06-05) 에서 검증된 동작이며, PR 5+ 제거 시 **동등 동작이 DB 기반으로 대체된 후**에만 env 분기를 제거할 수 있다.

---

## 4. 회귀 테스트 현황 (PR 1 에서 고정)

`tests/config/test_active_strategy.py`:

| 대상 | 테스트 | 상태 |
|---|---|---|
| `get_active_strategy()` env 매핑 (각 값/대소문자/공백/잘못된값/미설정→NONE) | 8건 | 기존 |
| `is_strategy_enabled_db()` DB row enabled=True → True | 1건 | **PR 1 신규** |
| `is_strategy_enabled_db()` DB row enabled=False → False (DB 우선) | 1건 | **PR 1 신규** |
| `is_strategy_enabled_db()` no row → env fallback (match/mismatch) | 2건 | **PR 1 신규** |
| `is_strategy_enabled_db()` DB error → env fallback (set/unset) | 2건 | **PR 1 신규** |

→ resolver/가드 레벨(env + DB fallback)은 **고정 완료** (총 14건 pass).

### 4.1 아직 고정 못 한 동작 (제거 전 선행 필요)

§2.2/§2.3 의 **live_trader `main()` 내부 인라인 분기**(외부 holdings 태깅, 갭/보유손절 게이트, WS 우회)는 3700줄 `main()` 안에 있어 **현재 구조로는 단위 테스트 불가**. PR 1 은 코드 변경 금지이므로 이 분기들을 테스트 가능하게 추출(refactor)하지 않는다. → **PR 5+ 제거 작업의 선행 조건**으로 characterization 테스트(또는 추출 후 단위 테스트)를 둔다 (§5 게이트 G2).

---

## 5. PR 5+ 제거/대체 계획 (단계적)

> 전제: budget(PR 2), ownership/sell authority(PR 3) 가 머지되어 전략별 보유/청산 권한이 DB 기반으로 자리잡은 뒤 시작.

### 단계

| 단계 | 작업 | 대체 방향 |
|---|---|---|
| **R0** | §2.5 호환(UI) 경로의 env → DB(`is_strategy_enabled_db`/portfolio view) 전환 | status API 가 단일 active 대신 enabled 전략 목록 반환 (§multi-strategy §9) |
| **R1** | §2.2 안전 분기 DB 화: 외부 holdings 태깅 + 갭/보유손절 게이트를 ownership(PR 3) 기반으로 | "momentum 손절은 ownership=momentum/multi_regime 포지션만" — env 무관 |
| **R2** | §2.3 실행 모드: WS vs polling 을 env 대신 전략 capability + strategy_runtime enabled 조합으로 | "multi_regime enabled → WS, 아니면 polling" |
| **R3** | §2.4 seed: 1회성 env seed 제거 (DB seed 가 표준이 된 후) | alembic seed / 관리 UI 로 대체 |
| **R4** | `get_active_strategy()` / `ActiveStrategy` enum deprecate → 제거 | 잔존 참조 0 확인 후 |

### 제거 게이트 (각 단계 공통)

- **G1**: 해당 분기의 DB 기반 대체가 머지 + 테스트 green.
- **G2**: 해당 분기의 characterization 테스트(현재 동작 == 대체 후 동작) 존재 + pass.
- **G3**: mock dry-run 에서 cross_momentum 포지션 보존 + 의도치 않은 sell 0 재확인 (5/5~5/6 회귀).
- **G4**: 사용자 review OK (trading/안전 변경 → escalation).

### 절대 금지

- 안전 분기(§2.2)를 DB 대체 없이 먼저 제거.
- 6/15 본 관찰 기간 중 `ACTIVE_STRATEGY` 동작 변경.
- `main()` 구조를 이유 없이 대규모 refactor (제거에 필요한 최소 추출만).

---

## 6. PR 1 산출물

- 본 문서 (`docs/design/active-strategy-legacy-audit.md`).
- `tests/config/test_active_strategy.py` — `is_strategy_enabled_db` 회귀 6건 추가 (총 14건).
- **코드(프로덕션) 변경 0.** ACTIVE_STRATEGY 제거/대체 없음.
