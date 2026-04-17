"""종목별 수급 데이터 수집기 (pykrx 기반)."""

from __future__ import annotations

import logging
import time
from typing import Any

try:
    from pykrx import stock
except ImportError:
    stock = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# pykrx rate limit 준수 간격 (초)
_SLEEP_INTERVAL = 1.5


def load_watch_symbols() -> list[str]:
    """감시 종목 목록 로드.

    DB stock_universe 테이블에서 활성 종목 코드를 우선 조회하고,
    DB 연결 실패 시 data/screened_*.json 파일에서 fallback 로드한다.

    Returns:
        종목코드 목록. 조회 실패 시 빈 리스트.
    """
    # DB 조회 우선
    try:
        from collectors.storage import _get_db_conn

        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT symbol FROM stock_universe"
                    " WHERE is_active = true ORDER BY symbol"
                )
                rows = cur.fetchall()
            symbols = [row[0] for row in rows]
            logger.info("DB에서 감시 종목 %d개 로드", len(symbols))
            return symbols
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("DB 종목 로드 실패, JSON fallback 시도: %s", exc)

    # JSON fallback — data/screened_*.json 최신 파일 사용
    import glob
    import json

    from collectors.storage import DATA_DIR

    pattern = str(DATA_DIR / "screened_*.json")
    files = sorted(glob.glob(pattern), reverse=True)  # 최신 파일 우선
    if files:
        try:
            with open(files[0], encoding="utf-8") as f:
                data = json.load(f)
            # [{"symbol": "005930", ...}] 또는 {"symbols": [...]} 형식 지원
            if isinstance(data, list):
                symbols = [item["symbol"] for item in data if "symbol" in item]
            elif isinstance(data, dict) and "symbols" in data:
                symbols = data["symbols"]
            else:
                symbols = []
            logger.info("JSON에서 감시 종목 %d개 로드: %s", len(symbols), files[0])
            return symbols
        except Exception as exc:
            logger.warning("JSON 종목 로드 실패: %s", exc)

    logger.warning("감시 종목 로드 실패 — 종목별 수급 수집 건너뜀")
    return []


def collect_stock_investor_flow(
    date: str,
    symbols: list[str],
) -> dict[str, Any]:
    """종목별 외국인/기관 순매수 데이터 수집.

    pykrx get_market_trading_value_by_date를 사용해 각 종목의
    외국인·기관·개인 순매수 금액을 수집한다.
    개별 종목 수집 실패 시 해당 종목만 available=False로 기록하고 계속 진행한다.

    Args:
        date: 조회 날짜 (YYYYMMDD 형식).
        symbols: 수집할 종목코드 목록.

    Returns:
        종목별 수급 딕셔너리.
        예: {
            "date": "20250101",
            "available": True,
            "total": 10,
            "success": 9,
            "stocks": {
                "005930": {
                    "available": True,
                    "institution_net": 5000000000,
                    "foreign_net": -3000000000,
                    "individual_net": -2000000000,
                },
                "000660": {"available": False, "reason": "no_data"},
            },
        }
        종목 목록이 비어있으면 available=False, reason="empty_symbols".

    Raises:
        ImportError: pykrx 미설치 시.
    """
    if stock is None:
        raise ImportError("pykrx 패키지 미설치 — pip install pykrx")

    if not symbols:
        logger.warning("수집할 종목 목록이 비어있음")
        return {
            "date": date,
            "available": False,
            "reason": "empty_symbols",
            "stocks": {},
        }

    stocks_result: dict[str, Any] = {}

    for symbol in symbols:
        try:
            df = stock.get_market_trading_value_by_date(date, date, symbol)
            time.sleep(_SLEEP_INTERVAL)

            if df is None or df.empty:
                logger.debug("수급 데이터 없음: %s %s", symbol, date)
                stocks_result[symbol] = {"available": False, "reason": "no_data"}
                continue

            # pykrx 컬럼: 기관합계, 기타법인, 개인, 외국인합계, 전체
            row = df.iloc[0]
            institution_net: int | None = None
            foreign_net: int | None = None
            individual_net: int | None = None

            for col in df.columns:
                col_str = str(col)
                if "기관" in col_str:
                    institution_net = int(row[col])
                elif "외국인" in col_str:
                    foreign_net = int(row[col])
                elif "개인" in col_str:
                    individual_net = int(row[col])

            stocks_result[symbol] = {
                "available": True,
                "institution_net": institution_net,
                "foreign_net": foreign_net,
                "individual_net": individual_net,
            }
        except Exception as exc:
            logger.warning("종목 수급 수집 실패: %s %s — %s", symbol, date, exc)
            stocks_result[symbol] = {"available": False, "reason": str(exc)}

    success_count = sum(1 for v in stocks_result.values() if v.get("available") is True)
    logger.info(
        "종목별 수급 수집 완료: %d/%d 성공 (date=%s)",
        success_count,
        len(symbols),
        date,
    )

    return {
        "date": date,
        "available": True,
        "total": len(symbols),
        "success": success_count,
        "stocks": stocks_result,
    }
