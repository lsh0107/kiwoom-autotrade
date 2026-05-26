# PR E 설계 — regime 신호 + bias 재설계 + live_trader 실제 소비

작성일: 2026-05-22 (개정 2026-05-26: 사용자 검토 피드백 7건 반영)
상태: **설계 검토 단계 (코드 변경 전)**
선행 PR: PR A (evaluation) / PR G (market constraints) / PR F (sizing) / PR B (portfolio context) / PR C (investor flows) / PR D (sector signal) — 모두 머지 완료.
선행 문서:
- `docs/ai-hedge/PROPOSAL_QUALITY_ROADMAP.md` (전체 PR 로드맵)
- `docs/ai-hedge/AI_HEDGE_FUND_INTEGRATION_HANDOFF.md` (수집/승인 큐 인계)

이 문서는 **PR E 가 실제 거래 결정 경계를 처음 건드리는 PR** 이므로, 다음 작업자(human 또는 다른 Claude/Codex) 가 이 문서만 읽어도 컨텍스트가 완성되도록 작성한다.

---

## 0. PR E 가 하는 일 한 줄

> AI hedge 가 만든 `boost_buy` / `review_sell` / `boost_sell` 결정을 `kiwoom-autotrade.live_trader` 가 **승인된 경우에 한해 실제로 소비**한다.

지금까지 PR (A~D) 는 모두 "ai-hedge-fund-lab 내부에서 더 좋은 제안을 만든다" 였고, kiwoom 쪽 live_trader 는 사용자가 승인한 `block_buy` 만 후보 제외에 쓰고 다른 bias 는 무시했다 (`docs/ai-hedge/AI_HEDGE_FUND_INTEGRATION_HANDOFF.md` 의 주의사항 그대로). PR E 는 이 비대칭을 메운다.

---

## 1. 현재 상태 (PR E 이전, 머지 기준)

### 1.1 ai-hedge-fund-lab — bias emit 현황

`ai-hedge-fund-lab/kr/ai-hedge-fund/src/korea_ai_hedge/exports/kiwoom_decision_export.py::_bias_for_proposal` 매핑:

| 입력 | 출력 bias |
|---|---|
| `action=hold` + `_BLOCK_BUY_FLAGS` 교집합 ≥ 1 | `block_buy` |
| `action=hold` + `HOLDING_*_REVIEW` ∧ `holding_qty>0` | `review_sell` (PR B 도입) |
| `action=buy` | `boost_buy` |
| `action=sell` | `review_sell` |
| 그 외 | (emit 안 함) |

`_BLOCK_BUY_FLAGS` 는 `risk_gate` 산 7개 + `market_constraints.BUY_BLOCKING_FLAGS` (TRADING_HALTED / MANAGEMENT_ISSUE / INVESTMENT_WARNING / UPPER_LIMIT_NEAR).

### 1.2 kiwoom-autotrade — bias 소비 현황

`src/trading/llm_decision_loader.py::apply_universe_decisions`:

- `universe_adjust.exclude` 와 `symbol_bias.bias == "block_buy"` 만 symbols 에서 제거.
- `boost_buy` / `review_sell` 은 무시 (loader 가 의도적으로 안 씀).

`scripts/live_trader.py` (대략 line 3140 ~ ):
- `load_approved_decisions_with_ids(database_url, since_hours=24)` 호출 (PR #466 이후).
- `apply_universe_decisions(symbols, ...)` 로 후보 제외.
- `extract_strategy_param_hints` + `apply_llm_param_hints` (PR #466).
- 적용된 ID 는 `determine_applied_decision_ids` 로 식별 후 `mark_decisions_applied`.

PR #461 / #466 의 안전 경계 contract:
- AI hedge proposal → pending decision → 사용자 승인 → 기존 live_trader/risk/broker.
- AI hedge 가 broker order API 를 직접 호출하지 않는다.
- ai_hedge context 는 auto_approval 대상에서 제외 (#464).
- 실제 반영된 결정만 applied 전환 (#466).

### 1.3 confidence 조정 누적 현황 (PR C/D 이후)

`risk_gate` 가 technical confidence 에 다음을 누적 ±10 씩 조정 (clamp 0~100):
- PR C — flow signal (외인+기관 정규화 상대강도)
- PR D — sector signal (벤치마크 대비 상대강도)

action 변경은 모두 PR E 에서 처음 도입.

---

## 2. PR E 가 처음 도입하는 것

1. **regime 신호**: 시장 전체 (KOSPI/KOSDAQ) 의 추세/변동성 regime 분류 (bull / bear / range).
2. **bias 재설계 매핑 표** (확정).
3. **`boost_sell` bias 신규** (현재 없음).
4. **kiwoom-autotrade loader** 가 `boost_buy` / `review_sell` / `boost_sell` 을 *어떻게* 소비할지 정의 + 구현.
5. **live_trader** 가 새 소비 로직을 호출하도록 통합.
6. **안전 게이트 추가**: AI bias 가 실제 주문에 영향을 주는 첫 PR 이므로 다층 게이트.

---

## 3. 데이터 모델 변경

### 3.1 ai-hedge-fund-lab 측

새 데이터:
```python
@dataclass(frozen=True)
class MarketRegime:
    """KOSPI/KOSDAQ regime 분류."""
    benchmark: str  # "KOSPI" | "KOSDAQ"
    label: str      # "bull" | "bear" | "range"
    trend_signal: float  # 200d MA cross score 등
    volatility_pct: float  # 20d realized vol
    latest_date: date
    source: str  # "fixture" | "pykrx" | ...
```

`InputPayload` 에 옵션 필드:
```python
market_regime: MarketRegime | None = None
```

`RuntimeConfig` 신규:
```python
# regime 임계값
regime_trend_ma_window: int = 200
regime_volatility_window: int = 20
regime_volatility_bull_max: float = 0.025  # 안정 상승
regime_volatility_bear_min: float = 0.040  # 변동성 폭증
# boost 정책: regime 별 적용 강도
regime_bull_boost_pct_extra: float = 0.0   # PR E 1차에서는 정책 비활성 가능
regime_bear_caution_pct: float = 0.0
```

새 bias enum:
- `BOOST_BUY = "boost_buy"`
- `BLOCK_BUY = "block_buy"`
- `REVIEW_SELL = "review_sell"`
- `BOOST_SELL = "boost_sell"` ← 신규

`_bias_for_proposal` 정리:
| 입력 | 출력 |
|---|---|
| `action=hold` + `_BLOCK_BUY_FLAGS` | `block_buy` |
| `action=hold` + `HOLDING_*_REVIEW` + holdings | `review_sell` |
| `action=buy` + regime ∈ {bull, range} | `boost_buy` |
| `action=buy` + regime == bear | `boost_buy` + `risk_flag=BEAR_REGIME_CAUTION` (bias 유지, 가중치는 loader 쪽 정책) |
| `action=sell` + 강한 sell 신호 (confidence ≥ X) | **`boost_sell` (신규)** |
| `action=sell` + 약한 신호 | `review_sell` |
| 그 외 | emit 없음 |

### 3.2 kiwoom-autotrade 측

`src/trading/llm_decision_loader.py`:
- `apply_universe_decisions` 는 그대로 두고, **새 함수 추가**:
  - `apply_boost_buy_ranking(symbols, decisions) -> tuple[list[str], dict]` — symbols 는 변경 안 함, 같은 종목군 안에서 우선순위(priority/score) 와 함께 반환.
  - `apply_sell_intent(open_positions, decisions) -> SellIntent` — 보유 종목 중 어떤 것이 `review_sell` / `boost_sell` 추천인지.
- 새 결정 타입 등은 도입 안 함 (현 `symbol_bias` 유지).

`scripts/live_trader.py`:
- 보유 종목 평가 사이클에서 `SellIntent` 를 *후보 신호로 합쳐* 기존 risk gate / 손익 조건 통과 시 매도.
- 매수 후보 산정에서 `boost_buy` 가 있는 종목을 같은 universe 내 우선 후보로.
- **action 강제 X**. 모든 결정은 기존 live_trader 의 risk gate 와 사용자 kill switch 를 통과해야 함.

---

## 4. live_trader 소비 정의 (가장 위험한 부분 — 명시적으로 합의 필요)

### 4.1 `boost_buy`

| 항목 | 결정 |
|---|---|
| 효과 | 같은 universe 후보들 중 **우선순위 가산** 만. 신규 종목 추가는 안 함 (universe 는 별도 path) |
| 적용 시점 | live_trader 매수 사이클의 후보 정렬 단계 |
| 강제 매수? | 아니오. 기존 매수 조건 (signal + risk gate + sizing + cash) 모두 통과해야 |
| 가산 폭 | 후보 ranking 의 가장 후순위와 같은 정도, 즉 *지금 살까 말까 라인* 의 종목이 우선 후보로 올라오는 정도. 정확한 score 가중은 PR E 구현 시 결정 |
| 회귀 | 동일 입력에 boost_buy 적용 전/후 매수 종목 차이 1건 이하 (보수적 기본값) |

### 4.2 `review_sell`

| 항목 | 결정 |
|---|---|
| 효과 | 다음 보유 평가 사이클에서 **사용자가 사전에 정의한 매도 조건** 의 *임계값을 살짝 낮춤* (예: trailing stop 2% → 1.5%). 즉시 매도 X |
| 적용 시점 | live_trader 의 sell 평가 사이클 |
| 강제 매도? | 아니오 |
| 결정 만료 | applied 마킹된 시점 또는 24h 이내 |
| 회귀 | 적용 전/후 매도 수량 차이 0~소량. orders 폭증 금지 |

### 4.3 `boost_sell` (신규)

| 항목 | 결정 |
|---|---|
| 효과 | review_sell 보다 강한 권고. **여전히 강제 매도 X**. 다음 사이클에서 매도 조건 임계 더 강하게 (예: trailing 2% → 1.0%) |
| 주문 타입/수량/가격 | **AI bias 가 절대 변경 안 함**. 기존 live_trader/broker safety gate 가 결정 (지정가 vs 시장가, 수량, 가격) |
| 적용 시점 | sell 평가 사이클 |
| 안전 게이트 | (필수) 일일 매도 한도 / 단일 종목 최대 매도 수량 / kill_switch 모두 적용 |
| 만료 | applied 마킹 후 즉시. 또는 12h 이내 |

### 4.4 `block_buy` (회귀 없음)

기존과 동일. 변경 없음. (확정.)

---

## 5. 안전 게이트 — 주문 생성 직전

PR E 에서 **반드시 통과해야 주문이 나간다**. 게이트는 `loader` 진입에서 차례로 평가하며, 하나라도 실패하면 그 결정은 소비되지 않는다 (조용히 skip + 구조화 로깅).

### 5.1 Feature flag (최상위)

- 환경변수: **`AI_HEDGE_BIAS_CONSUMPTION_ENABLED`** — 기본 `false`.
- main 머지 후에도 기본 동작은 PR E 이전과 **완전 동일**. flag 가 명시적으로 `true` 인 환경에서만 신규 소비 로직이 활성화.
- 모의투자 QA 환경에서만 flag ON. 실거래 전환은 별도 사용자 결정.
- flag OFF 시 loader 는 `boost_buy` / `review_sell` / `boost_sell` 을 **무시**하고 기존 `block_buy` only 동작 유지.

### 5.2 source / status gate (소비 대상 화이트리스트)

신규 소비 대상은 다음 조건을 **모두** 만족하는 결정만:

| 속성 | 허용 값 |
|---|---|
| `context_source` | `'ai_hedge'` (정확 일치). 다른 source 의 동일 bias 는 소비 안 함 |
| `status` | `'approved'` (정확 일치). `pending` / `auto_rejected` / `applied` / `rejected` / `expired` 전부 제외 |

source 가 unknown 이거나 missing 인 경우의 boost_buy/review_sell/boost_sell 은 **항상 무시**.

**중요 — `block_buy` 는 본 게이트 적용 대상이 아님**:
- `block_buy` 는 PR E 이전부터 loader 가 소비 중인 **기존 동작**. 현재 `apply_universe_decisions` 는 `approved` `block_buy` 를 source 와 무관하게 universe 제외에 사용한다.
- PR E 는 신규 bias (`boost_buy / review_sell / boost_sell`) **소비 도입** PR 이지, 기존 `block_buy` 소비 정책 변경 PR 이 아니다.
- 따라서 본 §5.2 source gate 는 신규 3종 bias 에만 적용하며, **`block_buy` 는 회귀 없이 기존 동작 그대로 유지**한다.
- `block_buy` 에 source gate 를 거는 것은 본 PR E 범위 밖이며, 필요 시 별도 정책 PR 로 분리한다. (#464 의 auto-approval 제외 정책은 그대로 유지 — 이건 별개)

### 5.3 bias whitelist (loader/validation)

`llm_decision_loader` 와 decisions 검증 레이어에서 허용 bias 값 enum 명시:

```
ALLOWED_BIAS = {"block_buy", "boost_buy", "review_sell", "boost_sell"}
```

- 그 외 값 (오타, 미래 확장 시 ai-hedge-fund-lab 단독 추가 등) 은 **reject + 구조화 로깅** (no-op).
- `boost_sell` 신규 추가 시 다음 모두 동시 반영:
  - `/api/v1/decisions/drafts` request schema (validation)
  - `llm_decision_loader` 매핑
  - tests (loader / validation / e2e)
  - 누락 시 PR E2 머지 금지.

### 5.4 기본 안전 게이트 (기존 정책 유지)

1. **사용자 명시 승인** (`status='approved'`). pending/auto_rejected 는 절대 소비 안 함. (#461)
2. **ai_hedge auto-approval 제외 정책 (#464)** 유지. ai_hedge 결정은 사용자 manual approve 만 거친다.
3. **`applied` 로 마킹된 결정은 재소비 안 함** (#466 정책).
4. **kill_switch ON 이면 모든 AI bias 소비 정지**.
5. **모의투자 기본값 (`is_mock_trading=True`)** 우선. 실거래 전환은 별도 명시적 설정.
6. **일일 주문 횟수 / 최대 주문 금액 / 가격제한 / 거래정지** — 기존 broker layer 게이트 그대로.

### 5.5 신규 over-reaction 방지 게이트 (DB 기반, process memory 금지)

7. **`boost_sell` 1일 최대 적용 종목 수 상한 (예: 3)**. 동일 영업일 (`KST` 기준) 안에서 누적 카운트.
8. **AI bias 가 만든 매도 후보의 totaled notional 이 일일 한도의 N% 초과 시 자동 정지** (그 날은 더 이상 AI 매도 X).

**중요**: 위 7/8 의 카운트는 반드시 **DB (orders / trade_logs)** 기준으로 산정한다. process memory (in-memory dict / counter) 금지.

- 이유: live_trader 재시작이 잦은 환경에서 process 카운터는 재시작 시 0 으로 리셋 → 한도 우회 가능.
- 산정 기준: `trade_logs` 에서 `created_at >= 당일 09:00 KST` AND `evidence ~ 'ai_hedge_bias=*'` (또는 `decisions.context_source='ai_hedge'` join) 인 주문만 누계.
- 즉 주문 생성 evidence 에 **"이 주문이 AI bias 에 의해 유발되었음"** 식별 정보가 들어가야 함. 미식별 주문은 한도 계산에서 제외 (보수적으로 보일 수 있으나, AI 유발이 아닌 일반 주문까지 막으면 사용자 정상 거래가 막힘).
- 필수 evidence 필드 (drafts ingestion 시 trade_logs 로 전파):
  - `ai_hedge_decision_id`: 트리거한 결정 ID
  - `ai_hedge_bias`: `boost_buy | review_sell | boost_sell`
  - `ai_hedge_context_source`: `'ai_hedge'`

---

## 6. `approved` ↔ `applied` 상태 전환과 충돌 여부

PR #466 정책 (현행):
- approved 결정이 universe 필터 / strategy_param_hint / holding 평가 등에 **실제로 반영되었을 때만** `applied` 마킹.
- mismatch / no-effect 결정은 `approved` 유지 (다음 사이클 재평가).

PR E 와의 충돌 분석:

| 신규 동작 | applied 마킹 시점 | 충돌? |
|---|---|---|
| `boost_buy` 가 universe 후보 ranking 에 반영되어 매수 후보로 진입했고, 실제 매수 1주 이상 실행 | applied | 없음. 새 determiner 가 actual_buy_qty>0 면 applied 카운트 |
| `boost_buy` 반영됐지만 매수 조건 미충족 → 매수 실행 X | approved 유지 | 없음 (no-effect → 재평가) |
| `review_sell` / `boost_sell` 이 매도 임계값 변경에 반영되어 실제 매도 실행 | applied | 없음 |
| `review_sell` 이 임계값을 낮췄지만 그 사이클에 매도 안 일어남 | approved 유지 | 약간 모호. **정책 명시 필요** — "임계값 변경이 1회 적용된 시점 = applied" 로 갈지, "실제 매도 발생 시점 = applied" 로 갈지 결정 필요 |

**확정 정책** (코드 변경 가이드):

1. **`applied` 마킹은 "실제 주문 발생" 기준만**. 임계값 노출만 있고 미체결이면 `approved` 유지.
   - 식별 기준: `orders.order_id` 가 1개 이상 새로 발생하고 그 주문의 evidence 에 `ai_hedge_decision_id=<id>` 가 있을 때.
   - 즉 `determine_applied_decision_ids` 는 process memory 가 아닌 **orders / trade_logs row 존재** 로 판단.
2. **TTL 명시**: `boost_buy` / `review_sell` 은 24h 동안 반복 영향 가능성이 있으므로 `created_at + 24h` 후 자동 만료. TTL 만료된 결정은 더 이상 loader 가 소비하지 않음 (status 는 그대로 두되 query filter 에서 제외).
3. **`boost_sell` TTL 은 12h** (더 짧음). over-reaction 위험이 더 큼.
4. **TTL 만료된 결정의 표시**: status 강제 변경하지 않음. 단 응답 evidence 에 `ttl_expired=true` 노출. 사용자가 재승인하려면 새 결정으로 다시 제출.
5. **재시작 안전성**: live_trader / kiwoom backend 가 재시작되어도 위 1~4 가 깨지지 않아야 함 (DB 기준이므로 자동 보장).

---

## 7. ai-hedge-fund-lab export 변경 범위

### 7.1 변경 파일
- `src/korea_ai_hedge/exports/kiwoom_decision_export.py` (bias 매핑 확장)
- `src/korea_ai_hedge/agents/regime_signal.py` (신규)
- `src/korea_ai_hedge/models.py` (`MarketRegime`, RuntimeConfig 임계값)
- `src/korea_ai_hedge/risk/risk_gate.py` (regime 통합)
- `src/korea_ai_hedge/adapters/regime_pykrx.py` (optional, lazy)
- tests/* 신규/확장

### 7.2 변경 안 하는 파일
- 다른 PR (A~D) 의 산출물은 그대로 유지.

### 7.3 호환성
- 기존 fixture / proposal JSON 은 그대로 호환. `boost_sell` 은 추가만, 기존 보일러 안 깬다.

---

## 8. kiwoom-autotrade loader/live_trader 변경 범위

### 8.1 변경 파일
- `src/trading/llm_decision_loader.py`:
  - `apply_boost_buy_ranking` 신규
  - `apply_sell_intent` 신규
  - `determine_applied_decision_ids` 확장 (boost_buy/review_sell/boost_sell 효과 검출)
- `scripts/live_trader.py`:
  - 매수 사이클: 후보 ranking 직전 `apply_boost_buy_ranking` 호출
  - 매도 사이클: `apply_sell_intent` 호출 후 기존 매도 평가 임계값에 반영
  - `mark_decisions_applied` 호출 인자 확장
- tests:
  - `tests/trading/test_llm_decision_loader.py` (신규 함수 단위)
  - `tests/scripts/test_live_trader_*.py` (필요 시 통합)

### 8.2 변경 안 하는 부분
- broker order API 자체.
- 기존 kill_switch / risk gate / cash check.
- `/api/v1/decisions/drafts` 엔드포인트 (그대로).

---

## 9. 모의투자 E2E 시나리오 (머지 전 필수 검증)

새 PR 의 머지 조건. 모두 모의투자 (`is_mock_trading=True`) 에서:

| # | 시나리오 | 기대 |
|---|---|---|
| 1 | approved 가 아닌 ai_hedge boost_buy 가 있어도 live_trader 무시 | 적용 0 |
| 2 | approved boost_buy 1건 + universe 후보에 해당 종목 포함 + 매수 조건 충족 | 그 종목이 우선 매수됨. applied 마킹 |
| 3 | approved boost_buy 1건 + 해당 종목 universe 미포함 | 매수 안 됨. approved 유지 |
| 4 | approved review_sell + 매도 임계값 살짝 낮춰져서 실제 매도 1건 발생 | applied 마킹 |
| 5 | approved review_sell + 임계값 낮췄지만 미체결 | approved 유지 |
| 6 | approved boost_sell 1건 | 매도 조건 강하게 평가, 실 매도 시 applied |
| 7 | kill_switch ON 상태에서 위 모든 bias 무시 | orders 변화 0 |
| 8 | ai_hedge 1일 매도 한도 (예: 3종목) 초과 시 자동 정지 | 4번째 boost_sell 무시 |
| 9 | block_buy 회귀 (#461 ~ #466 시나리오) | 기존과 동일 동작 |
| 10 | applied 마킹 후 같은 결정 재처리 X | orders 변화 0 |

이 10 케이스는 모두 모의투자 DB 에서 직접 검증. 1주일 dry-run 후 orders 변화량 사용자 확인.

---

## 10. PR E 분할 제안 (단일 PR 위험 크므로 2단계)

| 단계 | 범위 | 위험 |
|---|---|---|
| **PR E1** | ai-hedge-fund-lab 측: regime + bias 매핑 확장 + boost_sell 도입 + tests | 낮음 (lab 안에서 끝남, 기존 export 호환) |
| **PR E2** | kiwoom-autotrade 측: loader 신규 함수 + live_trader 소비 통합 + tests + 모의투자 E2E | 높음 (실 거래 결정 경계) |

PR E1 머지 → 며칠 fixture/eval 관찰 → PR E2 진행.

### 10.1 PR E2 머지 → 활성화 순서 (절대 동시에 X)

PR E2 는 머지 직후 곧바로 실소비가 되지 **않는다**. 다음 순서 준수:

1. **PR E2 머지** — `AI_HEDGE_BIAS_CONSUMPTION_ENABLED=false` 기본값으로 머지. main 동작은 PR E 이전과 동일.
2. **모의투자 환경에서만 flag ON** — `is_mock_trading=True` 가 보장된 환경에서 환경변수 export.
3. **§9 의 10 시나리오 모의 E2E 수행**.
4. **orders / trade_logs / `applied` 전환 결과 사용자 확인**.
5. **사용자 명시 OK** 후에야 운영 모의투자 (계속 mock) 에서 상시 ON.
6. 실거래 전환은 본 PR 범위 외 — 별도 결정 + 별도 PR.

이 단계 중 어느 한 곳이라도 사용자 OK 가 없으면 다음 단계로 진행 금지.

---

## 11. 이 PR 에서 *하지 않을 것* (out of scope)

- LLM 에이전트 도입.
- 분할 진입 (`entry_slices`) — PR H.
- 새 dependency.
- 자동 실거래 전환 (`is_mock_trading=False`).
- 자동 universe 확장 (boost_buy 가 universe 외 종목을 자동 추가하는 동작 등).

---

## 12. 다음 액션

1. 본 문서 사용자 최종 검토.
2. **이 문서 자체를 docs PR 로 kiwoom-autotrade 에 머지** (코드 변경 0). 본 문서가 고정되기 전에는 PR E1 코드 진입 금지.
3. §4 / §5 / §6 / §10.1 명시적 합의 확인.
4. PR E1 (ai-hedge-fund-lab) 진행 — regime + bias 매핑 확장 + boost_sell export. lab 내부에서 끝.
5. PR E1 머지 후 며칠 fixture/eval 관찰.
6. PR E2 (kiwoom-autotrade) 진행 — feature flag OFF 로 머지.
7. 모의투자에서 flag ON QA → 사용자 OK → 상시 ON.

---

## 13. 다른 작업자 / 다른 Claude 가 처음 봐도 이해되는 컨텍스트

이 작업이 어디서 어떻게 굴러가고 있는지 파악할 진입점:

- **두 repo / 워크스페이스**
  - `/Users/sanghyuklee/individual/stock/ai-hedge-fund-lab` — Korea AI hedge proposal lab. GitHub `lsh0107/ai-hedge-fund-lab` (private).
  - `/Users/sanghyuklee/individual/stock/kiwoom-autotrade` — 실 트레이딩 엔진. GitHub `lsh0107/kiwoom-autotrade` (private).
  - 두 repo 는 사이드 by 사이드. 부모 디렉토리는 git 아님 (의도).
- **운영 인계**: `docs/ai-hedge/AI_HEDGE_FUND_INTEGRATION_HANDOFF.md` (kiwoom-autotrade) — 두 repo 가 어떻게 연결되는지.
- **PR 로드맵**: `docs/ai-hedge/PROPOSAL_QUALITY_ROADMAP.md` (kiwoom-autotrade) — 전체 PR 분할 + 정책.
- **머지 후 자동 재빌드**: `kiwoom-autotrade/scripts/post_merge_rebuild.sh` + `.claude/rules/post-merge-rebuild.md`.
- **머지된 PR 현황 (2026-05-22 기준)**:
  - kiwoom-autotrade: #461, #462, #463, #464, #465, #466, #467, #468, #469, #470, #471, #472, #473, #474, #475, #476, #477, #478, #479. main HEAD = `806f07f` (#479 머지 후).
  - ai-hedge-fund-lab: #1 (PR G), #2 (PR F), #3 (PR B), #4 (PR C), #5 (PR D). main HEAD = `64ed345` (PR #5 머지 후).
- **현재 진행**: PR E 설계 단계 — 이 문서.
- **안전 경계 contract (절대 깨지 않는 것)**:
  - AI hedge 가 broker order API 를 직접 호출하지 않는다.
  - 사용자 승인 없는 결정은 실 주문화되지 않는다.
  - 모의투자 기본. 실거래 전환은 별도 명시.
  - 모든 PR 의 e2e QA 에 `orders count 불변` 확인 포함.
  - **PR E2 는 feature flag (`AI_HEDGE_BIAS_CONSUMPTION_ENABLED`) 기본 OFF 로만 머지된다.**

---

## 14. 개정 이력

| 일자 | 변경 |
|---|---|
| 2026-05-22 | 초안 작성 (PR D 머지 직후) |
| 2026-05-26 | 사용자 검토 피드백 7건 반영: ① feature flag 기본 OFF (§5.1) ② boost_sell 시장가 허용 문구 제거 (§4.3) ③ source/status gate 명시 (§5.2) ④ bias whitelist (§5.3) ⑤ applied TTL 및 order_id 기준 (§6) ⑥ 일일 한도 DB 기반 (§5.5) ⑦ PR E2 머지 → 활성화 순서 (§10.1) |
| 2026-05-26 | PR #480 리뷰 반영: §5.2 의 "block_buy 도 동일" 문구 제거. block_buy 는 기존 소비 동작 유지 (회귀 금지), 신규 3종 bias 만 source gate 대상. block_buy source gate 변경은 PR E 범위 밖. |
