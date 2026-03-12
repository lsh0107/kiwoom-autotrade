"""야간 해외 선물/지수 데이터 수집 (yfinance)."""

from dataclasses import dataclass

import structlog

from src.ai.data.cache import TTLCache

logger = structlog.get_logger(__name__)

# 해외 캐시: 5분 TTL
_futures_cache = TTLCache(default_ttl=300)

# 주요 해외 지수 심볼
OVERSEAS_SYMBOLS = {
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "NIKKEI": "^N225",
    "VIX": "^VIX",
}


@dataclass
class OverseasIndex:
    """해외 지수 데이터."""

    name: str
    symbol: str
    price: float
    change_pct: float


async def get_overseas_indices() -> list[OverseasIndex]:
    """주요 해외 지수 조회."""
    cached = _futures_cache.get("overseas_indices")
    if cached:
        return cached

    try:
        import yfinance as yf

        indices = []
        for name, symbol in OVERSEAS_SYMBOLS.items():
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = info.last_price if hasattr(info, "last_price") else 0
            prev = info.previous_close if hasattr(info, "previous_close") else 0
            change_pct = ((price - prev) / prev * 100) if prev > 0 else 0

            indices.append(
                OverseasIndex(
                    name=name,
                    symbol=symbol,
                    price=round(price, 2),
                    change_pct=round(change_pct, 2),
                )
            )

        _futures_cache.set("overseas_indices", indices)
        return indices

    except Exception:
        await logger.aexception("해외 지수 조회 실패")
        return []
