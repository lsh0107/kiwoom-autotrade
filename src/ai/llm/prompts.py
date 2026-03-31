"""LLM 프롬프트 템플릿.

레짐별 동적 프롬프트를 지원한다.
"""

from __future__ import annotations

SYSTEM_MARKET_ANALYST = """당신은 한국 주식 시장 전문 분석가입니다.
주어진 시장 데이터를 분석하여 매매 시그널을 생성합니다.
항상 한국어로 응답하며, 근거 기반의 분석을 제공합니다.
리스크와 수익 기회를 균형 있게 평가하고, 명확한 근거가 있으면 적극적으로 시그널을 제시합니다."""

# 레짐별 시스템 프롬프트 보조 지시
_REGIME_SYSTEM_DIRECTIVE: dict[str, str] = {
    "aggressive": (
        "\n\n현재 시장은 **공격 레짐**(KOSPI 상승추세 + 낮은 변동성)입니다."
        " 적극적 매수 기회를 포착하세요."
        " 신뢰도 0.5 이상이면 BUY 시그널을 제시하고,"
        " position_size_pct를 0.15~0.25로 설정하세요."
        " 단, 과열 징후(RSI>70, 급등 후 갭)가 있으면 주의하세요."
    ),
    "neutral": (
        "\n\n현재 시장은 **중립 레짐**(KOSPI 상승추세 + 보통 변동성)입니다."
        " 균형 잡힌 분석을 수행하세요."
        " 신뢰도 0.6 이상일 때만 BUY/SELL 시그널을 제시하고,"
        " position_size_pct는 0.10~0.15로 유지하세요."
    ),
    "defensive": (
        "\n\n현재 시장은 **방어 레짐**(추세 약화 또는 높은 변동성)입니다."
        " 보수적으로 분석하세요."
        " 신뢰도 0.7 이상의 확실한 기회만 BUY하고,"
        " position_size_pct는 0.05~0.10으로 제한하세요."
        " 기존 보유 종목의 SELL 시그널을 적극 검토하세요."
    ),
    "crisis": (
        "\n\n현재 시장은 **위기 레짐**(하락추세 + 극도로 높은 변동성)입니다."
        " 자본 보전이 최우선입니다."
        " 신규 BUY는 금지하고 HOLD 또는 SELL만 판단하세요."
        " 기존 보유 종목은 손실 제한을 위해 SELL을 우선 고려하세요."
    ),
}

# 분석 프롬프트에 삽입되는 레짐 컨텍스트 블록
_REGIME_CONTEXT_BLOCK: dict[str, str] = {
    "aggressive": (
        "### 시장 레짐: 공격 (AGGRESSIVE)\n"
        "- KOSPI: 12개월 이평 상회 (상승추세)\n"
        "- VKOSPI: 20 미만 (낮은 변동성)\n"
        "- 자본 배분: 모멘텀 55% / MR 30% / 현금 15%\n"
        "- **적극적 포지션 확대 권장**"
    ),
    "neutral": (
        "### 시장 레짐: 중립 (NEUTRAL)\n"
        "- KOSPI: 12개월 이평 상회 (상승추세)\n"
        "- VKOSPI: 20~30 (보통 변동성)\n"
        "- 자본 배분: 모멘텀 40% / MR 40% / 현금 20%\n"
        "- **선별적 매수, 리스크 관리 병행**"
    ),
    "defensive": (
        "### 시장 레짐: 방어 (DEFENSIVE)\n"
        "- KOSPI: 12개월 이평 하회 또는 VKOSPI 30+ (약세/고변동)\n"
        "- 자본 배분: 모멘텀 25% / MR 40% / 현금 35%\n"
        "- **신규 매수 최소화, 현금 비중 확대**"
    ),
    "crisis": (
        "### 시장 레짐: 위기 (CRISIS)\n"
        "- KOSPI: 12개월 이평 하회 + VKOSPI 30+ (하락추세 + 극고변동)\n"
        "- 자본 배분: 100% 현금\n"
        "- **신규 매수 금지, 보유종목 정리 우선**"
    ),
}

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
균형 잡힌 시각으로 판단하며, 확신도가 0.6 미만이면 HOLD로 결정하세요.
"""


def build_system_prompt(regime: str | None = None) -> str:
    """레짐 반영 시스템 프롬프트를 생성한다.

    Args:
        regime: 현재 시장 레짐 (aggressive/neutral/defensive/crisis).
               None이면 기본 시스템 프롬프트만 반환.

    Returns:
        레짐 지시가 포함된 시스템 프롬프트
    """
    base = SYSTEM_MARKET_ANALYST
    if regime and regime in _REGIME_SYSTEM_DIRECTIVE:
        return base + _REGIME_SYSTEM_DIRECTIVE[regime]
    return base


def build_analysis_prompt(
    formatted: dict[str, str | int | float],
    regime: str | None = None,
) -> str:
    """레짐 컨텍스트가 포함된 분석 프롬프트를 생성한다.

    Args:
        formatted: format_for_llm() 결과
        regime: 현재 시장 레짐. None이면 레짐 블록 미포함.

    Returns:
        포맷팅된 분석 프롬프트
    """
    prompt = MARKET_ANALYSIS_PROMPT.format(**formatted)

    if regime and regime in _REGIME_CONTEXT_BLOCK:
        # 레짐 블록을 "## 분석 지시" 바로 위에 삽입
        regime_section = "\n" + _REGIME_CONTEXT_BLOCK[regime] + "\n"
        prompt = prompt.replace(
            "\n## 분석 지시",
            regime_section + "\n## 분석 지시",
        )

    return prompt
