---
name: design-020-extended-validation
description: 확장 walk-forward 검증 결과 (KOSPI30+KOSDAQ30 60종목, 3년, 27 combo, slippage=0.15%) — 전 전략 0/59 폐기, 일봉 mean-reversion/range/pullback 카테고리 전체 제외 결정
type: design
status: 활성 — 일봉 카테고리 전체 폐기 확정, 후속 방향 결정 대기
created: 2026-04-27
depends_on:
  - design-015-backtest-engine-integrity
  - design-016-strategy-redesign
  - design-018-strategy-rerun
  - design-019-pullback-range-validation
related:
  - src/backtest/generic_daily_engine.py
  - src/backtest/generic_walk_forward.py
  - src/strategy/pullback.py
  - src/strategy/range_trade.py
  - scripts/run_pullback_range_wf.py
  - docs/backtest-results/walk_forward_extended_20260427_180305.json
pr:
  - "abacd4d (feat/extended-backtest-60stocks)"
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-27 | ADR-019 후속: 신호 희소성 가설 검증 위해 확장 실험 설계 |
| 2026-04-27 | 유니버스 60종목(KOSPI30+KOSDAQ30), 기간 3년, slippage 0.0015, grid 27조합으로 확장 |
| 2026-04-27 | 전 전략 0/59 폐기 확정 — 일봉 카테고리 전체 제외 결정 |

---

# Design 020: 확장 walk-forward 검증 결과 (ADR-020)

## 1. 배경 및 실험 목적

ADR-019에서 Pullback/Range/MR 전략이 KOSPI 대형주 20종목에서 0/20 폐기된 후,
**"KOSPI 대형주의 신호 희소성"** 가설이 주요 실패 원인으로 지목됐다.

이 가설을 검증하기 위해 다음 3가지 조건을 확장했다:

| 항목 | ADR-019 (이전) | ADR-020 (확장) | 변경 이유 |
|------|----------------|----------------|----------|
| 유니버스 | KOSPI 상위 20종목 | KOSPI30 + KOSDAQ30 = 59종목 (285540 쏘카 데이터 없음) | KOSDAQ 소형/중형주 포함 → 신호 희소성 가설 직접 검증 |
| 기간 | 18개월 | 3년 (20230427~20260427) | 더 많은 윈도우로 통계 유의성 확보 |
| grid | 12 combo | 27 combo | 파라미터 공간 확장 |
| slippage | 0.0 (버그) | 0.0015 (ADR-015 기준) | 슬리피지 미적용 버그 수정 |

---

## 2. 실험 설계

| 항목 | 값 |
|------|-----|
| 유니버스 | KOSPI30 + KOSDAQ30 (59/60 종목, 285540 쏘카 데이터 없음) |
| 기간 | 2023-04-27 ~ 2026-04-27 (3년) |
| 슬라이딩 윈도우 | IS 6개월 / OOS 2개월 |
| 전략 × grid | Pullback(9) + Range(9) + MR(9) = 27 combo |
| slippage_pct | 0.0015 (ADR-015) |
| 결과 파일 | `docs/backtest-results/walk_forward_extended_20260427_180305.json` |

---

## 3. 윈도우 거래 발생 현황 (신호 희소성 가설 검증)

**22,302개 윈도우 전체 분석:**

| 구간 | 총 윈도우 | 거래 발생 | 거래 발생률 |
|------|-----------|-----------|------------|
| IS (학습) | 22,302 | 14,815 | **66.4%** |
| OOS (검증) | 22,302 | 6,962 | **31.2%** |

**결론: 신호 희소성 가설 기각.**

ADR-019에서 제기된 "KOSPI 대형주의 신호 희소성" 가설은 틀렸다. KOSDAQ 종목과 더 긴 기간을 포함하면 OOS 기간에서도 31%의 윈도우에서 거래가 발생한다. 문제는 신호 부재가 아니라 **거래가 발생해도 수익을 내지 못하는 카테고리 자체의 구조적 한계**다.

---

## 4. 전략별 결과

### 4-1. Pullback 전략

**9개 grid 조합 × 59종목, 전 조합 0/59 (0%)**

| 항목 | 값 |
|------|----|
| best_combo | band=0.015_rsi_max=50 |
| pass_count | 0 |
| pass_rate | 0.0% |
| verdict | FAIL(폐기 권고) |

### 4-2. Range 전략

**9개 grid 조합 × 59종목, 전 조합 0/59 (0%)**

| 항목 | 값 |
|------|----|
| best_combo | rsi_max=40_bb_std=1.5 |
| pass_count | 0 |
| pass_rate | 0.0% |
| verdict | FAIL(폐기 권고) |

### 4-3. MR (Mean-Reversion) 전략

**9개 grid 조합 × 59종목, 전 조합 0/59 (0%)**

| 항목 | 값 |
|------|----|
| best_combo | rsi_oversold=30_bb_std=1.8 |
| pass_count | 0 |
| pass_rate | 0.0% |
| verdict | FAIL(폐기 권고) |

---

## 5. 누적 폐기 5건 패턴 분석

| # | 전략 | 폐기 사유 | ADR/PR |
|---|------|----------|--------|
| 1 | 5분봉 모멘텀 | 왕복비용 0.53% × 일 5거래 → 일 -2.65% 비용 구조 | ADR-016 |
| 2 | 52주 신고가 일봉 (기본 grid) | 20종목 0/20 — OOS/IS 일관성 붕괴(19/20), RR 구조 한계(15/20) | ADR-016 |
| 3 | 52주 신고가 + atr_tp/tp_pct 400 시나리오 | 0/20 — 파라미터 탐색 공간 소진 | ADR-018 |
| 4 | Pullback/Range/MR 일봉 (KOSPI 대형주 20종목) | 12 combo × 20종목 0/20 — 신호 희소 + RR 미달 | ADR-019 |
| 5 | Pullback/Range/MR 일봉 (KOSPI30+KOSDAQ30 59종목, 3년) | 27 combo × 59종목 0/59 — 거래 발생(OOS 31%)해도 수익 불가 | **ADR-020** |

### 핵심 구조적 결론

ADR-019의 신호 희소성 가설(#1)은 기각됐다. 새롭게 확인된 구조적 원인:

1. **카테고리 자체의 수익 불가 구조**: OOS 31% 윈도우에서 거래가 발생해도 Sharpe ≥ 1.0 + WR ≥ 35% + RR ≥ 2.0을 동시에 충족하는 종목이 한 개도 없다. 신호가 있어도 수익 구조가 성립하지 않는다.

2. **IS 과최적화 → OOS 붕괴**: IS Sharpe는 일부 종목에서 양수이나 OOS Sharpe ≈ 0.0. 파라미터가 특정 IS 기간에 과최적화되어 OOS에서 재현되지 않는다.

3. **일봉 mean-reversion/range/pullback의 한국 시장 부적합성**: KOSPI·KOSDAQ를 불문하고, 3년·59종목·27 combo 전부 실패는 개별 종목·파라미터 문제가 아니라 이 카테고리 전체의 구조적 한계임을 의미한다.

---

## 6. 핵심 결정

**일봉 mean-reversion / range / pullback 카테고리를 한국 시장 검증 대상에서 전면 제외한다.**

| 근거 | 상세 |
|------|------|
| 신호 희소성 아님 | OOS 31% 윈도우에서 거래 발생 확인 |
| 카테고리 수익 불가 | 27 combo × 59종목 × 3년 전부 기준 미달 |
| 파라미터 탐색 소진 | ADR-019에서 이미 grid 확장 시도 — ADR-020에서 확인 |
| 투자 비용 대비 효과 없음 | 추가 검증은 동일한 결론의 반복에 불과 |

`USE_MULTI_REGIME=false` 계속 유지. 모의투자 재개 조건 미충족.

---

## 7. 모의투자 재개 권고: NO

**모의투자 차단 유지 — walk-forward 통과 전략 등장 시까지.**

---

## 8. 후속 옵션 (열거만 — 결정 보류)

| 옵션 | 내용 | 비용 | 불확실성 |
|------|------|------|---------|
| (a) breakout/모멘텀 일봉 재시도 | 52주 신고가 이외의 돌파 기반 전략 (예: 박스권 상단 돌파, 거래량 폭발) | 낮음 (엔진 재활용) | 중간 |
| (b) 분봉(15/30분) 모멘텀 + 거래비용 모델 강화 | ADR-016에서 폐기된 5분봉의 교훈 반영 — 거래횟수 대폭 감소, RR 2.0 달성 가능성 재검토 | 중간 (데이터 수집 + 엔진 수정) | 높음 |
| (c) LLM 보조 결정 + 펀더멘털 신호 | design-010 LLM decision 부활 + 수급/테마 신호(design-009) 결합 | 높음 (설계 재작성) | 높음 |
| (d) 운영 잠정 중단·관찰만 | 백테스트 통과 전략 나타날 때까지 시스템 관찰만 유지 | 없음 | 낮음 |

**결정 방식**: 사용자 지시 또는 별도 ADR로 옵션 선택 후 진행. 현 시점 어떤 옵션도 착수하지 않는다.

---

## 9. 파생 결정

| 결정 | 내용 |
|------|------|
| design-013 상태 | 배선 완성 유지, `USE_MULTI_REGIME=false` — 통과 전략 없으므로 활성화 금지 |
| 모의투자 재개 | walk-forward 통과 전략 등장 시까지 완전 차단 |
| 판정 기준 | 유지 (Sharpe 1.0, OOS/IS 0.7) |
| 일봉 카테고리 | Pullback/Range/MR 일봉 재검증 금지 — 추가 검증은 동일 결론의 반복 |

---

## 10. 교차 참조

- design-015: 백테스트 엔진 무결성 (slippage=0.0015 ADR-015 기준 적용 확인)
- design-016: 52주 신고가 전략 재설계 (폐기 확정)
- design-018: 파라미터 재검증 통합 ADR (400 시나리오 소진 확정)
- design-019: Pullback/Range/MR KOSPI 대형주 0/20 — 이 ADR의 선행 실험
- design-013: multi-regime 아키텍처 (배선 완성, `USE_MULTI_REGIME=false` 유지)
- operations/strategy-redesign-rollout: 차단 상태 갱신, 후속 옵션 변경 반영
