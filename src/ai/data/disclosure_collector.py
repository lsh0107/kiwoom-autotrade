"""DART 공시 데이터 수집."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
import structlog

from src.ai.data.cache import TTLCache
from src.config.settings import get_settings
from src.utils.time import KST

logger = structlog.get_logger(__name__)

DART_BASE_URL = "https://opendart.fss.or.kr/api"

# 공시 캐시: 10분 TTL
_disclosure_cache = TTLCache(default_ttl=600)


@dataclass
class Disclosure:
    """공시 정보."""

    corp_name: str
    report_nm: str  # 공시 제목
    rcept_dt: str  # 접수일
    flr_nm: str  # 공시 제출인
    rcept_no: str  # 접수번호


async def get_recent_disclosures(
    corp_code: str | None = None,
    stock_code: str | None = None,
    days: int = 7,
) -> list[Disclosure]:
    """최근 공시 조회 (DART OpenAPI)."""
    settings = get_settings()
    if not settings.dart_api_key:
        return []

    cache_key = f"disclosure:{stock_code or corp_code}:{days}"
    cached = _disclosure_cache.get(cache_key)
    if cached:
        return cached

    end_date = datetime.now(tz=KST)
    begin_date = end_date - timedelta(days=days)

    params: dict[str, str] = {
        "crtfc_key": settings.dart_api_key,
        "bgn_de": begin_date.strftime("%Y%m%d"),
        "end_de": end_date.strftime("%Y%m%d"),
        "page_count": "20",
    }
    if corp_code:
        params["corp_code"] = corp_code

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{DART_BASE_URL}/list.json", params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "000":
            return []

        disclosures = []
        for item in data.get("list", []):
            # stock_code 필터링
            if stock_code and item.get("stock_code", "").strip() != stock_code:
                continue
            disclosures.append(
                Disclosure(
                    corp_name=item.get("corp_name", ""),
                    report_nm=item.get("report_nm", ""),
                    rcept_dt=item.get("rcept_dt", ""),
                    flr_nm=item.get("flr_nm", ""),
                    rcept_no=item.get("rcept_no", ""),
                )
            )

        _disclosure_cache.set(cache_key, disclosures)
        return disclosures

    except Exception:
        await logger.aexception("DART 공시 조회 실패")
        return []
