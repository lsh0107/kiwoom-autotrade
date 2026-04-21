#!/usr/bin/env python3
# ruff: noqa: T201, DTZ005
"""종목 스크리닝 — 모멘텀 돌파 전략 대상 종목 자동 선별.

고정 유니버스에서 52주 신고가 근처 + 거래량 급증 조건을 충족하는 종목을 선별한다.

사용법:
    python scripts/screen_symbols.py
    python scripts/screen_symbols.py --threshold 0.90 --volume-ratio 1.2

필수 환경변수:
    KIWOOM_MOCK_APP_KEY: 모의투자 앱 키
    KIWOOM_MOCK_APP_SECRET: 모의투자 앱 시크릿
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.broker.constants import API_IDS, DEFAULT_EXCHANGE, ENDPOINTS, MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import DailyPrice, to_kiwoom_symbol
from src.screening.engine import (
    calc_prev_day_change,
    check_screen_condition,
    check_volume_surge,
    count_consecutive_bullish,
    is_52w_new_high,
    rank_and_fill,
)

# 기존 임포트 경로 유지용 재노출 (tests/scripts/test_screen_symbols.py 호환).
__all__ = [
    "calc_prev_day_change",
    "check_screen_condition",
    "check_volume_surge",
    "count_consecutive_bullish",
    "is_52w_new_high",
    "rank_and_fill",
]

# ── 고정 유니버스 ─────────────────────────────────────
# KOSPI 시총 상위 + KOSDAQ 대형주 (2026 기준, 필요시 수정)
# 테마별 최소 3종목 확보, 총 140개

UNIVERSE: dict[str, str] = {
    # ── 반도체 ──
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "009150": "삼성전기",
    "403870": "HPSP",
    "095340": "ISC",
    "058470": "리노공업",
    "042700": "한미반도체",
    "241560": "두산테스나",
    "357780": "솔브레인",
    "166090": "하나머티리얼즈",
    "187220": "제주반도체",
    "039030": "이오테크닉스",
    "103140": "풍산",
    "436530": "HPSP",
    # ── 2차전지/소재 ──
    "051910": "LG화학",
    "003670": "포스코퓨처엠",
    "006400": "삼성SDI",
    "247540": "에코프로비엠",
    "086520": "에코프로",
    "373220": "LG에너지솔루션",
    "006260": "LS",
    "011790": "SKC",
    "298040": "효성중공업",
    "064350": "현대로템",
    "006110": "삼아알미늄",
    # ── 자동차 ──
    "005380": "현대차",
    "000270": "기아",
    "012330": "현대모비스",
    "018880": "한온시스템",
    "161390": "한국타이어앤테크놀로지",
    "204320": "만도",
    # ── 바이오/헬스케어 ──
    "068270": "셀트리온",
    "196170": "알테오젠",
    "145020": "휴젤",
    "328130": "루닛",
    "207940": "삼성바이오로직스",
    "326030": "SK바이오팜",
    "000100": "유한양행",
    "128940": "한미약품",
    "302440": "SK바이오사이언스",
    "950210": "프레스티지바이오파마",
    "141080": "레고켐바이오사이언스",
    "195940": "HK이노엔",
    "009420": "한올바이오파마",
    "298380": "에이비엘바이오",
    "269620": "시선바이오",
    # ── IT/플랫폼 ──
    "035420": "NAVER",
    "035720": "카카오",
    "377300": "카카오페이",
    "018260": "삼성에스디에스",
    "030200": "KT",
    "017670": "SK텔레콤",
    "259960": "크래프톤",
    "036930": "주성엔지니어링",
    "000990": "DB하이텍",
    # ── 금융 ──
    "055550": "신한지주",
    "105560": "KB금융",
    "086790": "하나금융지주",
    "316140": "우리금융지주",
    "032830": "삼성생명",
    "138930": "BNK금융지주",
    "024110": "기업은행",
    "175330": "JB금융지주",
    "139130": "DGB금융지주",
    "000810": "삼성화재",
    "088350": "한화생명",
    # ── 조선/해운 ──
    "009540": "HD한국조선해양",
    "042660": "한화오션",
    "329180": "HD현대중공업",
    "011200": "HMM",
    "010620": "HD현대미포",
    # ── 방산 ──
    "012450": "한화에어로스페이스",
    "079550": "LIG넥스원",
    "047810": "한국항공우주",
    "299660": "현대로템",
    "014970": "삼기이브이",
    # ── 엔터/미디어 ──
    "352820": "하이브",
    "041510": "에스엠",
    "035900": "JYP Ent.",
    "034230": "파라다이스",
    "079160": "CJ CGV",
    # ── 게임 ──
    "263750": "펄어비스",
    "036570": "엔씨소프트",
    "293490": "카카오게임즈",
    "112040": "위메이드",
    "251270": "넷마블",
    "078340": "컴투스",
    # ── 건설/인프라 ──
    "000720": "현대건설",
    "028260": "삼성물산",
    "006360": "GS건설",
    "047040": "대우건설",
    "375500": "DL이앤씨",
    # ── 에너지/유틸리티 ──
    "010950": "S-Oil",
    "015760": "한국전력",
    "034020": "두산에너빌리티",
    "047050": "포스코인터내셔널",
    "267260": "HD현대일렉트릭",
    "009830": "한화솔루션",
    "336260": "두산퓨얼셀",
    "034730": "SK",
    # ── 철강/소재 ──
    "005490": "POSCO홀딩스",
    "010130": "고려아연",
    "004020": "현대제철",
    "001040": "CJ",
    "002380": "KCC",
    # ── 소비재 ──
    "033780": "KT&G",
    "090430": "아모레퍼시픽",
    "051900": "LG생활건강",
    "004170": "신세계",
    "023530": "롯데쇼핑",
    "139480": "이마트",
    "069960": "현대백화점",
    "097950": "CJ제일제당",
    "271560": "오리온",
    "280360": "롯데웰푸드",
    # ── 지주 ──
    "003550": "LG",
    "267250": "HD현대",
    "000150": "두산",
    "006800": "미래에셋증권",
    "003490": "대한항공",
    "020560": "아시아나항공",
    # ── AI/로봇/신산업 ──
    "454910": "두산로보틱스",
    "272210": "한화시스템",
    "443060": "레인보우로보틱스",
    "357120": "코람코라이프인프라리츠",
    "322000": "현대에너지솔루션",
    "089030": "테크윙",
    "005385": "현대차2우B",
    "226320": "잇츠한불",
    # ── KOSDAQ 대형주 ──
    "086900": "메디톡스",
    "214150": "클래시스",
    "041190": "우리기술투자",
    "365550": "ESR켄달스퀘어리츠",
    "140410": "메지온",
    "383220": "F&F",
    "348370": "엔켐",
    "039200": "오스코텍",
    "950170": "JTC",
    "067160": "아프리카TV",
    "240810": "원익IPS",
}

# ── 테마/섹터 분류 ────────────────────────────────────
# 같은 섹터 내 최대 1개 포지션 규칙 적용 시 사용

SECTOR_MAP: dict[str, str] = {
    # 반도체
    "005930": "반도체",
    "000660": "반도체",
    "009150": "반도체",
    "403870": "반도체",
    "095340": "반도체",
    "058470": "반도체",
    # 2차전지
    "051910": "2차전지",
    "003670": "2차전지",
    "006400": "2차전지",
    "247540": "2차전지",
    "086520": "2차전지",
    # 자동차
    "005380": "자동차",
    "000270": "자동차",
    "012330": "자동차",
    # 바이오
    "068270": "바이오",
    "196170": "바이오",
    "145020": "바이오",
    "328130": "바이오",
    "207940": "바이오",
    # IT/플랫폼
    "035420": "IT플랫폼",
    "035720": "IT플랫폼",
    "377300": "IT플랫폼",
    "018260": "IT플랫폼",
    # 금융
    "055550": "금융",
    "105560": "금융",
    "086790": "금융",
    "316140": "금융",
    "032830": "금융",
    # 조선
    "009540": "조선",
    "042660": "조선",
    "329180": "조선",
    "011200": "조선",
    # 방산
    "012450": "방산",
    "079550": "방산",
    # 엔터
    "352820": "엔터",
    "041510": "엔터",
    "035900": "엔터",
    # 게임
    "263750": "게임",
    "036570": "게임",
    "293490": "게임",
    "112040": "게임",
    # 건설
    "000720": "건설",
    "028260": "건설",
    # 에너지
    "010950": "에너지",
    "015760": "에너지",
    "034020": "에너지",
    "047050": "에너지",
    # 철강/소재
    "005490": "철강",
    "010130": "철강",
    # 소비재
    "033780": "소비재",
    "090430": "소비재",
    "051900": "소비재",
    # 지주
    "003550": "지주",
    "034730": "지주",
    "267250": "지주",
}

# ── 단타/스윙 적합도 힌트 ─────────────────────────────
# "day": 변동성 크고 유동성 좋은 종목 (단타 우선)
# "swing": 추세 안정적 대형주 (스윙 우선)
# "both": 둘 다 가능

STRATEGY_HINT: dict[str, str] = {
    # 반도체
    "005930": "swing",
    "000660": "swing",
    "009150": "both",
    "403870": "day",
    "095340": "day",
    "058470": "day",
    # 2차전지
    "051910": "both",
    "003670": "day",
    "006400": "swing",
    "247540": "day",
    "086520": "day",
    # 자동차
    "005380": "swing",
    "000270": "swing",
    "012330": "swing",
    # 바이오
    "068270": "both",
    "196170": "day",
    "145020": "day",
    "328130": "day",
    "207940": "swing",
    # IT
    "035420": "swing",
    "035720": "both",
    "377300": "day",
    "018260": "swing",
    # 금융
    "055550": "swing",
    "105560": "swing",
    "086790": "swing",
    "316140": "swing",
    "032830": "swing",
    # 조선
    "009540": "day",
    "042660": "day",
    "329180": "day",
    "011200": "both",
    # 방산
    "012450": "day",
    "079550": "day",
    # 엔터
    "352820": "day",
    "041510": "day",
    "035900": "day",
    # 게임
    "263750": "day",
    "036570": "both",
    "293490": "day",
    "112040": "day",
    # 건설
    "000720": "swing",
    "028260": "swing",
    # 에너지
    "010950": "swing",
    "015760": "swing",
    "034020": "both",
    "047050": "swing",
    # 철강
    "005490": "swing",
    "010130": "both",
    # 소비재
    "033780": "swing",
    "090430": "swing",
    "051900": "swing",
    # 지주
    "003550": "swing",
    "034730": "swing",
    "267250": "swing",
}


def get_sector(symbol: str) -> str:
    """종목코드의 섹터 반환. 미분류 시 '기타'."""
    return SECTOR_MAP.get(symbol, "기타")


def get_strategy_hint(symbol: str) -> str:
    """종목의 단타/스윙 적합도 힌트 반환."""
    return STRATEGY_HINT.get(symbol, "both")


RESULTS_DIR = Path("docs/backtest-results")


# ── 유틸 ──────────────────────────────────────────────


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        print(f"[ERROR] 환경변수 {key}가 없습니다.")
        sys.exit(1)
    return value


def _safe_int(v: str | int) -> int:
    """부호 접두사 포함 가격/수량 안전 변환."""
    if isinstance(v, int):
        return abs(v)
    s = str(v).lstrip("+-")
    return int(s) if s else 0


def parse_daily_raw(raw_items: list[dict]) -> list[DailyPrice]:
    """ka10086 원본 응답을 DailyPrice 리스트로 변환."""
    results: list[DailyPrice] = []
    for item in raw_items:
        try:
            results.append(
                DailyPrice(
                    date=item.get("date", ""),
                    open=_safe_int(item.get("open_pric", 0)),
                    high=_safe_int(item.get("high_pric", 0)),
                    low=_safe_int(item.get("low_pric", 0)),
                    close=_safe_int(item.get("close_pric", item.get("cur_prc", 0))),
                    volume=_safe_int(item.get("trde_qty", 0)),
                )
            )
        except (ValueError, TypeError):
            continue
    return results


# ── 데이터 수집 ──────────────────────────────────────


def _is_db_daily_candles_enabled() -> bool:
    """USE_DB_DAILY_CANDLES 활성 여부 (Design 011 feature flag)."""
    return os.environ.get("USE_DB_DAILY_CANDLES", "false").lower() in ("true", "1", "yes")


async def fetch_daily_pages(
    client: KiwoomClient, symbol: str, max_pages: int = 13
) -> list[DailyPrice]:
    """일봉 데이터 수집 (ka10086). 연속 조회로 52주 데이터 수집.

    Design 011: `USE_DB_DAILY_CANDLES` 활성 시 `DailyCandleStore`로 DB 우선 조회,
    비활성 시 종전 키움 페이징 경로 유지(기본값).
    """
    if _is_db_daily_candles_enabled():
        from src.trading.daily_candle_store import DailyCandleStore

        database_url = os.environ.get("DATABASE_URL")
        store = DailyCandleStore(database_url=database_url, use_db=True)
        # max_pages 13 * 60bars =~ 260 거래일 → lookback_days=max_pages*30
        lookback_days = max(60, max_pages * 30)
        return await store.get_daily_prices(
            symbol,
            lookback_days=lookback_days,
            kiwoom_client=client,
        )

    all_raw: list[dict] = []
    qry_dt = datetime.now().strftime("%Y%m%d")

    for page in range(max_pages):
        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)
        try:
            data = await client._request(
                ENDPOINTS["market"],
                API_IDS["daily_price"],
                json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
            )
        except Exception:
            print(f"    [{symbol}] 일봉 {page}페이지 에러 → 3초 대기 후 재시도")
            await asyncio.sleep(3)
            try:
                data = await client._request(
                    ENDPOINTS["market"],
                    API_IDS["daily_price"],
                    json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
                )
            except Exception as e:
                print(f"    [{symbol}] 재시도 실패: {e}")
                break

        items = data.get("daly_stkpc", [])
        if not items:
            break
        all_raw.extend(items)

        last_date = items[-1].get("date", "")
        if not last_date:
            break
        qry_dt = last_date
        await asyncio.sleep(0.8)

    daily = parse_daily_raw(all_raw)
    daily.sort(key=lambda x: x.date)
    return daily


# ── 스크리닝 ─────────────────────────────────────────
# 순수 계산 로직(calc_prev_day_change, check_volume_surge, count_consecutive_bullish,
# is_52w_new_high, check_screen_condition, rank_and_fill)은 src/screening/engine.py
# 로 이동했다. 이 파일은 CLI/네트워크 래퍼에 집중한다.


async def screen_all(
    client: KiwoomClient,
    universe: dict[str, str],
    threshold: float,
    volume_ratio: float,
    min_stocks: int = 10,
) -> list[dict]:
    """유니버스 전체 스크리닝.

    조건 충족 종목이 min_stocks 미만이면 price_ratio 상위로 채운다.
    """
    all_candidates: list[dict] = []
    total = len(universe)

    for i, (symbol, name) in enumerate(universe.items(), 1):
        print(f"  [{i}/{total}] {symbol} {name}...", end=" ", flush=True)

        try:
            daily = await fetch_daily_pages(client, symbol)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        if not daily:
            print("데이터 없음")
            continue

        result = check_screen_condition(daily, threshold, volume_ratio)
        if result is None:
            print("데이터 부족")
            continue

        sector = get_sector(symbol)
        hint = get_strategy_hint(symbol)
        entry = {"symbol": symbol, "name": name, "sector": sector, "hint": hint, **result}
        all_candidates.append(entry)

        status = "PASS" if result["passed"] else "skip"
        bonus = result.get("bonus_score", 0)
        print(
            f"{status} | 종가 {result['close']:,} | "
            f"52주고 {result['high_52w']:,} ({result['price_ratio']:.1%}) | "
            f"거래량 {result['vol_ratio']:.1f}x | 보너스 {bonus}점"
        )

        # 종목 간 쿨다운 (일봉 연속조회 후 다음 종목)
        await asyncio.sleep(2)

    # 정렬 + 최소 종목 보충 (순수 로직은 engine.rank_and_fill 재사용)
    before_fill_passed = {c["symbol"] for c in all_candidates if c.get("passed")}
    passed = rank_and_fill(all_candidates, min_stocks=min_stocks)
    for c in passed:
        if c["symbol"] not in before_fill_passed:
            sym, name = c["symbol"], c["name"]
            pr = c["price_ratio"]
            bs = c.get("bonus_score", 0)
            print(f"  [보충] {sym} {name} (bonus={bs}, price_ratio={pr:.1%})")

    return passed


# ── 장중 재스크리닝 ──────────────────────────────────


async def rescreen_intraday(
    client: KiwoomClient,
    existing_symbols: list[str],
    *,
    threshold: float = 0.75,
    volume_ratio: float = 0.8,
) -> list[str]:
    """장중 재스크리닝 — 기존 유니버스에서 새 조건 통과 종목 추가 발견.

    UNIVERSE 전체를 대상으로 check_screen_condition 재실행.
    이미 existing_symbols에 포함된 종목은 스킵.

    Returns:
        새로 통과한 종목 코드 리스트
    """
    new_symbols: list[str] = []
    skip_set = set(existing_symbols)

    for symbol in UNIVERSE:
        if symbol in skip_set:
            continue

        try:
            daily = await fetch_daily_pages(client, symbol, max_pages=5)
        except Exception as e:
            print(f"    [{symbol}] 재스크리닝 일봉 조회 실패: {e}")
            continue

        if not daily:
            continue

        result = check_screen_condition(daily, threshold, volume_ratio)
        if result is not None and result["passed"]:
            new_symbols.append(symbol)

    return new_symbols


# ── 메인 ─────────────────────────────────────────────


async def main() -> None:
    """종목 스크리닝 실행."""
    parser = argparse.ArgumentParser(description="모멘텀 돌파 전략 종목 스크리닝")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="52주 신고가 대비 최소 비율 (기본: 0.75 = 75%%)",
    )
    parser.add_argument(
        "--volume-ratio",
        type=float,
        default=0.8,
        help="평균 거래량 대비 최소 배수 (기본: 0.8)",
    )
    parser.add_argument(
        "--min-stocks",
        type=int,
        default=10,
        help="최소 통과 종목 수 (미달 시 price_ratio 상위로 보충, 기본: 10)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("모멘텀 돌파 전략 — 종목 스크리닝")
    print(f"실행: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"유니버스  : {len(UNIVERSE)}개 (KOSPI+KOSDAQ)")
    print(f"조건     : 52주고가 {args.threshold:.0%} 이상 + 거래량 {args.volume_ratio}배 이상")
    print(f"최소 종목: {args.min_stocks}개 (미달 시 상위 랭킹 보충)")
    print("=" * 60)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    app_key = get_env_or_exit("KIWOOM_MOCK_APP_KEY")
    app_secret = get_env_or_exit("KIWOOM_MOCK_APP_SECRET")

    client = KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key=app_key,
        app_secret=app_secret,
        is_mock=True,
    )

    try:
        await client.authenticate()
        print("\n[OK] 토큰 발급 성공\n")

        passed = await screen_all(
            client, UNIVERSE, args.threshold, args.volume_ratio, args.min_stocks
        )
    finally:
        await client.close()

    # 결과 출력
    print(f"\n{'=' * 60}")
    print(f"스크리닝 결과: {len(passed)}개 / {len(UNIVERSE)}개 통과")
    print(f"{'=' * 60}")
    for s in passed:
        sector = s.get("sector", "기타")
        hint = s.get("hint", "both")
        bonus = s.get("bonus_score", 0)
        print(
            f"  {s['symbol']} {s['name']} [{sector}/{hint}] | "
            f"종가 {s['close']:,} | 52주고 ({s['price_ratio']:.1%}) | "
            f"거래량 {s['vol_ratio']:.1f}x | 보너스 {bonus}점"
        )

    if not passed:
        print("  (조건 충족 종목 없음)")

    # 결과 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"screened_{timestamp}.json"

    output = {
        "run_at": datetime.now().isoformat(),
        "threshold": args.threshold,
        "volume_ratio": args.volume_ratio,
        "universe_size": len(UNIVERSE),
        "passed_count": len(passed),
        "symbols": [s["symbol"] for s in passed],
        "details": passed,
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {result_path}")


if __name__ == "__main__":
    asyncio.run(main())
