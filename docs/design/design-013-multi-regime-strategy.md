---
name: design-013-multi-regime-strategy
description: 4사분면 시장 스타일 + 동적 거래량 임계치 + 신규 전략(Pullback/Range) 도입
type: design
status: 활성 (PR 1~7 머지 완료, PR 9 가중치 분배 미구현)
created: 2026-04-21
depends_on:
  - design-009-market-context-integration (머지 완료)
  - design-011-daily-candle-caching (머지 완료)
  - design-012-pre-screening-cache (머지 완료)
related:
  - src/trading/market_regime.py
  - src/trading/market_style.py (신규 PR 1)
  - src/trading/market_context.py
  - src/trading/regime_strategy_map.py (신규 PR 6)
  - src/strategy/momentum.py
  - src/strategy/mean_reversion.py
  - src/strategy/pullback.py (신규 PR 4)
  - src/strategy/range_trade.py (신규 PR 5)
  - src/backtest/strategy.py (MomentumStrategy)
  - src/ai/signal/position_sizer.py (StrategyBudget)
  - scripts/live_trader.py
  - airflow/dags/premarket/data_collection.py
feature_flag: USE_MULTI_REGIME  # 기본 false (PR 7 통합)
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-22 | USE_MULTI_REGIME flag만 추가되고 `_assign_symbol_strategies` 가중치 분배는 미구현(skeleton). PR 9(가중치 분배) 후속 필요. |

# Design 013: 다중 레짐 전략

## 1. 배경
2026-04-22 장중 모멘텀 단일 의존으로 매수 0건 사태가 발생했다. 시장이 횡보/저거래장인데
`MomentumStrategy.check_entry_signal`이 `volume_ratio >= 0.5~0.8` 고정 임계치로 종목 진입을
전부 차단했다. 현재 구조는 다음 한계를 가진다:

1. **리스크 축만 존재**: `MarketRegime`(AGGRESSIVE/NEUTRAL/DEFENSIVE/CRISIS)는 VKOSPI와
   KOSPI 이평만으로 판단 — 시장 활발도/추세 강도를 전혀 구분하지 못함.
2. **전략 단일화**: `MomentumStrategy` + `MeanReversionStrategy` 두 개가 사실상 전부.
   박스권/조용한 상승장/pullback 엔트리를 커버하는 전략 없음.
3. **거래량 임계치 고정**: 시장 전체 거래대금이 평균 대비 50%만 나오는 날에도
   종목 `volume_ratio` 동일 기준 요구 → 매수 0건.

## 2. 목표 / 비목표

### 목표
- **MarketStyle 4사분면** 도입: 추세방향(bull/range/bear) × 활발도(strong/quiet) 축.
- **시장 거래대금 정규화**: 종목 거래량 임계치를 시장 전체 거래대금 대비 동적으로 조정.
- **신규 전략 2개**: PullbackStrategy(상승장 눌림목), RangeStrategy(박스권 역추세).
- **전략 매트릭스**: 스타일별 전략 가중치 분배로 포트폴리오 자동 다각화.
- **점진 적용**: `USE_MULTI_REGIME=false` 기본. flag on 시에만 신규 경로 활성.

### 비목표
- 백테스트 엔진(`src/backtest/engine.py`, `mr_engine.py`) 수정 — 이번 설계 범위 밖.
- LLM 기반 스타일 판단 — 추후 확장.
- 실시간 섹터 로테이션 기반 자본 재분배 — Phase 4 이후.

## 3. 아키텍처

```
premarket (Airflow 09:00 이전)
  └── data_collection
       ├─ KOSPI OHLCV (기존)
       └─ 시장 전체 거래대금 집계  ← PR 2
             └─ market_data[category="market_value"]

live_trader 시작
  MarketContext.refresh()
    ├─ VKOSPI / KOSPI 이평 (기존)
    └─ 시장 거래대금 (today / rolling_5d_avg)  ← PR 2

루프 (기존 market_regime 판단과 병행)
  style = detect_style(
      kospi_close, kospi_ma, kospi_adx,
      market_value_ratio,          # today / 5d_avg
      atr_pct,
  )                                  ← PR 1
  weights = REGIME_STRATEGY_WEIGHTS[style]         ← PR 6
  strategies = StrategyBudget.apply_regime(regime, style)  ← PR 6

  for symbol in universe:
      vol_override = base_vol * clamp(market_value_ratio, 0.5, 1.5)  ← PR 7
      if momentum.check_entry_signal(..., volume_ratio_override=vol_override): ...  ← PR 3
      if pullback.check_entry_signal(..., volume_ratio_override=vol_override): ...  ← PR 4
      if range_trade.check_entry_signal(..., volume_ratio_override=vol_override): ...  ← PR 5
```

## 4. 핵심 모델

### 4.1 MarketStyle (신규)

```python
class MarketStyle(StrEnum):
    TREND_BULL_STRONG = "trend_bull_strong"   # KOSPI>MA + ADX>25 + vol 충분
    TREND_BULL_QUIET  = "trend_bull_quiet"    # KOSPI>MA + vol<0.7*avg
    RANGE             = "range"               # |KOSPI-MA|<1% + ATR% 낮음
    TREND_BEAR        = "trend_bear"          # KOSPI<MA + ADX>25
    CHOP              = "chop"                # 변동성↑ 추세↓
```

`MarketRegime`(리스크 축)과 **직교**. 리스크 레짐은 자본 배분(pool_a/pool_b/buffer)에,
스타일은 전략 선택과 거래량 임계치에 사용한다.

### 4.2 가중치 매트릭스 (PR 6)

```python
REGIME_STRATEGY_WEIGHTS: dict[MarketStyle, dict[str, float]] = {
    MarketStyle.TREND_BULL_STRONG: {"momentum": 0.70, "pullback": 0.30},
    MarketStyle.TREND_BULL_QUIET:  {"pullback": 0.50, "mean_reversion": 0.30, "momentum": 0.20},
    MarketStyle.RANGE:             {"range_trade": 0.60, "mean_reversion": 0.40},
    MarketStyle.TREND_BEAR:        {"mean_reversion": 0.40, "momentum": 0.20},  # 합<1 = 현금보유
    MarketStyle.CHOP:              {"mean_reversion": 0.30},                     # 합<1 = 현금↑
}
```

TREND_BEAR/CHOP은 의도적으로 가중치 합<1 → 나머지는 현금 버퍼.

### 4.3 거래량 override (PR 3)

기존:
```python
check_entry_signal(...)  # volume_ratio >= self.volume_threshold 내부 검증
```

확장:
```python
check_entry_signal(..., volume_ratio_override: float | None = None)
# override 주어지면 self.volume_threshold 대신 사용.
```

live_trader에서 `base * clamp(market_value_ratio, 0.5, 1.5)` 로 계산.
시장 거래대금이 평균의 50%면 임계치도 절반으로 완화, 150%면 1.5배로 강화.

### 4.4 신규 전략

**PullbackStrategy** (`src/strategy/pullback.py`, PR 4)
- 진입: 일봉 종가>MA20, 현재가가 MA20±1% 근처, 최근 5봉 중 양봉 ≥ 1개, RSI 35~55.
- 청산: take_profit +2.5%, stop_loss -1.2%, trailing 비활성.
- 의도: 상승 추세 내 단기 조정 구간 재진입.

**RangeStrategy** (`src/strategy/range_trade.py`, PR 5)
- 진입: 최근 20봉 (high-low)/close 평균<2%, BB(20, 1.8) 하단 ±0.5%, RSI<45.
- 청산: BB 중심선 회귀 익절 / BB 하단 추가 -1% 손절 / 진입 후 2시간 미회귀 타임컷.
- 의도: 저변동 박스권에서 하단 접근 시 역추세 매수.

## 5. PR 쪼개기

| PR | 브랜치 | 내용 | 런타임 영향 |
|----|--------|------|-------------|
| 1 | feat/design-013-market-style | MarketStyle enum + detect_style + 설계 문서 | 0 (dead code) |
| 2 | feat/design-013-market-value | premarket DAG 거래대금 수집 + MarketContext getter | 수집 쪽 추가 (읽기 경로 영향 0) |
| 3 | feat/design-013-volume-override | check_entry_signal에 volume_ratio_override keyword | 0 (기본 None = 기존 동작) |
| 4 | feat/design-013-pullback | PullbackStrategy 구현 + 테스트 | 0 (호출처 없음) |
| 5 | feat/design-013-range-trade | RangeStrategy 구현 + 테스트 | 0 |
| 6 | feat/design-013-regime-mapping | REGIME_STRATEGY_WEIGHTS + StrategyBudget.apply_regime(style=None) | 0 (style None = 기존 동작) |
| 7 | feat/design-013-integration | live_trader 통합 + USE_MULTI_REGIME flag (기본 off) | flag on일 때만 |

## 6. 리스크 / 완화

| 리스크 | 완화 |
|--------|------|
| MarketStyle 판단 오류 → 잘못된 전략 선택 | flag off 기본. 활성화 시 전일 스냅샷 로그 확인 후 승인 |
| 신규 전략 오버핏 | 백테스트 엔진 수정 금지 (기존 엔진으로 별도 검증) |
| 거래량 override 과도 완화 → 잡음 매수 | clamp(0.5, 1.5) 상하한으로 극단값 차단 |
| StrategyBudget 분배 합≠1 | 가중치 정규화 / 나머지는 buffer 반영 |

## 7. 롤아웃

1. PR 1~6 머지 후 `USE_MULTI_REGIME=false` 유지 → 회귀 0.
2. dev 스테이징에서 일일 스냅샷(`style`, `market_value_ratio`, 전략별 진입 카운트) 수집.
3. 1주 관찰 후 사용자 승인 시 `.env`에 `USE_MULTI_REGIME=true` + backend 재시작.
4. 모의투자 1주 → 실전 전환 시 금액 한도/일일 주문 수 제한 재점검.

## 8. 검증 기준

- 모든 신규 모듈 커버리지 85%+.
- `pre-commit run --all-files` 통과.
- 기존 회귀 테스트(`test_live_trader.py`, `test_market_context.py`, `test_market_regime.py`
  등) 변경 없이 통과.
- PR 7에서 `USE_MULTI_REGIME=false` 경로를 명시적으로 테스트.
