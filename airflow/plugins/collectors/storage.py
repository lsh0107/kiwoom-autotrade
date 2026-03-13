"""데이터 저장 유틸리티."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("KIWOOM_DATA_DIR", "data"))


def save_json(category: str, date_str: str, data: Any) -> Path:
    """JSON 데이터 저장.

    Args:
        category: 데이터 카테고리 (예: "premarket", "news").
        date_str: 날짜 문자열 (예: "20250101").
        data: 저장할 데이터.

    Returns:
        저장된 파일 경로.
    """
    path = DATA_DIR / category / f"{date_str}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("저장 완료: %s", path)
    return path


def load_json(category: str, date_str: str) -> Any:
    """JSON 데이터 로드.

    Args:
        category: 데이터 카테고리.
        date_str: 날짜 문자열.

    Returns:
        로드된 데이터. 파일이 없으면 None.
    """
    path = DATA_DIR / category / f"{date_str}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def today_str() -> str:
    """오늘 날짜 문자열 반환 (YYYYMMDD, KST 기준).

    Returns:
        오늘 날짜 문자열 (예: "20250101").
    """
    kst = datetime.now(tz=UTC) + timedelta(hours=9)
    return kst.strftime("%Y%m%d")
