"""daily_candles 최신성 preflight (PR A: stale guard).

cross_momentum / 향후 short_swing 전략이 모의 가동 직전에 호출.
DB `daily_candles` 의 max(date) 와 active universe (FROZEN_UNIVERSE) coverage 를
검사해 stale 데이터로 인한 silent 산출 사고를 차단한다.

용도:
    - §9.1 preflight 자동화 항목 (live_trader 가동 직전).
    - regime daily dry-run 의 사전 게이트.

종료 코드:
    0 : PASS (max_date 기준 충족 + universe coverage 충족)
    1 : FAIL (stale 또는 coverage 미달)
    2 : 환경 오류 (DB 연결 실패 등)

사용:
    uv run python scripts/preflight_data_freshness.py
    uv run python scripts/preflight_data_freshness.py --min-coverage 0.85
    uv run python scripts/preflight_data_freshness.py --as-of 2026-06-17
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime


@dataclass(frozen=True)
class FreshnessResult:
    """preflight 결과 (텍스트 보고 + 종료 코드 결정용)."""

    as_of: date
    cutoff: date
    max_date: date | None
    universe_size: int
    fresh_count: int
    coverage: float
    min_coverage: float

    @property
    def max_date_pass(self) -> bool:
        return self.max_date is not None and self.max_date >= self.cutoff

    @property
    def coverage_pass(self) -> bool:
        return self.coverage >= self.min_coverage

    @property
    def passed(self) -> bool:
        return self.max_date_pass and self.coverage_pass


def _resolve_cutoff(as_of: date) -> date:
    """as_of 가 영업일이면 as_of, 휴장이면 직전 영업일."""
    from src.utils.krx_calendar import is_business_day, previous_business_day

    return as_of if is_business_day(as_of) else previous_business_day(as_of)


def _connect_database_url() -> str:
    """env DATABASE_URL 또는 settings 에서 DB URL 획득."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    from src.config.settings import get_settings

    return get_settings().database_url


def _check_freshness(
    as_of: date,
    universe: Iterable[str],
    min_coverage: float,
) -> FreshnessResult:
    """DB 에 직접 연결해 max(date) 와 universe coverage 를 측정."""
    import psycopg2

    cutoff = _resolve_cutoff(as_of)
    universe_list = list(universe)
    universe_set = set(universe_list)

    url = _connect_database_url().replace("postgresql+asyncpg://", "postgresql://")
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT max(date) FROM daily_candles;")
        max_row = cur.fetchone()
        max_date: date | None = max_row[0] if max_row else None

        cur.execute(
            "SELECT DISTINCT symbol FROM daily_candles WHERE date >= %s",
            (cutoff,),
        )
        fresh_symbols = {r[0] for r in cur.fetchall()}

    fresh_in_universe = fresh_symbols & universe_set
    coverage = (len(fresh_in_universe) / len(universe_list)) if universe_list else 0.0

    return FreshnessResult(
        as_of=as_of,
        cutoff=cutoff,
        max_date=max_date,
        universe_size=len(universe_list),
        fresh_count=len(fresh_in_universe),
        coverage=coverage,
        min_coverage=min_coverage,
    )


def _format_report(result: FreshnessResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"daily_candles freshness preflight: {status}",
        f"  as_of               = {result.as_of.isoformat()}",
        f"  cutoff (영업일)     = {result.cutoff.isoformat()}",
        f"  max_date            = {result.max_date.isoformat() if result.max_date else 'NULL'}",
        f"  max_date_pass       = {result.max_date_pass}",
        f"  universe_size       = {result.universe_size}",
        f"  fresh_in_universe   = {result.fresh_count}",
        f"  coverage            = {result.coverage:.3f} (min={result.min_coverage:.3f})",
        f"  coverage_pass       = {result.coverage_pass}",
    ]
    if not result.passed:
        lines.append("")
        if not result.max_date_pass:
            lines.append("  reason: max_date stale → backfill 후 재시도 권장")
        if not result.coverage_pass:
            lines.append("  reason: universe coverage 부족 → backfill 범위 확인")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="daily_candles 최신성 preflight")
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="기준일 YYYY-MM-DD (default: 오늘, KST 가정)",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.85,
        help="universe 중 fresh 비율 임계 (default 0.85)",
    )
    args = parser.parse_args(argv)

    as_of = (
        datetime.strptime(args.as_of, "%Y-%m-%d").replace(tzinfo=UTC).date()
        if args.as_of
        else datetime.now(tz=UTC).date()
    )

    try:
        from src.strategy.cross_momentum_universe import get_universe

        universe = get_universe()
    except Exception as exc:
        print(f"universe 로드 실패: {exc}", file=sys.stderr)  # noqa: T201
        return 2

    try:
        result = _check_freshness(as_of, universe, args.min_coverage)
    except Exception as exc:
        print(f"DB 조회 실패: {exc}", file=sys.stderr)  # noqa: T201
        return 2

    print(_format_report(result))  # noqa: T201
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
