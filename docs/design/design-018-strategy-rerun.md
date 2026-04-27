---
name: design-018-strategy-rerun
description: 52주 신고가 일봉 전략 파라미터 재검증 결과 (전 조합 폐기) + design-013 multi-regime 배선 완성 (skeleton→완전) + 후속 전략 방향 결정
type: design
status: 활성 — 52주 신고가 일봉 폐기 확정, multi-regime 배선 완성, 후속 전략 선택 대기
created: 2026-04-27
depends_on:
  - design-015-backtest-engine-integrity
  - design-016-strategy-redesign
  - design-013-multi-regime-strategy
related:
  - src/strategy/momentum_daily.py
  - src/backtest/walk_forward.py
  - src/strategy/pullback.py
  - src/strategy/range_trade.py
  - scripts/live_trader.py
  - docs/backtest-results/walk_forward_rerun_20260427_045847.json
pr:
  - "#333 (T1: walk-forward 파라미터 재검증)"
  - "#334 (T2: design-013 PR9 실배선)"
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-27 | T1: 20 grid × 20종목 재검증 — 전 조합 0/20, 52주 신고가 폐기 확정 |
| 2026-04-27 | T2: design-013 `_assign_symbol_strategies` 실배선 완료 (skeleton → 완전) |
| 2026-04-27 | ADR-018 작성 — 폐기 결론 + 후속 옵션 정리 |

---

# Design 018: 전략 재검증 결과 통합 (ADR-018)

## 1. 배경

design-016 walk-forward 20종목 결과(통과 0/20)를 받아, 팀은 두 가지 후속 작업을 병렬로 진행했다:

- **T1**: 실패 원인(RR < 2.0)이 `atr_tp_mult`/`tp_pct` 제한에 있다는 가설 검증 → 파라미터 grid 재검증
- **T2**: design-013 multi-regime 배선 skeleton 해소 → `_assign_symbol_strategies` 실배선

이 ADR은 두 작업의 결과를 통합하여 **모의투자 재개 여부**와 **후속 전략 방향**을 결정한다.

---

## 2. T1 결과: 52주 신고가 일봉 파라미터 재검증

### 2-1. 실험 설계

| 항목 | 값 |
|------|-----|
| 전략 | 52주 신고가 일봉 모멘텀 (design-016) |
| 종목 수 | 20종목 (KOSPI 대형주) |
| 기간 | 18개월 (2024-10-16 ~ 2026-04-27) |
| 슬라이딩 윈도우 | IS 6개월 / OOS 2개월 |
| 고정 파라미터 | lookback=20, vol_mult=1.5, atr_stop_mult=1.5 |
| Grid 변수 | atr_tp_mult ∈ {4.0, 5.0, 6.0, 7.0, 8.0} × tp_pct ∈ {0.05, 0.07, 0.10, None} |
| 결과 파일 | `docs/backtest-results/walk_forward_rerun_20260427_045847.json` |

### 2-2. 통과 기준

| 기준 | 임계값 |
|------|--------|
| OOS Sharpe | ≥ 1.0 |
| MDD | ≤ -10% |
| 승률 | ≥ 35% |
| RR (Reward/Risk) | ≥ 2.0 |
| OOS/IS 일관성 | ≥ 0.7 |
| **최소 통과율** | **≥ 30% (20종목 중 6종 이상)** |

### 2-3. 결과 요약

| 조합 | 통과율 | 판정 |
|------|--------|------|
| atr_tp_mult=4.0, tp_pct=0.05 | 0/20 (0%) | FAIL(폐기 권고) |
| atr_tp_mult=4.0, tp_pct=0.07 | 0/20 (0%) | FAIL(폐기 권고) |
| atr_tp_mult=4.0, tp_pct=0.10 | 0/20 (0%) | FAIL(폐기 권고) |
| atr_tp_mult=4.0, tp_pct=None | 0/20 (0%) | FAIL(폐기 권고) |
| atr_tp_mult=5.0, tp_pct=None | 0/20 (0%) | FAIL(폐기 권고) |
| atr_tp_mult=6.0, tp_pct=None | 0/20 (0%) | FAIL(폐기 권고) |
| atr_tp_mult=7.0, tp_pct=None | 0/20 (0%) | FAIL(폐기 권고) |
| atr_tp_mult=8.0, tp_pct=None | 0/20 (0%) | FAIL(폐기 권고) |
| **전체 20개 조합** | **0/20 (0%)** | **전 조합 폐기** |

### 2-4. tp_pct=None 집계 성과 (익절 상한 제거 케이스)

| 지표 | 평균값 | 기준 | 판정 |
|------|--------|------|------|
| OOS Sharpe | -0.60 | ≥ 1.0 | ❌ |
| MDD | -1.95% | ≤ -10% | ✅ (낮은 변동) |
| 승률 | 30.47% | ≥ 35% | ❌ |
| RR | 1.81 | ≥ 2.0 | ❌ |
| OOS/IS 일관성 | 0.01 | ≥ 0.7 | ❌ |

> **주목**: tp_pct=None으로 MDD는 개선됐으나 Sharpe 음수(-0.60), 승률 30%, RR 1.81로
> 기준 OOS/IS 일관성 0.01(목표 0.7의 1.4%)은 오히려 크게 악화. IS 학습이 OOS에 전혀 전이되지 않음.

### 2-5. 주요 실패 원인 분석 (첫 번째 조합 기준)

| 실패 기준 | 실패 종목 수/20 | 해석 |
|----------|----------------|------|
| OOS/IS 일관성 < 0.7 | 19/20 | OOS 성과가 IS 대비 붕괴 — 과적합 구조 |
| RR < 2.0 | 15/20 | 대형주 ATR 구조상 손익비 2.0 달성 어려움 |
| 승률 < 35% | 14/20 | 52주 신고가 돌파 후 단기 되돌림 빈발 |
| OOS Sharpe < 1.0 | 8/20 | 수익 변동성 대비 절대 수익 부족 |

### 2-6. 결론: 52주 신고가 일봉 전략 폐기

**파라미터 재조정 가설 기각.** atr_tp_mult 4.0 → 8.0, tp_pct 5% → None 전 범위 탐색에서
단 하나도 기준을 통과하지 못했다. 이는 파라미터 문제가 아닌 **KOSPI 대형주 + 52주 신고가
돌파 구조의 한계**임을 시사한다:

1. **OOS/IS 일관성 붕괴 (19/20)**: 신고가 돌파 신호가 IS 기간에 학습된 것이 OOS 기간에 재현되지 않음
2. **RR 구조적 한계**: KOSPI 대형주는 ATR 대비 움직임 폭이 좁아 2.0 이상 RR 달성이 어려움
3. **파라미터 탐색 공간 소진**: 20개 조합이 전부 같은 결론 → 추가 파라미터 조정은 의미 없음

---

## 3. T2 결과: design-013 multi-regime 배선 완성

### 3-1. 이전 상태 (skeleton)

`USE_MULTI_REGIME=true`로 설정해도 `_assign_symbol_strategies`가
실제 가중치 분배 없이 skeleton만 존재. Pullback/Range 전략 인스턴스화 안 됨.

### 3-2. PR #334 변경 사항

| 변경 | 내용 |
|------|------|
| `_assign_symbol_strategies` 신설 | REGIME_STRATEGY_WEIGHTS 기반 실제 가중치 분배 |
| PullbackStrategy 인스턴스화 | `USE_MULTI_REGIME=true` 시 `src/strategy/pullback.py` 활성 |
| RangeStrategy 인스턴스화 | `USE_MULTI_REGIME=true` 시 `src/strategy/range_trade.py` 활성 |
| DEFENSIVE/CRISIS 차단 확장 | 레짐 DEFENSIVE/CRISIS에서 Pullback/Range도 차단 |
| flag off 회귀 보호 | `USE_MULTI_REGIME=false` (기본) 시 기존 모멘텀 단독 경로 유지 |

### 3-3. 가중치 분배 매트릭스 (활성화 후)

| MarketStyle | momentum | pullback | mean_reversion | range_trade |
|-------------|----------|----------|----------------|-------------|
| TREND_BULL_STRONG | 0.70 | 0.30 | — | — |
| TREND_BULL_QUIET | 0.20 | 0.50 | 0.30 | — |
| RANGE | — | — | 0.40 | 0.60 |
| TREND_BEAR | 0.20 | — | 0.40 | — |
| CHOP | — | — | 0.30 | — |

DEFENSIVE/CRISIS 레짐: 전략 배정 없음 (현금 보유).

### 3-4. 검증 상태

- `USE_MULTI_REGIME=false` 회귀: ✅ 기존 동작 보호 (flag off = 모멘텀 단독)
- `USE_MULTI_REGIME=true` 경로: 배선 완료, **단독 백테스트 미실시**
- Pullback/Range 전략 자체 walk-forward: **미완료**

---

## 4. 모의투자 재개 권고: 보수적 NO

**권고: 모의투자 차단 유지.**

| 근거 | 상세 |
|------|------|
| 52주 신고가 전략 폐기 | T1 결과. 현재 `USE_MULTI_REGIME=false` 기본값 → 모멘텀 경로 작동 = 폐기된 전략 |
| multi-regime 미검증 | T2 배선 완성됐으나 Pullback/Range 전략 단독 walk-forward 없음 |
| OOS/IS 일관성 0.01 | 어떤 전략이든 OOS 검증 없이 실거래 적용은 과적합 리스크 |

> 주의: `USE_MULTI_REGIME=true`로 활성화해도 Pullback/Range 전략이 별도 walk-forward를
> 통과하지 않은 상태에서 모의투자 시작은 **검증 없는 전략 운용**이다.

---

## 5. 후속 옵션 비교

아래 세 옵션 중 하나를 선택해야 한다. 트레이드오프를 명시한다.

### 옵션 A: KOSPI 소형주/중형주 유니버스로 52주 신고가 재검증

| 항목 | 내용 |
|------|------|
| 전제 | 대형주 구조 한계 → 소형주는 ATR 폭 크고 모멘텀 지속성 다를 수 있음 |
| 장점 | 기존 `MomentumDailyStrategy` 코드 재활용 가능 (유니버스만 교체) |
| 단점 | 소형주 유동성 리스크 ↑ (슬리피지 실제로 더 클 수 있음), 운영 복잡도 ↑ |
| 선행 조건 | 소형주 20종목 선정 기준 정의 + 동일 walk-forward 재실행 |
| 소요 추정 | 중간 (전략 코드 불변, 데이터 수집 + 재실행) |

### 옵션 B: Pullback/MeanReversion 전략 단독 walk-forward (multi-regime 상태)

| 항목 | 내용 |
|------|------|
| 전제 | T2 배선 완료 → `USE_MULTI_REGIME=true` 상태에서 PullbackStrategy 단독 검증 |
| 장점 | multi-regime 아키텍처 전체를 검증 (배선 + 전략 동시 검증) |
| 단점 | 백테스트 엔진이 일봉 엔진(`daily_engine.py`)으로 구현 — Pullback/Range는 일중 시그널을 사용하므로 엔진 확장 필요 가능성 |
| 선행 조건 | Pullback/Range 백테스트 엔진 지원 여부 확인 |
| 소요 추정 | 높음 (엔진 지원 확인 → 구현 → walk-forward) |

### 옵션 C: 레짐 필터 강화 (BULL_STRONG만 진입)

| 항목 | 내용 |
|------|------|
| 전제 | 52주 신고가 전략을 TREND_BULL_STRONG 레짐에서만 진입하도록 조건 강화 |
| 장점 | 기존 전략 재활용, 진입 조건 강화만으로 OOS 일관성 개선 기대 |
| 단점 | 진입 빈도 ↓ (신호 희소화) → 통계적 유의성 확보 어려움. 핵심 문제(OOS/IS 일관성)를 우회하는 접근 |
| 선행 조건 | 레짐 필터 추가 후 walk-forward 재실행 |
| 소요 추정 | 낮음~중간 |

### 권고 순서

**1순위 옵션 B → 2순위 옵션 A → 3순위 옵션 C**

- 옵션 B: multi-regime 아키텍처 자체 검증이 장기 운영 기반 구축에 가장 효율적
- 옵션 A: 52주 신고가 전략 자체의 유효성이 확인되지 않은 상황에서 유니버스만 바꾸는 것은 차선책
- 옵션 C: 구조적 문제를 해결하지 않고 필터로 우회하는 것은 재발 가능성 높음

---

## 6. 파생 결정

| 결정 | 내용 |
|------|------|
| design-016 상태 | 52주 신고가 일봉 전략 폐기 — design-016 상태를 "폐기 확정"으로 갱신 |
| design-013 상태 | multi-regime 배선 완성 (skeleton → 완전) — 단독 walk-forward 검증 후 운영 결정 |
| 모의투자 재개 | 선택된 옵션의 walk-forward 통과(≥ 30%) 후 검토 |
| `USE_MULTI_REGIME` flag | false 유지 — 검증 완료 전 활성화 금지 |

---

## 7. 교차 참조

- design-015: 백테스트 엔진 무결성 (look-ahead/slippage 보정)
- design-016: 52주 신고가 전략 재설계 (이 ADR로 폐기 확정)
- design-013: multi-regime 아키텍처 (이 ADR로 배선 완성 확인)
- design-017: 리스크 가드레일 + 마이크로구조 (후속 전략 검증 후 연동)
- operations/strategy-redesign-rollout: 모의투자 차단 유지 조건 갱신 필요
