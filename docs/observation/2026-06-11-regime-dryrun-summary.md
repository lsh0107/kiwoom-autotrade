# Regime daily dry-run summary — 2026-06-11

> public-safe 요약 (실계좌 금융정보 미포함). read-only dry-run, 거래 0.

- **regime**: `risk_off` (confidence 94)
- flags: REGIME_KOSDAQ_WEAK, REGIME_DRAWDOWN, REGIME_RISK_OFF_COOLDOWN, REGIME_VOL_SPIKE, REGIME_OVERHEAT_DISPERSION
- timeline 요약: {'structural_bull': 2, 'bull_overheat': 5, 'volatile_bull': 1, 'risk_off': 2}

## proposal overlay

- proposal 15건 · action 변경 **0** · boost_sell 자동소비 **0** · boost_sell 신규생성 **0**

## sleeves (enabled / budget_pct 비율만)

| 전략 | enabled | budget_pct | regime 권장 |
|---|---|---|---|
| cross_momentum | True | 0.6 | 신규매수 제한 (보존) |
| short_swing | False | 0.3 | 신규매수 제한, review_sell evidence 만 |

## 안전 (전후 검증)

- orders Δ 0 · trade_logs Δ 0 · llm_decisions Δ 0
- strategy_runtime 변경 False · idle in tx 0 · broker order 0 · decision POST 0

## 활성화 blocker

- PR 2b total-equity budget 미구현 (현재 available_cash*budget_pct 현금 기준만)
- PR 3 ownership / sell authority 미구현 (전략별 보유/청산 권한 분리 안 됨)
- boost_sell 자동 소비 미개방 (validator 는 수용하지만 자동 매도/주문 연결 금지)
