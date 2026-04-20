---
name: design-010-llm-decision-integration
description: LLMDecision(approved) → live_trader 반영 통합 설계
type: design
status: 활성 (PR 1/2/3 완료 — strategy_param_hint 반영까지 머지)
created: 2026-04-20
related:
  - design-008-llm-db-context
  - src/models/llm_decision.py
  - src/api/v1/decisions.py
  - src/trading/market_context.py
  - scripts/live_trader.py
---

# Design 010: LLMDecision approved → live_trader 반영

> T2-D. Airflow overnight DAG이 생성한 LLM 판단 중 사용자가 승인(`approved`)한
> 결정을 live_trader 매매 루프에 안전하게 주입한다.

## 1. 배경

- `src/models/llm_decision.py` / `src/api/v1/decisions.py`에 LLM 결정 저장과
  승인/거부 워크플로가 이미 구현되어 있다.
- Airflow overnight/premarket/postmarket DAG이 `llm_decisions` 테이블에
  `status=pending`으로 결정을 기록한다.
- 그러나 `scripts/live_trader.py`는 이 테이블을 한 번도 조회하지 않기 때문에
  **LLM 판단이 실매매에 반영되는 비율이 0%**이다.
- 동시에 LLM 결정을 자동 적용하는 것은 리스크가 크므로, **승인된 결정만 소비**
  하고, **feature flag로 쉽게 롤백 가능**한 구조가 필요하다.

## 2. 목표 / 비목표

### 목표
- approved 상태의 LLM 결정을 live_trader가 주기적으로 읽는다.
- 사용자 DB(strategy_config) 설정이 LLM 제안을 덮어쓴다(사용자 우선).
- feature flag(`USE_LLM_DECISIONS`)로 반영 여부를 전환할 수 있다.
- DB 장애 시에도 기존 live_trader 동작을 유지한다(graceful).
- 각 기능은 독립 PR로 배포하여 plain revert로 롤백 가능하다.

### 비목표
- 승인 워크플로 자체 변경(기존 API 유지).
- `pending` 결정 자동 적용(사람 승인 필수).
- Airflow DAG 쪽 decision 생성 로직 변경.

## 3. 소비할 `decision_type`

`LLMDecision.decision_type` 값 중 live_trader가 이해할 수 있는 것만 소비한다.
현재 모델 주석에는 `weight_adjust`, `risk_mode`, `param_tune`, `stock_swap`이
예시로 적혀 있으나, 본 통합에서는 다음 3종을 **소비 타입**으로 정의한다.

| decision_type | 설명 | 적용 지점 | PR |
|---|---|---|---|
| `universe_adjust` | 특정 종목 제외 또는 (향후) 추가 제안 | 루프 시작 시 `symbols` 필터링 | PR 2 |
| `symbol_bias` | 특정 종목 매수 가산/차단 (예: 악재 뉴스) | 시그널 발생 시 매수 차단/완화 | PR 2 |
| `strategy_param_hint` | 전략 파라미터 조정 힌트 | PR 2는 로그만, PR 3에서 실제 반영 | PR 2/3 |

`content` JSON 스키마 (소비자 기준, Airflow 쪽은 이미 생성 중):

```jsonc
// universe_adjust
{
  "exclude": ["005930", "000660"],   // 제외할 종목
  "reason": "악재 뉴스",               // 로그용
  "confidence": 0.85                 // 선택
}

// symbol_bias
{
  "symbol": "005930",
  "bias": "block_buy" | "boost_buy" | "block_sell",
  "reason": "...",
  "expires_at": "2026-04-21T09:00:00+09:00"  // 선택
}

// strategy_param_hint
{
  "strategy": "momentum" | "mean_reversion" | "global",
  "params": {"max_positions": 2, "volume_ratio": 1.5},
  "reason": "..."
}
```

인식 불가능한 decision_type은 **무시**하고 WARN 로그만 남긴다.

## 4. 소비 조건

- `status = 'approved'` 만 읽는다. `pending` / `rejected` / `applied` 무시.
- `created_at >= NOW() - interval N hours` (기본 24h). 만료된 승인은
  실수로 다시 반영되지 않도록 시간창 제한.
- `applied_at`은 이번 통합에서는 **갱신하지 않는다** (Idempotent 유지).
  재시작 시 같은 approved 결정을 다시 로드한다.

## 5. 로드 주기

- live_trader 시작 시 1회 (MarketContext와 함께 Layer 0).
- 장중 **1시간마다** 재조회 (MarketContext TTL 30분보다 크게 잡아 과도한 쿼리 방지).
- DB 쿼리 timeout 2초. 실패 시 이전 캐시 유지(= graceful).
- database_url이 비어 있으면 no-op.

## 6. 우선순위

```
사용자 DB 설정(strategy_config) > LLM approved decision > 코드 기본값
```

- PR 2에서 `universe_adjust.exclude`는 사용자 symbols 선택과 교집합만 제거하므로
  사용자 의도를 침해하지 않는다.
- PR 3에서 `strategy_param_hint`는 **사용자 DB에 값이 없을 때만** 덮어쓴다.
  사용자가 DB에 명시한 키는 절대 override 하지 않는다.

## 7. feature flag

- `Settings.use_llm_decisions: bool = False` (env: `USE_LLM_DECISIONS`).
- PR 1에서는 설정값만 도입(사용처 없음). PR 2에서 실제 게이트로 사용.
- off 상태에서는 loader가 실행되어도 **로그만** 남기고 `symbols` / 매매 흐름은
  변경하지 않는다. 관측 모드(shadow).

## 8. PR 구조

| PR | 브랜치 | 내용 | 동작 변경 |
|---|---|---|---|
| 1 | `feat/llm-decision-loader` | 본 설계 문서 + `src/trading/llm_decision_loader.py` + 테스트 | 없음 |
| 2 | `feat/llm-decision-integration` | live_trader에 loader 호출 + `USE_LLM_DECISIONS` 게이트 + universe_adjust/symbol_bias 반영 | flag on 시 있음 |
| 3 | `feat/llm-param-hint-apply` (선택) | `strategy_param_hint` 일시 override (whitelist + 사용자값 존중) | flag on 시 있음 |

## 9. 안전장치

- DB 쿼리 timeout 2초, 실패는 graceful (기존 동작 유지).
- whitelist: `strategy_param_hint` override 대상 키는 코드 상수로 제한
  (예: `max_positions`, `volume_ratio`, `atr_stop_mult`, `atr_tp_mult`).
- feature flag 기본 off — 실거래 안전성 최우선.
- 각 PR 독립, plain revert로 롤백.

## 10. 롤백 절차

1. GitHub에서 해당 PR의 머지 커밋을 `revert`한다 (`gh pr revert`
   또는 `git revert -m 1 <merge SHA>`).
2. PR 2/3 revert 후에도 PR 1 loader는 남아 있으나 **사용처가 없어** 무해.
3. 긴급 차단이 필요하면 `.env`에 `USE_LLM_DECISIONS=false` 설정 후
   live_trader 재시작. 코드 revert 불필요.

## 11. 테스트 전략

- PR 1: loader 단위 테스트
  - 빈 결과 / 여러 decision_type 혼합 / DB 타임아웃 / database_url 없음.
  - SQLAlchemy async session을 mock, 스키마 레벨에서 검증.
- PR 2: live_trader 통합 테스트
  - flag off 시 symbols 불변 확인.
  - flag on + universe_adjust.exclude → symbols 필터 확인.
  - flag on + DB 실패 → 기존 symbols 유지 (graceful).
- PR 3: param override 테스트
  - 사용자 DB 값이 있으면 override 되지 않음.
  - whitelist 외 키는 무시.
