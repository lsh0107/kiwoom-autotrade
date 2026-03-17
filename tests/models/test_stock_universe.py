"""StockUniverse 모델 테스트."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.stock_universe import StockPool, StockUniverse


class TestStockUniverseCRUD:
    """StockUniverse CRUD 테스트."""

    async def test_create_stock(self, db: AsyncSession) -> None:
        """종목 생성 기본 동작."""
        stock = StockUniverse(
            pool=StockPool.POOL_A,
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            market="KOSPI",
            is_active=True,
        )
        db.add(stock)
        await db.flush()
        await db.refresh(stock)

        assert stock.id is not None
        assert stock.pool == "pool_a"
        assert stock.symbol == "005930"
        assert stock.name == "삼성전자"
        assert stock.sector == "반도체"
        assert stock.market == "KOSPI"
        assert stock.is_active is True

    async def test_unique_symbol_pool_constraint(self, db: AsyncSession) -> None:
        """(symbol, pool) 중복 시 IntegrityError."""
        stock1 = StockUniverse(
            pool=StockPool.POOL_A,
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            market="KOSPI",
        )
        stock2 = StockUniverse(
            pool=StockPool.POOL_A,
            symbol="005930",
            name="삼성전자 중복",
            sector="반도체",
            market="KOSPI",
        )
        db.add(stock1)
        db.add(stock2)

        with pytest.raises((IntegrityError, Exception)):
            await db.flush()

    async def test_same_symbol_different_pools(self, db: AsyncSession) -> None:
        """같은 symbol이 pool_a, pool_b에 동시 존재 가능."""
        stock_a = StockUniverse(
            pool=StockPool.POOL_A,
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            market="KOSPI",
        )
        stock_b = StockUniverse(
            pool=StockPool.POOL_B,
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            market="KOSPI",
        )
        db.add(stock_a)
        db.add(stock_b)
        await db.flush()

        result = await db.execute(select(StockUniverse).where(StockUniverse.symbol == "005930"))
        rows = result.scalars().all()
        assert len(rows) == 2
        pools = {r.pool for r in rows}
        assert pools == {"pool_a", "pool_b"}

    async def test_filter_by_pool(self, db: AsyncSession) -> None:
        """pool 기준 필터링."""
        for symbol, name, pool in [
            ("005930", "삼성전자", StockPool.POOL_A),
            ("000660", "SK하이닉스", StockPool.POOL_A),
            ("000100", "중형주A", StockPool.POOL_B),
        ]:
            db.add(
                StockUniverse(
                    pool=pool,
                    symbol=symbol,
                    name=name,
                    sector="기타",
                    market="KOSPI",
                )
            )
        await db.flush()

        result = await db.execute(
            select(StockUniverse).where(StockUniverse.pool == StockPool.POOL_A)
        )
        pool_a_rows = result.scalars().all()
        assert len(pool_a_rows) == 2

    async def test_is_active_default_true(self, db: AsyncSession) -> None:
        """is_active 기본값 True."""
        stock = StockUniverse(
            pool=StockPool.POOL_B,
            symbol="000100",
            name="중형주A",
            sector="기타",
            market="KOSPI",
        )
        db.add(stock)
        await db.flush()
        await db.refresh(stock)

        assert stock.is_active is True

    async def test_deactivate_stock(self, db: AsyncSession) -> None:
        """is_active=False로 비활성화."""
        stock = StockUniverse(
            pool=StockPool.POOL_A,
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            market="KOSPI",
            is_active=True,
        )
        db.add(stock)
        await db.flush()

        stock.is_active = False
        await db.flush()
        await db.refresh(stock)

        assert stock.is_active is False

    async def test_delete_stock(self, db: AsyncSession) -> None:
        """종목 삭제."""
        stock = StockUniverse(
            pool=StockPool.POOL_A,
            symbol="005930",
            name="삼성전자",
            sector="반도체",
            market="KOSPI",
        )
        db.add(stock)
        await db.flush()
        stock_id = stock.id

        await db.delete(stock)
        await db.flush()

        result = await db.execute(select(StockUniverse).where(StockUniverse.id == stock_id))
        assert result.scalar_one_or_none() is None


class TestStockPool:
    """StockPool StrEnum 테스트."""

    def test_pool_values(self) -> None:
        """풀 값 확인."""
        assert StockPool.POOL_A == "pool_a"
        assert StockPool.POOL_B == "pool_b"

    def test_pool_str(self) -> None:
        """StrEnum — str() 그대로 사용 가능."""
        assert str(StockPool.POOL_A) == "pool_a"
