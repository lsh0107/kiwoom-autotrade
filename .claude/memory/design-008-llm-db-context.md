---
name: design-008-llm-db-context
description: LLM DB 컨텍스트 기반 동적 투자 결정 시스템 설계
type: design
status: 활성 (Phase A/B/C/D 완료)
created: 2026-03-24
---

# Design 008: LLM DB 컨텍스트 기반 동적 투자 결정

> 4개 관점(PM·데이터엔지니어·백엔드·투자전문가) 토론 결과 종합

## 1. 핵심 목표

LLM이 DB에 축적된 과거 데이터를 참조하여, 장 마감 후(야간)와 장 시작 전(아침)에 **맥락 있는 동적 투자 결정**을 내리도록 한다.

현재 문제: LLM이 당일 수집 데이터만 보고 판단 → 과거 패턴, 이전 제안의 성과, 트렌드 변화를 전혀 반영 못 함.

---

## 2. 시간별 데이터 흐름 (PM 관점)

```
[장중 09:00~15:30]
  ├── news_collection (2시간 간격) → news_articles DB
  └── 매매 실행 → orders, trade_logs, ai_signals DB

[장 마감 15:30~16:30]
  ├── postmarket_trade_review → trade_reviews DB     ← DB 컨텍스트 강화
  └── postmarket_param_adjustment → 파라미터 제안

[야간 22:00~06:00]  ← ★ 신규
  ├── 미국장 개장 (22:30 KST) → S&P500, NASDAQ, 다우 실시간
  ├── overnight_index_collection (23:00, 03:00, 06:00)
  │   → 해외지수 + 선물 데이터 → market_data DB
  └── overnight_analysis (06:30) ← ★ 신규 DAG
      → 야간 해외 변동 분석 → LLM 야간 브리핑 → llm_briefings DB

[장 시작 전 07:00~09:00]
  ├── premarket_data_collection (08:00) → market_data DB
  └── llm_briefing (08:30) ← DB 컨텍스트 강화
      → 야간 브리핑 + 과거 7일 패턴 + 이전 제안 성과 참조
      → 당일 테마 비중, 진입 전략 결정
```

---

## 3. 투자전문가 관점

### 3-1. 왜 야간 해외지수가 중요한가

- **한국 증시는 전일 미국장에 강하게 연동** — S&P500이 2% 빠지면 다음날 코스피 갭다운 확률 80%+
- 미국장 마감(06:00 KST) 후 ~ 한국장 개장(09:00) 사이 3시간이 **핵심 의사결정 구간**
- CME 선물(E-mini S&P 등)은 거의 24시간 거래 → 새벽에도 변동 추적 가능

### 3-2. LLM이 참조해야 할 핵심 데이터

| 우선순위 | 데이터 | 활용 | 기간 |
|---------|--------|------|------|
| ★★★ | 해외지수 (S&P, NASDAQ, VIX) | 갭 예측, 리스크 판단 | 당일 + 최근 5일 |
| ★★★ | 이전 브리핑/리뷰 제안 vs 실제 결과 | 피드백 루프 (자기 교정) | 최근 5건 |
| ★★☆ | 섹터별 뉴스 감성 추세 | 테마 모멘텀 판단 | 최근 7일 |
| ★★☆ | 내 포트폴리오 현황 (보유, 수익률) | 비중 조절, 손절 판단 | 현재 |
| ★☆☆ | 거시경제 (금리, 환율) | 매크로 방향성 | 최근 30일 |
| ★☆☆ | 과거 월봉 시그널 | 중장기 추세 | 최근 3개월 |

### 3-3. 투자 결정 유형

1. **비중 조정** — 테마별 투자 비중 변경 (예: 반도체 30%→25%)
2. **종목 교체** — 유니버스 내 편출입 제안
3. **리스크 모드** — 공격/중립/방어 전환 (VIX 기반)
4. **파라미터 튜닝** — ATR 배수, 손절/익절 비율 조정
5. **매매 중단** — 극단적 상황 시 soft-stop 제안

### 3-4. 주의사항 (안전장치)

- **LLM은 조언자, 실행자가 아님** — 모든 결정은 `status: pending`으로 저장, 자동 적용은 Phase 2
- **할루시네이션 방지** — DB 데이터를 수치로 명확히 제공, "추측하지 말고 데이터 기반으로만 판단" 시스템 프롬프트
- **과적합 방지** — 최근 1~2일만 보면 노이즈에 반응. 최소 5일 이상 추세 참조
- **비용 관리** — 하루 LLM 호출 3~4회, 각 호출 당 입력 ~15K 토큰 이내
- **백테스트 없는 전략 변경 금지** — LLM 제안은 항상 "제안"이며, 실행 전 사람 확인 필수 (Phase 1)

---

## 4. 데이터 파이프라인 설계 (data-eng 관점)

### 4-1. 신규 DAG: overnight_index_collection

```python
# airflow/dags/overnight/index_collection.py
@dag(
    schedule="0 23,3,6 * * 1-5",  # 23시, 03시, 06시 (미국장 중)
    tags=["overnight", "수집"],
)
def overnight_index_collection():
    """야간 해외지수 수집 (미국장 시간대)"""

    @task()
    def collect_overnight():
        from collectors.overseas import fetch_major_indices
        return fetch_major_indices()  # yfinance: ^GSPC, ^IXIC, ^DJI, ^VIX, ES=F

    @task()
    def store(data):
        from collectors.storage import save_market_data, today_str
        save_market_data("overnight_index", today_str(), data)

    store(collect_overnight())
```

**수집 대상 (yfinance 티커)**:
| 지수 | 티커 | 중요도 |
|------|------|--------|
| S&P 500 | ^GSPC | ★★★ |
| NASDAQ | ^IXIC | ★★★ |
| 다우존스 | ^DJI | ★★☆ |
| VIX | ^VIX | ★★★ |
| S&P 500 선물 | ES=F | ★★★ |
| NASDAQ 선물 | NQ=F | ★★☆ |
| 유로스톡스 50 | ^STOXX50E | ★☆☆ |
| 닛케이 225 | ^N225 | ★☆☆ |
| USD/KRW | KRW=X | ★★☆ |
| 10Y US Treasury | ^TNX | ★★☆ |

### 4-2. 신규 DAG: overnight_analysis

```python
# airflow/dags/overnight/analysis.py
@dag(
    schedule="30 6 * * 1-5",  # 06:30 (미국장 마감 후)
    tags=["overnight", "LLM"],
)
def overnight_analysis():
    """야간 해외 변동 분석 → LLM 야간 브리핑"""

    @task()
    def build_context():
        from context.builder import build_overnight_context
        return build_overnight_context()  # DB에서 야간 데이터 + 과거 패턴 조합

    @task()
    def analyze(ctx):
        from llm.briefing import generate_overnight_briefing
        return generate_overnight_briefing(ctx)

    @task()
    def store(briefing):
        from collectors.storage import save_briefing, today_str
        save_briefing(today_str(), briefing)

    store(analyze(build_context()))
```

### 4-3. 기존 DAG 수정: llm_briefing 강화

```python
# 기존 llm_briefing.py의 prepare_data 태스크에 DB 컨텍스트 추가
@task()
def prepare_data():
    from collectors.storage import load_json, today_str
    from context.builder import build_premarket_context  # ← 신규

    date = today_str()
    raw_data = load_json("premarket", date)
    db_context = build_premarket_context(days=7)  # ← DB 과거 데이터

    return {**raw_data, "db_context": db_context}
```

### 4-4. DAG 의존성 (Asset 기반)

```
overnight_index_collection ──→ Asset("overnight_data")
                                      │
                               overnight_analysis
                                      │
                               Asset("overnight_briefing")
                                      │
premarket_data_collection ────→ Asset("premarket_data")
              │                       │
              └───────────── llm_briefing (두 Asset 모두 소비)
```

---

## 5. DB 컨텍스트 빌더 (backend 관점)

### 5-1. 모듈 구조

```
airflow/plugins/context/
├── __init__.py
├── builder.py          # 컨텍스트 조합 (오케스트레이션)
├── market.py           # 시장 데이터 쿼리
├── portfolio.py        # 포트폴리오/매매 실적 쿼리
├── history.py          # 과거 LLM 결정 + 결과 쿼리
└── formatter.py        # LLM 프롬프트용 텍스트 포맷터
```

### 5-2. 핵심 함수

```python
# context/market.py
def get_market_summary(days: int = 7) -> dict:
    """최근 N일 시장 데이터 요약"""
    # market_data 테이블에서 category별 최근 데이터
    # → VIX 추세, 금리 변동, 해외지수 변동률 계산
    # 반환: {"vix": {"current": 18.5, "5d_avg": 17.2, "trend": "상승"},
    #        "sp500": {"close": 5200, "1d_chg": -1.2, "5d_chg": +0.8}, ...}

def get_news_sentiment_trend(days: int = 7) -> dict:
    """최근 N일 뉴스 감성 추세 (섹터별)"""
    # news_articles에서 keyword별 sentiment 집계
    # 반환: {"반도체": {"pos": 12, "neg": 3, "trend": "긍정"}, ...}

# context/portfolio.py
def get_portfolio_status() -> dict:
    """현재 보유 종목 + 수익률"""
    # orders (status=filled) + 현재가 비교
    # 반환: [{"symbol": "005930", "name": "삼성전자", "qty": 10, "avg_price": 72000, "pnl": +3.2%}, ...]

def get_recent_trades(days: int = 7) -> dict:
    """최근 N일 매매 내역 요약"""
    # trade_logs에서 집계
    # 반환: {"total_trades": 15, "win_rate": 60%, "avg_pnl": +1.2%, ...}

# context/history.py
def get_decision_feedback(n: int = 5) -> list[dict]:
    """최근 N건 LLM 제안 vs 실제 결과"""
    # llm_briefings.weight_adjustments + 실제 수익률 비교
    # 반환: [{"date": "2026-03-20", "suggestion": "반도체 비중 +10%",
    #         "actual_result": "반도체 +2.3%", "evaluation": "적중"}, ...]

# context/builder.py
def build_premarket_context(days: int = 7) -> dict:
    """장전 브리핑용 통합 컨텍스트"""
    return {
        "market_summary": get_market_summary(days),
        "sentiment_trend": get_news_sentiment_trend(days),
        "portfolio": get_portfolio_status(),
        "recent_trades": get_recent_trades(days),
        "decision_feedback": get_decision_feedback(5),
    }

def build_overnight_context() -> dict:
    """야간 분석용 통합 컨텍스트"""
    return {
        "overnight_indices": get_overnight_indices(),  # 야간 해외지수
        "today_review": get_latest_review(),           # 당일 장후 리뷰
        "market_summary": get_market_summary(5),
    }
```

### 5-3. 토큰 예산 관리

```python
# context/formatter.py
TOKEN_BUDGET = {
    "market_summary": 2000,      # 시장 데이터 요약
    "sentiment_trend": 1500,     # 뉴스 감성
    "portfolio": 1000,           # 포트폴리오
    "recent_trades": 1000,       # 매매 이력
    "decision_feedback": 2000,   # 피드백 루프
    "overnight_indices": 1500,   # 야간 해외지수
    "raw_data": 5000,            # 당일 원본 데이터
    "system_prompt": 1000,       # 시스템 프롬프트
}
# 합계 ~15K tokens — Claude Sonnet 기준 충분
```

각 섹션은 토큰 한도 내로 **DB에서 집계 쿼리로 미리 요약**. 원본 데이터를 LLM에 통째로 넘기지 않음.

### 5-4. 투자 결정 저장 테이블

```sql
-- 새 테이블: llm_decisions (LLM 투자 결정 추적)
CREATE TABLE llm_decisions (
    id UUID PRIMARY KEY,
    date DATE NOT NULL,
    decision_type VARCHAR(30) NOT NULL,  -- weight_adjust, risk_mode, param_tune, stock_swap
    context_source VARCHAR(20) NOT NULL, -- overnight, premarket, postmarket
    content JSONB NOT NULL,              -- 결정 내용 (구조는 type별 상이)
    confidence FLOAT,                    -- LLM 자체 신뢰도 (0~1)
    status VARCHAR(20) DEFAULT 'pending', -- pending → approved → applied → evaluated
    applied_at TIMESTAMPTZ,
    evaluation JSONB,                    -- 사후 평가 (수익률, 적중 여부)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_llm_decisions_date_type ON llm_decisions(date, decision_type);
CREATE INDEX ix_llm_decisions_status ON llm_decisions(status);
```

**status 플로우**: `pending` → `approved` (사람 확인) → `applied` (실행) → `evaluated` (사후 평가)

---

## 6. 구현 Phase (PM 관점)

### Phase A: DB 컨텍스트 빌더 (1주)
- `plugins/context/` 모듈 구현
- 기존 llm_briefing, trade_review에 DB 컨텍스트 연결
- **효과**: 기존 DAG가 과거 데이터를 참조해서 더 나은 판단

### Phase B: 야간 해외지수 수집 (3일)
- overnight_index_collection DAG 구현
- yfinance 기반 해외지수 + 선물 수집
- market_data 테이블에 "overnight_index" 카테고리 저장

### Phase C: 야간 분석 + 피드백 루프 (1주)
- overnight_analysis DAG 구현
- llm_decisions 테이블 + 사후 평가 로직
- decision_feedback 쿼리 (이전 제안 vs 실제 결과)

### Phase D: 대시보드 연동 (완료)
- 백엔드: `src/api/v1/decisions.py` — GET /decisions, POST approve/reject
- 프론트엔드: `(authenticated)/decisions/page.tsx` — 결정 목록, 상태 필터, 승인/거부 UI
- 사이드바: "LLM 결정" 메뉴 추가
- 텔레그램: `send_telegram()` 헬퍼, overnight_analysis store 태스크에서 야간 분석 완료 알림

---

## 7. 리스크/트레이드오프

| 리스크 | 대응 |
|--------|------|
| LLM 비용 증가 | 호출 3~4회/일, 토큰 예산 15K 고정. 월 ~$30 수준 |
| 할루시네이션 | 수치 데이터만 제공, "추측 금지" 시스템 프롬프트 |
| 과적합 (단기 노이즈 반응) | 최소 5일 추세 참조, 급격한 비중 변경 ±20% 제한 |
| 야간 API 장애 | yfinance 실패 시 이전 데이터 사용 (graceful degradation) |
| 자동 매매 위험 | Phase 1: pending → 사람 승인만. 자동 적용은 Phase 2 |

---

## 8. 성공 기준 (KPI)

1. **피드백 적중률**: LLM 비중 조정 제안 중 실제 양(+) 수익률 비율 > 55%
2. **응답 품질**: 이전 제안 결과를 인용하며 근거 기반 판단하는 비율 > 80%
3. **비용**: 일 LLM 비용 < $2 (토큰 예산 내)
4. **커버리지**: 야간 해외지수 수집 성공률 > 95%
