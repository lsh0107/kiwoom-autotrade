---
name: design-017-risk-microstructure
description: T3 리스크 가드레일(HWM/cooldown/auto kill_switch) + T4 마이크로구조(지정가/점심차단/동적유니버스) 통합 설계
type: design
status: 활성 (PR #327 T3, PR #325 T4 머지 완료)
created: 2026-04-27
depends_on:
  - design-015-backtest-engine-integrity
  - design-016-strategy-redesign
related:
  - src/trading/drawdown_guard.py
  - src/trading/kill_switch.py
  - scripts/live_trader.py
  - scripts/screen_symbols.py
  - tests/trading/test_drawdown_guard.py
  - tests/trading/test_kill_switch.py
  - tests/scripts/test_microstructure.py
pr: "#327 (T3 리스크 가드레일), #325 (T4 마이크로구조)"
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-27 | PR #325 (T4) dev 머지 완료 — 지정가/점심차단/동적유니버스 |
| 2026-04-27 | PR #327 (T3) dev 머지 완료 — HWM drawdown/cooldown/auto kill_switch |

# Design 017: 리스크 가드레일 + 마이크로구조 통합 (ADR-017)

## 1. 배경

T1/T2로 백테스트 현실화를 완료했으나, 실거래 환경에서 추가로 두 가지 레이어가 필요했다:

1. **리스크 가드레일 (T3)**: 드로우다운 한도, 연속 손절 대응, 자동 거래 중단
2. **마이크로구조 (T4)**: 체결 품질 개선, 저유동성 시간대 회피, 동적 유니버스 필터

## 2. T3 리스크 가드레일

### 2-1. HWM(High-Water Mark) 드로우다운 관리

**구현 위치**: `src/trading/drawdown_guard.py`

```
당일 최고 평가액(HWM) 기준 드로우다운:
  -5%: STOP_BUY (신규 매수 중단)
  -7%: FORCE_CLOSE (전량 청산)
  
주간 손실:
  -6%/주: 투자금 80%로 축소
```

**설계 의도**:
- 일중 최고점 대비 하락을 실시간 추적 → 단순 일별 손익보다 정밀한 제어
- STOP_BUY 후 회복 시 자동 해제 (동일 거래일 내)
- FORCE_CLOSE는 수동 확인 후 resume 가능

**트레이드오프**:
- -5% STOP_BUY: 모의투자 기준으로 공격적. 실거래 전환 시 -3%로 강화 권고
- 일중 변동성이 높은 종목(셀트리온, SK이노베이션)은 빈번한 STOP_BUY 발생 가능
- 완화: STOP_BUY가 반드시 손실 구간인 것은 아님 (수익 구간에서도 발동)

### 2-2. Auto Kill Switch (자동 거래 중단)

**구현 위치**: `src/trading/kill_switch.py` — `AutoKillSwitchMonitor`

3종 자동 트리거:

| 트리거 | 조건 | 결과 |
|--------|------|------|
| 연속 손절 | 동일 종목 3회 연속 손절 | SOFT_STOP |
| 단기 PnL | 10분 슬라이딩 윈도우 누적 -1.5% | SOFT_STOP |
| 주문 과다 | 일일 40건 초과 | SOFT_STOP |
| | 일일 60건 초과 | HARD_STOP |

**상태 전이**:
```
normal → soft_stopped → (resume) → normal
normal → hard_stopped → (confirm=True resume) → normal
soft_stopped → hard_stopped
```

**파일 기반 영속화**: `.kill_switch_state.json` — 서버 재시작 후에도 상태 유지

### 2-3. Cooldown 메커니즘

연속 손절 감지 후 **cooldown 기간**:
- SOFT_STOP 이후 30분 대기 → 자동 normal 복귀 가능 여부 평가
- HARD_STOP: 반드시 수동 confirm=True 필요

### 2-4. live_trader 통합 게이트 순서

```
진입 시도
  │
  ├─ [1] KillSwitch.check() → HARD/SOFT_STOP → 즉시 차단
  │
  ├─ [2] DrawdownGuard.check() → STOP_BUY → 신규 매수 차단
  │       → FORCE_CLOSE → 전량 청산 실행
  │
  ├─ [3] is_entry_blocked(current_time) → 점심/변동성 시간대 차단
  │
  ├─ [4] 동적 유니버스 필터 통과 여부 확인
  │
  └─ [5] 체결 (지정가 우선 → 시장가 fallback)
```

## 3. T4 마이크로구조

### 3-1. 지정가 주문 우선

**구현 위치**: `scripts/live_trader.py` — `execute_buy()`, `execute_sell()`

```
매수 체결 흐름:
  호가 조회 (Orderbook) → 1호가(매도) = limit_price
  → 지정가 주문 제출
  → 호가 조회 실패 시: 시장가 fallback

매도 체결 흐름:
  긴급 청산 사유(stop_loss, max_holding): 시장가
  목표 달성 사유(take_profit, trailing_stop): 지정가 (1호가 매수)
```

**트레이드오프**:
- 지정가 미체결 위험: 빠르게 상승하는 종목에서 매수 기회 놓칠 수 있음
- 완화: 1호가 기준으로 체결 가능성 최대화. 3분 내 미체결 시 시장가 전환 (구현 예정)

### 3-2. 점심 시간대 진입 차단

**구현 위치**: `scripts/live_trader.py` — `is_entry_blocked()`

```python
ENTRY_BLOCKED_WINDOWS: list[tuple[str, str]] = [
    ("1130", "1300"),  # 점심 저유동성 구간
]
BLOCK_OPEN_VOLATILITY: bool = False  # 09:00~09:30 차단 (기본 비활성)
```

**근거**: 점심 시간대(11:30~13:00) 실패 집중 분석 결과. 거래대금이 평균의 30~40%로 감소 → 슬리피지 증가 + 추세 노이즈 비율 증가.

**설정 가능**: `ENTRY_BLOCKED_WINDOWS` 리스트로 커스텀 차단 구간 설정 가능.

### 3-3. 동적 유니버스 필터

**구현 위치**: `scripts/screen_symbols.py` — `apply_dynamic_filters()`

진입 전 실시간 필터:

| 필터 | 기준 | 목적 |
|------|------|------|
| 거래대금 | 최소 X억 (설정 가능) | 저유동성 종목 제외 |
| 스프레드 | 호가 스프레드 Y% 이하 | 슬리피지 최소화 |
| 당일 변동폭 | ATR 기준 정상 범위 | 이상 급등락 종목 제외 |

**LLM 결정 연동** (design-010 참조):
- `universe_adjust.exclude`: LLM이 제외 권고한 종목 자동 필터링
- `symbol_bias.block_buy`: 특정 종목 매수 차단

## 4. 통합 동작 — live_trader 흐름

```
사전 스크리닝 (Airflow DAG, 장전)
  └─ screen_symbols.py → 기본 유니버스 구성

장중 루프
  ├─ KOSPI 레짐 갱신 (10시, 11시)
  ├─ 동적 유니버스 필터 재적용 (design-013 거래량 override)
  │
  └─ 종목별 신호 확인
      ├─ [T3] KillSwitch 체크
      ├─ [T3] DrawdownGuard 체크
      ├─ [T4] 시간대 차단 체크
      ├─ [T2] 52주 신고가 신호 확인
      └─ [T4] 지정가 주문 제출
```

## 5. 리스크 파라미터 설정 (모의투자 기준)

| 파라미터 | 현재값 | 실거래 전환 시 권고 |
|----------|--------|-------------------|
| DRAWDOWN_STOP_BUY_PCT | -5.0% | -3.0% |
| DRAWDOWN_FORCE_CLOSE_PCT | -7.0% | -5.0% |
| WEEKLY_LOSS_SCALE_PCT | -6.0% | -4.0% |
| 연속 손절 SOFT_STOP | 3회 | 2회 |
| 10분 PnL SOFT_STOP | -1.5% | -1.0% |
| 일일 주문 SOFT_STOP | 40건 | 20건 |

## 6. 알려진 한계 및 후속 과제

- [ ] 지정가 미체결 시 자동 시장가 전환 (3분 타임아웃)
- [ ] HWM 드로우다운이 미실현 손익 포함 실시간 계산인지 검증 (현재 실현 손익 기반 추정)
- [ ] 점심 차단 구간 확장성: 현재 하드코딩, DB 설정화 예정
- [ ] BLOCK_OPEN_VOLATILITY 실거래 데이터 기반 검증 (현재 기본 비활성)
