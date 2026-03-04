"""LLM 프롬프트 템플릿."""

SYSTEM_MARKET_ANALYST = """당신은 한국 주식 시장 전문 분석가입니다.
주어진 시장 데이터를 분석하여 매매 시그널을 생성합니다.
항상 한국어로 응답하며, 근거 기반의 분석을 제공합니다.
리스크를 보수적으로 평가하고, 확신이 낮으면 HOLD를 권장합니다."""

MARKET_ANALYSIS_PROMPT = """## 종목 분석 요청: {symbol} ({name})

### 현재 시세
- 현재가: {price:,}원
- 전일대비: {change:+,}원 ({change_pct:+.2f}%)
- 거래량: {volume:,}주
- 고가: {high:,}원 / 저가: {low:,}원

### 최근 일봉 (5일)
{daily_prices}

### 공시 정보
{disclosures}

### 해외 시장 동향
{overseas_data}

## 분석 지시
위 데이터를 기반으로 다음을 분석하세요:
1. 현재 추세 (상승/하락/횡보)
2. 주요 지지/저항 수준
3. 거래량 분석
4. 공시 영향 평가
5. 해외 시장 영향

최종적으로 BUY/SELL/HOLD 중 하나를 결정하고 신뢰도(0.0~1.0)를 제시하세요.
"""

DISCLOSURE_ANALYSIS_PROMPT = """## 공시 분석 요청

### 종목: {symbol} ({name})

### 공시 내용
{disclosure_text}

## 분석 지시
이 공시가 주가에 미칠 영향을 분석하세요:
1. 공시 유형 (실적, M&A, 유상증자, 배당 등)
2. 긍정/부정 영향
3. 단기/중기 전망
4. 투자 판단에 미치는 영향도 (HIGH/MEDIUM/LOW)
"""

COMPREHENSIVE_JUDGMENT_PROMPT = """## 종합 투자 판단 요청

### 대상 종목들
{symbols_data}

### 포트폴리오 현황
- 가용 현금: {available_cash:,}원
- 보유 종목: {current_holdings}
- 일일 손익: {daily_pnl:+,}원

### 시장 전반
{market_overview}

## 판단 지시
각 종목에 대해 매매 시그널을 생성하세요.
보수적으로 판단하며, 확신도가 0.7 미만이면 HOLD로 결정하세요.
"""
