"""stocks.theme 백필 순수 파이썬 로직.

stock_universe.sector → stocks.theme 복제 후,
매핑 미존재 종목은 SECTOR_MAP fallback으로 채운다.
기존 theme 비-NULL 행은 건드리지 않는다 (멱등).

Airflow DAG 및 스크립트 양쪽에서 임포트해 사용한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    """백필 실행 결과 요약."""

    updated_from_universe: int
    """stock_universe.sector → stocks.theme 복제 건수."""

    updated_from_sector_map: int
    """SECTOR_MAP fallback 적용 건수."""

    remaining_null: int
    """백필 후 잔여 NULL 건수."""

    total: int
    """stocks 테이블 전체 행 수."""

    @property
    def null_pct(self) -> float:
        """NULL 비율 (%)."""
        if self.total == 0:
            return 0.0
        return round(self.remaining_null * 100.0 / self.total, 2)


def run_theme_backfill(
    conn_uri: str,
    sector_map: dict[str, str],
    dry_run: bool = False,
) -> BackfillResult:
    """stocks.theme 백필을 실행한다.

    1단계: stock_universe.sector → stocks.theme (NULL인 행만)
    2단계: 여전히 NULL인 행 → SECTOR_MAP fallback
    기존 theme 비-NULL 행은 보존 (UPDATE … WHERE theme IS NULL).

    Args:
        conn_uri: psycopg2 연결 URI (postgresql://...).
        sector_map: 종목코드 → 섹터명 딕셔너리 (screen_symbols.SECTOR_MAP).
        dry_run: True이면 롤백 (DB 변경 없음).

    Returns:
        BackfillResult 실행 결과.
    """
    import psycopg2

    # SQLAlchemy 드라이버 접두사 제거
    for prefix, replacement in [
        ("postgresql+psycopg2://", "postgresql://"),
        ("postgresql+asyncpg://", "postgresql://"),
        ("postgres+psycopg2://", "postgresql://"),
        ("postgres+asyncpg://", "postgresql://"),
        ("postgres://", "postgresql://"),
    ]:
        conn_uri = conn_uri.replace(prefix, replacement)

    updated_from_universe = 0
    updated_from_sector_map = 0

    conn = psycopg2.connect(conn_uri)
    try:
        with conn.cursor() as cur:
            # 1단계: stock_universe.sector → stocks.theme
            cur.execute(
                """
                UPDATE stocks s
                SET theme = su.sector, updated_at = NOW()
                FROM stock_universe su
                WHERE s.symbol = su.symbol
                  AND s.theme IS NULL
                  AND su.is_active = TRUE
                """,
            )
            updated_from_universe = cur.rowcount
            logger.info(
                "1단계 stock_universe → stocks.theme 업데이트: %d건",
                updated_from_universe,
            )

            # 2단계: 여전히 NULL → SECTOR_MAP fallback
            if sector_map:
                cur.execute("SELECT symbol FROM stocks WHERE theme IS NULL")
                null_symbols = [row[0] for row in cur.fetchall()]

                for symbol in null_symbols:
                    sector = sector_map.get(symbol)
                    if sector:
                        cur.execute(
                            "UPDATE stocks SET theme = %s, updated_at = NOW()"
                            " WHERE symbol = %s AND theme IS NULL",
                            (sector, symbol),
                        )
                        if cur.rowcount > 0:
                            updated_from_sector_map += 1

                logger.info(
                    "2단계 SECTOR_MAP fallback 업데이트: %d건",
                    updated_from_sector_map,
                )

            # 잔여 NULL 집계
            cur.execute("SELECT COUNT(*) FILTER(WHERE theme IS NULL), COUNT(*) FROM stocks")
            row = cur.fetchone()
            remaining_null = int(row[0]) if row else 0
            total = int(row[1]) if row else 0

        if dry_run:
            conn.rollback()
            logger.info("dry-run 모드: 롤백 완료 (실제 DB 변경 없음)")
        else:
            conn.commit()
            logger.info("커밋 완료")

    finally:
        conn.close()

    result = BackfillResult(
        updated_from_universe=updated_from_universe,
        updated_from_sector_map=updated_from_sector_map,
        remaining_null=remaining_null,
        total=total,
    )
    logger.info(
        "백필 완료 — universe=%d, fallback=%d, 잔여NULL=%d/%d (%.2f%%)",
        result.updated_from_universe,
        result.updated_from_sector_map,
        result.remaining_null,
        result.total,
        result.null_pct,
    )
    return result
