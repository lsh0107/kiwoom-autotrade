"""종목 유니버스(Pool A/B) 관리 라우터."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from src.api.deps import CurrentUser, DBSession
from src.models.stock_universe import StockPool, StockUniverse

router = APIRouter(prefix="/settings", tags=["전략 설정"])


# ── Pydantic 스키마 ──────────────────────────────────────


class StockUniverseResponse(BaseModel):
    """종목 유니버스 항목 응답."""

    id: uuid.UUID
    pool: str
    symbol: str
    name: str
    sector: str
    market: str
    is_active: bool

    model_config = {"from_attributes": True}


class StockUniverseCreateRequest(BaseModel):
    """종목 추가 요청."""

    pool: StockPool = Field(description="pool_a (모멘텀) | pool_b (평균회귀)")
    symbol: str = Field(min_length=6, max_length=6, description="종목코드 6자리")
    name: str = Field(min_length=1, max_length=100, description="종목명")
    sector: str = Field(default="기타", max_length=50, description="섹터/테마")
    market: str = Field(default="KOSPI", max_length=20, description="KOSPI | KOSDAQ")


# ── 엔드포인트 ────────────────────────────────────────────


@router.get(
    "/universe",
    response_model=list[StockUniverseResponse],
)
async def list_universe(
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
    pool: StockPool | None = Query(default=None, description="풀 필터 (없으면 전체)"),
    active_only: bool = Query(default=True, description="활성 종목만 조회"),
) -> list[StockUniverseResponse]:
    """종목 유니버스를 조회한다.

    pool 파라미터로 특정 풀만 필터링 가능.
    active_only=True(기본값)이면 is_active=True인 종목만 반환.
    """
    stmt = select(StockUniverse).order_by(StockUniverse.pool, StockUniverse.symbol)

    if pool is not None:
        stmt = stmt.where(StockUniverse.pool == pool)
    if active_only:
        stmt = stmt.where(StockUniverse.is_active.is_(True))

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [StockUniverseResponse.model_validate(r) for r in rows]


@router.post(
    "/universe",
    response_model=StockUniverseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_universe_stock(
    body: StockUniverseCreateRequest,
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> StockUniverseResponse:
    """종목 풀에 종목을 추가한다.

    (symbol, pool) 조합이 이미 존재하면 409 반환.
    """
    existing = await db.execute(
        select(StockUniverse).where(
            StockUniverse.symbol == body.symbol,
            StockUniverse.pool == body.pool,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 {body.pool}에 존재하는 종목입니다 (symbol={body.symbol})",
        )

    stock = StockUniverse(
        pool=body.pool,
        symbol=body.symbol,
        name=body.name,
        sector=body.sector,
        market=body.market,
        is_active=True,
    )
    db.add(stock)
    await db.flush()
    await db.refresh(stock)
    return StockUniverseResponse.model_validate(stock)


@router.delete(
    "/universe/{stock_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_universe_stock(
    stock_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,  # noqa: ARG001
) -> None:
    """종목 풀에서 종목을 삭제한다.

    존재하지 않는 ID이면 404 반환.
    """
    result = await db.execute(select(StockUniverse).where(StockUniverse.id == stock_id))
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="종목을 찾을 수 없습니다",
        )

    await db.execute(delete(StockUniverse).where(StockUniverse.id == stock_id))
    await db.flush()
