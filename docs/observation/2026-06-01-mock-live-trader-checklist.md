# §8 가동 전 체크리스트 (v0.4)

> **상태**: 사용자 가동 기본안 8 항목 입력 완료 (§11.1, 2026-06-01 KST). 시작일 (§4) 과 환경 점검 (8a~8e) 은 가동 직전 명시 (§11.2 deferred). **본 입력은 가동 기본안 (provisional decision) 의 기록일 뿐이며, 실제 가동 승인은 §11.2 deferred 명시 + 사용자 별도 OK 후에만**.
>
> **변경 이력**:
> - v0.1 (2026-06-01) — 초안.
> - v0.2 (2026-06-01) — 사용자 P1 지적 반영. §1 권장값을 `ACTIVE_STRATEGY` 기반에서 DB `strategy_runtime.enabled` 기반으로 변경 (design-025 source of truth 일치). §8a 에서 `ACTIVE_STRATEGY` 를 필수 → legacy fallback 으로 강등. 기준 문서 §9.1 / §9.2 도 같은 PR 에서 동기.
> - v0.3 (2026-06-01) — 사용자 §11.1 가동 기본안 8 항목 입력. §11.2 deferred (T+0 구체 날짜 + 8a~8e 환경 점검) 명시. 기준 plan §8.2 표 동기 append.
> - v0.4 (2026-06-01) — 표현 정정 (사용자 지적): "결정값 확정" 어휘를 "가동 기본안 / provisional decision" 으로 통일. T+0 deferred + 8a~8e deferred 상태에서 "확정" 표현은 가동 승인으로 오해될 수 있음.
>
> **기준 문서**: `docs/observation/2026-06-01-mock-live-trader-observation-plan.md` (v0.4, 머지 완료 — PR #503/#504)
>
> **목적**: 기준 문서 §8 의 8 개 미해결 항목 각각에 대해 **선택지 / 권장값 / 대안 / 리스크** 만 정리. 실제 가동 결정은 본 체크리스트에 사용자가 결정값을 채워 OK 한 뒤에만.
>
> **금지**: 본 문서 작성/리뷰 동안 코드 수정 / live_trader 실행 / PR E2 진입 / threshold·bias·전략 로직 변경 / P2 audit 코드 작업.
>
> **작성일**: 2026-06-01

---

## 사용법

1. 사용자가 항목별 "결정값" 컬럼을 채운다 (권장값 채택 또는 대안 선택 또는 별도값).
2. 사용자가 본 문서 전체에 명시 OK.
3. OK 된 결정값을 기준 문서 §8 표에 append + Phase O.1 시작 절차 (§9.1 preflight) 진행.
4. 8 항목 모두 결정 전에는 가동 금지.

---

## 1. 전략 옵션 (기준 문서 §2.2)

| 항목 | 값 |
|---|---|
| 권장값 | **A** — DB `strategy_runtime` 에서 `cross_momentum.enabled=true`, `multi_regime.enabled=false`, `short_swing.enabled=false` |
| 대안 | B — `multi_regime.enabled=true` 만 / C — `cross_momentum.enabled=true` + `multi_regime.enabled=true` 둘 다 |
| 결정값 (사용자) | TBD |

> **활성 전략 source of truth 주의**: design-025 이후 활성 전략은 **DB `strategy_runtime` 테이블** 이 source of truth (`src/config/active_strategy.py:45-74` `is_strategy_enabled_db()`, `src/models/strategy_runtime.py`). env `ACTIVE_STRATEGY` 는 **deprecated / UI status 호환 / fallback only** (`src/config/active_strategy.py:32-42` `get_active_strategy()` 주석). 신규 관찰 계획은 DB 기준으로 결정하고, `ACTIVE_STRATEGY` 는 존재 시 DB 결정값과 충돌하지 않는지 보조 점검만 한다 (§8a 참조).

### 권장 이유

- 본 세션의 audit P1 #1 (token_store isolated) / #2 (gate session async with) fix 가 직접 작동하는 경로. 인프라 안정성 검증과 코드 변경 검증이 함께 이루어진다.
- 신호량이 weekly / monthly 빈도라 관찰 모니터링 부담이 작다.

### 리스크 / 트레이드오프

| 옵션 | 리스크 |
|---|---|
| A (cross_momentum 만) | 신호량 적어 §6.2 D.1 (매수/매도 ≥ 5) 충족까지 N1 관찰 연장 가능성 ↑. multi_regime / short_swing 안정성은 검증 안 됨. |
| B (multi_regime 만) | 60 초 폴링 자체의 인프라 부담. P1 fix 경로 (cross_momentum) 가 라이브에서 검증되지 않음. |
| C (둘 다) | 동일 종목 양 전략 신호 충돌 가능. 관찰 / 로컬 검증 부담 ↑. 어느 전략의 결정인지 trade_logs 분류가 명확해야 함. |

### 결정 필요 여부

**필수** — 결정 없으면 §1 절차 진행 불가.

---

## 2. cross_momentum 모드 (기준 문서 §2.2)

| 항목 | 값 |
|---|---|
| 권장값 | **weekly** — `strategy_config` 의 `cross_momentum.rebalance_freq='weekly'` |
| 대안 | monthly |
| 결정값 (사용자) | TBD |

> 본 항목은 §1 결정이 A 또는 C 인 경우에만 의미. B 단독이면 N/A.

### 권장 이유

- 15 영업일 (Phase O.1 5d + O.2 10d) 안에 weekly 리밸런스 사이클이 약 3 회 관측 가능.
- monthly 는 15 영업일 안에 0~1 회 사이클 → 데이터 충분성 (D.1) 미달 거의 확정.

### 리스크 / 트레이드오프

| 옵션 | 리스크 |
|---|---|
| weekly | lab 측 §5 진입 기준 (`actions.sell ≥ 30`) 은 daily proposal 기준이라 weekly 실 매도와 연결 어려움. weekly 매수+매도는 매주 금요일 한 시점에 몰림 → 그날 인프라 부담 ↑. |
| monthly | 관찰 데이터 부족. 사실상 인프라 안정성 (§5.1) 만 측정 가능. 전략 신호 관찰 (§4.3) 은 거의 빈 결과. |

### 결정 필요 여부

**필수 (§1 = A 또는 C 인 경우)** — 결정 없으면 `strategy_config` 키 미정의 상태로 가동되어 의도와 다른 모드로 돌 위험.

---

## 3. 관찰 기간 (기준 문서 §3)

| 항목 | 값 |
|---|---|
| 권장값 | **Phase O.1 = 5 영업일, O.2 = 10 영업일, 합산 15 영업일** |
| 대안 | 짧게 (O.1 3 + O.2 7 = 10d) / 길게 (O.1 10 + O.2 15 = 25d) |
| 결정값 (사용자) | TBD |

### 권장 이유

- O.1 5 영업일 = 1 주 무중단 가동 = 인프라 P0 미발생 최소 입증 기간.
- O.2 10 영업일 = 추가 2 주 = weekly 사이클 2 회 + monthly 사이클 0~1 회 관측 가능 폭.
- 합산 15 영업일 = 약 3 주. 작업 환경 변화 / 다른 PR 진행 / 시장 이벤트 (FOMC, 만기 등) 영향 받기 전에 종료 가능한 길이.

### 리스크 / 트레이드오프

| 옵션 | 리스크 |
|---|---|
| 권장값 (15d) | weekly 사이클 3 회만으로 §6.2 D.1 (매수/매도 ≥ 5) 충족 어려울 수 있음 → N1 연장 회부 가능성 보통 ↑. |
| 짧게 (10d) | 인프라 P0 (5 분 idle in transaction / lock 등) 가 1 주 안에 안 보일 가능성. 데이터 충분성 거의 미달. |
| 길게 (25d) | 시장 / 작업 환경 변화 가능. 다른 PR (P2 audit, AI hedge 등) 와 충돌. |

### 결정 필요 여부

**필수** — 결정 없으면 §3.3 일정표 작성 불가, 종료일 알 수 없음.

---

## 4. 시작일 T+0 (기준 문서 §3.3)

| 항목 | 값 |
|---|---|
| 권장값 | **사용자가 본 체크리스트 OK 한 영업일의 다음 영업일 (단, 시장 이벤트 회피)** |
| 대안 | 즉시 / 다음 주 월요일 / 특정 날짜 |
| 결정값 (사용자) | TBD (예: `2026-06-04` 목요일) |

### 권장 이유

- 체크리스트 OK 직후 가동하면 §9.1 preflight 점검 시간 부족.
- 다음 영업일 시작 → 당일 시장 개장 전 preflight 가능.
- 월요일 시작 추천 — 한 주 단위 사이클 관찰 + 주말 동안 환경 안정화.

### 회피 권장 시점

| 회피 사유 | 일정 |
|---|---|
| 주요 시장 이벤트 | FOMC, 옵션 만기, 월말 / 분기말, 한국 공휴일 직전 |
| 작업 환경 변화 | 본 repo 의 다른 코드 PR 머지 직후 24h 내 |
| weekly 리밸런스 직전 | cross_momentum weekly 모드에서 시작 당일이 리밸런스 trigger 일이면 사이클 부분 관측만 가능 → 다음 영업일로 미루는 것이 안전 |

### 리스크 / 트레이드오프

| 옵션 | 리스크 |
|---|---|
| 다음 영업일 (권장) | 위 회피 사유와 충돌하지 않는 날짜만 OK. 사용자가 직접 확인 필요. |
| 즉시 | preflight 충분 시간 없음 — 인프라 점검 누락 위험. |
| 다음 주 월요일 | 본 plan 의 결정이 식어버릴 가능성 (사용자 의도 변경 등). 다음 주까지 P2 audit / 다른 작업이 끼어들 수 있음. |

### 결정 필요 여부

**필수 — 사용자가 구체 날짜 명시.** Claude 가 추측해서 정하지 않는다.

---

## 5. lab daily pipeline 병행 여부 (기준 문서 §4.4)

| 항목 | 값 |
|---|---|
| 권장값 | **병행 (단 본 plan 데이터와 연결하지 않음)** |
| 대안 | 병행 중단 / 병행 + 결과 통합 |
| 결정값 (사용자) | TBD |

### 권장 이유

- lab 측 `docs/07_OBSERVATION_PIPELINE.md` §5 PR E2 진입 정량 기준 (`actions.sell ≥ 30`, `boost_sell ≥ 5`) 은 lab daily proposal 누적이 있어야 측정 가능.
- 본 plan 의 모의 live_trader 와 lab proposal pipeline 은 PR E2 미진입 상태에서는 **분리된 시스템**. 연결하지 않는 것이 안전.

### 리스크 / 트레이드오프

| 옵션 | 리스크 |
|---|---|
| 병행 (권장) | lab pipeline 도 매 영업일 실행하는 손이 필요 (현재 정책 A 수동). 두 시스템 결과를 같은 영업일 보고에 적었을 때 사용자가 혼동할 가능성 → 보고 템플릿에서 명시 분리 필요. |
| 병행 중단 | lab §5 진입 데이터 누적 멈춤. 향후 PR E2 회부 시점에 lab 측 정량 근거 부족. |
| 병행 + 결과 통합 | **PR E2 진입 위험**. 본 plan 의 명시 금지 사항. 절대 채택 금지. |

### 결정 필요 여부

**필수** — 결정 없으면 lab pipeline 운용 정책이 모호.

---

## 6. kill criteria 임계값 (기준 문서 §5.1 / §5.2 / §5.3)

| 항목 | 값 |
|---|---|
| 권장값 | **본 plan §5.1 ~ §5.3 추천값 그대로 채택** |
| 대안 | 더 엄격 / 더 느슨 (개별 임계 조정) |
| 결정값 (사용자) | TBD (전체 채택 / 부분 조정) |

### 본 plan §5 추천 임계값 요약 (참고)

| 카테고리 | 임계 | 출처 |
|---|---|---|
| unexpected backend restart | > 0 | §5.1 |
| idle in transaction 5 분 이상 지속 | > 0 | §5.1 |
| balance 5xx + 내부 lock 동반 | 1 회 | §5.1 |
| broker_credentials row lock | > 30s | §5.1 |
| 토큰 폭주 재발급 | 시간당 > 3 | §5.1 |
| is_mock=False 주문 | 1 건 | §5.2 |
| ai_hedge / PR E2 origin applied delta | > 0 | §5.2 |
| kill_switch HARD_STOPPED 자동 트리거 | 1 회 | §5.2 |
| MAX_DAILY_ORDERS=200 초과 시도 | 1 회 | §5.2 |
| broker_order_no NULL 비율 | > 5% | §5.3 |
| `filled_quantity > quantity` | 1 건 | §5.3 |
| 자격 증명 / 토큰 raw 노출 | 1 건 | §5.3 |
| balance 5xx (외부 transient) 1 영업일 누적 | ≥ 5 → P0 격상 | §5.5 |

### 리스크 / 트레이드오프

| 방향 | 리스크 |
|---|---|
| 본 추천값 채택 (권장) | 검증 안 된 임계라 false alarm 가능. 첫 5 영업일 결과로 임계 재조정 후보. |
| 더 엄격 (예: idle in transaction > 1 분 / restart 0 즉시 P0) | false alarm 잦음 → 본 plan 자주 멈춤 → 관찰 데이터 부족. |
| 더 느슨 (예: idle in transaction 30 분 / 토큰 시간당 10) | leak 재발 늦게 감지. audit P1 fix 의 의미가 약해짐. |

### 결정 필요 여부

**필수** — 전체 추천 채택 vs 부분 조정 vs 전면 재정의. "본 plan 추천 그대로" 도 명시적 OK 필요.

---

## 7. 다음 단계 우선순위 (기준 문서 §6.3 N1~N4)

| 항목 | 값 |
|---|---|
| 권장값 | **회부 시점에 결정 — 본 체크리스트에서 사전 확정하지 않음** (단 리드 권장: N2 → N4 → N3) |
| 대안 | 사전에 N2 우선 명시 / 사전에 N3 (PR E2) 우선 명시 / 회부 시점 결정 |
| 결정값 (사용자) | TBD (사전 확정 / 회부 시점 결정) |

### §6.3 옵션 요약 (참고)

| 옵션 | 의미 |
|---|---|
| N1 | 관찰 연장 — 데이터 부족 시 Phase O.2 추가 N 영업일 |
| N2 | P2 audit 작업 진입 (bot.py / engine.run_analysis / idle in transaction 모니터링) — 인프라 보강 |
| N3 | PR E2 설계 재검토 — lab §5 진입 기준도 별도 충족 필요 |
| N4 | 추가 전략 관찰 — multi_regime / short_swing 관찰 plan 별도 작성 |

### 리스크 / 트레이드오프

| 방향 | 리스크 |
|---|---|
| 회부 시점 결정 (권장) | 회부 시점에 사용자와 다시 논의 필요 → 결정 지연 가능. 단 관찰 결과에 맞춰 최선 선택 가능. |
| 사전에 N2 우선 확정 | P2 audit 작업이 본 관찰 종료와 동시에 시작 가능 → 매끄러움. 단 관찰 결과가 N3 (PR E2) / N4 (추가 전략) 를 가리켜도 묶임. |
| 사전에 N3 (PR E2) 우선 확정 | **위험** — lab §5 진입 기준 미충족 상태에서 PR E2 진입 가속 위험. 권장하지 않음. |

### 결정 필요 여부

**선택** — 미결정 (회부 시점 결정) 도 명시적 결정. 미결정 채택해도 OK.

---

## 8. live_trader 실행 위치

| 항목 | 값 |
|---|---|
| 권장값 | **host + tmux** (`tmux new -s live_trader_mock` + `uv run python scripts/live_trader.py --auto`) |
| 대안 | docker container / host + nohup / host + systemd |
| 결정값 (사용자) | TBD |

### 권장 이유

- §9.3 의 긴급 중단 절차 (`touch data/.kill_switch` + `cat data/.trader.pid` + `kill <PID>`) 가 host 직접 실행 + PID 파일 추적과 가장 잘 맞음.
- tmux detach 로 세션 끊김 영향 없이 가동 유지 + 사용자가 언제든 `tmux attach` 로 라이브 로그 확인 가능.
- backend / postgres docker container 와 라이프사이클 분리 → backend 재빌드 (post-merge rebuild) 가 live_trader 세션에 영향 안 줌.

### 리스크 / 트레이드오프

| 옵션 | 장점 | 리스크 |
|---|---|---|
| **host + tmux (권장)** | PID 추적 단순. backend 재빌드와 분리. detach/attach 자유. | 호스트 재부팅 시 자동 재시작 없음 → 다음 영업일 수동 가동 필요 (관찰 기간 중 호스트 재부팅 회피 필요). `.env` 로딩 / `DATABASE_URL` / `KIWOOM_MOCK_*` env 가 tmux 세션에 정확히 전달돼야 함. |
| docker container | 환경 격리. systemd 같은 자동 재시작 정책 가능. | 컨테이너 재시작 / 재빌드 시 라이브 세션 영향. 별도 컨테이너로 분리 안 하면 backend 와 충돌. `data/.kill_switch` / `data/.trader.pid` 파일이 컨테이너 안에서 보여야 함 (볼륨 마운트 필요). |
| host + nohup | 셸 닫혀도 동작. | attach 어려움 — 라이브 로그 확인은 파일 tail 만. 디버깅 부담 ↑. |
| host + systemd | 자동 재시작. 표준 init 통합. | **unexpected restart 트리거 회피와 충돌** — systemd 가 process 죽으면 자동 재시작 → §5.1 "unexpected restart" 분류 모호. RestartPolicy 명시적 비활성화 필요. |

### 추가 환경 점검 항목 (가동 전 사용자 확인)

| # | 확인 |
|---|---|
| 8a | **`.env` 필수**: `KIWOOM_MOCK_*`, `DATABASE_URL`. **`ACTIVE_STRATEGY` 는 필수가 아니라 legacy fallback** — 존재하면 DB `strategy_runtime` 결정값과 충돌 없는지 보조 점검. 예: §1 결정이 A 이면 `ACTIVE_STRATEGY` 가 설정돼 있더라도 `cross_momentum` 또는 미설정 이어야 함. `multi_regime` 같은 충돌값이면 즉시 정정. |
| 8b | tmux / docker / nohup 중 선택한 도구가 호스트에 설치돼 있음 |
| 8c | `data/` 디렉토리 쓰기 권한 (kill_switch / trader.pid 생성 가능) |
| 8d | 호스트 시간대 = KST (또는 명시) — daily SQL KST 범위와 일치 |
| 8e | 호스트 디스크 여유 (structlog 파일 누적 — 15 영업일 분량 추정 후 확인) |

### 결정 필요 여부

**필수** — 결정 + 8a~8e 환경 점검 모두 PASS 후에야 가동 가능.

---

## 9. 본 체크리스트 OK 절차

1. 위 8 항목 각각의 "결정값 (사용자)" 컬럼에 사용자가 값 채움 (TBD → 실제값).
2. §1 결정이 B 단독이면 §2 는 N/A 명시.
3. §8 의 환경 점검 8a~8e 모두 PASS 명시.
4. 사용자가 본 문서 전체에 "OK" 명시 (예: 문서 하단 "사용자 OK 시각 / 사용자명" append).
5. 결정값을 기준 문서 `2026-06-01-mock-live-trader-observation-plan.md` §8 표에 append + 본 체크리스트 PR 로 머지.
6. 그 후에야 §9.1 preflight 진입 가능.

위 1~5 중 하나라도 누락 시 가동 금지.

---

## 10. 본 문서 lifecycle

- 본 문서는 **untracked 초안**. 사용자 OK 후에만 커밋 / PR.
- OK 후 머지 시 기준 문서 §8 도 함께 갱신 (같은 PR).
- 결정값이 가동 중 변경되면 본 문서 + 기준 문서 둘 다 같은 PR 로 동기 갱신.

---

## 11. 사용자 가동 기본안 입력 영역

> 본 §11 의 입력 = **가동 기본안 (provisional decision)** 의 문서화. 실제 가동 승인 아님. 시작일 (§11.2 항목 4) + 환경 점검 (§11.2 8a~8e) 이 가동 직전 명시 + 사용자 별도 OK 후에만 §9.1 preflight 진입.

### 11.1 가동 기본안 (2026-06-01 KST 입력)

```
항목 1 전략 옵션:          A — DB strategy_runtime 에서 cross_momentum.enabled=true,
                            multi_regime.enabled=false, short_swing.enabled=false
항목 2 cross_momentum 모드: weekly (strategy_config.cross_momentum.rebalance_freq='weekly')
항목 3 관찰 기간:           Phase O.1 = 5 영업일, Phase O.2 = 10 영업일, 합산 15 영업일
항목 4 시작일 T+0:          사용자가 여행 후 직접 확인 가능한 첫 영업일
                            (구체 날짜 미정 — §11.2 deferred 처리, 가동 직전 사용자 명시)
항목 5 lab pipeline 병행:   병행하되 live_trader 결과와 연결하지 않음
항목 6 kill 임계값:         기준 plan §5.1~§5.3 추천값 그대로 채택
항목 7 다음 단계 우선순위:   회부 시점 결정. 사전 PR E2 (N3) 확정 금지
항목 8 실행 위치:           host + tmux
환경 점검 8a~8e:           가동 직전 PASS 확인 (§11.2 deferred 처리)
```

### 11.2 가동 직전 추가 명시 필요 (deferred)

본 §11.1 입력 시점 기준으로 아래 2 항목은 의도적으로 deferred 상태. 사용자가 여행 후 가동 직전에 본 문서에 명시한 뒤 §9.1 preflight 진입.

| 항목 | deferred 사유 | 가동 직전 명시 형식 |
|---|---|---|
| 항목 4 시작일 T+0 (구체 날짜) | 사용자 여행 일정 미정 → 복귀 후 시장 / 작업 환경 확인 후 결정 (§4 회피 사유 점검: FOMC / 만기 / 월말 / weekly trigger 일 / 다른 코드 PR 직후 24h 등) | `T+0 = YYYY-MM-DD` (KST 영업일) |
| 환경 점검 8a~8e | 가동 직전 호스트 환경 직접 확인 필요 (env / 도구 설치 / 디스크 여유 / KST timezone / data/ 권한) | `8a PASS / 8b PASS / 8c PASS / 8d PASS / 8e PASS` + 점검 시각 |

### 11.3 OK 명시

| 항목 | 값 |
|---|---|
| 사용자 가동 기본안 8 항목 (§11.1) | ✅ 입력 완료 (2026-06-01 KST) — provisional |
| 가동 직전 deferred 2 건 (§11.2) | ⏸ 가동 직전 명시 대기 |
| 사용자 가동 OK 시각 | TBD (가동 직전 별도 명시) |
| 사용자명 | TBD |

**중요**: §11.1 입력 = **"가동 전 기본안 문서화"** 의미. **가동 승인 아님**. 실제 가동은 §11.2 deferred 2 건 (T+0 구체 날짜 + 8a~8e PASS) 이 가동 직전에 명시되고 사용자 가동 OK 가 별도로 표시된 뒤에만.
