---
name: strategy-redesign-rollout
description: 전략 롤아웃 체크리스트 — 누적 폐기 5건(ADR-020) 후 cross-sectional momentum V2 PASS (ADR-021). ADR-022 어댑터 설계 + 모의 4주 대기.
type: operations
status: 차단 → ADR-021 PASS, ADR-022 어댑터 설계 대기
created: 2026-04-27
updated: 2026-04-27
depends_on:
  - design-015-backtest-engine-integrity
  - design-016-strategy-redesign
  - design-017-risk-microstructure
  - design-018-strategy-rerun
  - design-019-pullback-range-validation
  - design-020-extended-validation
  - design-021-cross-sectional-momentum
---

# 전략 재설계 롤아웃 체크리스트

> **현재 상태 (2026-04-27 갱신 — ADR-021)**:
> - 52주 신고가 일봉 전략 **폐기 확정** (파라미터 20개 조합 전부 0/20 — ADR-018)
> - Pullback/Range/MR 일봉 어댑터 **폐기 확정** (12 combo × 20종목 0/20 — ADR-019)
> - **확장 검증 완료 → 일봉(daily) timeframe Pullback/Range/MR 폐기** (27 combo × 59종목 0/59 — ADR-020). **주봉/이주봉/월봉 timeframe은 별개 검증 대상으로 보존 (옵션 (e))**
> - **ADR-021: Cross-sectional momentum V2 기준 PASS** — top20pct_novol_notrend (2/6 = 33%). 모의 진입 후보 확정.
> - design-013 multi-regime 배선 완성 (skeleton → 완전, PR #334)
> - **모의투자 차단 유지** — ADR-022 어댑터 설계 + 모의 4주 관찰 전까지
> - `USE_MULTI_REGIME=false` 유지 — cross-momentum은 별도 어댑터(ADR-022) 필요

## 0. 현재 차단 상태 요약

| 항목 | 상태 | 근거 |
|------|------|------|
| 모의투자 | ⛔ 차단 | ADR-022 어댑터 설계 + 모의 4주 관찰 필요 |
| 실전 전환 | ⛔ 차단 | 모의투자 미통과 |
| `USE_MULTI_REGIME` 활성화 | ⛔ 금지 | cross-momentum 별도 어댑터(ADR-022) 필요 |
| 52주 신고가 파라미터 재조정 | ✅ 완료(폐기) | 20 grid × 20종목 전 조합 0% — ADR-018 §2 |
| Pullback/Range/MR walk-forward | ✅ 완료(폐기) | 12 combo × 20종목 전 조합 0% — ADR-019 §3~5 |
| 확장 검증 (60종목, 3년, 27 combo) | ✅ 완료(폐기) | 27 combo × 59종목 전 조합 0%, **일봉 timeframe** 제외 (주봉~월봉은 보존) — ADR-020 |
| **Cross-sectional momentum WF** | ✅ **PASS (ADR-021)** | top20pct_novol_notrend 2/6 (33%) — V2 기준 |

---

## 1단계: 후속 전략 선택 + walk-forward 검증

ADR-021 §9 결정: **Cross-sectional momentum (top20pct_novol_notrend) V2 기준 PASS. 모의 진입 후보 확정.**

> ✅ **옵션 (a) Cross-sectional momentum (ADR-021 PASS)**: top20pct_novol_notrend 2/6 (33%) V2 PASS.  
> 단, ADR-022(live_trader 어댑터) 설계 완료 + 모의 4주 관찰 후 실전 전환.

> 보존 후보 (ADR-021 이후):
> - **(e) 주봉/이주봉/월봉 timeframe Pullback/Range/MR 재검증** — pykrx 일봉 resample, 노이즈/거래비용 비율이 일봉과 본질적으로 다름

### ~~옵션 A: KOSPI 소형/중형주 유니버스로 Pullback/Range/MR 재검증~~ (ADR-020 폐기 확정)

**ADR-020 결과**: KOSPI30+KOSDAQ30 59종목, 3년, 27 combo 확장 검증 → 0/59 폐기 확정.
신호 희소성 가설 기각 (OOS 31% 윈도우 거래 발생). 카테고리 자체 수익 불가 구조 확인.
→ **일봉(daily) timeframe Pullback/Range/MR 재검증 불필요 — 일봉 한정 폐기. 주봉~월봉은 옵션 (e)로 보존.**

상세 결과: [ADR-020](docs/design/design-020-extended-validation.md) §3~6 참조

### Cross-sectional Momentum (ADR-021 PASS)

**ADR-021 결과**: KOSPI100+KOSDAQ100 172종목, 5년, 8 combo WF 실행.  
V2 기준(IR 0.3, IS Sharpe ≤ 0 윈도우 OOS/IS ratio 면제) 재집계 → **top20pct_novol_notrend 2/6 (33%) PASS**.

- best combo OOS Sharpe 평균(6W): 1.61 / best combo OOS Return 평균(6W): +22.5%
- V2 PASS 윈도우: W1(OOS Sharpe 1.22, IR 1.37, +15.8%), W2(OOS Sharpe 3.24, IR 1.75, +40.3%)
- W5·W6 IR 음수: 벤치마크 KOSPI 강세로 절대수익 양수지만 인덱스 underperform — 구조적 한계 인지

→ **모의 진입 후보 확정. ADR-022 어댑터 설계 후 진행.**

상세 결과: [ADR-021](docs/design/design-021-cross-sectional-momentum.md) §6~9 참조

---

## 2단계: 모의투자 재개 조건

1단계 완료(ADR-022 어댑터 구현) 후 진행.

### 전제 조건 (ADR-021 기준 갱신)

- [ ] **Cross-sectional momentum best combo (top20pct_novol_notrend)** — ADR-021 V2 PASS 확인 ✅
- [ ] **ADR-022 어댑터 설계 완료** — live_trader portfolio rebalance 어댑터 구현 (월말 ranking → 매수/매도 큐 전달)
- [ ] **모의 4주 관찰** — V2 기준 OOS Sharpe ≥ 1.0, MDD ≥ -25% 달성 여부 확인
- [ ] `USE_MULTI_REGIME=false` 유지 — cross-momentum은 별도 어댑터 경로 사용
  - cross-momentum 어댑터 구현 시: `_assign_symbol_strategies` 우회, 월말 ranking 스케줄러 별도 등록
- [ ] T3 리스크 가드레일 모의투자 계좌에서 작동 확인
  - [ ] DrawdownGuard: HWM -5% STOP_BUY 트리거 확인
  - [ ] KillSwitch: SOFT_STOP / HARD_STOP 상태 전이 확인
- [ ] T4 마이크로구조 작동 확인
  - [ ] 지정가 주문 정상 체결 확인 (log 분석)
  - [ ] 11:30~13:00 구간 진입 차단 확인

### `USE_MULTI_REGIME=true` 활성화 절차 (옵션 B 선택 시)

```bash
# 1. .env에 플래그 추가
echo "USE_MULTI_REGIME=true" >> .env

# 2. live_trader 재기동 (is_mock_trading=True 확인)
bash scripts/start_trading.sh

# 3. regime 분배 로그 확인 (시작 직후 3분 내)
tail -f logs/live_trader.log | grep -E "(MarketStyle|assign_strategy|REGIME_WEIGHTS)"

# 4. 예상 로그 예시 (TREND_BULL_STRONG 레짐일 때)
# [INFO] MarketStyle: TREND_BULL_STRONG
# [INFO] assign_strategy: 005930 -> momentum(0.70), pullback(0.30)
```

### 최소 검증 표본

| 지표 | 최소 기준 |
|------|-----------|
| 진입 신호 발생 건수 | 10건 이상 (모의투자 시작 후) |
| 레짐 분류 정상 동작 | 3일 연속 로그 확인 |
| MDD 발동 없음 | 첫 1주 STOP_BUY/FORCE_CLOSE 없음 |

### 모의투자 시작 절차

```bash
# 1. kill_switch 상태 초기화
# 2. live_trader.py 시작 (is_mock_trading=True 확인)
bash scripts/start_trading.sh

# 3. 로그 모니터링
tail -f logs/live_trader.log | grep -E "(진입|청산|STOP|killswitch)"
```

### 관찰 기간

**최소 2주, 권장 4주**

| 주차 | 확인 사항 |
|------|----------|
| 1주 | 진입 신호 발생 빈도 (목표: 주 3~5건) |
| 1주 | 가드레일 발동 빈도 (STOP_BUY 과다 시 임계값 재조정) |
| 2주 | 누적 PnL 추세 방향 확인 |
| 2~4주 | OOS 기간 성과 vs 백테스트 비교 |

---

## 3단계: 소액 실전 전환 전 최종 확인

모의투자 2~4주 완료 후.

### 필수 확인 사항

- [ ] 모의투자 누적 PnL ≥ 0% (손실 구간 진입 시 차단)
- [ ] 실전 vs 백테스트 성과 비율 ≥ 50%
  - 실전 Sharpe / 백테스트 OOS Sharpe ≥ 0.5
- [ ] MDD 관찰값 ≤ -10% (모의투자 기간 중)
- [ ] 가드레일 비정상 발동 없음 (HARD_STOP 0회)
- [ ] API 연결 안정성 확인 (접속 오류 0회)

### 파라미터 조정 사항 (실거래 강화)

| 파라미터 | 모의투자 | 실거래 |
|----------|----------|--------|
| DRAWDOWN_STOP_BUY_PCT | -5.0% | **-3.0%** |
| DRAWDOWN_FORCE_CLOSE_PCT | -7.0% | **-5.0%** |
| 연속 손절 SOFT_STOP | 3회 | **2회** |
| 일일 주문 SOFT_STOP | 40건 | **20건** |
| max_positions | 3 | **2** (초기) |

### 실전 전환 절차

```bash
# .env에서 MOCK_TRADING=False 설정 (명시적 변경 필요)
# 초기 투자금: 전체 가용 자금의 10~20% (소액 테스트)
# 1주 관찰 후 이상 없으면 점진적 증액
```

---

## 4단계: 중단 조건 (자동 + 수동)

### 자동 중단 (Kill Switch)

| 조건 | 동작 |
|------|------|
| 일일 HWM 드로우다운 -7% | FORCE_CLOSE (전량 청산) |
| 주간 손실 -6% | 투자금 80% 축소 |
| 동일 종목 3회 연속 손절 | SOFT_STOP |
| 10분 PnL -1.5% | SOFT_STOP |

### 수동 중단 — 실전 성과 vs 백테스트 50% 이하

다음 중 하나 발생 시 즉시 실전 중단 → 모의투자 복귀:

- [ ] **실전 누적 수익률 < OOS 기대수익률의 50%** (4주 기준)
- [ ] **실전 MDD > 백테스트 MDD × 1.5** (예: 백테스트 MDD -10% → 실전 -15% 초과)
- [ ] **승률 < 25%** (모의 검증값의 절반 이하)
- [ ] **API 연결 장애 3회 이상** (연속 또는 일간)

### 중단 절차

```bash
# 1. 즉시 전량 청산
# live_trader.py에서 manual kill_switch 활성화

# 2. 포지션 확인
curl -X GET http://localhost:8000/api/v1/orders?status=open

# 3. 원인 분석 후 모의투자 재개 여부 결정
```

---

## 참조 문서

- design-015: 백테스트 엔진 무결성 (slippage/MDD/look-ahead)
- design-016: 전략 재설계 + walk-forward 결과 (52주 신고가 **폐기 확정**)
- design-017: 리스크 가드레일 + 마이크로구조 설계
- design-018: 파라미터 재검증 결과 통합 (ADR-018) + 후속 전략 옵션 분석
- design-019: Pullback/Range/MR walk-forward 결과 + 누적 폐기 4건 패턴 분석 (**ADR-019**)
- design-020: 확장 검증 (KOSPI30+KOSDAQ30 59종목, 3년, 27 combo) + **일봉 timeframe** Pullback/Range/MR 폐기 (주봉~월봉은 보존, **ADR-020**)
- **design-021**: **Cross-sectional momentum V2 PASS** — top20pct_novol_notrend 33%, 모의 진입 후보 (**ADR-021**)
- design-013: multi-regime 아키텍처 (배선 완성, cross-momentum 어댑터 별도)
- `.env.example`: 모의/실거래 전환 설정 키 목록 (`USE_MULTI_REGIME` 포함)
