"""키움 시세 데이터 수집."""

from dataclasses import dataclass

import structlog

from src.ai.data.cache import TTLCache
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import Quote

logger = structlog.get_logger(__name__)

# 시세 캐시: 30초 TTL
_quote_cache = TTLCache(default_ttl=30)


@dataclass
class DailyPrice:
    """일봉 데이터."""

    date: str
    open: int
    high: int
    low: int
    close: int
    volume: int
    change_pct: float


async def get_cached_quote(client: KiwoomClient, symbol: str) -> Quote:
    """캐시된 현재가 조회."""
    cached = _quote_cache.get(f"quote:{symbol}")
    if cached:
        return cached

    quote = await client.get_quote(symbol)
    _quote_cache.set(f"quote:{symbol}", quote)
    return quote


async def get_daily_prices(
    client: KiwoomClient,
    symbol: str,
    days: int = 5,
) -> list[DailyPrice]:
    """최근 일봉 데이터 조회."""
    cache_key = f"daily:{symbol}:{days}"
    cached = _quote_cache.get(cache_key)
    if cached:
        return cached

    try:
        raw = await client.get_daily_price(symbol)
        prices = []
        for item in raw[:days]:
            prices.append(
                DailyPrice(
                    date=item.get("stck_bsop_date", ""),
                    open=int(item.get("stck_oprc", 0)),
                    high=int(item.get("stck_hgpr", 0)),
                    low=int(item.get("stck_lwpr", 0)),
                    close=int(item.get("stck_clpr", 0)),
                    volume=int(item.get("acml_vol", 0)),
                    change_pct=float(item.get("prdy_ctrt", 0)),
                )
            )
        _quote_cache.set(cache_key, prices, ttl=300)
        return prices
    except Exception:
        await logger.aexception("일봉 데이터 조회 실패", symbol=symbol)
        return []
