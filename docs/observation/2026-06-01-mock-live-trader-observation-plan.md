# 모의투자 live_trader 관찰 계획 (기준 문서 — v0.5)

> **상태**: 기준 문서. **본 plan 의 머지는 "관찰 계획의 방향과 절차를 기준 문서로 고정" 의 의미일 뿐, 실제 모의 live_trader 가동을 승인하는 것은 아니다.** 가동은 §8 8 항목 체크리스트 (`2026-06-01-mock-live-trader-checklist.md`) 가 별도로 확정 + 사용자 명시 OK 된 후에만. threshold 변경 / PR E2 진입 / bias 소비 로직 변경 **모두 보류 유지**.
>
> **변경 이력**:
> - v0.1 (2026-06-01 작성) — 초안.
> - v0.2 (2026-06-01 사용자 1차 리뷰 반영) — §5/§6 중단/통과 조건 정교화, §8 승인 의미 약화, §9 실행 절차 추가.
> - v0.3 (2026-06-01 사용자 2차 리뷰 반영) — §9.3 kill/rollback 명령 실제 코드 (`KILL_SWITCH_FILE` / `PID_FILE` / `KillSwitch.soft_stop/hard_stop/resume`) 기준으로 재작성, §4.2/§6.2 restart 기준 "unexpected only" 통일, §2.2 C "운영" 표현 제거, §9.4 daily SQL KST timezone 명시, §6.2 매수/매도 ≥5 → "데이터 충분성 조건 (FAIL 아닌 N1 연장)".
> - v0.4 (2026-06-01 사용자 3차 리뷰 반영) — §5.4 중단 절차도 파일 기반 (`data/.kill_switch` + `data/.trader.pid`) 으로 통일, §9.4 SQL `:obs_date` 변수화 설명 제거 + "매 영업일 `YYYY-MM-DD` 수동 치환" 으로 정리. PR #503/#504 머지.
> - v0.5 (2026-06-01 사용자 P1 지적 반영) — 활성 전략 source of truth 정정. §9.1 preflight #3/#4 를 DB `strategy_runtime` 우선 + env `ACTIVE_STRATEGY` legacy fallback 으로 재작성. §9.2 start command 사전 단계에 DB 적용 절차 명시 + ACTIVE_STRATEGY 는 legacy 명시. 체크리스트 (v0.2) 와 같은 PR.
>
> **목적**: 지금까지 read-only proposal pipeline 만 몇 번 돌린 상태에서는 전략 성능 / sell 신호 적정성 / boost_sell threshold / live_trader 장기 안정성 어느 것도 판단 불가. 모의 live_trader 를 일정 기간 가동해 관찰 데이터를 누적한 뒤에야 PR E2 / threshold 같은 다음 단계 판단이 의미 있다. 그 가동을 어떻게 할지 결정하는 문서.
>
> **작성일**: 2026-06-01
> **선행 문서**:
> - `docs/ai-hedge/PR_E_DESIGN.md` — PR E1/E2 설계 (이미 머지됨, 코드 진입 보류)
> - `ai-hedge-fund-lab/docs/07_OBSERVATION_PIPELINE.md` — lab 측 proposal 관찰 §5 정량 기준
> - `docs/audit/2026-06-01-async-transaction-audit.md` — 본 세션 audit

---

## 1. 전제

본 계획이 다루지 **않는** 것:

- 실거래 가동 (`is_mock_trading=False`) — 절대 금지
- AI hedge live consumption (PR E2 코드 진입) — 보류 유지
- threshold / 전략 로직 / bias 소비 로직 변경 — 보류
- live_trader 코드 변경 — 본 관찰은 현재 코드 그대로 실행해서 안정성/관측성만 확인

본 계획이 다루는 것:

- 어떤 전략을 모의로 켤지 (§2)
- 몇 영업일 관찰할지 (§3)
- 어떤 신호를 볼지 — 로그 / DB / structlog 키 (§4)
- 어떤 조건이면 즉시 멈출지 (§5)
- 어떤 조건이면 다음 단계 (PR E2 또는 별도 안정화 PR) 진입을 사용자 결정에 회부할지 (§6)

---

## 2. 어떤 전략을 켤지

### 2.1 가용 전략 (현재 코드 기준)

`src/config/active_strategy.py:20`

| enum | 비고 |
|---|---|
| `cross_momentum` | 월말/주말 리밸런스. 매수+매도 다회. 본 세션에서 P1 #1/#2 fix 적용된 경로. |
| `multi_regime` | 60초 폴링. 더 자주 신호 발생. |
| `short_swing` | reconciler 가 별도 작동. |
| `none` | 비활성. |

### 2.2 추천 (사용자 결정 대상)

| 옵션 | 장점 | 단점 |
|---|---|---|
| **A. `cross_momentum` 만 켜기** | 본 세션의 audit P1 fix 가 직접 작동하는 경로 검증. 1주 1회(weekly) ~ 1달 1회(monthly) 리밸런스라 신호량 적어 관찰 부담 작음. | 신호량이 너무 적어 관찰 기간이 길어짐. |
| B. `multi_regime` 만 켜기 | 60초 폴링 → 신호량 많음. 짧은 기간에도 데이터 쌓임. | cross_momentum P1 fix 경로는 검증 안 됨. polling 자체의 안정성 부담. |
| C. 둘 다 켜기 | 둘 다 검증. | 결정 권한 충돌 가능 (동일 종목 양쪽 신호). 관찰 / 로컬 검증 부담 증가. |

**리드 권장**: **옵션 A** (cross_momentum 만, weekly 모드). 이유:
1. 본 세션 audit P1 fix 가 직접 작동하는 경로.
2. 1주 1회 리밸런스라 사용자가 한 번 켜고 1주 단위로 관찰 가능.
3. multi_regime 은 본 계획 종료 후 별도 관찰 plan 으로 분리.

→ **사용자 결정 필요**: A/B/C 중 선택. 본 문서는 A 가정으로 §3~§6 작성.

### 2.3 강제 mock 확인

다음 모두 사실인지 가동 전 1회 확인 (코드 변경 없음, 점검만):

- `src/config/settings.py:41` — `is_mock_trading: bool = True` 기본값
- env `KIWOOM_IS_MOCK` 가 `false` 로 명시되지 않음 (`live_order_persist.py:28`)
- live_trader 부팅 로그에 `is_mock=True` 가 명시 출력

---

## 3. 몇 영업일 볼지

### 3.1 추천 기간

| 단계 | 기간 | 종료 조건 |
|---|---|---|
| **Phase O.1 — 안정성 관찰** | 최소 5 영업일 (1 주) | 인프라 이슈 (504 / DB lock / token / restart 필요) 0 건 |
| **Phase O.2 — 신호 관찰** | Phase O.1 통과 후 추가 10 영업일 (2 주) | 신호 누적이 lab §5 진입 기준 (`actions.sell ≥ 30`, `boost_sell ≥ 5`) 충족 또는 명백히 미충족 확정 |
| 합산 | 최소 15 영업일 (3 주) | — |

### 3.2 기간 산정 근거

- `cross_momentum` weekly 모드: 1 주 1회 리밸런스 → 3 주면 3회 리밸런스 사이클 관찰.
- monthly 모드 선택 시 산정 변경 필요 (사용자 결정 후 본 문서 갱신).
- lab §5 진입 기준 (`actions.sell 누적 ≥ 30`) 는 lab proposal 기준이라 cross_momentum 실 매도와 다름. 본 plan §6 에서 별도 매핑 정의.

### 3.3 일정

| 단계 | 시작 | 종료 |
|---|---|---|
| 본 문서 사용자 승인 | T+0 | T+0 |
| 모의 live_trader 가동 시작 | T+1 영업일 | — |
| Phase O.1 평가 | T+1 + 5 영업일 | T+6 영업일 |
| Phase O.2 평가 | T+6 + 10 영업일 | T+16 영업일 |
| §6 결정 회부 | T+16 영업일 | 사용자 결정 |

T+0 = 사용자 승인일.

---

## 4. 어떤 로그 / DB / 지표를 볼지

### 4.1 DB 테이블 (source of truth)

| 테이블 | 핵심 컬럼 | 본 관찰의 용도 |
|---|---|---|
| `orders` | `status` (created→submitted→accepted→partial_fill/filled/rejected/cancelled/expired/failed), `side`, `quantity`, `filled_quantity`, `filled_price`, `broker_order_no`, `is_mock`, `submitted_at`, `filled_at` | 체결 품질 (rejected/failed 비율, partial_fill 비율, submitted→filled 지연) |
| `trade_logs` | `event_type`, `side`, `price`, `quantity`, `message`, `details`(JSON) | 의사결정 경로 (어떤 신호로 어떤 종목 주문이 발생/스킵됐는지) |
| `llm_decisions` | `status` (pending/approved/applied/evaluated), `context_source` (`ai_hedge` / `overnight` / `manual` / `strategy_param_hint` / …), `confidence`, `applied_at` | **관찰 시작 직전 baseline 카운트를 찍어두고, 이후 delta 만 본다**. 기존 정책으로 발생하는 overnight / manual / strategy_param_hint applied 는 정상. `context_source='ai_hedge'` (또는 PR E2 관련 bias 소비) 로 인한 신규 applied delta > 0 이면 중단 (= 사용자 동의 없이 PR E2 코드 진입). 그 외 source 의 applied delta 는 본 plan 의 중단 트리거 아님. |
| `strategies` | `is_auto_trading`, `max_investment` | 활성 전략이 cross_momentum 만인지 확인 |

### 4.2 indicator (Phase O.1 인프라 안정성)

| 지표 | 정상 기준 | 측정 방법 |
|---|---|---|
| backend container **unexpected** restart | 0 (planned rebuild / 수동 restart 는 §5.5 INFO 로 daily report 에 별도 기록) | `docker ps` `Up <duration>` 단조 증가 + planned 이벤트 로그 대조 |
| balance API 응답 | 200, < 2s (95th pct) | curl + structlog `account.balance` |
| `idle in transaction` 세션 | 0 | `pg_stat_activity` |
| `broker_credentials` row lock > 5s | 0 | `pg_locks` + `pg_stat_activity` |
| 토큰 재발급 빈도 | 만료 5분 전만 (TOKEN_REFRESH_BUFFER_SECONDS) | structlog `token.refresh` 카운트 |
| 외부 키움 5xx | 알려진 패턴 외 0 | structlog `kiwoom.error` |

### 4.3 indicator (Phase O.2 신호 관찰)

| 지표 | 측정 방법 |
|---|---|
| cross_momentum 리밸런스 실 횟수 | `trade_logs.event_type='cross_momentum_rebalance_*'` 카운트 |
| 매수/매도 주문 수 | `orders.side` 별 group by date |
| 체결률 | `filled / submitted` |
| 게이트 차단 횟수 | structlog `gate.blocked` / `drawdown_guard.run_all_checks` REJECT 카운트 |
| 비중 조정 (adjust_sells / adjust_buys) 발생 빈도 | `trade_logs` details JSON 파싱 |
| 일일 누적 주문 수 vs `MAX_DAILY_ORDERS=200` | structlog |

### 4.4 외부 관측 (lab 측 — 별도)

본 plan 은 본 repo (kiwoom-autotrade) 의 live_trader 관찰 plan. lab daily proposal pipeline 은 별도로 매 영업일 실행하되, 본 관찰 결과와 **연결하지 않는다** (PR E2 미진입 = 두 시스템이 분리된 상태가 정상).

---

## 5. 어떤 조건이면 중단할지 (kill criteria)

다음 중 하나라도 발생 시 **즉시 live_trader 정지** + 사용자에 보고 + 본 plan 일시 중단:

### 5.1 인프라 P0

| 조건 | 의미 |
|---|---|
| **unexpected** backend container restart > 0 | 안정성 미달. (planned rebuild / 수동 restart 는 §5.5 별도 분류 — P0 아님) |
| `idle in transaction` 세션 > 0 이 5 분 이상 지속 | audit P1 fix 무력화 신호 |
| balance API 5xx 발생 시 **즉시 `pg_stat_activity` / `pg_locks` 동반 확인** → 내부 `idle in transaction` / `broker_credentials` 류 row lock 동반이면 P0 | 내부 leak 재발 신호 |
| balance API 5xx 가 내부 lock 동반 없이 외부 upstream transient (Kiwoom 5xx / network) 로 추정되면 **degraded observation 으로 기록 + 재시도** | P0 아님 (§5.5 분류) |
| `broker_credentials` row lock > 30s | DB lock 위험 |
| 토큰 폭주 재발급 (시간당 > 3회) | 캐시 미작동 |

### 5.2 전략 P0

| 조건 | 의미 |
|---|---|
| `is_mock=False` 주문 1 건이라도 발생 | 모드 누설 — 즉시 정지 + revoke 검토 |
| `llm_decisions` 신규 applied 중 **`context_source='ai_hedge'`** 또는 PR E2 관련 bias 소비 origin 1 건이라도 발생 (관찰 시작 시점 baseline 대비 delta) | 사용자 동의 없는 PR E2 코드 진입. 기존 overnight / manual / strategy_param_hint applied 는 정상 — 본 트리거 아님 |
| kill_switch 자동 트리거 (HARD_STOPPED) | drawdown / 게이트 차단 누적 |
| `MAX_DAILY_ORDERS=200` 초과 시도 | 신호 폭주 |

### 5.3 데이터 P0

| 조건 | 의미 |
|---|---|
| `orders.broker_order_no` NULL 비율 > 5% | broker / persist 비일관 |
| `filled_quantity > quantity` 비정상 | 데이터 정합성 깨짐 |
| structlog 에 자격 증명 / 토큰 raw 값 노출 | 보안 위반 — 즉시 정지 |

### 5.4 중단 절차

> 권장 경로 = 파일 기반. user-level `KillSwitch.hard_stop(user_id)` / `data/.kill_switch_state.json` 직접 조작은 라이브 세션 UUID (`scripts/live_trader.py:92` `_TRADER_USER_ID` — 매 세션 새로 생성) 를 알지 못하면 라이브 세션과 분리된 상태만 바꾼다. 기본 중단 절차에서 제외하고, 필요 시 §9.3 "user-level API 를 외부에서 호출하려면" 절을 따른다.

1. **신규 매수 차단 신호 생성**: `touch data/.kill_switch` — live_trader 가 다음 사이클에서 감지 → "신규 매수 차단 + 보유분 청산 후 종료" 진입 (`scripts/live_trader.py::check_web_kill_switch` 가 `KILL_SWITCH_FILE` 존재만 확인).
2. **라이브 PID 확인 + 종료**: `cat data/.trader.pid` 로 PID 확보 → 일정 시간 (1~2 사이클) 대기 후 graceful 종료 안 되면 `kill <PID>`. PID 가 없거나 stale 이면 `ps aux | grep -E "scripts/live_trader\.py" | grep -v grep` 으로 동명 프로세스 0 확인 후에만 `pkill -f "scripts/live_trader.py"` fallback.
3. 본 plan §10 결과 섹션에 "중단 트리거" 시각 + 사유 + 증거 (로그 / SQL 결과 / pg_stat_activity 스냅샷) append.
4. 사용자 보고 + 재가동 결정 대기.

자세한 명령은 §9.3 참조. rollback / 안전장치 해제는 §9.3 "rollback" 절 (사용자 명시 OK 후에만 `rm -f data/.kill_switch`).

### 5.5 비-P0 이벤트 분류 (관찰 로그에 기록만, 즉시 중단 아님)

| 이벤트 | 분류 | 처리 |
|---|---|---|
| planned rebuild / 수동 restart (post-merge / 수동 docker restart 등) | INFO | §10 daily report 의 "planned restart" 섹션에 시각 + 사유 기록 |
| balance API 5xx 가 내부 lock 동반 없이 외부 upstream (Kiwoom 5xx) 로 추정 | DEGRADED | 발생 시각 + curl 응답 + `pg_stat_activity` 스냅샷 동봉. N 분 후 자동 재시도. 1 영업일 누적 N ≥ 5 회면 P0 로 격상 검토 |
| 외부 키움 일시 timeout (단발) | DEGRADED | 동일 처리 |
| 자기진단용 read-only DB lock 단발 (< 5 분) | INFO | 기록만 |
| 일일 주문 0 건 (cross_momentum weekly 정상 시나리오 포함) | INFO | §6.1 통과 조건 아님. cycle 실행 / 후보 평가 로그가 있으면 정상 |

---

## 6. 어떤 조건이면 다음 단계로 넘어갈지

### 6.1 Phase O.1 → Phase O.2 진입 조건

다음 **모두** 충족:

- 5 영업일 **unexpected** 중단 0 건 가동 (planned rebuild / 수동 restart 는 §5.5 INFO 분류이므로 통과 가능)
- §5.1 인프라 P0 위반 0 건
- balance API p95 < 2s 유지 (degraded transient 제외)
- `idle in transaction` 5 분 이상 지속 0 건
- live_trader cycle 이 예정된 trigger 시각마다 실행됐다 (cron / 폴링 사이클 누락 0)
- 각 cycle 마다 후보 평가 로그 (universe 조회 / 시그널 계산 / 게이트 평가 결과) 가 structlog 또는 trade_logs 에 남아 있다
- 주문이 0 건이면 **반드시 "no-order reason"** (`signal_below_threshold` / `no_target_diff` / `gate_blocked` / `market_closed` / `duplicate_prevention` 등) 이 trade_logs 또는 structlog 에 기록돼 있다

**주문 발생 여부는 Phase O.1 통과 기준 아님** (cross_momentum weekly 는 신호 없으면 주문 0 이 정상). 주문량은 §6.2 Phase O.2 의 전략 관찰 지표.

미충족 시: 본 plan 중단 + 원인별 분기 (코드 수정 필요 시 별도 PR / 환경 문제면 환경 점검 / 신호 부재면 관찰 기간 연장 결정).

### 6.2 Phase O.2 통과 → 다음 PR 진입 회부 조건

다음 **모두** 충족 시 사용자 결정에 회부:

| # | 조건 | 측정 |
|---|---|---|
| 1 | Phase O.1 + O.2 합산 15 영업일 **unexpected** 중단 0 건 (planned restart 는 §5.5 INFO) | restart 로그 분류 결과 |
| 2 | 보안/로그 위반 0 건 | structlog 검토 |
| 3 | audit P1 #1/#2 재발 0 건 | `pg_stat_activity` log |

**"데이터 충분성" 조건** (FAIL 아님 — 미충족 시 §6.3 N1 관찰 연장):

| # | 조건 | 측정 | 미충족 시 |
|---|---|---|---|
| D.1 | 실 모의 매수 ≥ 5 회 / 실 모의 매도 ≥ 5 회 | `orders.filled` count, side 별 | N1 관찰 연장 (cross_momentum weekly 는 시장 상황 따라 매도 0 이 정상일 수 있음) |
| D.2 | 체결률 ≥ 70% (rejected/failed 합산 ≤ 30%) | `filled / submitted`. 표본 < 10 이면 판정 보류 | 표본 부족이면 N1, 표본 충분 + 실패 시 N2/N3 검토 |
| D.3 | 게이트 차단이 "0" 도 아니고 "다수" 도 아닌 적정 (1~`MAX_DAILY_ORDERS*0.1`) | structlog gate count. 표본 < 10 이면 판정 보류 | 표본 부족이면 N1 |

위 D 조건들은 **회부 조건이 아님**. PR E2 / threshold 변경 같은 다음 단계로 넘어가기 위한 "전략 품질 판단 근거 데이터 확보 여부" 만 측정. 데이터 부족 시 자동 FAIL 처리하지 말고 N1 (연장) 으로 보낸다.

### 6.3 다음 PR 후보 (회부 시점에 사용자 결정)

회부 시 다음 중 하나를 사용자가 선택:

| 옵션 | 의미 |
|---|---|
| **N1. 관찰 연장** | 데이터 부족. Phase O.2 추가 N 영업일. |
| **N2. P2 audit 작업 진입** | (`bot.py _start_bg`, `engine.run_analysis`, idle in transaction 모니터링) 인프라 보강 우선. |
| **N3. PR E2 설계 재검토** | AI hedge bias 소비 코드 진입 검토. 단 lab §5 진입 기준 (`actions.sell ≥ 30`, `boost_sell ≥ 5`) 도 별도 충족 필요. |
| **N4. 추가 전략 관찰** | multi_regime / short_swing 관찰 plan 작성. |

**리드 권장 (회부 시점에 다시 검토)**: N2 → N4 → N3 순서. PR E2 는 lab + main 양쪽 진입 기준 모두 충족 후.

---

## 7. 본 plan 의 변경 / 폐기

- 본 plan 은 활성 문서. 사용자 결정 변경 시 같은 PR / 같은 세션에서 갱신.
- §2 전략 선택이 바뀌면 §3 기간 / §6 조건 매핑도 함께 갱신.
- Phase O.1 / O.2 종료 시 평가 결과를 본 문서에 append (별도 결과 문서 분리하지 않음).
- 본 plan 폐기 조건: 사용자 명시 (예: 자동매매 자체 보류 결정) + 메모리 / 세션 로그에 결정 기록.

---

## 8. 미해결 / 사용자 결정 필요 항목

| # | 항목 | 본 문서 가정 | 결정 필요 |
|---|---|---|---|
| 1 | §2.2 전략 옵션 | A (cross_momentum 만) | A / B / C |
| 2 | §2.2 cross_momentum 모드 | weekly | weekly / monthly |
| 3 | §3 관찰 기간 | Phase O.1=5d, O.2=10d, 합산 15d | 조정 가능 |
| 4 | §3.3 시작일 (T+0) | — | 사용자 명시 필요 |
| 5 | §4.4 lab daily pipeline 병행 여부 | 병행 (단 연결 안 함) | 병행 / 중단 |
| 6 | §5.1 ~ §5.3 kill criteria 임계 | 본 문서 추천값 | 조정 가능 |
| 7 | §6.2 N1~N4 우선순위 | 회부 시점에 결정 | — |
| 8 | live_trader 실행 위치 (docker / host / tmux) | — | 결정 필요 |

**본 문서 승인은 관찰 계획의 "방향" 승인일 뿐이며, §8 의 8 개 항목은 가동 전 별도 체크리스트로 명시 확정해야 한다.** 8 개 항목 모두 결정된 별도 체크리스트가 본 문서에 append 되기 전까지는 실제 모의 live_trader 가동 금지.

---

## 9. 실행 절차

> 본 §9 는 §8 체크리스트 확정 + 본 문서 정식 머지 후에만 실제로 사용. 명령 / SQL / 템플릿은 실제 코드 (`scripts/live_trader.py`, `src/trading/kill_switch.py`) 기준으로 작성됐으나, 실제 가동 전 사용자와 함께 한 줄씩 점검 + 환경 (호스트 / docker / tmux 등) 에 맞춰 보정 필요.
>
> **v0.3**: §9.3 kill / rollback 명령을 실제 코드 (`KILL_SWITCH_FILE`=`data/.kill_switch` / `PID_FILE`=`data/.trader.pid` / `KillSwitch.soft_stop/hard_stop/resume(user_id)`) 기준으로 재작성. 검증 안 된 `set_status(...)` one-liner 제거. rollback 은 자동 복구가 아닌 사용자 명시 OK 후 안전장치 해제로 정의.

### 9.1 Preflight checklist (가동 직전 사용자 + Claude 공동 점검)

| # | 항목 | 확인 방법 (예시) |
|---|---|---|
| 1 | `is_mock_trading=True` 기본값 살아 있음 | `grep "is_mock_trading" src/config/settings.py` |
| 2 | env `KIWOOM_IS_MOCK` 가 `false` 로 설정돼 있지 않음 | `env \| grep KIWOOM_IS_MOCK` |
| 3 | **DB `strategy_runtime` 이 활성 전략의 source of truth** (design-025, `src/config/active_strategy.py:45-74`). §8 결정값과 일치하는 전략만 `enabled=true`, 나머지 `enabled=false`. | `SELECT strategy, enabled, budget_pct, max_order_amount, max_daily_orders FROM strategy_runtime` |
| 4 | env `ACTIVE_STRATEGY` 가 DB `strategy_runtime` 결정과 **충돌 없음** (legacy fallback). 미설정 OK. 설정돼 있으면 §3 enabled 전략 식별자 중 하나 또는 enabled 1개일 때 그 값과 동일해야 함. | `env \| grep ACTIVE_STRATEGY` + §3 결과 대조 |
| 5 | balance API 200 + p95 < 2s | curl + `time` |
| 6 | `pg_stat_activity` idle in transaction = 0 | §9.4 SQL |
| 7 | `data/.kill_switch` 파일이 **없음** (live_trader 신규 매수 차단 신호 없음) + `data/.kill_switch_state.json` 의 모든 user-level 상태가 NORMAL (또는 없음) | `ls -l data/.kill_switch data/.kill_switch_state.json` + `cat data/.kill_switch_state.json` (있으면) |
| 8 | `llm_decisions` baseline applied count 캡쳐 (관찰 시작 시점 delta 기준선) | §9.4 SQL |
| 9 | 본 plan §8 체크리스트 8 항목 모두 결정 완료 + append 됨 | 본 문서 grep |
| 10 | backend / postgres 컨테이너 healthy + last restart 시각 기록 | `docker ps` |

10 항목 모두 PASS 가 아니면 가동 금지.

### 9.2 Start command (초안)

> 실제 명령은 §8 결정 (실행 위치 = docker / host / tmux) 에 따라 사용자와 함께 보정.

```bash
# 예시 — host 직접 실행 (tmux session 권장)
# 사전:
#   1) .env 파일에 KIWOOM_MOCK_* / DATABASE_URL 설정 (필수).
#   2) DB strategy_runtime 에 §8 결정값 적용 (활성 전략 source of truth, design-025).
#      예: UPDATE strategy_runtime SET enabled=true WHERE strategy='cross_momentum';
#          UPDATE strategy_runtime SET enabled=false WHERE strategy IN ('multi_regime','short_swing');
#   3) env ACTIVE_STRATEGY 는 legacy fallback. 설정해도 무방하나 DB 결정과
#      충돌하면 안 됨 (§9.1 preflight #4 에서 검증).

tmux new -s live_trader_mock
cd /Users/sanghyuklee/individual/stock/kiwoom-autotrade
uv run python scripts/live_trader.py --auto 2>&1 | tee -a logs/live_trader_mock_$(date +%Y%m%d).log
# Ctrl-B D 로 detach
```

부팅 직후 로그에 다음 명시 출력 확인:
- `is_mock=True` 또는 동일 의미 라인
- DB `strategy_runtime` 의 enabled 전략과 라이브 세션이 가동하는 전략 일치
- 토큰 발급 1 회 (이후 5 분 전 갱신만)

### 9.3 Stop / rollback / kill switch command (실제 코드 기준)

> **중요**: 본 절 명령은 `scripts/live_trader.py` + `src/trading/kill_switch.py` 의 **실제 코드 기준**.
>
> - `scripts/live_trader.py:139` — `KILL_SWITCH_FILE = _PROJECT_ROOT / "data" / ".kill_switch"` (확장자 없음). live_trader 가 매 사이클 `check_web_kill_switch()` 로 이 파일 존재 여부만 확인 → 존재 시 "신규 매수 차단 + 보유분 청산 후 종료" 진입.
> - `scripts/live_trader.py:140` — `PID_FILE = _PROJECT_ROOT / "data" / ".trader.pid"` 가 현재 라이브 프로세스 PID 보관.
> - `src/trading/kill_switch.py` — `KillSwitch` 클래스의 메서드는 `soft_stop(user_id)` / `hard_stop(user_id, confirm=True)` / `resume(user_id)` / `get_status(user_id)`. **`set_status` 함수는 존재하지 않는다**. 모든 메서드가 `user_id: uuid.UUID` 인자 필수.
> - live_trader 는 부팅 시 자기 세션 UUID (`_TRADER_USER_ID = uuid.uuid4()`, line 92) 를 생성. 외부 스크립트에서 user-level `KillSwitch` API 를 호출해도 **그 UUID 를 모르면 라이브 세션에 영향을 못 준다**. → 외부 긴급 중단은 파일 + PID 기준이 권장 경로.

#### 일반 정지 (재시작 가능)

```bash
tmux attach -t live_trader_mock
# Ctrl-C 로 graceful stop (live_trader 가 보유분 청산 + 정리 후 종료)
```

#### 긴급 중단 — 외부에서 라이브 세션 차단 (권장)

```bash
# 1. 신규 매수 차단 신호 — kill_switch 파일 생성
#    live_trader 가 다음 사이클에서 감지하면 "신규 매수 차단 + 보유분 청산 후 종료" 진입
touch data/.kill_switch

# 2. 라이브 PID 확인
ls -l data/.trader.pid data/.kill_switch
LIVE_PID=$(cat data/.trader.pid 2>/dev/null)
echo "live_trader PID: $LIVE_PID"

# 3. 일정 시간 (예: 1~2 사이클) 기다린 뒤 정상 종료되지 않으면 PID 종료
#    PID 가 없으면 pkill fallback (다른 동명 프로세스가 없는지 ps 로 확인 후)
ps aux | grep -E "scripts/live_trader\.py" | grep -v grep
# 위에서 단일 프로세스 확인되면:
kill "$LIVE_PID"           # PID 있을 때
# 또는:
# pkill -f "scripts/live_trader.py"   # PID 없거나 stale 일 때만, 동명 프로세스 0 확인 후

# 4. 종료 확인
ps aux | grep -E "scripts/live_trader\.py" | grep -v grep
ls -l data/.kill_switch data/.trader.pid
```

#### user-level `KillSwitch` API 를 외부에서 호출하려면 (선택)

`KillSwitch.soft_stop / hard_stop / resume` 은 **라이브 세션의 `_TRADER_USER_ID` 와 같은 UUID** 로 호출돼야 의미가 있다. live_trader 가 그 UUID 를 어딘가에 노출하지 않는다면 외부 호출은 라이브 세션과 분리된 상태만 변경한다 (영향 없음).

따라서 외부에서 user-level API 사용은 권장하지 않는다. 필요 시:

1. 라이브 세션 UUID 확보 절차를 먼저 설계 (현재 미정 — 코드 변경 필요할 수 있음, 본 plan 범위 밖).
2. UUID 가 확보된 경우에만 Python REPL 에서:
   ```python
   import uuid
   from src.trading.kill_switch import kill_switch
   live_uuid = uuid.UUID("<라이브 세션 UUID>")
   # 신규 매수 중단
   kill_switch.soft_stop(live_uuid)
   # 또는 전량 청산 (위험 — 사용자 명시 OK 후에만)
   kill_switch.hard_stop(live_uuid, confirm=True)
   ```

#### rollback (관찰 폐기) — 자동 복구 아님

**원칙**: rollback 은 "안전장치를 자동으로 풀고 재가동" 이 아니라 **"관찰 자체를 폐기 + 원인 분석 + 사용자 명시 OK 후에만 안전장치 해제"** 로 정의.

순서:

1. 라이브 세션이 완전히 종료된 것 확인 (`ps aux | grep live_trader` 결과 없음).
2. 본 plan §10 결과 섹션에 중단 사유 / 시각 / 증거 (로그 / SQL 결과 / pg_stat_activity 스냅샷) 를 append.
3. 사용자 보고 + 원인 분석 결과 공유.
4. **사용자가 명시적으로 "다시 가동해도 좋다" / "안전장치 풀어도 좋다" 를 OK 한 경우에만** 다음 명령:
   ```bash
   # kill_switch 파일 제거 (사용자 OK 후)
   rm -f data/.kill_switch
   # PID 파일 stale 정리 (사용자 OK 후, 라이브 프로세스 종료 확인된 경우만)
   rm -f data/.trader.pid
   ```
5. user-level `KillSwitch` 상태가 `HARD_STOPPED` / `SOFT_STOPPED` 인 경우 `kill_switch.resume(live_uuid)` 도 위와 동일하게 사용자 OK 후에만.

자동 복구 / 일괄 rollback 스크립트는 만들지 않는다 (원인 분석 전 복구는 본 plan 의 가장 큰 안티패턴).

### 9.4 Daily check SQL (영업일 종료 후 실행 — KST 명시)

> **timezone 주의**: 한국장 영업일 기준 보고를 위해 모든 시각 비교는 KST (`+09:00`) 로 명시. DB session timezone 에 의존하지 않는다.
>
> **사용법**: 아래 SQL 의 `YYYY-MM-DD` 자리 (예시값 `2026-06-04`) 는 **매 영업일 실행 시 수동으로 치환**한다. psql 변수 (`\set obs_date ...` + `:obs_date`) 는 `TIMESTAMPTZ` 리터럴과 섞일 때 따옴표 처리 실수 가능성이 있어 본 plan 에서는 사용하지 않는다. 변수화가 필요해지면 application layer 의 안전한 파라미터 바인딩으로 별도 wrapper 작성 (본 plan 범위 밖).

```sql
-- 관찰 대상 영업일 범위 (KST). 아래 '2026-06-04' 는 매 영업일 수동 치환.

-- A. 인프라 — idle in transaction (관찰 시점 스냅샷. 영업일 범위 무관)
SELECT count(*) AS idle_in_tx, max(now() - xact_start) AS max_xact_age
FROM pg_stat_activity
WHERE state = 'idle in transaction';

-- B. 인프라 — broker_credentials row lock (관찰 시점 스냅샷)
SELECT pid, mode, granted, now() - query_start AS age, query
FROM pg_locks l JOIN pg_stat_activity a USING(pid)
WHERE relation = 'broker_credentials'::regclass;

-- C. 주문 — 일일 발생/상태 분포 (KST 범위)
SELECT side, status, count(*) AS n
FROM orders
WHERE submitted_at >= TIMESTAMPTZ '2026-06-04 00:00:00+09'
  AND submitted_at <  TIMESTAMPTZ '2026-06-04 00:00:00+09' + INTERVAL '1 day'
  AND is_mock = true
GROUP BY side, status
ORDER BY side, status;

-- D. trade_logs — no-order reason 분포 (KST 범위, 주문 0 일에도 cycle 실행 증거)
SELECT event_type, count(*) AS n
FROM trade_logs
WHERE created_at >= TIMESTAMPTZ '2026-06-04 00:00:00+09'
  AND created_at <  TIMESTAMPTZ '2026-06-04 00:00:00+09' + INTERVAL '1 day'
  AND is_mock = true
GROUP BY event_type
ORDER BY event_type;

-- E. llm_decisions — applied delta + source 별 (KST 범위)
--    baseline 은 §9.1 preflight 시 별도 캡쳐. 본 query 는 영업일 delta.
SELECT context_source, count(*) AS n
FROM llm_decisions
WHERE applied_at >= TIMESTAMPTZ '2026-06-04 00:00:00+09'
  AND applied_at <  TIMESTAMPTZ '2026-06-04 00:00:00+09' + INTERVAL '1 day'
GROUP BY context_source
ORDER BY context_source;

-- F. broker_order_no 누락 비율 (KST 범위)
SELECT side,
       count(*) AS total,
       sum(CASE WHEN broker_order_no IS NULL THEN 1 ELSE 0 END) AS no_broker_no,
       round(100.0 * sum(CASE WHEN broker_order_no IS NULL THEN 1 ELSE 0 END) / NULLIF(count(*),0), 2) AS pct_null
FROM orders
WHERE submitted_at >= TIMESTAMPTZ '2026-06-04 00:00:00+09'
  AND submitted_at <  TIMESTAMPTZ '2026-06-04 00:00:00+09' + INTERVAL '1 day'
  AND is_mock = true
GROUP BY side;
```

위 query 의 `'2026-06-04'` 는 매 영업일 실제 날짜로 치환. psql 변수화 (`\set obs_date 2026-06-04` + `:obs_date` 참조) 또는 application layer 에서 안전한 파라미터 바인딩 사용.

### 9.5 Daily report template (영업일 종료 후 append)

```markdown
## YYYY-MM-DD 영업일 보고

### 인프라
- backend container unexpected restart: <count>, planned restart/rebuild: <count + 사유>
- idle in transaction max age: <초>
- balance API p95: <초>
- broker_credentials row lock > 5s: <횟수>
- token 재발급 횟수: <count>

### live_trader 활동
- cycle 실행 횟수: <count> (예정 <count>)
- 후보 평가 로그 발생: yes/no
- 주문 발생: buy <n> / sell <n>
- 주문 0 인 경우 no-order reason 분포: {signal_below_threshold: n, gate_blocked: n, ...}

### llm_decisions applied delta
- baseline: <count>
- 오늘: <count>
- source 별 delta: {ai_hedge: 0 ← 필수, overnight: n, manual: n, ...}

### 비-P0 이벤트 (§5.5)
- planned restart: <시각, 사유>
- balance 5xx (degraded): <발생 횟수, upstream / 내부 분류>
- 기타 INFO: <목록>

### 결정
- Phase O.1 통과 진행: <on track / blocked>
- 다음 영업일 액션: <continue / pause / escalate>

### 비고
- <자유 기술>
```

### 9.6 가동 중 1 회 / 영업일 종료 시 1 회 — 사용자 확인 트리거

다음 중 하나 발생 시 즉시 사용자 보고:
- §5.1 ~ §5.3 P0 위반
- §5.5 degraded 1 영업일 누적 ≥ 5 회
- daily report 의 "결정" 이 `pause` 또는 `escalate`
- Phase O.1 / O.2 종료일 도달

---

## 10. 관찰 결과 (가동 시작 후 append)

> 본 §10 은 §9.5 daily report 를 시간순으로 append 하는 영역. 가동 시작 전까지 비워둠.

---

## 11. 다음 작업자 진입점

- 본 문서 §8 미해결 항목
- `docs/ai-hedge/PR_E_DESIGN.md` (PR E2 진입 조건)
- `ai-hedge-fund-lab/docs/07_OBSERVATION_PIPELINE.md` §5 정량 기준
- `docs/audit/2026-06-01-async-transaction-audit.md`
- `src/config/active_strategy.py` — 전략 토글
- `src/trading/drawdown_guard.py` / `src/trading/kill_switch.py` — 안전 게이트
- `scripts/live_trader.py` — 단일 진입점
