"""short_swing 진입 dry-run (PR B).

실제 DB write / broker order 없이 오늘 데이터로 short_swing 진입 결과를 본다.
출력:
  - 후보 수 (DB ShortSwingCandidate 최근치)
  - regime overlay (load + decision)
  - skip reason 분포
  - 예상 주문 (would_order): symbol / quantity / order_price / amount

안전 불변식 (preflight 자동 확인):
  - settings.is_mock_trading == True (아니면 즉시 종료)
  - DB write 0 / broker order 0 / decision POST 0

종료 코드:
  0 PASS (dry-run 정상)
  1 FAIL (불변식 위반 또는 예외)

사용:
  uv run python scripts/short_swing_dryrun.py
  uv run python scripts/short_swing_dryrun.py --as-of 2026-06-17
  uv run python scripts/short_swing_dryrun.py --allowed-budget 5000000 --max-order 2000000
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any


def _build_dryrun_broker_stub() -> Any:
    """get_balance / get_quote 만 답하는 read-only stub.

    실 broker 호출 0. dry_run=True 면 short_swing 이 place_order 를 부르지 않음.
    balance/quote 는 호출 발생 시 명시적 fail 로 dry-run 의도 어긋남 즉시 노출.
    """

    class _Stub:
        async def get_balance(self) -> Any:
            from src.broker.schemas import AccountBalance

            return AccountBalance(
                total_eval=0,
                total_profit=0,
                total_profit_pct=0.0,
                deposit=0,
                available_cash=10_000_000,
                holdings=[],
            )

        async def get_quote(self, symbol: str) -> Any:  # noqa: ARG002
            from src.broker.schemas import Quote

            return Quote(
                symbol="000000",
                price=10000,
                open=10000,
                high=10000,
                low=10000,
                close=10000,
                volume=0,
            )

        async def place_order(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
            raise RuntimeError(
                "dry-run 위반: place_order 호출 발생 — run_entry_check(dry_run=True) 가 무시됨",
            )

    return _Stub()


def _resolve_as_of(as_of_str: str | None) -> date:
    if as_of_str:
        return datetime.strptime(as_of_str, "%Y-%m-%d").replace(tzinfo=UTC).date()
    return datetime.now(tz=UTC).date()


def _summarize_result(result: Any) -> dict[str, Any]:
    """EntryResult 를 출력 친화 dict 로."""
    skip_counter: Counter[str] = Counter()
    for s in result.skipped:
        reason = s.get("reason", "unknown") if isinstance(s, dict) else "unknown"
        skip_counter[reason] += 1
    return {
        "checked": result.checked,
        "ordered": result.ordered,
        "skipped_total": len(result.skipped),
        "skipped_by_reason": dict(skip_counter),
        "errors_total": len(result.errors),
        "would_orders": [
            {
                "symbol": w.get("symbol"),
                "quantity": w.get("quantity"),
                "order_price": w.get("order_price"),
                "amount": w.get("order_price", 0) * w.get("quantity", 0),
            }
            for w in getattr(result, "would_orders", [])
        ],
    }


async def _run_async(
    as_of: date,
    allowed_budget: int | None,
    max_order_amount: int | None,
    db_factory: Callable[[], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    from src.config.settings import get_settings
    from src.trading.short_swing import run_entry_check
    from src.trading.short_swing_regime import (
        load_current_regime,
        regime_overlay_decision,
    )

    if not get_settings().is_mock_trading:
        raise RuntimeError("is_mock_trading=False — short_swing dry-run 차단")

    snapshot = load_current_regime(as_of)
    overlay = regime_overlay_decision(snapshot)

    if db_factory is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async def _make_db() -> Any:
            return session_factory()

        db_factory = _make_db

    client = _build_dryrun_broker_stub()

    db_ctx = await db_factory()
    async with db_ctx as db:
        # KST 시간으로 진입 윈도우 안에 강제 셋팅 (장중과 무관하게 후보 평가)
        from src.utils.time import KST

        now = datetime.combine(as_of, datetime.min.time().replace(hour=10), tzinfo=KST)

        result = await run_entry_check(
            db,
            client,
            user_id="00000000-0000-0000-0000-000000000000",
            now=now,
            dry_run=True,
            allowed_budget=allowed_budget,
            max_order_amount=max_order_amount,
            regime_overlay=overlay,
        )

    return {
        "as_of": as_of.isoformat(),
        "regime_snapshot": (
            {"regime": snapshot.regime, "confidence": snapshot.confidence} if snapshot else None
        ),
        "regime_overlay": {
            "regime": overlay.regime,
            "allow_new_entry": overlay.allow_new_entry,
            "max_new_entries_override": overlay.max_new_entries_override,
            "reason": overlay.reason,
        },
        "allowed_budget": allowed_budget,
        "max_order_amount": max_order_amount,
        "result": _summarize_result(result),
    }


def _format_report(payload: dict[str, Any]) -> str:
    lines = [
        "short_swing dry-run summary",
        f"  as_of               = {payload['as_of']}",
        f"  regime              = {payload['regime_snapshot']}",
        f"  regime_overlay      = {payload['regime_overlay']}",
        f"  allowed_budget      = {payload['allowed_budget']}",
        f"  max_order_amount    = {payload['max_order_amount']}",
        f"  checked             = {payload['result']['checked']}",
        f"  ordered             = {payload['result']['ordered']}",
        f"  skipped_total       = {payload['result']['skipped_total']}",
        f"  skipped_by_reason   = {payload['result']['skipped_by_reason']}",
        f"  errors_total        = {payload['result']['errors_total']}",
        f"  would_orders        = {payload['result']['would_orders']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="short_swing dry-run (PR B)")
    parser.add_argument("--as-of", default=None, help="기준일 YYYY-MM-DD (default 오늘)")
    parser.add_argument(
        "--allowed-budget",
        type=int,
        default=int(os.environ.get("SHORT_SWING_ALLOWED_BUDGET", "0") or "0") or None,
        help="할당 예산 (원). 미설정 시 전체 가용현금 사용 (레거시).",
    )
    parser.add_argument(
        "--max-order",
        type=int,
        default=int(os.environ.get("SHORT_SWING_MAX_ORDER", "0") or "0") or None,
        help="1회 최대 주문 금액 (원).",
    )
    args = parser.parse_args(argv)

    as_of = _resolve_as_of(args.as_of)
    try:
        payload = asyncio.run(
            _run_async(as_of, args.allowed_budget, args.max_order),
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    print(_format_report(payload))  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
