---
name: Phase 1 리스크 관리 개선 작업 명세
description: 거래세 업데이트 + ATR 동적 손절(바닥+필터) + 단계적 리스크 관리 + 강제매수 제거 + 섹터 제한
type: project
---

# Phase 1: 리스크 관리 개선 — 작업 명세서 v2

> 작성일: 2026-03-13 | 근거: research-market-analysis-2026-03.md
> **상태**: 활성
> **v2 갱신 (19:30)**: 6개 설계 이슈 검증 후 수정 반영 (세션 로그 참조)

## 배경 요약

| 문제 | 현재 | 수정 후 |
|------|------|---------|
| 거래세 코드 | 0.18% (2025년) | **0.20%** (2026년 KOSPI) |
| 손절 방식 | 고정 -0.5% (모든 종목 동일) | **ATR 기반 동적** (바닥 0.5% + 변동성 필터) |
| R:R 비율 | 1:3 (고정) / 문서 불일치 | **1:2 통일** (SL=1.5×ATR, TP=3.0×ATR) |
| 리스크 관리 | 없음 | **단계적**: 2연패→50%축소, 3연패→블랙리스트 |
| 강제 매수 | 13:00에 매매 0건이면 강제 매수 | **제거** |
| 섹터 제한 | 없음 | 같은 테마 **최대 1개** |
| 강제 청산 시각 | 14:00 (코드) / 14:30 (주석) / 15:25 (문서) | **15:15 통일** |
| kill_switch | 구현됨 but 미연결 | **live_trader에 연결** |

---

## PR-A: 거래세율 업데이트 + 강제매수 제거

### 변경 파일

#### 1. `src/backtest/strategy.py` (라인 41)
```python
# 변경 전
tax_rate: float = 0.0018  # 매도 시 거래세 0.18%

# 변경 후
tax_rate: float = 0.0020  # 매도 시 거래세 0.20% (2026년 KOSPI: 0.05% + 농특세 0.15%)
```

#### 2. `src/backtest/strategy.py` — calc_trade_pnl 주석 수정
```python
# 변경 전
# 왕복 비용: 매수 수수료 + 매도 수수료 + 매도 거래세
# = 0.015% + 0.015% + 0.18% = 약 0.21%

# 변경 후
# 왕복 비용: 매수 수수료 + 매도 수수료 + 매도 거래세
# = 0.015% + 0.015% + 0.20% = 약 0.23%
```

#### 3. `scripts/live_trader.py` (라인 402-403)
```python
# 변경 전
tax_rate = 0.0018

# 변경 후
tax_rate = 0.0020  # 2026년 KOSPI 거래세 0.20%
```

#### 4. `scripts/live_trader.py` — 강제매수 로직 제거

삭제 대상:
- `FORCE_BUY_TIME = "1300"` (라인 653)
- `force_buy_best()` 함수 전체 (라인 574-650)
- 폴링 모드 호출부 (라인 688-690)
- WebSocket 모드 호출부 (라인 845-849)
- `force_buy_done` 변수 선언부

**근거**: 필터를 모두 통과하지 못한 상황에서 강제로 매수하는 것은
"물고기가 없는 곳에서 억지로 낚싯대 던지기". 거래 비용만 발생.

#### 5. 테스트 업데이트
- `tests/backtest/test_strategy.py` — `tax_rate` 기본값 검증이 있으면 0.0020으로 수정
- `tests/test_live_trader.py` — force_buy 관련 테스트 제거/수정

---

## PR-B: ATR 기반 동적 손절/익절 활성화

### 개념

```
고정 손절:   삼성전자 -0.5%, HPSP -0.5%  → HPSP에서 노이즈에 빈번히 걸림
동적 손절:   삼성전자 -1.2%, HPSP -3.5%  → 각 종목의 정상 변동폭 반영
```

### v2 핵심 변경: 바닥값 + 변동성 필터 + R:R 1:2 확정

#### 설계 결정 근거

**문제 1 — 저변동성 종목에서 손절폭 < 거래비용**:
```
ATR% = 0.2% → dynamic_stop = -(0.2% × 1.5) = -0.3%
왕복 비용 = 0.23% → 손익분기 최소 0.46% → 거래할수록 손실
```

**해결**: 2단계 방어 (Kevin Davey floor 패턴 + 변동성 필터)
1. **변동성 필터** (우선): ATR% < 0.35% → 진입 스킵
   - 0.35% × 1.5 = 0.525% > 0.46% (손익분기 통과)
   - 필터 통과 종목은 자동으로 바닥 이상의 SL 보장
2. **바닥값** (안전장치): `dynamic_stop = -max(ATR% × 1.5, 0.005)`
   - 필터를 통과했지만 ATR이 경계값인 종목 보호

**문제 2 — R:R 비율 불일치**:
- design-002-strategy.md: 4.5×ATR (R:R 1:3)
- design-003-risk-management.md: 3.0×ATR (R:R 1:2)

**결정: R:R = 1:2 (TP = 3.0×ATR)**

| 근거 | 상세 |
|------|------|
| 한국 시장 특성 | 일중 모멘텀 약함 (KAIST, MDPI 연구). 4.5×ATR은 하루에 비현실적 |
| 백테스트 실증 | HPSP: R:R 1:2 PF 4.12 > R:R 1:3 PF 3.23 |
| 승률 열화 | TP 멀어질수록 승률 하락 (75% → 67%), 기대값 상쇄 |
| 비용 효율 | ATR 기반 1:2의 BE 승률 ~37% (기대 승률 40-50%에서 충분한 마진) |

**비용 포함 손익분기 승률 비교**:
```
R:R 1:2 (ATR 1.6%): SL=2.4%, TP=4.8% → BE = (2.4+0.23)/(4.8+2.4) = 36.5%
R:R 1:3 (ATR 1.6%): SL=2.4%, TP=7.2% → BE = (2.4+0.23)/(7.2+2.4) = 27.4%
→ 1:3이 BE 승률은 낮지만, 먼 TP에 도달하는 빈도가 너무 낮아 실전에서 열위
```

**ATR 미산출 시**: 진입 스킵 (고정값 폴백 사용 안 함)
- R:R 혼재(동적 1:2 / 고정 1:3)는 기대값 계산 불안정
- 최후 수단 폴백 필요 시: 고정 SL=-2%, TP=+4% (R:R 1:2 통일)

### 변경 파일

#### 1. `scripts/live_trader.py` — 진입 시 ATR 계산 + 변동성 필터

```python
from src.ai.signal.position_sizer import calc_atr

MIN_ATR_PCT = 0.0035  # 0.35% — 이하면 진입 스킵 (거래비용 손익분기 미달)
ATR_STOP_MULT = 1.5   # 손절 = ATR의 1.5배
ATR_TP_MULT = 3.0     # 익절 = ATR의 3.0배 (R:R = 1:2)
MIN_STOP_PCT = 0.005  # 바닥: 최소 0.5% 손절폭

atr = calc_atr(daily, period=20)
if atr > 0 and price > 0:
    atr_pct = atr / price
    if atr_pct < MIN_ATR_PCT:
        continue  # 변동성 부족 → 진입 스킵
    dynamic_stop = -max(atr_pct * ATR_STOP_MULT, MIN_STOP_PCT)
    dynamic_tp = max(atr_pct * ATR_TP_MULT, MIN_STOP_PCT * 2)  # TP 바닥도 R:R 1:2 유지
else:
    continue  # ATR 미산출 → 진입 스킵
```

#### 2. LivePosition에 필드 추가
```python
dynamic_stop: float | None = None   # ATR 기반 동적 손절
dynamic_tp: float | None = None     # ATR 기반 동적 익절
```

#### 3. 청산 시 dynamic_stop/dynamic_tp 전달
```python
exit_reason = momentum_exit(
    pos.entry_price, quote.price, current_time,
    momentum_params,
    dynamic_stop=pos.dynamic_stop,
    dynamic_tp=pos.dynamic_tp,
    peak_price=pos.high_since_entry,
)
```

#### 4. 테스트
- ATR% < 0.35% → 진입 스킵 확인
- ATR 정상 → dynamic_stop이 바닥(0.5%) 이상인지 확인
- ATR=0 → 진입 스킵 확인
- 청산 시 dynamic_stop이 고정값 오버라이드하는지

---

## PR-B-2: force_close_time 통일 (15:15)

### 현재 상태 (불일치 3곳)

| 위치 | 현재 | 변경 |
|------|------|------|
| MomentumParams.force_close_time | "14:00" | **"15:15"** |
| live_trader.py 코드 | "1430" | **"1515"** |
| live_trader.py 주석/docstring | "14:30" | **"15:15"** |
| grid_search.py day trade config | "14:00" | **"15:15"** |
| strategy-momentum.md | "15:25" | **"15:15"** |

### 결정 근거

| 시각 | 판단 | 이유 |
|------|------|------|
| 14:00 | ❌ 너무 이름 | 마감 모멘텀(14:30~15:20) 완전 포기 |
| 14:30 | ❌ 보수적 | 마감 모멘텀 활용 불가 |
| **15:15** | **✅ 최적** | 마감 모멘텀 캡처 + 동시호가(15:20) 5분 안전 마진 |
| 15:25 | ❌ 위험 | 동시호가 구간(15:20~15:30), 가격 통제 불가 |

- RC4058 에러: 실제 로그 분석 결과 15:30:38에 최초 발생 (모의투자 장종료)
- 한국 자동매매 관행: 15:10~15:15가 일반적 (decomsoft, AI키움 참조)
- 장 종료 30분 전 모멘텀: KAIST 연구에서 첫 30분 수익률이 마지막 30분 예측 확인

### 실패 대응
```
15:15 시장가 매도 → 실패 시 15:18 공격적 지정가 → 15:19 미체결 시 동시호가 주문
```

---

## PR-C: 단계적 리스크 관리 (kill_switch 통합)

### v2 핵심 변경

**v1 문제**: "쿨다운 불필요, 포지션 축소가 낫다"(Connors 인용) → 2연패 블랙리스트(=쿨다운) 적용. 자기 모순.

**Connors 인용 삭제 이유**:
- Connors 연구는 **평균회귀 전략** 기준 (가격 역행 = 반등 확률↑ → 쿨다운 = 기회 상실)
- 우리 시스템은 **모멘텀 전략** (연속 손실 = 해당 종목에 모멘텀 없음 → 스킵이 합리적)
- 전략 유형이 다르므로 Connors 결론 직접 적용 불가

**블랙리스트 재정의**: "쿨다운"이 아닌 **"시그널 품질 필터"**
- 모멘텀 전략에서 3연패 = "이 종목에 오늘 모멘텀이 없다"는 시장 신호
- 감정 관리가 아닌 시그널 유효성 판단

### 단계적 접근

| 이벤트 | 조치 | 근거 |
|--------|------|------|
| 1연패 | 변경 없음 | 정상 분산 (승률 60%에서도 100거래 중 5연패 63%) |
| 2연패 (동일 종목) | 포지션 사이즈 50% 축소 | Anti-martingale: 엣지 약화 시 노출 감소 |
| 3연패 (동일 종목) | 당일 블랙리스트 | 시그널 품질 필터: "오늘 이 종목에 모멘텀 없음" |
| 일일 PnL ≤ -2% | 전체 risk_scale 0.5 | kill_switch 기존 로직 활용 |
| 일일 PnL ≤ -3% | 전포지션 강제 청산 | kill_switch FORCE_CLOSE |

### kill_switch.py 통합

**기존 구현 (미연결)**:
- `kill_switch.py`에 `update_drawdown()`, `update_weekly_loss()` 이미 존재
- `DRAWDOWN_STOP_BUY_PCT = -2%`, `DRAWDOWN_FORCE_CLOSE_PCT = -3%` 정의됨
- 일일 자정 자동 리셋 구현됨
- **하지만 live_trader.py에서 한 번도 호출하지 않음**

**수정 방향**: TradingState에 중복 필드 추가하지 않고 kill_switch 연결

```python
# TradingState에 추가하는 것 (kill_switch에 없는 것만)
symbol_losses: dict[str, int] = field(default_factory=dict)
symbol_blacklist: set[str] = field(default_factory=set)

# kill_switch에 이미 있는 것 (새로 만들지 않음)
# daily_pnl → kill_switch.KillSwitchState.daily_pnl
# risk_scale → kill_switch.KillSwitchState.scale_factor
# drawdown_stop_buy → kill_switch.update_drawdown() 결과
```

**risk_scale 복구 정책**: 당일 내 복구하지 않음 (의도적)
- 일일 -2% 도달 = 오늘 시장 조건이 전략에 불리
- 일시적 회복 후 재하락 시 더 큰 손실 위험
- 다음날 자정 자동 리셋 (kill_switch 기존 daily reset)

### 변경 파일

#### 1. `scripts/live_trader.py` — kill_switch 연결 + 단계적 리스크
```python
from src.trading.kill_switch import update_drawdown, DrawdownAction

# 매 청산 후
def update_risk_after_trade(state: TradingState, symbol: str, pnl: float) -> None:
    if pnl < 0:
        state.symbol_losses[symbol] = state.symbol_losses.get(symbol, 0) + 1
        if state.symbol_losses[symbol] >= 3:
            state.symbol_blacklist.add(symbol)  # 3연패 → 시그널 품질 필터
    else:
        state.symbol_losses[symbol] = 0

# 매 진입 전
if symbol in state.symbol_blacklist:
    continue

# 포지션 사이즈 계산 시
symbol_scale = 0.5 if state.symbol_losses.get(symbol, 0) >= 2 else 1.0
quantity = calc_dynamic_position_size(
    price=price, daily=daily, account_balance=account_balance,
    scale_factor=scale_factor * ks_state.scale_factor * symbol_scale,
)

# 매 체결 후 kill_switch 업데이트
action = update_drawdown(user_id, current_portfolio_value)
if action == DrawdownAction.FORCE_CLOSE:
    # 전포지션 강제 청산
elif action == DrawdownAction.STOP_BUY:
    state.drawdown_stop_buy = True
```

#### 2. 테스트
- 1연패 → 변경 없음 확인
- 2연패 → symbol_scale 0.5 확인
- 3연패 → 블랙리스트 등록 확인
- 수익 후 카운트 리셋 확인
- kill_switch update_drawdown 호출 확인

---

## PR-D: 섹터 포지션 제한

(변경 없음 — v1과 동일)

### 개념
```
현재:    삼성전자 + SK하이닉스 + 삼성전기 = 반도체 3개 동시 보유 가능
수정 후: 반도체는 1개만 보유, 나머지 섹터에서 나머지 2개 선택
```

### 변경 파일

#### 1. `scripts/live_trader.py` — 진입 시 섹터 체크
```python
from scripts.screen_symbols import get_sector

sector = get_sector(symbol)
if sector:
    sector_count = sum(
        1 for pos in state.positions.values()
        if get_sector(pos.symbol) == sector
    )
    if sector_count >= 1:
        continue
```

#### 2. 테스트
- 같은 섹터 2번째 진입 → 거부 확인
- 다른 섹터 진입 → 허용 확인
- 섹터 없는 종목 → 제한 없이 허용

---

## PR-E: 시장 레짐 필터 (VKOSPI 기반) — Phase 2

(변경 없음)

---

## PR-F: 스윙 인프라 — Phase 2

(변경 없음, force_close_time만 15:15로 정정)

---

## 작업 순서 및 의존성

```
PR-A (거래세 + 강제매수 제거 + 주석 수정)
  ↓
PR-B (ATR 동적 손절 + 바닥/필터 + R:R 1:2)
  + PR-B-2 (force_close_time 15:15 통일) ← PR-B와 병렬 가능
  ↓
PR-C (단계적 리스크 + kill_switch 통합) — PR-A,B와 독립 가능하지만 순서상 후행
  ↓
PR-D (섹터 제한) — 독립적, PR-C와 병렬 가능
  ↓
PR-E (VKOSPI 레짐) — Phase 2
  ↓
PR-F (스윙 인프라) — Phase 2
```

## 기대 효과

| 지표 | 현재 | Phase 1 후 예상 |
|------|------|----------------|
| 왕복 비용 계산 | 0.21% (오류) | **0.23%** (정확) |
| 노이즈 손절 빈도 | 높음 (고정 -0.5%) | **낮음** (ATR 기반, 바닥 0.5%) |
| 저변동성 종목 진입 | 거래비용 이하 SL | **스킵** (ATR% < 0.35%) |
| R:R 비율 | 불일치 (1:3/1:2 혼재) | **1:2 통일** |
| 같은 종목 연속 손절 | 무제한 | **단계적**: 2패→축소, 3패→블랙 |
| kill_switch 연결 | 미연결 (코드 존재, 미호출) | **연결** |
| 강제 청산 시각 | 불일치 (14:00/14:30/15:25) | **15:15 통일** |
| 섹터 리스크 | 반도체 3개 동시 가능 | **섹터당 1개** |
| 무의미한 강제 매수 | 있음 | **없음** |
| 일일 최대 손실 | 무제한 | **-2% 축소, -3% 강제 청산** |

## v2 변경 이력

| 이슈 | v1 (원본) | v2 (수정) | 근거 |
|------|----------|----------|------|
| ATR 바닥 | 없음 | 바닥 0.5% + 필터 0.35% | Kevin Davey floor 패턴, 거래비용 손익분기 |
| R:R | 3.0×ATR (문서 불일치 4.5×도 있음) | 3.0×ATR 확정 (1:2) | HPSP PF 4.12>3.23, 한국 약한 일중모멘텀 |
| ATR 미산출 | 고정값 폴백 | 진입 스킵 | R:R 혼재 방지 |
| 연패 처리 | 2연패→즉시 블랙 (Connors 인용) | 단계적(1무변경/2축소/3블랙), Connors 삭제 | Connors=평균회귀 전용, 시그널 품질 필터로 재정의 |
| force_close | 14:00 (코드) | 15:15 통일 | 마감모멘텀+동시호가 안전마진, RC4058 로그 분석 |
| risk_scale | 복구 로직 미정의 | 당일 복구 안 함 (명시) | 보수적 관리, kill_switch daily reset 활용 |
| kill_switch | 신규 필드 중복 생성 | 기존 kill_switch.py 통합 | 코드 중복 방지 |
| 주석 | 0.21% (오류) | 0.23% | 거래세 0.20% 반영 |

## 리서치 출처

- Kevin Davey, KJ Trading Systems — ATR floor/ceiling 패턴, 567K 백테스트 결과
- LuxAlgo — ATR 기반 5가지 손절 전략, ADX 조건부 승수
- Leung & Li (2015) — 거래비용 포함 최적 손절 수학적 증명
- KAIST — KOSPI 일중 모멘텀 연구 (첫 30분 → 마지막 30분 예측)
- MDPI (Roh/Yang) — 한국 30분봉 일중 모멘텀 (weak evidence)
- Tandfonline (2024) — 한국 개별주 모멘텀: 외국인 활성 종목만 양의 모멘텀
- Connors Research — TPS 스케일링 (평균회귀 전용, 모멘텀 적용 부적합 확인)
- decomsoft / AI키움 — 한국 자동매매 15:10~15:15 청산 관행
