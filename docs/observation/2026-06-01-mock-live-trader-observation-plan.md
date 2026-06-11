# 모의투자 live_trader 관찰 계획 (기준 문서 — v0.10)

> **상태**: 기준 문서 + §8.2 사용자 가동 기본안 (provisional decision) 입력 완료 (2026-06-01 KST). **본 plan 의 §8.2 입력 = "가동 전 기본안 문서화" 의미일 뿐, 실제 모의 live_trader 가동을 승인하는 것은 아니다.** 시작일 (§4 deferred — 사용자 여행 후 명시) + 환경 점검 (8a~8e deferred — 가동 직전 PASS) + 사용자 가동 OK 가 별도로 추가된 뒤에만 §9.1 preflight 진입. threshold 변경 / PR E2 진입 / bias 소비 로직 변경 **모두 보류 유지**.
>
> **변경 이력**:
> - v0.1 (2026-06-01 작성) — 초안.
> - v0.2 (2026-06-01 사용자 1차 리뷰 반영) — §5/§6 중단/통과 조건 정교화, §8 승인 의미 약화, §9 실행 절차 추가.
> - v0.3 (2026-06-01 사용자 2차 리뷰 반영) — §9.3 kill/rollback 명령 실제 코드 (`KILL_SWITCH_FILE` / `PID_FILE` / `KillSwitch.soft_stop/hard_stop/resume`) 기준으로 재작성, §4.2/§6.2 restart 기준 "unexpected only" 통일, §2.2 C "운영" 표현 제거, §9.4 daily SQL KST timezone 명시, §6.2 매수/매도 ≥5 → "데이터 충분성 조건 (FAIL 아닌 N1 연장)".
> - v0.4 (2026-06-01 사용자 3차 리뷰 반영) — §5.4 중단 절차도 파일 기반 (`data/.kill_switch` + `data/.trader.pid`) 으로 통일, §9.4 SQL `:obs_date` 변수화 설명 제거 + "매 영업일 `YYYY-MM-DD` 수동 치환" 으로 정리. PR #503/#504 머지.
> - v0.5 (2026-06-01 사용자 P1 지적 반영) — 활성 전략 source of truth 정정. §9.1 preflight #3/#4 를 DB `strategy_runtime` 우선 + env `ACTIVE_STRATEGY` legacy fallback 으로 재작성. §9.2 start command 사전 단계에 DB 적용 절차 명시 + ACTIVE_STRATEGY 는 legacy 명시. PR #505/#506 머지.
> - v0.6 (2026-06-01 사용자 결정값 입력) — §8.2 표 신규: A 전략 (cross_momentum 만 DB enabled) / weekly / 15 영업일 / T+0 deferred / lab 병행 (연결 X) / kill 임계 추천값 채택 / N1~N4 회부 시점 결정 / host+tmux. 체크리스트 §11 (v0.3) 와 같은 PR.
> - v0.7 (2026-06-01 사용자 표현 정정) — "결정값 확정" 어휘를 "가동 기본안 / provisional decision" 으로 통일. T+0 deferred + 8a~8e deferred 상태에서 "확정" 표현은 가동 승인으로 오해 가능. 체크리스트 (v0.4) 와 같은 PR.
> - v0.8 (2026-06-01 사용자 preflight 보고 검토 반영) — §8.2 항목 4 갱신 (T+0 기본안 = 2026-06-15 월, 산정 근거 명시). §9.1 #7 조항 명확화 — 기존 strict 문구 ("`kill_switch_state.json` 의 모든 user-level 상태가 NORMAL") 가 live_trader 구조 (`scripts/live_trader.py:92` 매 세션 새 UUID 생성) 와 맞지 않아 false alarm 유발. 새 문구 = "`data/.kill_switch` 파일 없음 + 새 live_trader 세션에 영향을 주는 kill switch 상태 없음" + admin user_id 포함 여부 별도 확인 절차 명시. **`data/.kill_switch_state.json` 파일은 삭제/초기화하지 않음** (다른 컨텍스트 — UI/API — 영향 불명확). 체크리스트 (v0.5) 와 같은 PR.
> - v0.9 (2026-06-10 사용자 지시 반영) — §11 신설: 본 관찰 (6/15~) 전 **사전 smoke run** (cross_momentum 단독, 장중 30~60분 1회). 사용자 지시 ("모의 live_trader 짧은 장중 실행 — 이건 해야 합니다. dry-run 만으로 끝내면 안 됩니다") 에 따라 §8.2 의 "가동 전 가동 금지" 범위에서 smoke run 1회를 분리. §11.2 종료 경로 안전성 코드 분석 (ADR-024 가드 — Ctrl-C `force_close_all(force_all=True)` 에서도 cross_momentum 포지션 청산 제외) 포함. 본 관찰 (§3 15영업일) 자체의 시작 조건은 변경 없음.
> - v0.10 (2026-06-11) — §10 에 2026-06-11 사전 smoke run 결과 append (**PASS with NOTE** — 60분 60사이클 무결·DB delta 0·보유 불변. #7 graceful 보존 로그는 직접 증거 없음 → DB delta 0 으로 간접 입증, NOTE 3건). §11.8 신설: **mini trigger smoke** (금 14:55 weekly trigger window 주문 lifecycle 사전 검증, 사용자 별도 go 필요). §11.4 trigger 회피 문구를 §11.8 분리 기준으로 갱신. §11.7 에 실행 결과 링크.
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

### 8.1 항목 표

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

### 8.2 사용자 가동 기본안 (2026-06-01 KST 입력, 출처: `2026-06-01-mock-live-trader-checklist.md` §11.1)

> **본 표 = 가동 기본안 (provisional decision)** 의 문서화. 가동 승인 아님.

| # | 가동 기본안 |
|---|---|
| 1 | **A** — DB `strategy_runtime` 에서 `cross_momentum.enabled=true`, `multi_regime.enabled=false`, `short_swing.enabled=false` |
| 2 | **weekly** (`strategy_config.cross_momentum.rebalance_freq='weekly'`) |
| 3 | Phase O.1 = 5 영업일, Phase O.2 = 10 영업일, 합산 **15 영업일** |
| 4 | **기본안 = 2026-06-15 (월)**. 대안 = 6-16 (화) / 6-17 (수) / 6-18 (목). 산정 근거: 2026-06-03 (수) KRX 휴장일 (지방선거) 제외, 2026-06-11 (목) 선물·옵션 동시만기 회피. 6/04~6/12 구간은 휴장 / 만기 / 만기 다음날 / 금요일 weekly trigger 가 섞여 첫 관찰 구간 부적합. ※ "가동 예정일" 아님. 사용자 최종 가동 OK 후에만 §9.1 preflight 재확인 → 가동. |
| 5 | **병행 (단 live_trader 결과와 연결 안 함)** |
| 6 | **기준 plan §5.1~§5.3 추천값 그대로 채택** |
| 7 | **회부 시점 결정. 사전 PR E2 (N3) 확정 금지** |
| 8 | **host + tmux** |
| 환경 8a~8e | 가동 직전 PASS 확인 (deferred — 체크리스트 §11.2) |

**현 상태**: §8.2 입력 완료 = **"가동 전 기본안 문서화"** 의미. **실제 가동 승인 아님**. 시작일 (§4 deferred) + 환경 점검 (8a~8e deferred) 이 가동 직전에 명시 + 사용자 가동 OK 가 별도로 표시된 뒤에만 §9.1 preflight 진입 가능.

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
| 7 | `data/.kill_switch` 파일이 **없음** (live_trader 신규 매수 차단 신호 없음) + **새 live_trader 세션에 영향을 주는 kill switch 상태 없음**. 근거: `scripts/live_trader.py:92` `_TRADER_USER_ID = uuid.uuid4()` — live_trader 가 매 세션 새 UUID 생성하므로 기존 `data/.kill_switch_state.json` 의 user-level state 와 직접 연결되지 않음. 단 admin / API caller 로 자주 쓰이는 user_id 가 `kill_switch_state.json` 에 non-normal 로 있으면 UI / API kill switch 표시에 영향 가능 → preflight 에서 admin user_id 포함 여부 별도 확인. | `ls -l data/.kill_switch` + `python3 -c "import json; d=json.load(open('data/.kill_switch_state.json')); admin='<admin_user_id>'; print('admin in state:', admin in d, d.get(admin,'(none)'))"` (admin user_id 는 `SELECT id FROM users WHERE email='admin@local.dev';` 등으로 확보) |
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

### 2026-06-11 사전 smoke run 결과 (§11) — **PASS with NOTE**

- **실행**: 13:53:46 시작 → 14:53 종료, 약 60분. cross_momentum 단독, polling 60초, host+tmux, mock.
- **§11.5 판정**:

| # | 기준 | 결과 |
|---|---|---|
| 1 | 부팅 로그 (`is_mock=True`/`ACTIVE_STRATEGY=cross_momentum`/WS 우회→polling) | ✅ |
| 2 | 토큰 발급 1회 (만료 익일 — 갱신 불필요 구간), 폭주 0 | ✅ |
| 3 | 폴링 사이클 60/60 누락 0 + `orchestrator tick 실패` 0 (`tick 완료` 매 사이클 출력 — cross_momentum handler 결과 반환) | ✅ |
| 4 | 주문 0 + cycle 증거 로그 (전략 실행/budget 산출 매 tick) | ✅ |
| 5 | idle in transaction 0 유지 | ✅ |
| 6 | unexpected 종료 | ⚠️ **외부(실행 환경) 종료 1건** — 약 60분 시점 tmux 서버째 소멸, 로그 무흔적. 60사이클 무결·에러 0 으로 live_trader 귀책 아님. 도구 샌드박스의 백그라운드 프로세스 회수로 추정 |
| 7 | graceful 종료 시 청산 0 + cross_momentum 보존 로그 | ⚠️ **직접 증거 없음** (보존 로그 미출력 — 종료 경로 미진입/미기록). **간접 입증**: 종료 후 orders Δ0 · trade_logs Δ0 · 보유 6종목 불변 → 강제청산/매도 미발생. ADR-024 경로의 직접 로그 검증은 차기 실행에서 완결 |
| 8 | 종료 후 orders delta 0 (baseline 154 → 154) | ✅ |
| 9 | kill_switch 미생성 ✅ / PID 파일 stale 잔존 → 사용자 확인 후 삭제 (§9.3 절차) | ✅ (후처리 완료) |
| 10 | 시크릿/토큰 raw 노출 0 (app_key/token 마스킹 확인) | ✅ |

- **DB**: orders_today 0 / orders_total 154 / trade_logs_total 117 / llm applied 0 / strategy_runtime 불변.
- **PR2a 검증 보너스**: 매 tick `budget = available_cash × 0.6` (= strategy_runtime budget_pct), `max_order = 50,000,000` 주입 확인.
- **NOTE (follow-up 후보, 6/15 전 코드 변경 없음)**:
  1. MarketContext VKOSPI/KOSPI/investor_flow cache fallback 경고 반복 — 루프 비치명, P2 개선 후보.
  2. 종료 로그 부재 (#6/#7) — 차기 실행에서 graceful 종료 로그 직접 확보 필요.
  3. 본 smoke 는 목요일 실행 — weekly trigger (금 14:55) 미발동. **주문 lifecycle 은 미검증** → §11.8 mini trigger smoke 로 별도 검증.

---

## 11. 사전 smoke run (본 관찰 전 1회, 장중 30~60분) — 2026-06-10 신설

> **근거**: 2026-06-10 사용자 지시 — "daily dry-run 만으로는 주문 후보/체결/루프 안정성을 확인할 수 없다. 모의 live_trader 짧은 장중 실행은 해야 한다."
> **위치**: §3 본 관찰 (6/15~, 15영업일) **이전**에 1회. 본 관찰의 시작 조건 (§8.2 + 사용자 가동 OK) 은 변경 없음 — smoke run 은 별도의 1회성 인프라 검증이다.

### 11.1 목적 / 범위

| 확인 대상 | daily regime dry-run 으로 확인 가능? | smoke run 으로 확인 |
|---|---|---|
| 실제 루프 기동/폴링 사이클 (orchestrator tick) | ❌ | ✅ |
| 토큰 발급 1회 + 5분 전 갱신만 | ❌ | ✅ |
| balance fetch (live 세션 내) | ❌ (API 단발 호출만) | ✅ |
| no-order reason 기록 (주문 0 인 날의 cycle 증거) | ❌ | ✅ |
| graceful 종료 (Ctrl-C) 시 의도치 않은 청산 0 | ❌ | ✅ |
| 전략 성과 / 체결 품질 | ❌ | ❌ (본 관찰 §6.2 영역 — smoke 범위 아님) |

- 전략 판단 아님. 현재 regime 이 risk_off (6/10 confidence 93) 이므로 **주문 0 이 정상 시나리오** — no-order reason 로그가 통과 기준이다 (§6.1 과 동일 원칙).
- 코드 변경 0. 현재 main 코드 그대로 실행.

### 11.2 종료 경로 안전성 (2026-06-10 코드 분석 — smoke 전 필독)

설계 PR 0 (`docs/design/multi-strategy-portfolio-controller.md`) 에서 "Ctrl-C → `force_close_all` 청산 위험" 을 지적했다. 현재 코드 재확인 결과:

| 경로 | 코드 | cross_momentum 영향 |
|---|---|---|
| Ctrl-C / 예외 종료 | `scripts/live_trader.py:3650-3655` → `force_close_all(force_all=True)` | **청산 제외** — ADR-024 가드 (`live_trader.py:2292-2302`) 가 `strategy == "cross_momentum"` 포지션을 `force_all=True` 여도 보존 |
| kill_switch 파일 감지 | `live_trader.py:2263-2266` → `force_close_all(force_all=True)` | 동일 가드로 보존 |
| 정상 루프 종료 (15:35) | `live_trader.py:3646` → `force_close_all(force_all=False)` | momentum 라벨만 청산 — cross_momentum 무관 |
| 장중 강제청산 시각 | `live_trader.py:1435/2643` — `pos.strategy == "momentum"` 만 | cross_momentum 무관 |

전제 조건 (smoke preflight 에서 확인):

1. **부팅 시 broker holdings 동기화가 cross_momentum 라벨 부여** — `live_trader.py:3385-3390`: `ACTIVE_STRATEGY=cross_momentum` 이면 외부 보유분 전체에 `strategy="cross_momentum"` 부여 (5/5~5/6 사고 재발 방지 코드). → 전 보유분이 보존 대상.
2. **overnight 파일 부재** — `data/overnight_positions.json` 에 swing 라벨 포지션이 복원되면 (`live_trader.py:3367-3378`) 그 포지션은 Ctrl-C 시 청산된다. 2026-06-10 현재 파일 없음 확인. smoke 직전 재확인 필수.

→ **결론**: cross_momentum 단독 + overnight 파일 부재 조건에서 Ctrl-C graceful stop 의 예상 청산 = 0. 종료 시 로그에 `"cross_momentum 포지션 N개 강제 청산 보존"` 또는 `"미청산 포지션 없음"` / `"청산 대상 없음"` 이 찍히는 것이 통과 조건.

### 11.3 Preflight (smoke 직전, §9.1 재사용)

- §9.1 의 #1~#8, #10 동일 적용 (#9 "§8 체크리스트 8항목" 은 smoke 에는 미적용 — §8.2 기본안 + 사용자 smoke go 신호로 대체).
- smoke 전용 추가:

| # | 항목 | 확인 |
|---|---|---|
| S1 | `data/overnight_positions.json` 없음 (또는 내용이 빈 리스트) | `cat data/overnight_positions.json` |
| S2 | `orders` / `trade_logs` / `llm_decisions` baseline count 캡쳐 (KST 당일) | §9.4 SQL C/D/E |
| S3 | DB `strategy_runtime`: `cross_momentum=true` 만 enabled | §9.1 #3 SQL |
| S4 | `strategy_config.cross_momentum.rebalance_freq` 확인 (weekly trigger = **금요일 14:55**, `REBALANCE_ORDER_HHMM="1455"`) | DB select |

### 11.4 실행

```bash
# §9.2 와 동일 (host + tmux)
tmux new -s live_trader_smoke
cd /Users/sanghyuklee/individual/stock/kiwoom-autotrade
uv run python scripts/live_trader.py --auto 2>&1 | tee -a logs/live_trader_smoke_$(date +%Y%m%d).log
```

- **실행 시간대 권장: 평일 오전 10:00~11:30 사이 60분** (장중, RESCREEN_TIMES 10:00/11:00 포함 — 재스크리닝 경로도 관찰됨).
- **14:55 trigger window 회피** — weekly trigger (금요일 14:55) 가 smoke 중 발동하면 모의 rebalance 주문이 발생해 6/15 본 관찰 baseline 을 오염시킨다. ~~trigger 관찰은 본 관찰 (§3) 영역.~~ → **v0.10: 주문 lifecycle 사전 검증용 mini trigger smoke 를 §11.8 로 분리** (별도 사용자 go 필요. 기본 smoke run 은 여전히 trigger 회피).
- 폴링 간격 60초 (`POLL_INTERVAL_SEC=60`) → 60분이면 ~60 사이클.
- 종료: 관찰 시간 경과 후 tmux attach → **Ctrl-C** (graceful). §11.2 의 보존 로그 확인 후 세션 종료.

### 11.5 통과 기준 (전부 충족 시 PASS)

| # | 기준 |
|---|---|
| 1 | 부팅 로그: `is_mock=True` + `ACTIVE_STRATEGY=cross_momentum` + WS 우회 → polling 진입 라인 |
| 2 | 토큰 발급 1회, 폭주 재발급 (시간당 >3회) 없음 |
| 3 | 폴링 사이클 로그 ("다음 폴링까지 N초 대기") 매 사이클 기록 (누락 0) + `orchestrator tick 실패` 로그 0. 주의: `orchestrator tick 완료` 로그는 결과 있을 때만 출력 (`live_trader.py:2255-2256`) — 미출력은 FAIL 아님 |
| 4 | 주문 0 이면 no-order reason 이 trade_logs/structlog 에 기록 |
| 5 | `idle in transaction` 0 유지 (§9.4 SQL A) |
| 6 | unexpected exception / restart 0 |
| 7 | Ctrl-C 종료 시 청산 주문 0 + cross_momentum 보존 로그 확인 (§11.2) |
| 8 | 종료 후 orders delta = 0 (baseline 대비) — 모의 주문 발생 시 사유 명시 필요 |
| 9 | `data/.trader.pid` 정리됨 + `data/.kill_switch` 미생성 |
| 10 | structlog 에 자격 증명 / 토큰 raw 값 노출 0 |

PASS → 결과를 §10 에 smoke report 로 append + 6/15 본 관찰 진입 판단 재료로 사용. FAIL → §5.4 중단 절차 + 원인 분석 + 사용자 보고 (재실행은 사용자 OK 후).

### 11.6 중단 기준

§5.1~§5.3 P0 동일 적용. 발생 시 즉시 Ctrl-C (또는 외부에서 `touch data/.kill_switch`) → §5.4 절차.

### 11.7 일정 / 승인

- 실행일·시각은 **사용자 go 신호 필요** (escalation 규칙 — live_trader 실행은 실행 직전 명시 승인).
- 권장 후보: **2026-06-11 (목) 또는 2026-06-12 (금) 오전 10:00~11:30 중 60분**. 6/11 은 선물·옵션 동시만기일이나 모의 인프라 smoke 에는 영향 제한적. 6/12 (금) 선택 시 14:55 weekly trigger 와 겹치지 않도록 오전 한정.
- **실행 결과**: 2026-06-11 13:53~14:53 완료 — §10 "2026-06-11 사전 smoke run 결과" (PASS with NOTE).

### 11.8 mini trigger smoke (weekly trigger window — 주문 lifecycle 사전 검증, 선택)

> **목적**: §11 기본 smoke (PASS with NOTE) 는 trigger 미발동이라 **주문 lifecycle (rebalance 후보 산출 → 시장가 주문 → submitted→filled → persist → reconcile) 미검증**. 6/15 본 관찰 첫 weekly trigger (6/19 금) 전에 주문 경로 결함을 발견하기 위한 1회성 선택 실행.
> **실행 조건**: 사용자 별도 go 신호 ("mini trigger smoke go") + 금요일 장중. 기본 후보 = **2026-06-12 (금) 14:30 시작 → 14:55 trigger 관찰 → 15:10 전후 graceful 종료**.

| 항목 | 내용 |
|---|---|
| 사전 인지 (trade-off) | (1) 모의 포트폴리오가 리밸런스된 상태로 6/15 본 관찰 시작 — weekly 주기의 자연 사전 사이클로 간주하고 §10 에 명시 기록. (2) 현재 regime risk_off 이나 cross_momentum 은 regime 미소비 (ranking 기반) — 모의 한정이므로 진행 가능, 실거래 아님 |
| preflight | §9.1 + §11.3 동일 + **rebalance 데이터 충분성**: universe momentum score 산정 가능 종목 수 확인 (DB daily_candles 13개월 — 부족 시 backfill 선행, `scripts/backfill_daily_candles.py`) |
| 관찰 항목 | trigger 14:55 발동 로그 / 후보 산출 (n_positions=5) / 매도→잔고 refresh→매수 4-phase / orders 상태 전이 (submitted→filled) / persist (qty·price 정확) / reconcile structlog / T+2 미적용 (모의) |
| 종료 | trigger 완료 + 주문 정산 확인 후 graceful 종료 (Ctrl-C 또는 `kill -INT $(cat data/.trader.pid)`). **§11 NOTE 2 의 종료 보존 로그 직접 확보를 이번에 완결** |
| 사후 검증 | orders/trade_logs delta = rebalance 주문분만 (사유 명시) / 보유 변경 내역 §10 기록 / llm_decisions delta 0 / idle 0 / kill_switch 미생성 |
| 통과 기준 | 주문 상태 전이 정상 (rejected/failed 0 또는 사유 식별) + persist qty·price 정확 + reconcile 로그 + 종료 보존 로그 확인 |
| 금지 유지 | 실거래 전환 / strategy_runtime 변경 / 코드 변경 / PR 2b/3 |

---

## 12. 다음 작업자 진입점

- 본 문서 §8 미해결 항목
- `docs/ai-hedge/PR_E_DESIGN.md` (PR E2 진입 조건)
- `ai-hedge-fund-lab/docs/07_OBSERVATION_PIPELINE.md` §5 정량 기준
- `docs/audit/2026-06-01-async-transaction-audit.md`
- `src/config/active_strategy.py` — 전략 토글
- `src/trading/drawdown_guard.py` / `src/trading/kill_switch.py` — 안전 게이트
- `scripts/live_trader.py` — 단일 진입점
