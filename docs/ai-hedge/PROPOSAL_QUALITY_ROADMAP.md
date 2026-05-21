# AI Hedge 제안 품질 개선 로드맵

작성일: 2026-05-21
대상: `ai-hedge-fund-lab/kr/ai-hedge-fund/`
선행 작업: `docs/ai-hedge/AI_HEDGE_FUND_INTEGRATION_HANDOFF.md` (수집/승인 큐 완료), kiwoom-autotrade #461/#464/#466 (안전 경계 + applied 정책)

지금까지: "AI hedge 제안 → pending 큐 → 사용자 승인 → orders" 안전 경로가 닫혀 있고, ai_hedge context는 자동승인 대상에서 제외되며, 실제 반영된 결정만 applied 로 전환된다. 다음 단계는 **그 큐에 올라가는 제안의 품질** 개선이다.

이 문서는 구현 계획이 아니라 **PR 분할 합의용 로드맵**이다. 코드 변경 전 사용자 검토를 거친다.

---

## 1. 현재 제안 품질의 한계

| 구분 | 현재 상태 | 한계 |
|---|---|---|
| 에이전트 | `technical_agent` 1개 (deterministic) | momentum/volume/drawdown 임계값만. LLM/펀더멘털/portfolio 에이전트 없음 |
| 데이터 | Kiwoom 일봉 OHLCV + 보유 + 현금 | 한국장 핵심 신호(수급, 섹터, regime, 가격제한, 호가) 전무 |
| 위험 게이트 | 신선도/포지션 한도/현금/신뢰도 | 갭, 변동성 regime, 청산 캐스케이드, 거래정지 미반영 |
| 사이징 | `cash × max_position_pct` → limit 으로 클리핑 | 변동성/체결 가능성 미반영. 호가 단위 미적용 |
| 평가 | **없음** | "이번 제안이 좋았는지" 측정 불가. 모든 개선 효과를 가설 검증할 도구가 부재 |
| 바이어스 종류 | `boost_buy` / `block_buy` / `review_sell` 만 | `boost_sell` / regime-aware downgrade 등 결단 부재 |

샘플 출력 (`samples/kr/proposal.kiwoom.generated.json`) 기준 패턴:
- `action="hold"` 비중이 매우 높음
- `suggested_quantity` / `suggested_notional_krw` 자주 0
- `risk_flags` 가 결정의 사실상 단일 드라이버 (technical signal 의 영향 약함)

---

## 2. 왜 지금 hold / block 위주로 나오나

원인은 단일이 아니라 **여러 보수 정책의 합** 때문이다.

| 정책 | 위치 | 효과 |
|---|---|---|
| `momentum_score >= 0.08` 강한 추세 요구 | `agents/technical_agent.py` | 약한 상승은 buy 안 됨 → hold |
| `min_confidence=60` 미만은 강제 hold | `risk/risk_gate.py` (`LOW_CONFIDENCE`) | 모호한 신호 일괄 차단 |
| `max_position_pct=10%` 기본 + 보유 시 자동 block_buy | `risk_gate.py` (`POSITION_LIMIT_REACHED`) | 강세장에서 이미 산 종목은 buy 불가 |
| 거의 모든 blocking flag 가 `block_buy` 로 정렬 (`STALE_DAILY_CANDLES`, `OPEN_ORDER_EXISTS`, `INSUFFICIENT_BUY_BUDGET` 등) | `exports/kiwoom_decision_export.py` | sell/review 시그널 없이 buy 만 막힘 |
| 매도 신호 (`sell`) 임계값도 강함 (`momentum_score <= -0.08 OR drawdown_60d <= -0.22`) | `agents/technical_agent.py` | 보유 종목 적기 매도 신호 약함 |
| 데이터 부족 시 안전하게 hold | 다수 | 신뢰 가능한 부정 답 위주 |

요약: **"틀려서 손해보지 말자"** 가 지배적이라 **"제안이 적극적으로 도움이 되는 경우"** 가 거의 없다. 이걸 깨려면 (1) 다양한 신호로 신뢰도를 보강해서 보수 정책을 유지하면서도 buy 신호가 살아남게 만들거나, (2) 측정 인프라로 보수 정책 자체를 데이터 기반으로 재교정해야 한다.

---

## 3. 한국장용으로 추가할 신호 후보

우선순위 (P0 = 효과 큼 + 데이터 확보 쉬움):

| P | 신호 | 출처 | 활용 방식 |
|---|---|---|---|
| P0 | **외인/기관 순매수** (일별 금액) | 키움 / pykrx | 매수 신호 가산, 매도 압력 감지 |
| P0 | **거래정지/관리종목/투자경고** | 키움 메타 | 강제 hold/제외 (buy 차단) |
| P0 | **상하한가 근접** | 일봉 + 가격제한폭 계산 | 상한가 근접 시 매수 비추, 하한가 매도 거부 |
| P1 | **섹터 회전** (업종 지수 momentum) | pykrx / KRX | 섹터 약세면 해당 종목 buy 감소 |
| P1 | **시장 regime** (KOSPI/KOSDAQ trend + 변동성) | 지수 일봉 | bull/bear/sideways → 임계값 조정 |
| P1 | **갭 리스크** (전일 종가 vs 시가) | 분봉/일봉 | 갭 큰 종목 buy 보류 |
| P2 | **변동성 (ATR)** | 일봉 high/low/close | 사이징 + 매수 시점 분산 |
| P2 | **공매도 잔고 / 대차** | KRX | 매도 압력 선행 지표 |
| P2 | **이벤트 캘린더** (배당락/분할/실적) | 외부 + 직접 입력 | 이벤트 전후 buy/sell 차단 |
| P3 | **VKOSPI** (변동성 지수) | KRX | regime 보강 |
| P3 | **뉴스 / 공시** | dart / 뉴스 API | LLM 에이전트 도입 시 |

데이터 어댑터는 모두 read-only. Kiwoom 으로 안 되는 것은 별도 source (pykrx 등) 로 추가 — 이미 ai-hedge-fund-lab 정책상 broker order 호출 없음.

---

## 4. 보유 종목 판단 로직 (개선)

현재 `Portfolio` 정보가 빈약함:

```python
# 현재 사용 중인 필드
holding_qty, current_position_value, total_asset_krw, cash_available
```

추가 필요:

| 필드 | 출처 | 용도 |
|---|---|---|
| `avg_entry_price` | kiwoom-autotrade orders 테이블 | unrealized PnL % 계산 |
| `holding_days` | orders 첫 매수일 ~ 현재 | 단기/장기 보유 분리 |
| `same_symbol_other_strategies` | kiwoom strategy_runtime | 전략 간 중복 비중 |
| `open_orders` (방향 포함) | kiwoom orders SUBMITTED | 매수/매도 대기 분리 |
| `remaining_buy_capacity_krw` | position_limit - current_value | 가능한 추가 매수액 |
| `realized_pnl_today` | orders 일별 net | 일일 손익 한도 게이트 |

이걸 활용해서:
- 평가손실 -5% 도달 → `review_sell` 후보
- 익절선 (예: +8%) 도달 → `review_sell` (사용자 확정 후 매도)
- 보유 7일 + 약한 추세 → `review_sell`
- 잔여 매수 한도 < 최소 주문 금액 → `block_buy` (이미 동일 효과지만 사유 명시)

---

## 5. boost_buy / block_buy / review_sell 기준 재설계

현재 매핑 (`exports/kiwoom_decision_export.py`):

```text
action="buy"  → boost_buy
action="sell" → review_sell
action="hold" + 차단 플래그 → block_buy
```

문제:
- `boost_buy` 는 본질적으로 "후보로 고려" 지만 현재 live_trader 가 별로 활용하지 않음 (handoff doc 명시: "loader 가 실제로 적용하는 핵심은 symbol_bias.block_buy 후보 제외")
- `review_sell` 도 마찬가지 — 매도 신호로 실제 소비되지 않음
- 결과적으로 의미 있는 결정은 `block_buy` 하나

재설계 방향:

| bias | 발동 조건 | live_trader 적용 방식 |
|---|---|---|
| `boost_buy` | 기술적 buy + 수급 양호 + regime 우호 + 잔여 한도 충분 | 후보 유니버스에 추가 + 우선순위 가산 (오늘은 후순위 후보였더라도 buy 시도) |
| `block_buy` | (현행 유지) limit 도달 / 데이터 부족 / 위험 플래그 | 유니버스에서 제외 (현행 동작 그대로) |
| `review_sell` | 보유 종목 + 손절/익절/추세 전환 신호 | live_trader 가 다음 익절/손절 평가 시 우선 검토 (자동 매도 X — 사용자 승인 라인 통과) |
| `boost_sell` (신규) | 강한 매도 신호 + 보유 | review_sell 의 강조 버전. 사용자 UI 에 "강한 매도 검토" 표시 |

각 bias 는 ai-hedge-fund-lab 에서 정의 + kiwoom-autotrade `llm_decision_loader` 에서 소비 로직 구현 필요 (양쪽 PR).

---

## 6. 수량 / 금액 산정 기준

현재 (`risk_gate.py`):
```python
budget = config.strategy_budget_krw or cash_available
suggested_notional = min(cash, budget) * max_position_pct
suggested_notional = min(suggested_notional, max(0, position_limit_krw - current_position_value))
suggested_quantity = suggested_notional // latest_close
```

문제:
- 변동성 무시 (저변동/고변동 종목 동일 비중)
- 호가 단위 무시 (정수 주만 — 호가 가격대별 거래 단위 다름)
- 분할 진입 옵션 없음

개선안:

1. **변동성 기반 사이징** (ATR 활용)
   - `target_risk_krw = total_asset × per_trade_risk_pct (예: 0.5%)`
   - `position_size_qty = target_risk_krw / (k × ATR)` (k=2~3)
   - 결과를 기존 limit 으로 클리핑
2. **호가 단위 정렬**
   - 한국 호가 단위 (1, 5, 10, 50, 100, 500, 1000원) 가격대별 round
3. **분할 진입 옵션**
   - `suggested_quantity` 외에 `entry_slices: [(qty, condition), ...]` 형식 추가
   - live_trader 가 1차 매수 후 조건 충족 시 추가
4. **최소 주문 정합**
   - 호가 단위 round 후 최소 주문 금액 미달이면 next-tick 단위 상향 OR `block_buy`

---

## 7. 백테스트 / 평가 루프

**이 항목이 가장 우선이다.** 평가 인프라 없이 다른 개선을 하면 효과 측정 불가.

설계:

```text
proposal_run(t)
  └─ snapshot: 그날 만든 모든 proposal
forward_simulation(t, horizon=1d/5d/20d)
  └─ 다음 거래일 시가 가상 매수 → +horizon 종가 P&L
metrics
  ├─ hit_rate (proposal action 방향 맞춘 비율)
  ├─ avg_pnl, median_pnl
  ├─ pnl_per_risk_flag (어떤 플래그가 좋은 거름망인지)
  └─ regime_split (bull/bear/sideways 별)
```

기술 선택:
- kiwoom-autotrade `daily_candles` 테이블 활용 (이미 적재됨)
- 백테스트 자체는 ai-hedge-fund-lab 내부 모듈 (`evaluation/`) — kiwoom 코드 미수정
- 결과는 JSON snapshot + (선택) markdown 리포트
- regime 라벨링은 단순한 KOSPI 200d MA cross 로 시작

산출물:
- `experiments/eval_<date>.json` — proposal 별 forward PnL
- `experiments/eval_summary_<period>.md` — 메트릭 요약

이 평가 인프라가 있어야 §3~§6 변경 후 "정말 좋아졌나" 답할 수 있다.

---

## 8. PR 분할 계획

각 PR 은 단일 ai-hedge-fund-lab 변경 단위. kiwoom-autotrade 동시 변경이 필요한 경우 명시.

| # | PR | 범위 | 종속성 | 위험도 |
|---|---|---|---|---|
| A | **평가 인프라 (backtest harness)** | `ai-hedge-fund-lab/kr/ai-hedge-fund/evaluation/` 신규 + CLI + 단위 테스트 | — | 낮음 (read-only) |
| B | **보유 종목 판단 강화** | `Portfolio` 모델 확장 + adapter (kiwoom orders 적분) | A (회귀 측정) | 낮음 |
| C | **외인/기관 수급 어댑터 + 통합** | `adapters/flows.py` 신규 + agent 입력 추가 + 신호 통합 | A | 중간 (외부 데이터 의존) |
| D | **섹터 회전 신호** | `adapters/sectors.py` + agent | A | 중간 |
| E | **regime + bias 기준 재설계** | technical_agent threshold regime-aware + bias 매핑 재정의 + **kiwoom-autotrade loader 변경** | A, B | 높음 (양쪽 변경) |
| F | **사이징 (ATR 변동성 기반 + 호가 단위)** | `risk/sizing.py` + 호가 단위 lib | A | 중간 |
| G | **상하한가 / 거래정지 / 가격제한 게이트** | `risk/market_constraints.py` | A | 낮음 |
| H | **분할 진입 옵션** (선택) | `Proposal.entry_slices` + loader 소비 로직 | E | 높음 |

권장 순서: **A → B → G → F → C → D → E → (H)**.

A 가 깔리면 이후 모든 PR 이 "before vs after metric" 으로 자기 검증을 한다.

---

## 9. 각 PR 별 검증 방법

| PR | 검증 |
|---|---|
| A | 과거 60일 baseline 데이터로 메트릭 산출 → 합리적 분포 확인 (hit_rate, avg_pnl). 같은 입력에 같은 출력 (deterministic) |
| B | 단위 테스트: avg_entry_price 계산, holding_days 정확. 통합 테스트: orders 모킹으로 unrealized PnL → review_sell 트리거 |
| C | 어댑터 단위 (외부 API 모킹). 통합: 같은 종목에 수급 +/-로 신호 변화 확인. baseline 대비 buy 비율 변화 보고 |
| D | 섹터 매핑 단위. 섹터 약세 시뮬 → 해당 종목 confidence 하락 확인 |
| E | regime 분기별 회귀 (bull → buy 우호, bear → sell 우호). kiwoom loader 변경분 별도 PR 로 분리 시 두 PR 함께 머지 |
| F | ATR 기반 size 단위. 호가 단위 round (1~1000원 가격대별 케이스) |
| G | 상한가/거래정지 종목 강제 hold + 차단 사유 명시 |
| H | 분할 진입 시뮬: 1차 후 조건 충족 → 추가 매수. 조건 미충족 → 추가 안 함 |

공통 검증:
- ai-hedge-fund-lab 단위 테스트 모두 통과
- 같은 입력에 같은 출력 (regression)
- 모의투자 모드에서 1주일 dry-run 후 orders 변화 없음 (handoff doc 안전 경계 유지)
- A 의 평가 메트릭으로 **변경 전/후 hit_rate 비교** — 개선 없거나 악화면 머지 보류

---

## 10. 안전 경계 (불변)

이 로드맵의 어떤 변경도 다음을 깨면 안 된다:

- AI hedge → pending decision → 사용자 승인 → broker order 경로 유지
- ai_hedge context_source 자동승인 제외 (#464)
- 실제 반영된 결정만 applied 로 전환 (#466)
- broker order API 직접 호출 금지 (ai-hedge-fund-lab 정책)
- 모의투자 기본값 (`is_mock_trading=True`)
- 모든 PR 의 e2e QA 에 "orders count 불변" 포함

---

## 11. 선행 — 라이브 QA 결과 (2026-05-21)

이 로드맵 작성 직전 `/decisions` 라이브 빌드 QA 통과 (Codex 실 브라우저 검수):

- 드롭다운 정상 열림
- 대기 / 승인 / 거부 / 적용 / 평가 / 전체 필터 정상
- 원본 보기 토글 정상
- 카드 요약 raw JSON 기본 미노출
- orders count 129 불변

발견된 P3 개선 (이 PR 에 함께 포함):

- 필터 선택 시 URL query 가 바뀌지 않음 → 새로고침/북마크 시 필터 유실
- 개선: 상태 필터를 URL `?status=` 쿼리와 동기화 (전체는 query 없음)
- 회귀 가드 테스트 추가 (vitest)

## 12. 다음 액션

1. 사용자가 이 로드맵 검토
2. 우선순위 / 순서 조정
3. **URL query 동기화 + 이 문서**가 같은 PR 로 머지된 후 → **PR A (평가 인프라)** 부터 본격 시작
4. PR A 완료 후 baseline 메트릭 한 번 기록 → 이후 PR 마다 비교

문서 갱신 정책 (`.claude/rules/doc-lifecycle.md`):
- 각 PR 머지 시 해당 행 상태 업데이트 (이 문서)
- 설계 결정 변경 시 즉시 갱신
