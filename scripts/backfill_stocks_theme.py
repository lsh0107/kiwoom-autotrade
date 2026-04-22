#!/usr/bin/env python3
# ruff: noqa: T201
"""stocks.theme 백필 스크립트 (1회성, Design 013).

stock_universe.sector → stocks.theme 복제 후,
매핑 미존재 종목은 SECTOR_MAP fallback으로 채운다.
기존 theme 비-NULL 행은 보존 (멱등).

사용법:
    python scripts/backfill_stocks_theme.py --dry-run
    python scripts/backfill_stocks_theme.py

실행 환경 (asyncpg 사용):
    docker exec kiwoom-autotrade-backend-1 python scripts/backfill_stocks_theme.py
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# SECTOR_MAP: screen_symbols.py 를 ast.parse로 추출 (모듈 전체 실행 없이).
# 모듈 상단 import가 httpx 등 무거운 의존성을 포함하므로 직접 실행 불가.
_SCRIPTS_DIR = Path(__file__).parent


def _load_sector_map() -> dict[str, str]:
    """screen_symbols.py에서 SECTOR_MAP 딕셔너리만 추출.

    ast.parse를 사용해 모듈 실행 없이 상수 값을 읽는다.

    Returns:
        종목코드 → 섹터명 딕셔너리. 파싱 실패 시 빈 딕셔너리.
    """
    src_file = _SCRIPTS_DIR / "screen_symbols.py"
    if not src_file.exists():
        logger.warning("screen_symbols.py 없음 — SECTOR_MAP 비활성화")
        return {}
    try:
        tree = ast.parse(src_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "SECTOR_MAP"
                and isinstance(node.value, ast.Dict)
            ):
                result: dict[str, str] = ast.literal_eval(node.value)
                logger.info("SECTOR_MAP 파싱 완료: %d종목", len(result))
                return result
    except Exception as exc:
        logger.warning("SECTOR_MAP 파싱 실패: %s", exc)
    return {}


def _normalize_uri(conn_uri: str) -> str:
    """SQLAlchemy 드라이버 접두사를 asyncpg DSN 형식으로 변환."""
    for prefix, replacement in [
        ("postgresql+asyncpg://", "postgresql://"),
        ("postgresql+psycopg2://", "postgresql://"),
        ("postgres+asyncpg://", "postgresql://"),
        ("postgres+psycopg2://", "postgresql://"),
        ("postgres://", "postgresql://"),
    ]:
        conn_uri = conn_uri.replace(prefix, replacement)
    return conn_uri


async def _run_backfill(
    conn_uri: str,
    sector_map: dict[str, str],
    dry_run: bool,
) -> dict[str, int]:
    """asyncpg로 stocks.theme 백필 실행.

    Args:
        conn_uri: asyncpg 연결 DSN.
        sector_map: 종목코드 → 섹터명 딕셔너리.
        dry_run: True이면 롤백.

    Returns:
        결과 딕셔너리 (updated_from_universe, updated_from_sector_map, remaining_null, total).
    """
    import asyncpg

    conn = await asyncpg.connect(conn_uri)
    try:
        async with conn.transaction():
            # 1단계: stock_universe.sector → stocks.theme (NULL인 행만)
            result = await conn.execute(
                """
                UPDATE stocks s
                SET theme = su.sector, updated_at = NOW()
                FROM stock_universe su
                WHERE s.symbol = su.symbol
                  AND s.theme IS NULL
                  AND su.is_active = TRUE
                """,
            )
            updated_from_universe = int(result.split()[-1])
            logger.info("1단계 stock_universe → stocks.theme: %d건", updated_from_universe)

            # 2단계: 여전히 NULL → SECTOR_MAP fallback
            updated_from_sector_map = 0
            if sector_map:
                null_rows = await conn.fetch("SELECT symbol FROM stocks WHERE theme IS NULL")
                for row in null_rows:
                    symbol: str = row["symbol"]
                    sector = sector_map.get(symbol)
                    if sector:
                        r = await conn.execute(
                            "UPDATE stocks SET theme = $1, updated_at = NOW()"
                            " WHERE symbol = $2 AND theme IS NULL",
                            sector,
                            symbol,
                        )
                        if int(r.split()[-1]) > 0:
                            updated_from_sector_map += 1
                logger.info("2단계 SECTOR_MAP fallback: %d건", updated_from_sector_map)

            # 잔여 NULL 집계
            row_stats = await conn.fetchrow(
                "SELECT COUNT(*) FILTER(WHERE theme IS NULL) AS null_cnt,"
                " COUNT(*) AS total FROM stocks"
            )
            remaining_null = int(row_stats["null_cnt"])
            total = int(row_stats["total"])

            if dry_run:
                raise _DryRunError()

    except _DryRunError:
        logger.info("dry-run 모드: 롤백 완료 (실제 DB 변경 없음)")
    finally:
        await conn.close()

    return {
        "updated_from_universe": updated_from_universe,
        "updated_from_sector_map": updated_from_sector_map,
        "remaining_null": remaining_null,
        "total": total,
    }


class _DryRunError(Exception):
    """asyncpg 트랜잭션 롤백을 위한 내부 시그널."""


async def _fetch_null_stats(conn_uri: str) -> tuple[float, int, int]:
    """현재 stocks.theme NULL 통계 조회.

    Args:
        conn_uri: asyncpg DSN.

    Returns:
        (null_pct, null_cnt, total) 튜플.
    """
    import asyncpg

    conn = await asyncpg.connect(conn_uri)
    try:
        row = await conn.fetchrow(
            "SELECT COUNT(*) FILTER(WHERE theme IS NULL)*100.0/NULLIF(COUNT(*),0),"
            " COUNT(*) FILTER(WHERE theme IS NULL), COUNT(*) FROM stocks"
        )
        null_pct = float(row[0] or 0)
        null_cnt = int(row[1])
        total = int(row[2])
        return null_pct, null_cnt, total
    finally:
        await conn.close()


def main() -> int:
    """커맨드라인 인자에 따라 stocks.theme 백필 실행.

    Returns:
        0: 성공, 1: 실패.
    """
    parser = argparse.ArgumentParser(
        description="stocks.theme 백필 (stock_universe.sector + SECTOR_MAP fallback)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 변경 없이 업데이트 건수만 확인",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="DEBUG/INFO/WARNING 등 (기본: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    conn_uri_raw = os.environ.get("DATABASE_URL") or os.environ.get("AIRFLOW_CONN_KIWOOM_DB")
    if not conn_uri_raw:
        logger.error("DATABASE_URL 또는 AIRFLOW_CONN_KIWOOM_DB 환경변수가 필요합니다.")
        return 1

    conn_uri = _normalize_uri(conn_uri_raw)
    sector_map = _load_sector_map()
    mode_label = "[DRY-RUN] " if args.dry_run else ""

    logger.info("%sstocks.theme 백필 시작", mode_label)

    # Before 통계
    null_pct, null_cnt, total = asyncio.run(_fetch_null_stats(conn_uri))
    print(f"[Before] NULL 비율: {null_pct:.2f}% ({null_cnt}/{total})")

    result = asyncio.run(_run_backfill(conn_uri, sector_map, args.dry_run))

    # After 통계
    after_label = "After(dry-run)" if args.dry_run else "After"
    null_pct2, null_cnt2, total2 = asyncio.run(_fetch_null_stats(conn_uri))
    print(f"[{after_label}] NULL 비율: {null_pct2:.2f}% ({null_cnt2}/{total2})")

    print(
        f"\n{'=' * 50}\n"
        f"  {mode_label}백필 결과 요약\n"
        f"  stock_universe 복제: {result['updated_from_universe']}건\n"
        f"  SECTOR_MAP fallback: {result['updated_from_sector_map']}건\n"
        f"  잔여 NULL: {result['remaining_null']}/{result['total']}"
        f" ({result['remaining_null'] * 100.0 / max(result['total'], 1):.2f}%)\n"
        f"{'=' * 50}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
