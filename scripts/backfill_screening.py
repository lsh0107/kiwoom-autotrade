#!/usr/bin/env python3
# ruff: noqa: T201
"""사전 스크리닝 backfill 스크립트 (1회성, Design 012 PR 3).

daily_candles 가 이미 채워진 특정 일자를 지정해 daily_screening_cache 를
직접 생성한다. DAG 시작 이전 과거 데이터 보충용.

사용법:
    python scripts/backfill_screening.py --date 2026-04-21
    python scripts/backfill_screening.py --date 2026-04-21 --threshold 0.75 --volume-ratio 0.8
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

# 프로젝트 루트 + airflow/plugins 경로 추가 (Airflow 미실행 시에도 import 가능)
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "airflow" / "plugins"))

logger = logging.getLogger(__name__)


def main() -> int:
    """커맨드라인 인자에 따라 backfill 실행."""
    parser = argparse.ArgumentParser(description="daily_screening_cache backfill (Design 012)")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD (장 마감일 기준)")
    parser.add_argument("--threshold", type=float, default=0.75)
    parser.add_argument("--volume-ratio", type=float, default=0.8)
    parser.add_argument("--min-stocks", type=int, default=10)
    parser.add_argument("--profile", default="momentum_breakout")
    parser.add_argument(
        "--run-id",
        default="backfill",
        help="감사용 run_id (기본: backfill)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="DEBUG/INFO/WARNING 등",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    on_date = dt.date.fromisoformat(args.date)
    params = {
        "profile": args.profile,
        "threshold": args.threshold,
        "volume_ratio": args.volume_ratio,
        "min_stocks": args.min_stocks,
    }

    # 지연 import (Airflow plugins 경로 활성화 후)
    from collectors.screening import compute_screening, upsert_screening_rows
    from scripts.screen_symbols import UNIVERSE, get_sector, get_strategy_hint

    print(f"[backfill] 대상일: {on_date} / profile={args.profile}")
    print(
        f"[backfill] 파라미터: threshold={args.threshold}, "
        f"volume_ratio={args.volume_ratio}, min_stocks={args.min_stocks}"
    )
    rows = compute_screening(
        params,
        on_date=on_date,
        universe=UNIVERSE.items(),
        get_sector=get_sector,
        get_hint=get_strategy_hint,
        run_id=args.run_id,
    )
    count = upsert_screening_rows(rows)
    passed = sum(1 for r in rows if r.get("passed"))
    print(f"[backfill] upsert 완료: 전체 {count} / 통과 {passed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
