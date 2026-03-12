"""데이터 소스 통합 → LLM 입력 포맷팅."""

from dataclasses import dataclass

import structlog

from src.ai.data.disclosure_collector import Disclosure, get_recent_disclosures
from src.ai.data.futures_collector import OverseasIndex, get_overseas_indices
from src.ai.data.market_collector import DailyPrice, get_cached_quote, get_daily_prices
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import Quote

logger = structlog.get_logger(__name__)


@dataclass
class AggregatedData:
    """통합 데이터."""

    symbol: str
    quote: Quote | None
    daily_prices: list[DailyPrice]
    disclosures: list[Disclosure]
    overseas_indices: list[OverseasIndex]


async def aggregate_symbol_data(
    client: KiwoomClient,
    symbol: str,
) -> AggregatedData:
    """종목별 데이터 통합 수집."""
    quote = None
    daily_prices: list[DailyPrice] = []
    disclosures: list[Disclosure] = []
    overseas: list[OverseasIndex] = []

    try:
        quote = await get_cached_quote(client, symbol)
    except Exception:
        await logger.aexception("시세 조회 실패", symbol=symbol)

    try:
        daily_prices = await get_daily_prices(client, symbol, days=5)
    except Exception:
        await logger.aexception("일봉 조회 실패", symbol=symbol)

    try:
        disclosures = await get_recent_disclosures(stock_code=symbol, days=7)
    except Exception:
        await logger.aexception("공시 조회 실패", symbol=symbol)

    try:
        overseas = await get_overseas_indices()
    except Exception:
        await logger.aexception("해외 지수 조회 실패")

    return AggregatedData(
        symbol=symbol,
        quote=quote,
        daily_prices=daily_prices,
        disclosures=disclosures,
        overseas_indices=overseas,
    )


def format_for_llm(data: AggregatedData) -> dict[str, str | int | float]:
    """LLM 입력용 포맷팅.

    숫자 필드는 정수/실수로 반환 (프롬프트의 {:,} 포맷 지정자 호환).
    """
    # 일봉 텍스트
    daily_text = ""
    for dp in data.daily_prices:
        daily_text += (
            f"  {dp.date}: 시{dp.open:,} 고{dp.high:,} "
            f"저{dp.low:,} 종{dp.close:,} 량{dp.volume:,} ({dp.change_pct:+.2f}%)\n"
        )

    # 공시 텍스트
    disclosure_text = ""
    if data.disclosures:
        for d in data.disclosures[:5]:
            disclosure_text += f"  [{d.rcept_dt}] {d.report_nm} ({d.flr_nm})\n"
    else:
        disclosure_text = "  최근 7일 내 공시 없음\n"

    # 해외 지수 텍스트
    overseas_text = ""
    for idx in data.overseas_indices:
        overseas_text += f"  {idx.name}: {idx.price:,.2f} ({idx.change_pct:+.2f}%)\n"

    quote = data.quote
    return {
        "symbol": data.symbol,
        "name": quote.name if quote else "",
        "price": quote.price if quote else 0,
        "change": quote.change if quote else 0,
        "change_pct": quote.change_pct if quote else 0.0,
        "volume": quote.volume if quote else 0,
        "high": quote.high if quote else 0,
        "low": quote.low if quote else 0,
        "daily_prices": daily_text or "  데이터 없음",
        "disclosures": disclosure_text,
        "overseas_data": overseas_text or "  데이터 없음",
    }
