---
name: strategy-redesign-rollout
description: 전략 롤아웃 체크리스트 — 52주 신고가 폐기(ADR-018) 후 후속 전략 검증 및 모의투자 전환 관리
type: operations
status: 차단 — 52주 신고가 폐기 확정, 후속 전략(Pullback/Range) walk-forward 필요
created: 2026-04-27
updated: 2026-04-27
depends_on:
  - design-015-backtest-engine-integrity
  - design-016-strategy-redesign
  - design-017-risk-microstructure
  - design-018-strategy-rerun
---

# 전략 재설계 롤아웃 체크리스트

> **현재 상태 (2026-04-27 갱신)**:
> - 52주 신고가 일봉 전략 **폐기 확정** (파라미터 20개 조합 전부 0/20 — ADR-018)
> - design-013 multi-regime 배선 완성 (skeleton → 완전, PR #334)
> - **모의투자 차단 유지** — Pullback/Range 전략 walk-forward 통과 전까지

## 0. 현재 차단 상태 요약

| 항목 | 상태 | 근거 |
|------|------|------|
| 모의투자 | ⛔ 차단 | 52주 신고가 폐기 + Pullback/Range walk-forward 미완료 |
| 실전 전환 | ⛔ 차단 | 모의투자 미통과 |
| `USE_MULTI_REGIME` 활성화 | ⛔ 금지 | Pullback/Range 단독 walk-forward 선행 필요 |
| 52주 신고가 파라미터 재조정 | ✅ 완료(폐기) | 20 grid × 20종목 전 조합 0% — ADR-018 §2 |

---

## 1단계: 후속 전략 선택 + walk-forward 검증

ADR-018 §5에서 정의한 세 옵션 중 하나를 선택한다. **권고 순서: B → A → C**

### 옵션 B (권고): Pullback/Range 전략 단독 walk-forward

#### 전제 확인

- [ ] `src/backtest/daily_engine.py`가 PullbackStrategy/RangeStrategy 시뮬레이션 지원하는지 확인
  - 지원 가능: 옵션 B 직접 진행
  - 지원 불가: 엔진 확장 또는 옵션 A 전환
- [ ] `USE_MULTI_REGIME=true` 환경변수 설정 후 로컬 테스트 실행

#### 실행

```bash
# 환경 변수 활성화 (테스트 전용)
export USE_MULTI_REGIME=true

# Pullback 전략 단독 walk-forward
python scripts/run_daily_backtest.py \
  --strategy pullback \
  --symbols [20종목] \
  --months 18

# Range 전략 단독 walk-forward
python scripts/run_daily_backtest.py \
  --strategy range_trade \
  --symbols [20종목] \
  --months 18
```

#### 통과 기준

| 기준 | 임계값 | 비고 |
|------|--------|------|
| OOS Sharpe | ≥ 1.0 | 완화 불가 |
| MDD | ≤ -15% | 완화 고려 가능 |
| 승률 | ≥ 35% | 유지 |
| RR | ≥ 1.5 | Pullback 특성 반영 (완화) |
| OOS/IS 일관성 | ≥ 0.7 | ADR-018 핵심 실패 원인 — 완화 불가 |
| **통과율** | **≥ 30% (6종목+)** | **미달 시 해당 전략 폐기** |

#### 완료 조건

- [ ] 통과 종목 6개 이상 확인
- [ ] JSON 결과를 `docs/backtest-results/`에 저장
- [ ] design-013 표 업데이트 (검증 완료 상태로)

### 옵션 A (차선): 소형주/중형주 유니버스로 52주 신고가 재검증

- [ ] KOSPI 소형주/중형주 20종목 선정 기준 정의 (시가총액 하한·상한, 거래대금 최소 기준)
- [ ] 동일 walk-forward 재실행 (기존 MomentumDailyStrategy 재활용)
- [ ] 위 통과 기준 동일 적용

### 옵션 C (보조): 레짐 필터 강화 (BULL_STRONG만 진입)

- 옵션 A/B가 모두 실패한 경우에만 검토
- 신호 희소화로 통계적 유의성 확보가 어려울 수 있음 — 50종목+ 확장 고려 필요

---

## 2단계: 모의투자 재개 조건

1단계 완료(후속 전략 walk-forward ≥ 30%) 후 진행.

### 전제 조건

- [ ] 후속 전략(옵션 B/A/C) walk-forward 통과 30%+ 달성
- [ ] `USE_MULTI_REGIME=true` 활성화 여부 결정 (옵션 B 선택 시)
  - 활성화 시: T2 배선 절차 참조 (`_assign_symbol_strategies` 동작 확인)
  - 비활성화 시: `USE_MULTI_REGIME=false` 유지, 선택 전략 단독 경로 확인
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
- design-013: multi-regime 아키텍처 (배선 완성, walk-forward 검증 대기)
- `.env.example`: 모의/실거래 전환 설정 키 목록 (`USE_MULTI_REGIME` 포함)
