#!/usr/bin/env python3
# ruff: noqa: T201, DTZ005
"""키움 모의투자 KiwoomClient 통합 라이브 테스트.

KiwoomClient를 통해 실제 API를 호출하며 전체 기능을 순서대로 검증한다.

사용법:
    python scripts/test_kiwoom_live.py

필수 환경변수:
    KIWOOM_MOCK_APP_KEY: 모의투자 앱 키
    KIWOOM_MOCK_APP_SECRET: 모의투자 앱 시크릿

안전장치:
    - 모의투자 URL만 사용 (is_mock=True 강제)
    - 매수 주문가 = 현재가 -30% (미체결 유도)
    - 주문 수량 1주 고정
    - 주문 후 즉시 취소
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.broker.constants import MOCK_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import (
    CancelRequest,
    OrderRequest,
    OrderSideEnum,
    OrderTypeEnum,
)

# ── 설정 ───────────────────────────────────────────────

RESULTS_PATH = Path("docs/kiwoom-rest-api/live-test-results.json")

# 시세 조회 대상 (삼성전자, SK하이닉스, POSCO홀딩스)
QUOTE_SYMBOLS = ["005930", "000660", "005490"]

# 주문 테스트 종목 (삼성전자)
ORDER_SYMBOL = "005930"
ORDER_QTY = 1

results: list[dict[str, Any]] = []


# ── 유틸 ───────────────────────────────────────────────


def get_env_or_exit(key: str) -> str:
    """환경변수를 읽거나 없으면 종료."""
    value = os.environ.get(key, "")
    if not value:
        print(f"[ERROR] 환경변수 {key}가 없습니다.")
        sys.exit(1)
    return value


def record(
    name: str,
    *,
    passed: bool,
    checks: dict[str, bool],
    data: Any = None,
    error: str = "",
    elapsed_ms: float = 0.0,
) -> None:
    """테스트 결과를 출력하고 기록한다."""
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name} ({elapsed_ms:.0f}ms)")
    if error:
        print(f"    → 오류: {error}")
    for k, v in checks.items():
        print(f"    [{'v' if v else 'x'}] {k}")

    results.append(
        {
            "test": name,
            "passed": passed,
            "checks": checks,
            "error": error,
            "elapsed_ms": round(elapsed_ms, 1),
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
    )


# ── 테스트 함수 ─────────────────────────────────────────


async def test_token(client: KiwoomClient) -> bool:
    """1. 토큰 발급."""
    print("\n== 1. 토큰 발급 ==")
    start = time.monotonic()
    try:
        token = await client.authenticate()
        elapsed = (time.monotonic() - start) * 1000
        now = datetime.now(token.expires_at.tzinfo)
        checks = {
            "access_token 존재": bool(token.access_token),
            "expires_at 미래": token.expires_at > now,
        }
        passed = all(checks.values())
        record(
            "토큰 발급",
            passed=passed,
            checks=checks,
            data={"expires_at": token.expires_at.isoformat()},
            elapsed_ms=elapsed,
        )
        return passed
    except Exception as e:
        record("토큰 발급", passed=False, checks={}, error=str(e))
        return False


async def test_quote(client: KiwoomClient) -> dict[str, int]:
    """2. 현재가 조회 (복수 종목). 주문가 계산을 위해 {symbol: price} 반환."""
    print("\n== 2. 현재가 조회 ==")
    prices: dict[str, int] = {}

    for symbol in QUOTE_SYMBOLS:
        start = time.monotonic()
        try:
            quote = await client.get_quote(symbol)
            elapsed = (time.monotonic() - start) * 1000
            checks = {
                "price > 0": quote.price > 0,
                "symbol 일치": quote.symbol == symbol,
                "종목명 존재": bool(quote.name),
                "prev_close > 0": quote.prev_close > 0,
            }
            passed = all(checks.values())
            record(
                f"현재가 조회 ({symbol})",
                passed=passed,
                checks=checks,
                data={
                    "name": quote.name,
                    "price": quote.price,
                    "prev_close": quote.prev_close,
                    "change_pct": quote.change_pct,
                },
                elapsed_ms=elapsed,
            )
            if passed:
                prices[symbol] = quote.price
        except Exception as e:
            record(f"현재가 조회 ({symbol})", passed=False, checks={}, error=str(e))

    return prices


async def test_orderbook(client: KiwoomClient) -> None:
    """3. 호가 조회."""
    print("\n== 3. 호가 조회 ==")
    start = time.monotonic()
    try:
        ob = await client.get_orderbook(ORDER_SYMBOL)
        elapsed = (time.monotonic() - start) * 1000
        checks = {
            "symbol 일치": ob.symbol == ORDER_SYMBOL,
            "매도호가 1단계 이상": len(ob.asks) > 0,
            "매수호가 1단계 이상": len(ob.bids) > 0,
            "최우선매도 > 0": ob.asks[0].price > 0 if ob.asks else False,
            "최우선매수 > 0": ob.bids[0].price > 0 if ob.bids else False,
            "매도 > 매수 (스프레드 정상)": (
                ob.asks[0].price > ob.bids[0].price if ob.asks and ob.bids else False
            ),
        }
        passed = all(checks.values())
        record(
            "호가 조회",
            passed=passed,
            checks=checks,
            data={
                "asks_count": len(ob.asks),
                "bids_count": len(ob.bids),
                "best_ask": ob.asks[0].price if ob.asks else 0,
                "best_bid": ob.bids[0].price if ob.bids else 0,
            },
            elapsed_ms=elapsed,
        )
    except Exception as e:
        record("호가 조회", passed=False, checks={}, error=str(e))


async def test_daily_price(client: KiwoomClient) -> None:
    """4. 일봉 조회."""
    print("\n== 4. 일봉 조회 ==")
    start = time.monotonic()
    try:
        daily = await client.get_daily_price(ORDER_SYMBOL)
        elapsed = (time.monotonic() - start) * 1000
        checks: dict[str, bool] = {
            "1개 이상 데이터": len(daily) > 0,
        }
        if daily:
            first = daily[0]
            checks["날짜 필드 존재"] = bool(
                first.get("dt") or first.get("date") or first.get("stk_bsns_date")
            )
            checks["종가 필드 존재"] = bool(
                first.get("close_pric") or first.get("cls_pric") or first.get("cur_prc")
            )
        passed = all(checks.values())
        record(
            "일봉 조회",
            passed=passed,
            checks=checks,
            data={"candle_count": len(daily), "latest": daily[0] if daily else {}},
            elapsed_ms=elapsed,
        )
    except Exception as e:
        record("일봉 조회", passed=False, checks={}, error=str(e))


async def test_balance(client: KiwoomClient) -> None:
    """5. 잔고 조회."""
    print("\n== 5. 잔고 조회 ==")
    start = time.monotonic()
    try:
        balance = await client.get_balance()
        elapsed = (time.monotonic() - start) * 1000
        checks = {
            "total_eval >= 0": balance.total_eval >= 0,
            "available_cash >= 0": balance.available_cash >= 0,
            "holdings 리스트": isinstance(balance.holdings, list),
        }
        passed = all(checks.values())
        record(
            "잔고 조회",
            passed=passed,
            checks=checks,
            data={
                "total_eval": balance.total_eval,
                "available_cash": balance.available_cash,
                "holdings_count": len(balance.holdings),
                "holdings": [
                    {
                        "symbol": h.symbol,
                        "name": h.name,
                        "qty": h.quantity,
                        "profit_pct": h.profit_pct,
                    }
                    for h in balance.holdings
                ],
            },
            elapsed_ms=elapsed,
        )
    except Exception as e:
        record("잔고 조회", passed=False, checks={}, error=str(e))


async def test_order_and_cancel(client: KiwoomClient, current_prices: dict[str, int]) -> None:
    """6. 매수 주문 + 즉시 취소 (현재가 -30% 지정가로 미체결 유도)."""
    print("\n== 6. 매수 주문 + 취소 ==")

    cur_price = current_prices.get(ORDER_SYMBOL, 0)
    order_price = int(cur_price * 0.7) if cur_price > 0 else 10000
    order_price = (order_price // 100) * 100  # 100원 단위 절사
    if order_price <= 0:
        order_price = 10000

    print(f"    현재가: {cur_price:,}원 → 주문가: {order_price:,}원 (미체결 유도)")

    # 6a. 매수 주문
    order_no = ""
    start = time.monotonic()
    try:
        req = OrderRequest(
            symbol=ORDER_SYMBOL,
            side=OrderSideEnum.BUY,
            price=order_price,
            quantity=ORDER_QTY,
            order_type=OrderTypeEnum.LIMIT,
        )
        resp = await client.place_order(req)
        elapsed = (time.monotonic() - start) * 1000
        order_no = resp.order_no
        checks = {
            "order_no 존재": bool(resp.order_no),
            "status=submitted": resp.status == "submitted",
            "symbol 일치": resp.symbol == ORDER_SYMBOL,
            "quantity 일치": resp.quantity == ORDER_QTY,
        }
        passed = all(checks.values())
        record(
            "매수 주문",
            passed=passed,
            checks=checks,
            data={"order_no": order_no, "price": order_price, "qty": ORDER_QTY},
            elapsed_ms=elapsed,
        )
    except Exception as e:
        record("매수 주문", passed=False, checks={}, error=str(e))
        return

    # 6b. 즉시 취소
    if order_no:
        start = time.monotonic()
        try:
            cancel_req = CancelRequest(
                order_no=order_no,
                symbol=ORDER_SYMBOL,
                quantity=ORDER_QTY,
            )
            cancel_resp = await client.cancel_order(cancel_req)
            elapsed = (time.monotonic() - start) * 1000
            checks = {
                "cancel order_no 존재": bool(cancel_resp.order_no),
                "original_order_no 일치": cancel_resp.original_order_no == order_no,
                "status=cancelled": cancel_resp.status == "cancelled",
            }
            passed = all(checks.values())
            record(
                "주문 취소",
                passed=passed,
                checks=checks,
                data={"cancel_no": cancel_resp.order_no, "original_no": order_no},
                elapsed_ms=elapsed,
            )
        except Exception as e:
            record("주문 취소", passed=False, checks={}, error=str(e))


# ── 메인 ───────────────────────────────────────────────


async def main() -> None:
    """테스트 실행."""
    print("=" * 60)
    print("키움 모의투자 KiwoomClient 통합 라이브 테스트")
    print(f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}")
    print("=" * 60)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    app_key = get_env_or_exit("KIWOOM_MOCK_APP_KEY")
    app_secret = get_env_or_exit("KIWOOM_MOCK_APP_SECRET")

    print(f"Base URL : {MOCK_BASE_URL}")
    print(f"App Key  : {app_key[:4]}{'*' * (len(app_key) - 4)}")
    print(f"종목     : {', '.join(QUOTE_SYMBOLS)}")
    print(f"주문종목 : {ORDER_SYMBOL} x {ORDER_QTY}주 (지정가 미체결 후 즉시 취소)")

    client = KiwoomClient(
        base_url=MOCK_BASE_URL,
        app_key=app_key,
        app_secret=app_secret,
        is_mock=True,
    )

    try:
        ok = await test_token(client)
        if not ok:
            print("\n[중단] 토큰 발급 실패 → 이후 테스트 스킵")
            return

        prices = await test_quote(client)
        await test_orderbook(client)
        await test_daily_price(client)
        await test_balance(client)
        await test_order_and_cancel(client, prices)

    finally:
        await client.close()

    # 결과 요약
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count
    print(f"\n{'=' * 60}")
    print(f"결과: {passed_count}/{total} 통과  {failed_count} 실패")
    print("=" * 60)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_at": datetime.now().isoformat(),
                "base_url": MOCK_BASE_URL,
                "summary": {"total": total, "passed": passed_count, "failed": failed_count},
                "tests": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"결과 저장: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
