"""시세 조회 라우터."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import ActiveBrokerCredential, CurrentUser, DBSession
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.broker.schemas import DailyPrice, Orderbook, Quote
from src.models.broker import BrokerCredential as BrokerCredentialModel
from src.models.daily_screening_cache import DailyScreeningCache
from src.models.stock import Stock
from src.utils.crypto import decrypt

router = APIRouter(prefix="/market", tags=["시세"])


class StockSearchResult(BaseModel):
    """종목 검색 결과 스키마."""

    symbol: str
    name: str
    market: str
    sector: str


class TopStockResult(BaseModel):
    """스크리닝 Top 종목 결과 스키마."""

    symbol: str
    name: str
    rank: int
    close: int
    vol_ratio: float
    sector: str


def _create_kiwoom_client(cred: BrokerCredentialModel, db: AsyncSession) -> KiwoomClient:
    """DB 자격증명으로 KiwoomClient를 생성한다."""
    base_url = MOCK_BASE_URL if cred.is_mock else REAL_BASE_URL
    return KiwoomClient(
        base_url=base_url,
        app_key=decrypt(cred.encrypted_app_key),
        app_secret=decrypt(cred.encrypted_app_secret),
        is_mock=cred.is_mock,
        db=db,
        credential_id=cred.id,
    )


@router.get(
    "/quote/{symbol}",
    response_model=Quote,
)
async def get_quote(
    symbol: str,
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
) -> Quote:
    """종목 현재가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    client = _create_kiwoom_client(credential, db)
    try:
        return await client.get_quote(symbol)
    finally:
        await client.close()


@router.get(
    "/orderbook/{symbol}",
    response_model=Orderbook,
)
async def get_orderbook(
    symbol: str,
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
) -> Orderbook:
    """종목 호가를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
    """
    client = _create_kiwoom_client(credential, db)
    try:
        return await client.get_orderbook(symbol)
    finally:
        await client.close()


@router.get(
    "/chart/{symbol}/daily",
    response_model=list[DailyPrice],
)
async def get_daily_chart(
    symbol: str,
    _current_user: CurrentUser,
    credential: ActiveBrokerCredential,
    db: DBSession,
    days: int = Query(default=60, ge=1, le=365, description="조회 일수 (기본 60일)"),
) -> list[DailyPrice]:
    """종목 일봉 차트를 조회한다.

    Args:
        symbol: 종목코드 (6자리, 예: 005930)
        days: 조회 일수 (1~365, 기본 60)

    Returns:
        일봉 데이터 리스트 (최신 순)
    """
    client = _create_kiwoom_client(credential, db)
    try:
        prices = await client.get_daily_chart(symbol)
        return prices[:days]
    finally:
        await client.close()


@router.get(
    "/search",
    response_model=list[StockSearchResult],
)
async def search_stocks(
    _current_user: CurrentUser,
    db: DBSession,
    q: str = Query(default="", description="검색어 (종목명 또는 종목코드)"),
    limit: int = Query(default=10, ge=1, le=50, description="최대 결과 수 (1~50)"),
) -> list[StockSearchResult]:
    """종목을 검색한다.

    q가 비어있으면 빈 리스트를 반환한다.
    종목명 ILIKE '%q%' 또는 종목코드 LIKE 'q%' 조건을 OR로 적용한다.
    is_active=True 인 종목만 대상으로 한다.

    Args:
        q: 검색어 (한글 종목명 또는 숫자 종목코드 prefix)
        limit: 최대 반환 수 (1~50)

    Returns:
        종목 검색 결과 리스트
    """
    if not q:
        return []

    stmt = (
        select(Stock)
        .where(
            Stock.is_active.is_(True),
            or_(
                Stock.name.ilike(f"%{q}%"),
                Stock.symbol.like(f"{q}%"),
            ),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    stocks = result.scalars().all()
    return [
        StockSearchResult(
            symbol=s.symbol,
            name=s.name,
            market=s.market,
            sector=s.sector,
        )
        for s in stocks
    ]


@router.get(
    "/top",
    response_model=list[TopStockResult],
)
async def get_top_stocks(
    _current_user: CurrentUser,
    db: DBSession,
    profile: str = Query(default="momentum_daily", description="스크리닝 프로파일명"),
    limit: int = Query(default=10, ge=1, le=50, description="최대 결과 수 (1~50)"),
) -> list[TopStockResult]:
    """스크리닝 Top 종목을 조회한다.

    daily_screening_cache 최신 거래일 기준으로 profile 매칭 + 통과 종목을
    rank 오름차순으로 반환한다.
    캐시가 비어있으면 빈 리스트를 반환한다 (404 아님).

    Args:
        profile: 스크리닝 프로파일명 (예: momentum_daily)
        limit: 최대 반환 수 (1~50)

    Returns:
        Top 종목 리스트 (rank 오름차순)
    """
    latest_date_subq = select(func.max(DailyScreeningCache.date)).scalar_subquery()

    stmt = (
        select(DailyScreeningCache)
        .where(
            DailyScreeningCache.date == latest_date_subq,
            DailyScreeningCache.profile == profile,
            DailyScreeningCache.passed.is_(True),
            DailyScreeningCache.rank.is_not(None),
        )
        .order_by(DailyScreeningCache.rank.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        TopStockResult(
            symbol=r.symbol,
            name=r.name,
            rank=r.rank,
            close=r.close,
            vol_ratio=r.vol_ratio,
            sector=r.sector,
        )
        for r in rows
    ]
