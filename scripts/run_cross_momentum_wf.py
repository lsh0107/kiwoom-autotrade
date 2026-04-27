#!/usr/bin/env python3
# ruff: noqa: DTZ005, T201, RUF002
"""Cross-sectional momentum (12-1) walk-forward 검증.

배경:
    ADR-016~020 폐기: individual asset / short-horizon / mean-reversion 계열 전부 실패.
    학계 사전증거 가장 강한 anomaly = Cross-sectional momentum (Jegadeesh-Titman 1993).
    한국 KOSPI/KOSDAQ 실증 다수. walk-forward 통과 못 하면 카테고리 카드 소진 기준 재논의.

전략:
    - 신호: 12-1 month cross-sectional momentum
    - 필터1: 252일 vol 하위 50% (Low-vol anomaly, Hsu 2013)
    - 필터2: 200일 이평 위 (Trend filter, Moskowitz 2012)
    - 포지션: 상위 데실 (~10-20종목), equal weight, monthly rebalance

파라미터 Grid (8 combo):
    top_decile   [0.1, 0.2]
    use_vol_filter   [True, False]
    use_trend_filter [True, False]
    2 × 2 × 2 = 8 조합

Walk-forward:
    - 데이터: 5년 (2021-04-27 ~ 2026-04-27) + 이력 1년 선행
    - IS: 24개월, OOS: 6개월, step: 6개월 → 6 윈도우
    - 유니버스: KOSPI50 + KOSDAQ50 = 100종목 (KOSPI100 + KOSDAQ100 대리)

통과 기준:
    - OOS Sharpe ≥ 1.0
    - OOS MDD ≥ -25%
    - OOS IR vs KOSPI ≥ 0.5
    - OOS/IS Sharpe 비율 ≥ 0.7
    - combo별 pass_rate ≥ 30% (6 윈도우 중 ≥ 2개 통과)

산출물:
    docs/backtest-results/walk_forward_cross_momentum_YYYYMMDD_HHMMSS.json

사용법:
    python scripts/run_cross_momentum_wf.py
    python scripts/run_cross_momentum_wf.py --fast          # 20종목 빠른 검증
    python scripts/run_cross_momentum_wf.py --dry-run       # Grid만 출력
    python scripts/run_cross_momentum_wf.py --combo 0      # 단일 combo
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.portfolio_engine import CrossMomentumPortfolioEngine, PortfolioBacktestResult
from src.broker.schemas import DailyPrice
from src.strategy.cross_momentum import CrossMomentumParams

RESULTS_DIR = Path("docs/backtest-results")

# ── 유니버스 정의 ─────────────────────────────────────────────────────────────
# KOSPI 시총 상위 100 (정적 근사 리스트 — pykrx KRX 마켓-레벨 API 불안정 대비)
KOSPI_UNIVERSE: list[str] = [
    # 초대형주 (시총 상위 30)
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "373220",  # LG에너지솔루션
    "207940",  # 삼성바이오로직스
    "005380",  # 현대차
    "005490",  # POSCO홀딩스
    "068270",  # 셀트리온
    "000270",  # 기아
    "035420",  # NAVER
    "035720",  # 카카오
    "006400",  # 삼성SDI
    "051910",  # LG화학
    "003670",  # 포스코퓨처엠
    "028260",  # 삼성물산
    "105560",  # KB금융
    "055550",  # 신한지주
    "096770",  # SK이노베이션
    "086790",  # 하나금융지주
    "032830",  # 삼성생명
    "012330",  # 현대모비스
    "034730",  # SK
    "066570",  # LG전자
    "003550",  # LG
    "030200",  # KT
    "017670",  # SK텔레콤
    "033780",  # KT&G
    "009150",  # 삼성전기
    "000810",  # 삼성화재
    "316140",  # 우리금융지주
    "010950",  # S-Oil
    # 대형주 (31-60)
    "015760",  # 한국전력
    "011200",  # HMM
    "011070",  # LG이노텍
    "024110",  # 기업은행
    "138040",  # 메리츠금융지주
    "267250",  # HD현대중공업
    "042660",  # 한화오션
    "009540",  # HD한국조선해양
    "010140",  # 삼성중공업
    "004020",  # 현대제철
    "010130",  # 고려아연
    "047050",  # POSCO인터내셔널
    "078930",  # GS
    "000100",  # 유한양행
    "071050",  # 한국금융지주
    "090430",  # 아모레퍼시픽
    "002790",  # 아모레G
    "011780",  # 금호석유화학
    "036460",  # 한국가스공사
    "008560",  # 메리츠화재
    "001450",  # 현대해상
    "039490",  # 키움증권
    "016360",  # 삼성증권
    "003600",  # SK케미칼
    "000240",  # 한국타이어앤테크놀로지
    "042670",  # 두산밥캣
    "001040",  # CJ
    "069960",  # 현대백화점
    "032640",  # LG유플러스
    "003690",  # 코리안리
    # 중대형주 (61-100)
    "000720",  # 현대건설
    "034020",  # 두산에너빌리티
    "011170",  # 롯데케미칼
    "009830",  # 한화솔루션
    "086280",  # 현대글로비스
    "097950",  # CJ제일제당
    "271560",  # 오리온
    "036570",  # 엔씨소프트
    "000080",  # 하이트진로
    "138930",  # BNK금융지주
    "175330",  # JB금융지주
    "047040",  # 대우건설
    "006360",  # GS건설
    "021240",  # 코웨이
    "047810",  # 한국항공우주
    "035250",  # 강원랜드
    "005940",  # NH투자증권
    "006800",  # 미래에셋증권
    "004170",  # 신세계
    "007070",  # GS리테일
    "000150",  # 두산
    "023530",  # 롯데쇼핑
    "028670",  # 팬오션
    "011790",  # SKC
    "010120",  # LS ELECTRIC
    "010620",  # HD현대미포조선
    "112610",  # 씨에스윈드
    "006260",  # LS
    "003230",  # 삼양식품
    "009880",  # 한화
    "004990",  # 롯데지주
    "007310",  # 오뚜기
    "002380",  # KCC
    "001230",  # 동국제강
    "000120",  # CJ대한통운
    "064350",  # 현대로템
    "005180",  # 빙그레
    "267270",  # HD현대
    "004370",  # 농심
    "057050",  # 현대홈쇼핑
]

# KOSDAQ 시총 상위 100 (정적 근사 리스트)
KOSDAQ_UNIVERSE: list[str] = [
    # 2차전지/소재 (상위권)
    "247540",  # 에코프로비엠
    "086520",  # 에코프로
    "066970",  # L&F
    "382800",  # 엔켐
    "091580",  # 상아프론테크
    "178920",  # PI첨단소재
    "357780",  # 솔브레인
    "078600",  # 대주전자재료
    "036830",  # 솔브레인홀딩스
    "024900",  # 덕산하이메탈
    # 반도체/장비
    "042700",  # 한미반도체
    "058470",  # 리노공업
    "036930",  # 주성엔지니어링
    "031980",  # 피에스케이
    "095340",  # ISC
    "140860",  # 파크시스템스
    "240810",  # 원익IPS
    "054950",  # 이오테크닉스
    "064760",  # 티씨케이
    "268280",  # AP시스템
    "403870",  # HPSP
    "080000",  # 서울반도체
    "100120",  # 뷰웍스
    "091700",  # 파트론
    "089030",  # 테크윙
    # 바이오/제약
    "196170",  # 알테오젠
    "145020",  # 휴젤
    "214150",  # 클래시스
    "328130",  # 루닛
    "086900",  # 메디톡스
    "084110",  # 휴온스글로벌
    "230240",  # 에스티팜
    "067630",  # 에이치엘비
    "028300",  # HLB
    "200130",  # 콜마비앤에이치
    "085660",  # 차바이오텍
    "145750",  # 파마리서치프로덕트
    "039420",  # 케어젠
    "330350",  # 현대바이오
    "298380",  # 에이비엘바이오
    "096530",  # 씨젠
    "039200",  # 오스코텍
    "950130",  # 엑스페릭스
    "083790",  # 크리스탈지노믹스
    # 게임/미디어/엔터
    "035900",  # JYP Ent.
    "041510",  # SM엔터테인먼트
    "263750",  # 펄어비스
    "293490",  # 카카오게임즈
    "112040",  # 위메이드
    "053580",  # 웹젠
    "067160",  # 수프(구 아프리카TV)
    "253450",  # 스튜디오드래곤
    "192400",  # 쿠쿠홀딩스
    # IT/소프트웨어
    "053800",  # 안랩
    "078250",  # 아이씨디
    "047560",  # 이스트소프트
    "033290",  # 코웰패션
    "285540",  # 쏘카
    "060310",  # 3S
    # 에너지/신소재
    "037670",  # 후성
    "025860",  # 남해화학
    "232140",  # 와이씨
    # 기타 산업재
    "091580",  # 상아프론테크 (중복 — 아래에서 자동 제거)
    "277880",  # 티엘아이
    "013310",  # 일진전기
    "192080",  # 위메이드맥스
    "065500",  # 오스코텍 (중복 — 아래서 자동 제거)
    "014190",  # 인터파크홀딩스
    "119650",  # 지씨셀
    "108675",  # LX하우시스우
    "089820",  # 지티에스앤엠
    "019540",  # 일진홀딩스
    "088800",  # 에이스테크
    "066830",  # 유바이오로직스
    "039570",  # 에이테크솔루션
    "041960",  # 단암시스템즈
    "049630",  # 재영솔루텍
    "064790",  # 아이씨디 (중복 가능)
    "067080",  # 대화제약
    "055490",  # 아주캐피탈?
    "019550",  # 일진전기 (중복 가능)
]


# 전체 유니버스: 중복 제거 후 최대 200종목 (KOSPI 100 + KOSDAQ 100)
def _deduplicate(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


FULL_UNIVERSE: list[str] = _deduplicate(KOSPI_UNIVERSE + KOSDAQ_UNIVERSE)

# 빠른 검증용 20종목 (--fast)
FAST_UNIVERSE: list[str] = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "005380",  # 현대차
    "035420",  # NAVER
    "105560",  # KB금융
    "055550",  # 신한지주
    "247540",  # 에코프로비엠
    "086520",  # 에코프로
    "196170",  # 알테오젠
    "145020",  # 휴젤
    "042700",  # 한미반도체
    "357780",  # 솔브레인
    "066570",  # LG전자
    "000270",  # 기아
    "035900",  # JYP Ent.
    "041510",  # SM엔터테인먼트
    "068270",  # 셀트리온
    "214150",  # 클래시스
    "009150",  # 삼성전기
    "140860",  # 파크시스템스
]

# KOSPI 지수 코드 (벤치마크)
KOSPI_INDEX_CODE = "1001"

# 데이터 기간 (이력 포함)
DATA_START_DATE = "20200101"  # 13개월 이력 확보를 위해 2021 시작보다 1년+ 선행
DATA_END_DATE = "20260427"

# Walk-forward 윈도우 정의 (IS=24mo, OOS=6mo, step=6mo, 6 윈도우)
WF_WINDOWS: list[tuple[str, str, str, str]] = [
    # (is_start, is_end, oos_start, oos_end)
    ("20210427", "20230331", "20230401", "20230930"),  # W1
    ("20211027", "20230930", "20231001", "20240331"),  # W2
    ("20220427", "20240331", "20240401", "20240930"),  # W3
    ("20221027", "20240930", "20241001", "20250331"),  # W4
    ("20230427", "20250331", "20250401", "20250930"),  # W5
    ("20231027", "20250930", "20251001", "20260430"),  # W6
]

# 통과 기준
PASS_SHARPE = 1.0
PASS_MDD = -0.25
PASS_IR = 0.5
PASS_OOS_IS_RATIO = 0.7
PASS_WINDOW_RATE = 0.30  # combo 통과: ≥ 30% 윈도우 통과

log = logging.getLogger("cross_momentum_wf")


# ── 데이터 클래스 ──────────────────────────────────────────────────────────────


@dataclass
class WFWindowResult:
    """Walk-forward 단일 윈도우 결과."""

    window_id: int
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    is_result: PortfolioBacktestResult
    oos_result: PortfolioBacktestResult

    @property
    def sharpe_degradation(self) -> float:
        """OOS Sharpe / IS Sharpe."""
        is_s = self.is_result.metrics.get("sharpe_ratio", 0.0)
        oos_s = self.oos_result.metrics.get("sharpe_ratio", 0.0)
        return oos_s / is_s if is_s > 0 else 0.0

    def oos_passes(self) -> bool:
        """OOS 기준 통과 여부."""
        oos = self.oos_result.metrics
        return (
            oos.get("sharpe_ratio", 0.0) >= PASS_SHARPE
            and oos.get("max_drawdown", 0.0) >= PASS_MDD
            and oos.get("ir_vs_benchmark", 0.0) >= PASS_IR
            and self.sharpe_degradation >= PASS_OOS_IS_RATIO
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "is_dates": f"{self.is_start}~{self.is_end}",
            "oos_dates": f"{self.oos_start}~{self.oos_end}",
            "is_metrics": self.is_result.metrics,
            "oos_metrics": self.oos_result.metrics,
            "sharpe_degradation": round(self.sharpe_degradation, 4),
            "oos_passes": self.oos_passes(),
        }


@dataclass
class ComboResult:
    """단일 파라미터 조합 walk-forward 결과."""

    combo_id: int
    label: str
    params: CrossMomentumParams
    windows: list[WFWindowResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for w in self.windows if w.oos_passes())

    @property
    def pass_rate(self) -> float:
        return self.pass_count / len(self.windows) if self.windows else 0.0

    @property
    def verdict(self) -> str:
        return "PASS" if self.pass_rate >= PASS_WINDOW_RATE else "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "combo_id": self.combo_id,
            "label": self.label,
            "params": self.params.to_dict(),
            "pass_count": self.pass_count,
            "total_windows": len(self.windows),
            "pass_rate": round(self.pass_rate, 4),
            "verdict": self.verdict,
            "windows": [w.to_dict() for w in self.windows],
        }


# ── 유틸 함수 ─────────────────────────────────────────────────────────────────


def setup_logging() -> None:
    """로깅 설정."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def fetch_pykrx_daily(symbol: str, start: str, end: str) -> list[DailyPrice]:
    """pykrx로 종목 일봉 수집.

    Args:
        symbol: 종목코드 (6자리)
        start: 시작일 (YYYYMMDD)
        end: 종료일 (YYYYMMDD)

    Returns:
        list[DailyPrice]: 일봉 데이터 (날짜 오름차순). 오류 시 []
    """
    from pykrx import stock as pykrx_stock  # lazy import

    df = pykrx_stock.get_market_ohlcv_by_date(start, end, symbol)
    if df is None or df.empty:
        return []

    result: list[DailyPrice] = []
    for idx, row in df.iterrows():
        date_str = str(idx).replace("-", "")[:8]
        result.append(
            DailyPrice(
                date=date_str,
                open=int(row.get("시가", row.get("Open", 0))),
                high=int(row.get("고가", row.get("High", 0))),
                low=int(row.get("저가", row.get("Low", 0))),
                close=int(row.get("종가", row.get("Close", 0))),
                volume=int(row.get("거래량", row.get("Volume", 0))),
            )
        )
    result.sort(key=lambda x: x.date)
    return result


def fetch_pykrx_index(index_code: str, start: str, end: str) -> list[DailyPrice]:
    """pykrx로 지수 일봉 수집 (벤치마크용).

    get_index_ohlcv_by_date 실패 시 KODEX 200 (069500) 종목 데이터로 fallback.

    Args:
        index_code: 지수코드 ("1001" = KOSPI, 현재는 fallback 트리거용)
        start: 시작일 (YYYYMMDD)
        end: 종료일 (YYYYMMDD)

    Returns:
        list[DailyPrice]: 지수 일봉 데이터 (날짜 오름차순). 실패 시 []
    """
    from pykrx import stock as pykrx_stock  # lazy import

    try:
        df = pykrx_stock.get_index_ohlcv_by_date(start, end, index_code)
        if df is not None and not df.empty:
            result: list[DailyPrice] = []
            for idx, row in df.iterrows():
                date_str = str(idx).replace("-", "")[:8]
                close_raw = row.get("종가", row.get("Close", 0))
                result.append(
                    DailyPrice(
                        date=date_str,
                        open=int(row.get("시가", row.get("Open", 0))),
                        high=int(row.get("고가", row.get("High", 0))),
                        low=int(row.get("저가", row.get("Low", 0))),
                        close=int(close_raw),
                        volume=int(row.get("거래량", row.get("Volume", 0)) or 0),
                    )
                )
            result.sort(key=lambda x: x.date)
            if result:
                return result
    except Exception as exc:
        log.warning("지수 API 실패 (%s), KODEX 200 fallback: %s", index_code, exc)

    # Fallback: KODEX 200 (069500) — KOSPI 200 추종 ETF
    log.info("벤치마크 fallback: KODEX 200 (069500)")
    return fetch_pykrx_daily("069500", start, end)


def _get_market_cap_top_n(market: str, n: int, candidates: list[str]) -> list[str]:
    """pykrx로 시장별 시총 상위 n종목 수집. 여러 후보 날짜를 순서대로 시도.

    Args:
        market: "KOSPI" 또는 "KOSDAQ"
        n: 상위 종목 수
        candidates: 시도할 기준일 리스트 (YYYYMMDD, 최근일 우선)

    Returns:
        list[str]: 시총 상위 n 종목 코드. 모두 실패 시 []
    """
    from pykrx import stock as pykrx_stock  # lazy import

    for ref in candidates:
        try:
            df = pykrx_stock.get_market_cap_by_ticker(ref, market=market)
            if df is None or df.empty:
                continue
            if "시가총액" not in df.columns:
                continue
            top_n = list(df.sort_values("시가총액", ascending=False).index[:n])
            if len(top_n) >= n // 2:  # 절반 이상 확보되면 사용
                log.info("%s 시총 상위 %d종목 수집 완료 (ref=%s)", market, len(top_n), ref)
                return top_n
        except Exception:
            pass  # 다음 후보 날짜로
    return []


def fetch_full_universe() -> list[str]:
    """pykrx로 KOSPI·KOSDAQ 시총 상위 100종목씩 동적 수집.

    최근 거래일 후보 여러 개를 순서대로 시도하고, 모두 실패 시 static fallback 사용.

    Returns:
        list[str]: 중복 제거 후 최대 200종목 목록.
    """
    # 최근 거래일 후보 (최신순 — 주말 제외 5일 간격)
    ref_candidates = [
        "20260425",  # 금요일
        "20260424",
        "20260423",
        "20260422",
        "20260421",
        "20260418",
        "20260417",
    ]

    symbols: list[str] = []

    kospi_top = _get_market_cap_top_n("KOSPI", 100, ref_candidates)
    if kospi_top:
        symbols.extend(kospi_top)
    else:
        log.warning("KOSPI 시총 동적 수집 실패 → static fallback (%d종목)", len(KOSPI_UNIVERSE))
        symbols.extend(KOSPI_UNIVERSE)

    kosdaq_top = _get_market_cap_top_n("KOSDAQ", 100, ref_candidates)
    if kosdaq_top:
        symbols.extend(kosdaq_top)
    else:
        log.warning("KOSDAQ 시총 동적 수집 실패 → static fallback (%d종목)", len(KOSDAQ_UNIVERSE))
        symbols.extend(KOSDAQ_UNIVERSE)

    # 중복 제거 (순서 유지)
    seen: set[str] = set()
    unique: list[str] = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    log.info("최종 유니버스: %d종목 (목표: 200)", len(unique))
    return unique


def build_combo_grid() -> list[tuple[str, CrossMomentumParams]]:
    """8개 파라미터 조합 Grid 생성.

    top_decile [0.1, 0.2] × vol_filter [True, False] × trend_filter [True, False]
    = 8 조합

    Returns:
        list[tuple[str, CrossMomentumParams]]: (레이블, 파라미터) 목록
    """
    combos: list[tuple[str, CrossMomentumParams]] = []
    for top in [0.1, 0.2]:
        for vol in [True, False]:
            for trend in [True, False]:
                p = CrossMomentumParams(
                    top_decile=top,
                    use_vol_filter=vol,
                    use_trend_filter=trend,
                )
                combos.append((p.label(), p))
    return combos


def run_combo(
    combo_id: int,
    label: str,
    params: CrossMomentumParams,
    universe_data: dict[str, list[DailyPrice]],
    benchmark_data: list[DailyPrice],
) -> ComboResult:
    """단일 파라미터 조합에 대해 6 윈도우 walk-forward 실행.

    Args:
        combo_id: 조합 인덱스
        label: 조합 레이블
        params: 전략 파라미터
        universe_data: 종목별 전체 일봉 데이터
        benchmark_data: 벤치마크 일봉 데이터

    Returns:
        ComboResult: walk-forward 결과
    """
    engine = CrossMomentumPortfolioEngine()
    result = ComboResult(combo_id=combo_id, label=label, params=params)

    for window_id, (is_start, is_end, oos_start, oos_end) in enumerate(WF_WINDOWS, 1):
        is_res = engine.run(universe_data, benchmark_data, params, is_start, is_end)
        oos_res = engine.run(universe_data, benchmark_data, params, oos_start, oos_end)

        wf_result = WFWindowResult(
            window_id=window_id,
            is_start=is_start,
            is_end=is_end,
            oos_start=oos_start,
            oos_end=oos_end,
            is_result=is_res,
            oos_result=oos_res,
        )
        result.windows.append(wf_result)

        verdict = "PASS" if wf_result.oos_passes() else "FAIL"
        oos_m = oos_res.metrics
        log.info(
            "    W%d [%s] IS Sharpe=%.2f → OOS Sharpe=%.2f MDD=%.1f%% IR=%.2f degrad=%.2f",
            window_id,
            verdict,
            is_res.metrics.get("sharpe_ratio", 0.0),
            oos_m.get("sharpe_ratio", 0.0),
            (oos_m.get("max_drawdown", 0.0) or 0) * 100,
            oos_m.get("ir_vs_benchmark", 0.0),
            wf_result.sharpe_degradation,
        )

    return result


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Cross-sectional momentum walk-forward 검증 실행."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Cross-sectional momentum walk-forward 검증 (KOSPI+KOSDAQ 100종목, 5년)"
    )
    parser.add_argument("--fast", action="store_true", help="20종목 빠른 검증 모드")
    parser.add_argument("--dry-run", action="store_true", help="Grid 조합 출력 후 종료")
    parser.add_argument(
        "--combo",
        type=int,
        default=None,
        help="특정 combo만 실행 (0-indexed)",
    )
    args = parser.parse_args()

    if args.fast:
        universe_list = FAST_UNIVERSE
    else:
        log.info("유니버스 동적 수집 중 (KOSPI+KOSDAQ 시총 상위 100+100)...")
        universe_list = fetch_full_universe()
    combo_grid = build_combo_grid()

    log.info("=" * 70)
    log.info("Cross-sectional Momentum (12-1) Walk-forward 검증")
    log.info("=" * 70)
    log.info("유니버스  : %d종목 (%s)", len(universe_list), "FAST" if args.fast else "FULL")
    log.info("기간      : %s ~ %s", DATA_START_DATE, DATA_END_DATE)
    log.info("WF 설정   : IS=24mo / OOS=6mo / 6 윈도우")
    log.info("Combo     : %d개", len(combo_grid))
    log.info(
        "통과 기준 : OOS Sharpe≥%.1f / MDD≥%.0f%% / IR≥%.1f / OOS-IS≥%.1f / pass_rate≥%.0f%%",
        PASS_SHARPE,
        PASS_MDD * 100,
        PASS_IR,
        PASS_OOS_IS_RATIO,
        PASS_WINDOW_RATE * 100,
    )
    log.info("=" * 70)

    if args.dry_run:
        print(f"\nCombo Grid ({len(combo_grid)} 조합):")
        for i, (label, p) in enumerate(combo_grid):
            print(f"  [{i:02d}] {label} | {p.to_dict()}")
        return

    # 종목 일봉 수집
    log.info("")
    log.info("━" * 70)
    log.info("종목 일봉 데이터 수집 중 (pykrx)... 종목 수: %d", len(universe_list))
    universe_data: dict[str, list[DailyPrice]] = {}
    for symbol in universe_list:
        daily = fetch_pykrx_daily(symbol, DATA_START_DATE, DATA_END_DATE)
        if len(daily) < 120:  # 최소 6개월 데이터
            log.warning("  [SKIP] %s — 데이터 부족 (%d개)", symbol, len(daily))
        else:
            universe_data[symbol] = daily
            log.info(
                "  [OK] %s — %d개 (%s ~ %s)",
                symbol,
                len(daily),
                daily[0].date,
                daily[-1].date,
            )

    log.info("유효 종목: %d/%d개", len(universe_data), len(universe_list))

    if not universe_data:
        log.error("유효 종목 없음 — 종료")
        sys.exit(1)

    # 벤치마크 수집
    log.info("")
    log.info("벤치마크 (KOSPI) 데이터 수집 중...")
    benchmark_data = fetch_pykrx_index(KOSPI_INDEX_CODE, DATA_START_DATE, DATA_END_DATE)
    log.info("  [OK] KOSPI — %d개", len(benchmark_data))

    # 단일 combo 필터
    if args.combo is not None:
        if args.combo < 0 or args.combo >= len(combo_grid):
            log.error("--combo %d 범위 초과 (0-%d)", args.combo, len(combo_grid) - 1)
            sys.exit(1)
        combo_grid = [combo_grid[args.combo]]

    # Combo 실행
    combo_results: list[ComboResult] = []
    log.info("")
    log.info("━" * 70)
    log.info("Walk-forward 실행 시작 (%d combo × 6 윈도우)", len(combo_grid))

    for combo_idx, (label, params) in enumerate(combo_grid, 1):
        log.info("")
        log.info("  [%02d/%02d] Combo: %s", combo_idx, len(combo_grid), label)

        combo_res = run_combo(combo_idx, label, params, universe_data, benchmark_data)
        combo_results.append(combo_res)

        log.info(
            "  → 통과: %d/%d (%.0f%%) [%s]",
            combo_res.pass_count,
            len(combo_res.windows),
            combo_res.pass_rate * 100,
            combo_res.verdict,
        )

    # 최종 요약
    log.info("")
    log.info("=" * 70)
    log.info("Combo별 최종 판정")
    log.info("=" * 70)

    pass_combos: list[str] = []
    fail_combos: list[str] = []

    for cr in combo_results:
        log.info(
            "  [%s] %-40s | 통과 %d/%d (%.0f%%)",
            cr.verdict,
            cr.label,
            cr.pass_count,
            len(cr.windows),
            cr.pass_rate * 100,
        )
        if cr.verdict == "PASS":
            pass_combos.append(cr.label)
        else:
            fail_combos.append(cr.label)

    log.info("")
    if pass_combos:
        best = max(combo_results, key=lambda r: r.pass_rate)
        log.info("통과 Combo: %s", ", ".join(pass_combos))
        log.info("최우수 Combo: %s (pass_rate=%.0f%%)", best.label, best.pass_rate * 100)
        strategy_verdict = "PASS — ADR-021 통과, 모의투자 진입 후보"
    else:
        log.info("⚠  전 Combo 실패 → cross-sectional momentum 폐기 권고")
        log.info("   누적 폐기 5건 → 전략 카테고리 기준 재논의 필요")
        strategy_verdict = "FAIL — 전 Combo 폐기"

    log.info("전략 판정: %s", strategy_verdict)

    # 결과 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "walk_forward_cross_momentum_fast" if args.fast else "walk_forward_cross_momentum_full"
    result_path = RESULTS_DIR / f"{prefix}_{timestamp}.json"

    save_data: dict[str, Any] = {
        "run_type": "cross_sectional_momentum_walk_forward",
        "run_at": datetime.now().isoformat(),
        "strategy_verdict": strategy_verdict,
        "universe": {
            "mode": "fast" if args.fast else "full",
            "total": len(universe_data),
            "symbols": list(universe_data.keys()),
        },
        "walk_forward_config": {
            "is_months": 24,
            "oos_months": 6,
            "step_months": 6,
            "n_windows": len(WF_WINDOWS),
            "windows": [{"is": f"{w[0]}~{w[1]}", "oos": f"{w[2]}~{w[3]}"} for w in WF_WINDOWS],
        },
        "pass_criteria": {
            "oos_sharpe": PASS_SHARPE,
            "oos_mdd": PASS_MDD,
            "oos_ir": PASS_IR,
            "oos_is_sharpe_ratio": PASS_OOS_IS_RATIO,
            "min_window_pass_rate": PASS_WINDOW_RATE,
        },
        "combo_summary": [
            {
                "combo_id": cr.combo_id,
                "label": cr.label,
                "pass_count": cr.pass_count,
                "total_windows": len(cr.windows),
                "pass_rate": round(cr.pass_rate, 4),
                "verdict": cr.verdict,
            }
            for cr in combo_results
        ],
        "combo_results": [cr.to_dict() for cr in combo_results],
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

    log.info("결과 저장: %s", result_path)


if __name__ == "__main__":
    main()
