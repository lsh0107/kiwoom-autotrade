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

# ── 고정 유니버스 ─────────────────────────────────────
# KOSPI 시총 상위 + KOSDAQ 대형주 (2026 기준, 필요시 수정)
# 테마별 최소 3종목 확보, 총 60+개

UNIVERSE: dict[str, str] = {
    # ── 반도체 ──
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "009150": "삼성전기",
    "403870": "HPSP",
    "095340": "ISC",
    "058470": "리노공업",
    # ── 2차전지/소재 ──
    "051910": "LG화학",
    "003670": "포스코퓨처엠",
    "006400": "삼성SDI",
    "247540": "에코프로비엠",
    "086520": "에코프로",
    # ── 자동차 ──
    "005380": "현대차",
    "000270": "기아",
    "012330": "현대모비스",
    # ── 바이오/헬스케어 ──
    "068270": "셀트리온",
    "196170": "알테오젠",
    "145020": "휴젤",
    "328130": "루닛",
    "207940": "삼성바이오로직스",
    # ── IT/플랫폼 ──
    "035420": "NAVER",
    "035720": "카카오",
    "377300": "카카오페이",
    "018260": "삼성에스디에스",
    # ── 금융 ──
    "055550": "신한지주",
    "105560": "KB금융",
    "086790": "하나금융지주",
    "316140": "우리금융지주",
    "032830": "삼성생명",
    # ── 조선/해운 ──
    "009540": "HD한국조선해양",
    "042660": "한화오션",
    "329180": "HD현대중공업",
    "011200": "HMM",
    # ── 방산 ──
    "012450": "한화에어로스페이스",
    "079550": "LIG넥스원",
    # ── 엔터/미디어 ──
    "352820": "하이브",
    "041510": "에스엠",
    "035900": "JYP Ent.",
    # ── 게임 ──
    "263750": "펄어비스",
    "036570": "엔씨소프트",
    "293490": "카카오게임즈",
    "112040": "위메이드",
    # ── 건설/인프라 ──
    "000720": "현대건설",
    "028260": "삼성물산",
    # ── 에너지/유틸리티 ──
    "010950": "S-Oil",
    "015760": "한국전력",
    "034020": "두산에너빌리티",
    "047050": "포스코인터내셔널",
    # ── 철강/소재 ──
    "005490": "POSCO홀딩스",
    "010130": "고려아연",
    # ── 소비재 ──
    "033780": "KT&G",
    "090430": "아모레퍼시픽",
    "051900": "LG생활건강",
    # ── 지주 ──
    "003550": "LG",
    "034730": "SK",
    "267250": "HD현대",
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


async def fetch_daily_pages(
    client: KiwoomClient, symbol: str, max_pages: int = 13
) -> list[DailyPrice]:
    """일봉 데이터 수집 (ka10086). 연속 조회로 52주 데이터 수집."""
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


# ── 보너스 조건 헬퍼 ─────────────────────────────────


def calc_prev_day_change(daily: list[DailyPrice]) -> float:
    """전일 등락률(%) 계산.

    (전일종가 - 전전일종가) / 전전일종가 * 100.
    데이터 2일 미만이면 0.0 반환.
    """
    if len(daily) < 2:
        return 0.0
    prev = daily[-1]
    prev_prev = daily[-2]
    if prev_prev.close == 0:
        return 0.0
    return (prev.close - prev_prev.close) / prev_prev.close * 100


def check_volume_surge(daily: list[DailyPrice], multiplier: float = 2.0) -> bool:
    """전일 거래량이 20일 평균의 multiplier배 이상인지."""
    if len(daily) < 20:
        return False
    recent_20 = daily[-20:]
    avg_volume = sum(d.volume for d in recent_20) / len(recent_20)
    if avg_volume == 0:
        return False
    return daily[-1].volume >= avg_volume * multiplier


def count_consecutive_bullish(daily: list[DailyPrice]) -> int:
    """최근 연속 양봉 수 (close > open)."""
    count = 0
    for d in reversed(daily):
        if d.close > d.open:
            count += 1
        else:
            break
    return count


def is_52w_new_high(daily: list[DailyPrice]) -> bool:
    """전일 종가가 52주 신고가인지."""
    if not daily:
        return False
    recent_250 = daily[-250:] if len(daily) > 250 else daily
    high_52w = max(d.high for d in recent_250)
    return daily[-1].close >= high_52w


# ── 스크리닝 ─────────────────────────────────────────


def check_screen_condition(
    daily: list[DailyPrice],
    threshold: float,
    volume_ratio: float,
) -> dict | None:
    """52주 신고가 근처 + 거래량 조건 확인 + 보너스 점수.

    기본 조건: 52주고가 비율 >= threshold, 거래량 비율 >= volume_ratio
    보너스: 전일등락률 3%+, 전일거래량 폭증, 5일연속양봉, 52주신고가

    Returns:
        스크리닝 정보 dict (항상 반환), 데이터 부족 시 None
    """
    if len(daily) < 20:
        return None

    recent_250 = daily[-250:] if len(daily) > 250 else daily
    high_52w = max(d.high for d in recent_250)

    recent_20 = daily[-20:]
    avg_volume = sum(d.volume for d in recent_20) // len(recent_20)

    latest = daily[-1]

    price_ratio = latest.close / high_52w if high_52w > 0 else 0
    vol_ratio = latest.volume / avg_volume if avg_volume > 0 else 0

    passed = price_ratio >= threshold and vol_ratio >= volume_ratio

    # 보너스 점수 계산
    bonus_score = 0
    prev_day_change_pct = calc_prev_day_change(daily)
    prev_day_vol_surge = check_volume_surge(daily)
    consecutive_bullish = count_consecutive_bullish(daily)
    new_high = is_52w_new_high(daily)

    if prev_day_change_pct >= 3.0:
        bonus_score += 1
    if prev_day_vol_surge:
        bonus_score += 1
    if consecutive_bullish >= 5:
        bonus_score += 1
    if new_high:
        bonus_score += 1

    return {
        "close": latest.close,
        "high_52w": high_52w,
        "price_ratio": round(price_ratio, 4),
        "volume": latest.volume,
        "avg_volume": avg_volume,
        "vol_ratio": round(vol_ratio, 2),
        "date": latest.date,
        "daily_bars": len(daily),
        "passed": passed,
        "bonus_score": bonus_score,
        "prev_day_change_pct": round(prev_day_change_pct, 2),
        "prev_day_vol_surge": prev_day_vol_surge,
        "consecutive_bullish": consecutive_bullish,
        "is_52w_high": new_high,
    }


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
    passed: list[dict] = []
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

        if result["passed"]:
            passed.append(entry)

        # 종목 간 쿨다운 (일봉 연속조회 후 다음 종목)
        await asyncio.sleep(2)

    # 보너스 점수 + price_ratio 기준 내림차순 정렬
    passed.sort(
        key=lambda x: (x.get("bonus_score", 0), x["price_ratio"]),
        reverse=True,
    )

    # 최소 종목 수 보장: 조건 미충족이어도 보너스+price_ratio 상위로 채움
    if len(passed) < min_stocks and all_candidates:
        ranked = sorted(
            all_candidates,
            key=lambda x: (x.get("bonus_score", 0), x["price_ratio"]),
            reverse=True,
        )
        for candidate in ranked:
            if candidate not in passed:
                passed.append(candidate)
                sym, name = candidate["symbol"], candidate["name"]
                pr = candidate["price_ratio"]
                bs = candidate.get("bonus_score", 0)
                print(f"  [보충] {sym} {name} (bonus={bs}, price_ratio={pr:.1%})")
            if len(passed) >= min_stocks:
                break

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
