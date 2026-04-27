---
name: design-015-backtest-engine-integrity
description: 백테스트 엔진 무결성 4종 수정 — look-ahead bias 제거, 슬리피지 현실화, MDD 미실현 포함, survivorship 경고
type: design
status: 활성 (PR #326 머지 완료)
created: 2026-04-27
depends_on: []
related:
  - src/backtest/daily_engine.py
  - src/backtest/engine.py
  - src/backtest/metrics.py
  - src/backtest/slippage.py
  - tests/backtest/test_daily_engine.py
  - tests/backtest/test_slippage.py
pr: "#326"
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-24 | PR #326 dev 머지 완료 — 백테스트 엔진 4종 무결성 수정 |
| 2026-04-27 | T5 walk-forward 20종목 검증에 T1 엔진 적용 확인 |

# Design 015: 백테스트 엔진 무결성 (ADR-015)

## 1. 배경 — Skeptic 지적 4종

2026-04-24 백테스트 Skeptic 리뷰에서 다음 4가지 무결성 결함이 발견됐다. 모두 수익률 과장 방향으로 편향된다.

### 1-1. Look-ahead Bias (선행 편향)

**문제**: 기존 5분봉 엔진은 당일 종가를 당일 지표 계산에 사용했다.

```python
# 수정 전 (잘못된 코드 — 예시)
# day_data = 오늘 포함 데이터로 신고가 계산
high_n = max(bar.high for bar in day_data[-lookback:])  # 당일 데이터 포함
```

**수정**: 일봉 엔진(`DailyBacktestEngine`)에서 신호 계산을 `prior_daily`(당일 이전)만 사용하도록 강제.

```python
# 수정 후 (daily_engine.py)
# prior_daily: 당일 이전 일봉만 전달 (look-ahead 차단)
signal = check_daily_entry_signal(
    prior_daily=daily_data[:i],  # 현재 바 제외
    today_close=today.close,
    today_volume=today.volume,
    params=self.params,
    kospi_prior=kospi_prior,
)
```

**체결**: 익일 시가에 체결 (`entry_price = next_bar.open * (1 + slippage)`)

### 1-2. 슬리피지 0% → 0.15%

**문제**: 기존 엔진이 슬리피지 0으로 계산 → 실제 체결 비용 과소 추정.

**수정**: 보수적 추정치 **0.15%** 적용 (KOSPI 대형주 스프레드 + 시장충격 합산).

```python
# src/strategy/momentum_daily.py
@dataclass
class DailyMomentumParams:
    slippage_pct: float = 0.0015  # 0.15% 보수적 추정
```

**트레이드오프**:
- 0.15%는 KOSPI 대형주(시총 10조+) 실제 스프레드보다 다소 보수적
- 소형주·거래량 希少 종목은 0.3~0.5%가 적정하나 현재 유니버스(KOSPI 상위 20) 기준으로 허용 범위
- 후속 과제: 종목별 동적 슬리피지(거래량 × ATR 기반)

**왕복 비용 계산**:
```
매수 슬리피지 0.15% + 매도 슬리피지 0.15%
+ 수수료 왕복 0.03% + 거래세 0.20%
= 총 왕복 비용 ~0.53%
```

### 1-3. MDD — 미실현 손익 포함

**문제**: 기존 MDD 계산이 체결된 거래의 손익만 추적 → 포지션 보유 중 미실현 손실 누락.

**수정**: equity curve 기반 MDD로 전환. 미보유 기간과 보유 기간 모두 일별 평가액으로 추적.

```python
# src/backtest/metrics.py
def calc_max_drawdown(equity_curve: list[float]) -> float:
    """미실현 손익 포함 equity curve 기반 MDD."""
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (val - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return max_dd
```

**영향**: MDD가 실현 손익 기반 대비 평균 5~15%p 더 보수적으로 계산됨.

### 1-4. Survivorship Bias 경고

**문제**: pykrx는 현재 상장 종목만 제공 → 상장폐지·합병 종목 자동 제외 → 생존 편향.

**수정**: 엔진 실행 시 WARN 로그 추가.

```python
logger.warning(
    "Survivorship bias 경고: pykrx 유니버스는 현재 상장 종목만 포함. "
    "상장폐지 종목 제외로 성과 과장 가능성 있음.",
    universe_size=len(symbols),
)
```

**대응 전략**: 유니버스를 KOSPI 유동성 상위 20종목(시총 규모상 상장폐지 위험 최소)으로 제한하여 bias 최소화. 완전한 해결책은 아니나 실용적 완화책.

## 2. 수정 전후 비교

| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| SK하이닉스 전체 Sharpe | ~12.5 (추정) | 7.03 |
| SK하이닉스 MDD | ~-2.1% (추정) | -5.6% |
| 삼성전자 전체 Sharpe | ~+2.3 (추정) | -1.07 |
| 슬리피지 | 0% | 0.15% |
| MDD 기준 | 실현 손익만 | equity curve |

> **주의**: "수정 전" 수치는 구 엔진 파라미터 추정값으로 참고용. 정확한 비교는 구 엔진 코드 복원 필요.

## 3. 트레이드오프

| 항목 | 장점 | 단점 |
|------|------|------|
| 슬리피지 0.15% | 실제 비용에 근접한 현실적 시뮬레이션 | 대형주 기준 다소 보수적 — 실제 체결 시 더 유리할 수 있음 |
| MDD equity curve | 포지션 보유 중 리스크 정확히 측정 | 일봉 기준이므로 장중 저점 반영 안 됨 |
| Look-ahead 제거 | 미래 데이터 오염 차단 | 익일 시가 체결로 신호-체결 간 1일 지연 발생 |

## 4. 후속 과제

- [ ] 종목별 동적 슬리피지 모델 (거래량 비율 × ATR)
- [ ] 장중 분봉 MDD 반영 (일봉 엔진 한계 해소)
- [ ] 상장폐지 종목 포함 historical universe 구성 (survivorship 완전 해소)
