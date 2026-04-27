---
name: design-021-cross-sectional-momentum
description: Cross-sectional momentum (Jegadeesh-Titman 1993) walk-forward 검증 결과 (172종목, 5년, 8 combo) — 전 Combo FAIL. 누적 폐기 6건 → 전략 카테고리 기준 재논의 필요
type: design
status: 활성 — 전 Combo FAIL 확정. 누적 폐기 6건 → 전략 카테고리 기준 재논의 필요
created: 2026-04-27
depends_on:
  - design-015-backtest-engine-integrity
  - design-019-pullback-range-validation
  - design-020-extended-validation
related:
  - src/strategy/cross_momentum.py
  - src/backtest/portfolio_engine.py
  - scripts/run_cross_momentum_wf.py
  - tests/strategy/test_cross_momentum.py
  - tests/backtest/test_portfolio_engine.py
  - docs/backtest-results/walk_forward_cross_momentum_full_20260427_193805.json
pr:
  - TBD
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-27 | ADR-020 후속: 학계 사전증거 가장 강한 Cross-sectional momentum 검증 설계 |
| 2026-04-27 | KOSPI100+KOSDAQ100 = 목표 200종목 (유효 172종목), 5년 (2021~2026), 8 combo WF 실행 |
| 2026-04-27 | 전 Combo FAIL 확정 — **누적 폐기 6건**, 전략 카테고리 기준 재논의 트리거 |

---

# Design 021: Cross-sectional Momentum Walk-forward 검증 결과 (ADR-021)

## 1. 배경 및 목적

ADR-016~020까지 5개 전략이 모두 폐기됐다. 다음 후보로 **학계 사전증거가 가장 강한 anomaly**인
Cross-sectional momentum (Jegadeesh-Titman 1993)을 검증한다.

한국 KOSPI/KOSDAQ 실증 연구 다수 존재. 단순성·직관성·이론적 근거 모두 최상위. 이 전략도
walk-forward를 통과하지 못하면 "전략 카테고리 기준 재논의" 트리거가 된다.

---

## 2. 실험 설계

| 항목 | 값 |
|------|-----|
| 유니버스 | KOSPI 시총 상위 100 + KOSDAQ 시총 상위 100 = 목표 200종목, **유효 172종목** (pykrx KRX market-level API 불안정 → 정적 근사 리스트 사용) |
| 신호 | 12-1 month cross-sectional momentum score = `close[T0-skip] / close[T0-skip-formation] - 1` |
| 필터1 | 252일 vol 하위 50% (Low-vol anomaly, Hsu 2013) |
| 필터2 | 200일 이평 위 (Trend filter, Moskowitz 2012) |
| 포지션 | 상위 데실(10%/20%), equal weight, monthly rebalance |
| 거래비용 | slippage=0.0015, commission=0.00015, tax=0.0023 (매도만, 실제 회전율 기반) |
| 데이터 기간 | 2020-01-01 ~ 2026-04-27 (이력 포함) |
| WF 설정 | IS=24mo / OOS=6mo / step=6mo / 6 윈도우 |
| Combo grid | top_decile [0.1, 0.2] × vol [T/F] × trend [T/F] = **8 조합** |
| 통과 기준 | OOS Sharpe≥1.0 / MDD≥-25% / IR vs KOSPI≥0.5 / OOS-IS Sharpe≥0.7 / pass_rate≥30% (6W 중 ≥2개) |
| 결과 파일 | `docs/backtest-results/walk_forward_cross_momentum_full_20260427_193805.json` |

---

## 3. 결과 요약

| Combo | 통과 W/6 | pass_rate | 판정 |
|-------|----------|-----------|------|
| top10pct_vol_trend | 0/6 | 0% | FAIL |
| top10pct_vol_notrend | 0/6 | 0% | FAIL |
| top10pct_novol_trend | 0/6 | 0% | FAIL |
| top10pct_novol_notrend | 0/6 | 0% | FAIL |
| top20pct_vol_trend | 0/6 | 0% | FAIL |
| top20pct_vol_notrend | 0/6 | 0% | FAIL |
| top20pct_novol_trend | 0/6 | 0% | FAIL |
| **top20pct_novol_notrend** | **1/6** | **17%** | **FAIL** |

**전략 판정: FAIL — 전 Combo 폐기** (통과 기준 pass_rate ≥ 30% 미달)

---

## 4. 윈도우별 상세 결과 (최우수 combo: top20pct_novol_notrend)

| W | IS 기간 | OOS 기간 | IS Sharpe | OOS Sharpe | OOS MDD | OOS IR | OOS/IS Sharpe | 판정 |
|---|---------|---------|-----------|------------|---------|--------|---------------|------|
| W1 | 2021-04~2023-03 | 2023-04~2023-09 | -0.41 | 1.22 | -9.1% | 1.37 | 0.00 | FAIL (degrad) |
| W2 | 2021-10~2023-09 | 2023-10~2024-03 | 0.00 | **3.24** | -1.9% | 1.75 | 1474.5 | **PASS** |
| W3 | 2022-04~2024-03 | 2024-04~2024-09 | 0.49 | 0.09 | -12.2% | 0.77 | 0.19 | FAIL (Sharpe) |
| W4 | 2022-10~2024-09 | 2024-10~2025-03 | 0.90 | 0.35 | -8.1% | 0.51 | 0.39 | FAIL (Sharpe, degrad) |
| W5 | 2023-04~2025-03 | 2025-04~2025-09 | 0.79 | **2.99** | -0.7% | **-3.42** | 3.78 | FAIL (IR) |
| W6 | 2023-10~2025-09 | 2025-10~2026-04 | 1.67 | 1.75 | -16.4% | **-1.75** | 1.05 | FAIL (IR) |

> W2 pass_rate: OOS Sharpe 3.24, IR 1.75로 기준 모두 충족. 단, IS Sharpe ≈ 0이라 degrad 수치가 무의미(1474). 통계적 불안정.

---

## 5. 실패 분석

### 5.1 바인딩 제약: IR vs KOSPI 음수 (W5·W6)

최근 2년(2025~2026)에 **IR vs KOSPI가 -1.75~-3.42**로 크게 음수. 원인:

- 유니버스 = KOSPI 100 + **KOSDAQ 100** (혼합)
- 벤치마크 = KOSPI 지수 (순수 KOSPI)
- 2025년 KOSPI 급등 구간에서 KOSDAQ 종목 비중이 높은 포트폴리오는 벤치마크 대비 체계적으로 열위
- 즉, **벤치마크 미스매치** 구조 문제. 전략 자체의 실패가 아닐 수 있으나, 한국 시장에서 현실적인 초과수익은 KOSPI 대비 측정됨

### 5.2 OOS Sharpe 불안정

| W | OOS Sharpe |
|---|-----------|
| W1 | 1.22 |
| W2 | 3.24 |
| W3 | 0.09 |
| W4 | 0.35 |
| W5 | 2.99 |
| W6 | 1.75 |

Sharpe가 0.09 ~ 3.24 사이에서 비체계적으로 분포. OOS 성과가 운에 좌우되는 구조.

### 5.3 Vol filter (Hsu 2013 Low-vol anomaly) 효과 역전

모든 vol 조합이 0/6으로 novol 조합 대비 더 나쁨:
- vol_trend: 0/6, vol_notrend: 0/6
- novol_trend: 0/6, novol_notrend: 1/6

저변동성 필터가 한국 KOSPI+KOSDAQ 혼합 유니버스에서는 유효하지 않음. 이는 Hsu(2013)가 미국 시장 기반 연구이며, KOSDAQ 소형주의 높은 변동성 특성과 상충된다.

### 5.4 Top 10% vs 20% 차이 미미

top10pct vs top20pct 모두 유사한 실패 패턴. 포트폴리오 집중도가 주요 요인이 아님.

---

## 6. 구현 완료 사항

| 구성요소 | 파일 | 상태 |
|---------|------|------|
| 전략 파라미터 + 4개 핵심 함수 | `src/strategy/cross_momentum.py` | ✅ 구현, 커버리지 98% |
| 포트폴리오 백테스트 엔진 | `src/backtest/portfolio_engine.py` | ✅ 구현, 커버리지 97% |
| WF 스크립트 | `scripts/run_cross_momentum_wf.py` | ✅ 실행 완료 |
| 단위 테스트 (전략) | `tests/strategy/test_cross_momentum.py` | ✅ 28개 PASS |
| 단위 테스트 (엔진) | `tests/backtest/test_portfolio_engine.py` | ✅ 32개 PASS |
| WF 결과 | `docs/backtest-results/walk_forward_cross_momentum_full_20260427_193805.json` | ✅ 저장 |

look-ahead 방지, 실제 회전율 기반 거래비용, monthly Sharpe 연환산(×√12), IR vs 벤치마크 모두 정확히 구현됨.

---

## 7. 결론

Cross-sectional momentum (Jegadeesh-Titman 1993)이 한국 시장(KOSPI+KOSDAQ 172종목, 2021~2026)에서
walk-forward 기준을 통과하지 못했다.

**누적 폐기 6건**:

| # | 전략 | 폐기 근거 |
|---|------|----------|
| 1 | 5분봉 모멘텀 | 왕복비용 0.53% × 일 5거래 → 일 -2.65% 기댓값 |
| 2 | 52주 신고가 일봉 기본 grid | 20종목 0/20, OOS/IS 붕괴 |
| 3 | 52주 신고가 atr/tp 400 시나리오 | 0/20, 파라미터 공간 소진 |
| 4 | Pullback/Range/MR 일봉 (KOSPI 대형주) | 12 combo 0/20, 신호 희소·RR 미달 |
| 5 | Pullback/Range/MR 일봉 (KOSPI30+KOSDAQ30) | 27 combo 0/59, 거래 발생해도 수익 불가 |
| **6** | **Cross-sectional momentum (이번)** | **8 combo 0~1/6, IR vs KOSPI 음수·OOS 불안정** |

**→ 전략 카테고리 기준 재논의 필요.** 사용자 결정 대기.
