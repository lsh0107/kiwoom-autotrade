# Mixed Allocation Dry-run (read-only) — 2026-06-09

> source: `example (read-only snapshot)` · **read-only** (enabled 변경 0 / 주문 0 / DB write 0 / POST 0 / broker order 0)

## 현재 regime: **structural_bull** (confidence 74)

## 계좌 (read-only snapshot)

- available_cash: 100,000,000
- holdings 평가액: 60,000,000
- total_equity: 160,000,000

## Sleeve 배분 (cross_momentum + short_swing 동시 가정)

| 전략 | enabled | budget_pct | max_order | PR2a allowed_cash | total-equity(diag) | regime 권장 |
|---|---|---|---|---|---|---|
| cross_momentum | True | 0.6 | 50,000,000 | 60,000,000 | 96,000,000 | core 유지 |
| short_swing | False | 0.3 | 5,000,000 | 30,000,000 | 48,000,000 | 소액 보조 가능 |

> PR2a allowed_cash = 현재 실제 사이징 기준 (available_cash x budget_pct).
> total-equity(diag) 는 PR 2b 전이라 **참고용 (미적용)**.

## 실제 동시 매매 활성화 전 blocker

- PR 2b total-equity budget 미구현 (현재 available_cash*budget_pct 현금 기준만)
- PR 3 ownership / sell authority 미구현 (전략별 보유/청산 권한 분리 안 됨)
- bias vocabulary alignment 미완료 (lab boost_sell vs kiwoom block_sell)

> 본 보고서는 dry-run. short_swing enabled=true 전환/주문 없음.
