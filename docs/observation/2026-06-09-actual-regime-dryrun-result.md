# 2026-06-09 실제 데이터 regime dry-run 결과

> **상태**: 실행 결과 기록 (read-only dry-run). **trading behavior 변경 없음.**
> **실행 주체**: Codex (2026-06-09 실제 시장/계좌 데이터로 R1~R4 파이프라인 실행).
> **본 문서 범위**: 결과 요약 + 안전 불변식 기록. 실계좌 금액(available_cash/holdings 등)은
> 본 repo 가 public 이므로 **커밋하지 않는다** (개인 금융정보). 정확한 수치는 로컬
> 미커밋 산출물(`outputs/regime/2026-06-09/`)에만 존재.

## 1. 파이프라인 (R1~R4) 실제 적용

R1(regime scorer) → R2(proposal overlay) → R3(read-only report) → R4(mixed allocation dry-run)
를 2026-06-09 실제 데이터로 1회 실행.

## 2. 현재 regime (R1/R3)

| 항목 | 값 |
|---|---|
| current regime | **`risk_off`** |
| confidence | **88** |
| flags | `REGIME_KOSDAQ_WEAK`, `REGIME_RISK_OFF_COOLDOWN`, `REGIME_VOL_SPIKE`, `REGIME_OVERHEAT_DISPERSION` |

**해석**: 장기 구조적 AI/반도체 상승장 자체는 유지되나, 6/8 급락 직후 **cooldown +
변동성 급등 + 과이격 + KOSDAQ 약세** 가 겹쳐 **오늘은 신규매수 확대 구간이 아니라
risk-off** 구간. → 신규매수 제한 / 보존이 regime 권장.

## 3. proposal overlay (R2)

- proposal 15건: **buy 1 / hold 11 / sell 3**.
- sell 3건은 confidence 85 → export 기준 boost_sell 분류. **자동 소비 0** (validator 수용만, 자동 매도/주문 연결 없음).
- R2 overlay 적용 후 buy 후보 1건 confidence **80 → 68** 감점 (risk_off buy caution).
- **action 변경 0.**

## 4. mixed allocation dry-run (R4)

- cross_momentum `enabled=true` (PR2a allowed_cash = available_cash × budget_pct 0.60).
- short_swing `enabled=false` (dry-run allowed_cash = available_cash × budget_pct 0.30, **실 활성화 아님**).
- total-equity budget 은 PR2b 전이라 diagnostic only.
- regime 권장: **신규매수 제한 / 보존** (risk_off).
- (정확한 KRW 금액은 본 문서 미수록 — §0 참조.)

## 5. 안전 불변식 (전부 확인)

| 항목 | 결과 |
|---|---|
| action 변경 | **0** |
| boost_sell 자동 소비 | **0** (loader 는 block_buy 만 소비) |
| orders | 154 (변화 없음) |
| trade_logs | 117 (변화 없음) |
| llm_decisions | 119 (변화 없음) |
| strategy_runtime | unchanged (cross_momentum:true / short_swing:false / multi_regime:false) |
| idle in transaction | 0 |
| 주문 / DB write / decision POST / broker order | 0 |

## 6. 결론

- 오늘 실제 데이터 기준 **regime = risk_off (88)**. 구조 상승장은 유지되지만 신규매수 확대가 아니라 cooldown/risk-off.
- R1~R4 파이프라인이 실제 데이터에서 의도대로 동작 (read-only, 거래 미발생).
- **실제 자동매매 확장은 여전히 보류** — PR 2b(total-equity budget) / PR 3(ownership·sell authority) + 6/15 본 관찰 이후. 현재 baseline 은 cross_momentum 단독.

> 본 문서는 결과 기록 전용. 코드/거래 동작 변경 없음. (R4 blocker 문구 정정은 별도 PR #537.)
