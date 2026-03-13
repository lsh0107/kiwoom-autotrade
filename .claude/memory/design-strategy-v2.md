# 전략 v2.0 설계 — 이중 전략 + 테마/뉴스 기반 종목 선정 + LLM 통합

> 버전: v2.0 (설계) | 상태: Phase 1 구현 대기
> 작성: 2026-03-13 | 근거: 모의투자 1일 실전 결과 (승률 13%, 손익 -35%)
> 관련: strategy-momentum.md, decisions-pending.md

---

## 1. 현행 시스템 진단 (2026-03-13 실전 결과)

### 결과 요약
- 138매수 / 135매도, 승률 13.3%, 총손익 -35.10%
- HPSP(403870) 유일한 수익 (+1.33%, 1건)
- 신한지주/하이브/KB금융 거의 본전 (승률 22-40%)
- 나머지 11개 종목 대량 손실 (승률 0-12%, 평균 -0.2~-0.8%)

### 근본 원인 5개

| # | 원인 | 심각도 | 상세 |
|---|------|--------|------|
| 1 | **진입 필터 무효화** | CRITICAL | `src/strategy/momentum.py:55-61`에서 `check_entry_signal` 호출 시 `current_time`, `day_open`, `bar_open` 미전달 → 양봉필터/시가상승률/진입시간 필터 전부 비활성 |
| 2 | **volume_ratio 0.5** | HIGH | 평균의 절반이면 진입 = 사실상 무조건 매수. 장 시작 30분이면 대부분 통과 |
| 3 | **쿨다운 없음** | HIGH | 손절 즉시 재매수 → "고빈도 손절 머신". 같은 종목 반복 매수-손절 패턴 |
| 4 | **고정 SL/TP** | MEDIUM | SL -0.5%가 대형주(호가단위 100-500원)에서는 수 호가 차이. 노이즈에 즉사 |
| 5 | **테마 집중 리스크** | MEDIUM | 조선주 3개, 금융주 4개 동시 보유 = 분산 아닌 집중 |

---

## 2. Phase 1: 긴급 패치 (1-3일) — "출혈 멈추기"

### 2-1. 진입 필터 복구

**파일**: `src/strategy/momentum.py`

**현재** (라인 55-61):
```python
return check_entry_signal(
    current_price=current_price,
    high_52w=high_52w,
    current_volume=current_volume,
    avg_volume=int(avg_volume * time_ratio),
    params=self.params,
)
```

**수정**: `current_time`, `day_open`, `bar_open` 전달 필요. live_trader.py의 `poll_cycle`에서 Quote 데이터를 활용해 day_open과 현재 시각을 넘겨야 함. `check_entry_signal` 시그니처:
```python
check_entry_signal(
    current_price, high_52w, current_volume, avg_volume, params,
    *, day_open=0, bar_open=0, current_time="", rsi=None
)
```

**영향 범위**:
- `src/strategy/momentum.py` — `check_entry_signal` 호출부 수정
- `scripts/live_trader.py` — `poll_cycle`에서 quote.open과 현재시각을 전략에 전달하는 인터페이스 수정
- `src/strategy/base.py` — Strategy Protocol에 시그니처 맞춤
- `tests/strategy/test_base.py` — 테스트 업데이트

### 2-2. volume_ratio 상향

**파일**: `scripts/live_trader.py`, `src/backtest/strategy.py`
- CLI 기본값: 0.5 → **1.5**
- `MomentumParams.volume_ratio` 기본값: 0.5 → **1.5**
- 그리드서치(`make_day_trade_config`)에서 최적값 탐색: [1.0, 1.5, 2.0, 2.5]

### 2-3. 쿨다운 메커니즘

**파일**: `scripts/live_trader.py`

**추가할 상태**:
```python
@dataclass
class TradingState:
    # 기존 필드...
    cooldown_until: dict[str, str] = field(default_factory=dict)  # {symbol: "HHMM"}
    consecutive_losses: dict[str, int] = field(default_factory=dict)  # {symbol: count}
    blacklist: set[str] = field(default_factory=set)  # 당일 블랙리스트
```

**규칙**:
1. 같은 종목 매도 후 30분간 재진입 금지 (`cooldown_until`)
2. 같은 종목 연속 손절 3회 → 당일 블랙리스트 (`blacklist`)
3. 전체 연속 손절 5회 → 30분간 전 종목 매수 중단
4. `poll_cycle` 진입 체크 전에 쿨다운/블랙리스트 확인

### 2-4. ATR 기반 동적 SL/TP

**파일**: `src/backtest/strategy.py`, `src/strategy/momentum.py`

**현재**: `atr_stop_multiplier` 필드 있으나 None(비활성)

**활성화**:
```python
# check_exit_signal에서 동적 SL/TP 계산
if params.atr_stop_multiplier is not None:
    atr = calculate_atr(daily_data[-20:])  # 20일 ATR
    dynamic_stop = -(atr / entry_price) * params.atr_stop_multiplier
    dynamic_tp = (atr / entry_price) * params.atr_stop_multiplier * 3  # 3:1 R:R 유지
```

**종목별 예시**:
| 종목 | 가격 | 20일ATR | ATR% | 동적SL(1.5x) | 동적TP(4.5x) |
|------|------|---------|------|------------|------------|
| SK하이닉스 | 930,000 | ~15,000 | 1.6% | -2.4% | +7.3% |
| KB금융 | 149,200 | ~2,000 | 1.3% | -2.0% | +6.0% |
| 에코프로비엠 | ~50,000 | ~3,000 | 6.0% | -9.0% | +27.0% |

### 2-5. 테마별 포지션 제한

**파일**: `scripts/live_trader.py` 또는 `scripts/screen_symbols.py`

**테마 매핑 테이블** (신규):
```python
SECTOR_MAP = {
    "반도체": ["005930", "000660", "009150"],
    "조선": ["009540", "042660", "329180"],
    "금융": ["105560", "055550", "086790", "316140"],
    "2차전지": ["247540", "086520", "003670", "006400"],
    "자동차": ["005380", "000270", "012330"],
    "방산/조선": ["042660", "329180", "009540"],
    "엔터": ["352820", "041510", "035900", "263750"],
    "바이오": ["068270", "196170", "145020", "328130"],
    ...
}
```

**규칙**: 같은 섹터 내 최대 1개 포지션. `poll_cycle` 진입 시 현재 보유 종목의 섹터 확인 후 중복 차단.

---

## 3. Phase 2: 전략 고도화 (1-2주)

### 3-1. 변동성 기반 전략 자동 분류 (live_trader 연결)

**현재**: `src/backtest/grid_search.py`에 `classify_volatility` 구현됨 (ATR% 기반)
**문제**: `live_trader.py`에서 사용하지 않음

**구현**:
1. 장전 일봉 로드 후 종목별 ATR% 계산
2. 전략 할당: `{symbol: "momentum" | "mean_reversion" | "skip"}`
3. 분류 기준 (2차원):
   - ATR% > 3% + ADX > 25 → 모멘텀 단타
   - ATR% < 2% → 평균회귀 스윙
   - 중간 → 모멘텀 (보수적 파라미터)
4. ADX 계산기 `src/strategy/indicators.py`에 추가 필요

### 3-2. 스크리닝 강화

**파일**: `scripts/screen_symbols.py`

**현재 조건**: 52주고가 비율 + 거래량 (장전이라 거래량 항상 0)
**추가 조건**:
1. 전일 등락률 >= 3% (급등 종목)
2. 전일 거래량 >= 20일 평균 × 2.0 (거래량 폭증)
3. 최근 5일 연속 양봉 (추세 확인)
4. 52주 신고가 갱신 (당일 기준)

**장전 스크리닝 문제 해결**: 당일 거래량 대신 전일 데이터 기반 판단

### 3-3. 장중 동적 유니버스

**파일**: `scripts/live_trader.py`

**구현**:
1. 10:00, 11:00에 별도 태스크로 스크리닝 재실행
2. 네이버 금융 거래량 상위 페이지 크롤링 (키움 API 대안)
3. 새로 발견된 종목을 `symbols` 리스트에 추가
4. WebSocket 모드: 추가 종목 `ws.subscribe` 호출

### 3-4. 전략별 자금 버킷

**파일**: `src/ai/signal/position_sizer.py`

**현재**: 전체 계좌 잔고에서 2% 리스크로 수량 계산
**수정**:
```python
# 전략별 자금 풀
STRATEGY_ALLOCATION = {
    "momentum": 0.40,       # 40% — 단타
    "mean_reversion": 0.60, # 60% — 스윙 (보유기간 길어 더 많은 자금)
}
```

### 3-5. 스윙 인프라 (overnight 보유)

**현재 제약**: `force_close_all`이 장 종료 시 무조건 실행

**필요한 변경**:
1. 전략별 청산 정책: 모멘텀 = 당일 14:30 강제청산, 스윙 = 보유 유지
2. 다음날 재개 로직: 이전 포지션 상태를 JSON/DB에서 복원
3. 갭 리스크 관리: 전일 종가 대비 -3% 이상 갭다운 시 즉시 손절
4. 보유 기간 제한: 최대 5거래일 후 강제 청산

---

## 4. Phase 3: 데이터 + AI 레이어 (2-4주)

### 4-1. 장전 브리핑 자동화

**구현 위치**: `src/ai/` 신규 모듈 `briefing.py`

**데이터 소스**:
1. DART OpenAPI — 이미 `src/ai/data/disclosure_collector.py` 구현됨
2. 해외 지수 — 이미 `src/ai/data/futures_collector.py` 구현됨 (yfinance)
3. 뉴스 — 신규 수집 필요

**LLM 프롬프트**:
```
오늘 한국 주식 시장 장전 브리핑을 작성하세요.
[해외 지수 데이터] [DART 공시 목록] [뉴스 헤드라인]
→ 출력: 오늘 유망 테마 3개, 각 테마별 관련 종목, 주의 섹터
```

**실행 시점**: 장전 08:00 (스크리닝 전)
**비용**: Claude Haiku 사용 시 ~$0.3/일

### 4-2. 뉴스 수집 파이프라인

**데이터 소스 우선순위**:
| 순위 | 소스 | 비용 | 장점 | 단점 |
|------|------|------|------|------|
| 1 | DART OpenAPI | 무료 | 공시 원문, 신뢰도 높음 | 공시만 (뉴스 없음) |
| 2 | 한국거래소 정보시스템 | 무료 | 시장 통계, 등락률 상위 | 비실시간 |
| 3 | 네이버 금융 크롤링 | 무료 | 거래량 순위, 테마별 종목 | 비공식, 구조 변경 리스크 |
| 4 | BigKinds (한국언론진흥재단) | 무료(학술) | 뉴스 전문 검색 | 학술/연구용 제한 |
| 5 | Naver News API | 유료 | 실시간 뉴스 | 비용 발생 |

**아키텍처**:
```
[DART] [거래소] [네이버] → DataAggregator → LLM Briefing → 종목 스코어
                                                              ↓
                                                     live_trader 진입 가중치 조정
```

### 4-3. 장후 매매 리뷰

**구현 위치**: `src/ai/` 신규 모듈 `review.py`

**입력**: `docs/backtest-results/live_YYYYMMDD_*.json` (매매 결과)
**LLM 프롬프트**:
```
오늘 매매 결과를 분석하세요.
[거래 목록 + PnL] [종목별 차트 컨텍스트]
→ 출력: 손실 원인 분석, 파라미터 조정 제안, 내일 전략 변경 사항
```

**실행 시점**: 장후 15:40
**출력**: 텔레그램 알림 + JSON 저장

### 4-4. MarketBriefing 서비스 (느슨한 결합)

**핵심 원칙**: LLM = "decision support", 절대 "decision maker" 아님

**구현**:
```python
class MarketBriefing:
    """장전 LLM 브리핑 결과를 종목 스코어에 반영."""

    def get_sector_scores(self) -> dict[str, float]:
        """테마별 가중치. {"반도체": 1.2, "바이오": 0.8, ...}"""
        # LLM 브리핑 결과 기반

    def adjust_entry_threshold(self, symbol: str, base_volume_ratio: float) -> float:
        """LLM 결과로 진입 기준 미세 조정.
        유망 테마 종목: volume_ratio 10% 완화
        부정적 테마 종목: volume_ratio 20% 강화"""
```

**안전장치**:
- LLM 결과가 없거나 오류면 기본 파라미터 사용
- 가중치 조정 범위 제한: ±20% 이내
- `AIEngine._execute_signal`이 직접 주문 내는 현재 구조는 제거
- LLM consensus 확인: OpenAI + Anthropic 둘 다 같은 방향일 때만 반영

---

## 5. 비용/수익 분석

### 비용
| 항목 | 현재 | Phase 1 후 | Phase 3 후 |
|------|------|-----------|-----------|
| 키움 API | 무료 (모의) | 무료 (모의) | 무료 (모의) |
| LLM API | $0 | $0 | ~$1-2/일 |
| 인프라 | $0 (로컬) | $0 (로컬) | $0 (로컬) |
| **합계** | **$0/월** | **$0/월** | **$30-60/월** |

### 수익 기대 (Phase 1 패치 후)
- 승률: 13% → **40-50%** (진입 필터 복구 + volume_ratio 상향)
- 일 매매 수: 138건 → **20-30건** (쿨다운 + 필터 강화)
- 평균 PnL: -0.44% → **+0.05~0.10%**
- 월 기대 수익률: **3-5%** (슬리피지/부분체결 감안, 연 42-85%)

---

## 6. 구현 우선순위 요약

```
[즉시] Phase 1-1: 진입 필터 복구 (momentum.py) ← 가장 급선무
  ↓
[즉시] Phase 1-2,3: volume_ratio 1.5 + 쿨다운
  ↓
[1-2일] Phase 1-4,5: ATR 동적 SL/TP + 테마 제한
  ↓
[백테스트 검증] 그리드서치로 Phase 1 변경사항 최적 파라미터 도출
  ↓
[1주] Phase 2-1,2: 전략 자동 분류 + 스크리닝 강화
  ↓
[2주] Phase 2-3,4,5: 동적 유니버스 + 자금 버킷 + 스윙 인프라
  ↓
[3-4주] Phase 3: LLM 장전 브리핑 + 뉴스 파이프라인 + 장후 리뷰
```
