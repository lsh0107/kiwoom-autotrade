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

UNIVERSE: dict[str, str] = {
    # KOSPI 대형주
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "000270": "기아",
    "068270": "셀트리온",
    "035420": "NAVER",
    "005490": "POSCO홀딩스",
    "055550": "신한지주",
    "035720": "카카오",
    "105560": "KB금융",
    "012330": "현대모비스",
    "028260": "삼성물산",
    "051910": "LG화학",
    "066570": "LG전자",
    "003550": "LG",
    "032830": "삼성생명",
    "034730": "SK",
    "015760": "한국전력",
    "003670": "포스코퓨처엠",
    "006400": "삼성SDI",
    # KOSDAQ 대형주
    "247540": "에코프로비엠",
    "086520": "에코프로",
    "196170": "알테오젠",
    "145020": "휴젤",
    "328130": "루닛",
    "403870": "HPSP",
    "041510": "에스엠",
    "263750": "펄어비스",
    "377300": "카카오페이",
    "036570": "엔씨소프트",
}

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
        await asyncio.sleep(0.5)

    daily = parse_daily_raw(all_raw)
    daily.sort(key=lambda x: x.date)
    return daily


# ── 스크리닝 ─────────────────────────────────────────


def check_screen_condition(
    daily: list[DailyPrice],
    threshold: float,
    volume_ratio: float,
) -> dict | None:
    """52주 신고가 근처 + 거래량 조건 확인.

    Returns:
        조건 충족 시 스크리닝 정보 dict, 미충족 시 None
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
    }


async def screen_all(
    client: KiwoomClient,
    universe: dict[str, str],
    threshold: float,
    volume_ratio: float,
) -> list[dict]:
    """유니버스 전체 스크리닝."""
    passed: list[dict] = []
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

        status = "PASS" if result["passed"] else "skip"
        print(
            f"{status} | 종가 {result['close']:,} | "
            f"52주고 {result['high_52w']:,} ({result['price_ratio']:.1%}) | "
            f"거래량 {result['vol_ratio']:.1f}x"
        )

        if result["passed"]:
            passed.append({"symbol": symbol, "name": name, **result})

        # 종목 간 쿨다운 (일봉 연속조회 후 다음 종목)
        await asyncio.sleep(1)

    return passed


# ── 메인 ─────────────────────────────────────────────


async def main() -> None:
    """종목 스크리닝 실행."""
    parser = argparse.ArgumentParser(description="모멘텀 돌파 전략 종목 스크리닝")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.90,
        help="52주 신고가 대비 최소 비율 (기본: 0.90 = 90%%)",
    )
    parser.add_argument(
        "--volume-ratio",
        type=float,
        default=1.2,
        help="평균 거래량 대비 최소 배수 (기본: 1.2)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("모멘텀 돌파 전략 — 종목 스크리닝")
    print(f"실행: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"유니버스  : {len(UNIVERSE)}개 (KOSPI+KOSDAQ)")
    print(f"조건     : 52주고가 {args.threshold:.0%} 이상 + 거래량 {args.volume_ratio}배 이상")
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

        passed = await screen_all(client, UNIVERSE, args.threshold, args.volume_ratio)
    finally:
        await client.close()

    # 결과 출력
    print(f"\n{'=' * 60}")
    print(f"스크리닝 결과: {len(passed)}개 / {len(UNIVERSE)}개 통과")
    print(f"{'=' * 60}")
    for s in passed:
        print(
            f"  {s['symbol']} {s['name']} | "
            f"종가 {s['close']:,} | 52주고 {s['high_52w']:,} ({s['price_ratio']:.1%}) | "
            f"거래량 {s['vol_ratio']:.1f}x"
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
