# Korea Regime Report (read-only) — 2026-06-09

> source: `ai-hedge-fund-lab (example, fixture)` · **read-only dry-run** (POST 0 / DB write 0 / orders 0 / trade_logs 0 / broker order 0)

## 현재 regime

- **structural_bull** (confidence 74)

## 전략 유불리 (정성, 주문 영향 없음)

- **cross_momentum**: favorable (core 추세 유지)
- **short_swing**: favorable (모멘텀 지속)

## 최근 regime timeline 요약

- structural_bull: 3일
- bull_overheat: 1일
- volatile_bull: 1일
- risk_off: 1일

## 현재 proposal overlay dry-run

- proposal 4건 · action 변경 **0** · boost_sell 신규생성 **0**

| symbol | action | conf before→after | bias before→after | added flags |
|---|---|---|---|---|
| 005930 | buy | 75→83 | boost_buy→boost_buy | REGIME_OVERLAY_STRUCTURAL_BULL_SUPPORT |
| 000660 | sell | 70→70 | review_sell→review_sell | REGIME_OVERLAY_STRUCTURAL_BULL_SELL_CAUTION |
| 042700 | buy | 62→70 | boost_buy→boost_buy | REGIME_OVERLAY_STRUCTURAL_BULL_SUPPORT |
| 035720 | hold | 55→55 | None→None |  |

## kiwoom 호환 view

- 허용 bias: block_buy, block_sell, boost_buy, boost_sell, review_sell
- 미허용(표시용): 없음
- boost_sell kiwoom 호환: **True**
- note: bias vocabulary alignment 후 boost_sell 도 kiwoom validator 수용. 단 validator 수용 != 자동 소비 — boost_sell 은 자동 매도/주문으로 연결되지 않는다 (소비는 review_sell 까지만, loader 는 block_buy 만). block_sell 은 deprecated(호환 수용). unsupported_biases 는 validator 미허용 어휘만 표기한다.
