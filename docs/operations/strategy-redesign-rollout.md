---
name: strategy-redesign-rollout
description: 52주 신고가 일봉 전략 모의투자 재개 및 실전 전환 체크리스트
type: operations
status: 대기 — walk-forward 재검증 선행 필요
created: 2026-04-27
depends_on:
  - design-015-backtest-engine-integrity
  - design-016-strategy-redesign
  - design-017-risk-microstructure
---

# 전략 재설계 롤아웃 체크리스트

> **현재 상태**: walk-forward 20종목 결과 통과 0/20 (0%) → **모의투자 재개 전 파라미터 재조정 필수**

## 0. 현재 차단 상태 요약

| 항목 | 상태 | 근거 |
|------|------|------|
| 모의투자 | ⛔ 차단 | walk-forward 통과 0/20 (기준: 30%+) |
| 실전 전환 | ⛔ 차단 | 모의투자 미통과 |
| 파라미터 재조정 | ⚠️ 필요 | atr_tp_mult 4.0 → 6.0 이상 검토 |

---

## 1단계: 파라미터 재조정 + walk-forward 재검증

### 조치 사항

- [ ] `atr_tp_mult` 조정 (4.0 → 6.0 또는 tp_pct 상한 제거)
- [ ] `atr_stop_mult` 조정 (1.5 → 2.0 검토)
- [ ] 재조정 파라미터로 20종목 walk-forward 재실행
  ```bash
  python scripts/run_daily_backtest.py \
    --symbols [20종목] \
    --months 18 \
    --atr-tp 6.0 \
    --atr-stop 2.0
  ```
- [ ] 통과 기준 재확인:

| 기준 | 임계값 | 비고 |
|------|--------|------|
| OOS Sharpe | ≥ 1.0 | 완화 불가 |
| MDD | ≤ -15% | 개별 종목 기준으로 -10% → -15% 완화 고려 |
| 승률 | ≥ 35% | 유지 |
| RR | ≥ 1.5 | 2.0 → 1.5 완화 고려 (대형주 특성 반영) |
| 통과율 | ≥ 30% | 폐기 임계값 유지 |

### 완료 조건

- [ ] 통과 종목 6개 이상 (30%+) 확인
- [ ] JSON 결과를 `docs/backtest-results/`에 저장
- [ ] design-016 표 업데이트

---

## 2단계: 모의투자 재개 조건

1단계 완료 후 진행.

### 전제 조건

- [ ] walk-forward 통과 30%+ 달성
- [ ] T3 리스크 가드레일 모의투자 계좌에서 작동 확인
  - [ ] DrawdownGuard: HWM -5% STOP_BUY 트리거 확인
  - [ ] KillSwitch: SOFT_STOP / HARD_STOP 상태 전이 확인
- [ ] T4 마이크로구조 작동 확인
  - [ ] 지정가 주문 정상 체결 확인 (log 분석)
  - [ ] 11:30~13:00 구간 진입 차단 확인

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
- design-016: 전략 재설계 + walk-forward 결과 (파라미터 재조정 근거)
- design-017: 리스크 가드레일 + 마이크로구조 설계
- `.env.example`: 모의/실거래 전환 설정 키 목록
