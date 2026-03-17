"""종목 유니버스 API 테스트."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.stock_universe import StockPool, StockUniverse


def _make_stock(
    pool: StockPool = StockPool.POOL_A,
    symbol: str = "005930",
    name: str = "삼성전자",
    sector: str = "반도체",
    market: str = "KOSPI",
    is_active: bool = True,
) -> StockUniverse:
    return StockUniverse(
        pool=pool,
        symbol=symbol,
        name=name,
        sector=sector,
        market=market,
        is_active=is_active,
    )


class TestListUniverse:
    """GET /api/v1/settings/universe 테스트."""

    async def test_empty_list(self, auth_client: AsyncClient) -> None:
        """종목 없으면 빈 목록."""
        resp = await auth_client.get("/api/v1/settings/universe")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_active_only_default(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """기본값 active_only=True — 비활성 종목 제외."""
        db.add(_make_stock(symbol="005930", name="삼성전자", is_active=True))
        db.add(_make_stock(symbol="000660", name="SK하이닉스", is_active=False))
        await db.flush()

        resp = await auth_client.get("/api/v1/settings/universe")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "005930"

    async def test_list_all_including_inactive(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """active_only=false — 비활성 포함 전체 반환."""
        db.add(_make_stock(symbol="005930", name="삼성전자", is_active=True))
        db.add(_make_stock(symbol="000660", name="SK하이닉스", is_active=False))
        await db.flush()

        resp = await auth_client.get("/api/v1/settings/universe?active_only=false")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_filter_by_pool_a(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """pool=pool_a 필터."""
        db.add(_make_stock(pool=StockPool.POOL_A, symbol="005930", name="삼성전자"))
        db.add(_make_stock(pool=StockPool.POOL_B, symbol="000100", name="중형주A"))
        await db.flush()

        resp = await auth_client.get("/api/v1/settings/universe?pool=pool_a")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["pool"] == "pool_a"
        assert data[0]["symbol"] == "005930"

    async def test_filter_by_pool_b(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """pool=pool_b 필터."""
        db.add(_make_stock(pool=StockPool.POOL_A, symbol="005930", name="삼성전자"))
        db.add(_make_stock(pool=StockPool.POOL_B, symbol="000100", name="중형주A"))
        await db.flush()

        resp = await auth_client.get("/api/v1/settings/universe?pool=pool_b")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["pool"] == "pool_b"

    async def test_requires_auth(self, client: AsyncClient) -> None:
        """미인증 요청 거부."""
        resp = await client.get("/api/v1/settings/universe")
        assert resp.status_code in (401, 403)

    async def test_response_fields(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """응답 필드 구조 확인."""
        db.add(_make_stock())
        await db.flush()

        resp = await auth_client.get("/api/v1/settings/universe")
        assert resp.status_code == 200
        item = resp.json()[0]
        assert {"id", "pool", "symbol", "name", "sector", "market", "is_active"} <= set(item.keys())


class TestAddUniverseStock:
    """POST /api/v1/settings/universe 테스트."""

    async def test_add_stock(self, auth_client: AsyncClient) -> None:
        """종목 추가 성공."""
        resp = await auth_client.post(
            "/api/v1/settings/universe",
            json={
                "pool": "pool_a",
                "symbol": "005930",
                "name": "삼성전자",
                "sector": "반도체",
                "market": "KOSPI",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "005930"
        assert data["pool"] == "pool_a"
        assert data["is_active"] is True

    async def test_add_to_pool_b(self, auth_client: AsyncClient) -> None:
        """pool_b에 종목 추가."""
        resp = await auth_client.post(
            "/api/v1/settings/universe",
            json={
                "pool": "pool_b",
                "symbol": "000100",
                "name": "중형주A",
                "sector": "기타",
                "market": "KOSPI",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["pool"] == "pool_b"

    async def test_same_symbol_different_pools(self, auth_client: AsyncClient) -> None:
        """같은 symbol을 pool_a, pool_b에 각각 추가 가능."""
        for pool in ("pool_a", "pool_b"):
            resp = await auth_client.post(
                "/api/v1/settings/universe",
                json={
                    "pool": pool,
                    "symbol": "005930",
                    "name": "삼성전자",
                    "sector": "반도체",
                    "market": "KOSPI",
                },
            )
            assert resp.status_code == 201

    async def test_duplicate_symbol_pool_409(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """같은 (symbol, pool) 중복 추가 → 409."""
        db.add(_make_stock(symbol="005930", pool=StockPool.POOL_A))
        await db.flush()

        resp = await auth_client.post(
            "/api/v1/settings/universe",
            json={
                "pool": "pool_a",
                "symbol": "005930",
                "name": "삼성전자",
                "sector": "반도체",
                "market": "KOSPI",
            },
        )
        assert resp.status_code == 409

    async def test_invalid_pool_422(self, auth_client: AsyncClient) -> None:
        """잘못된 pool 값 → 422."""
        resp = await auth_client.post(
            "/api/v1/settings/universe",
            json={
                "pool": "pool_c",
                "symbol": "005930",
                "name": "삼성전자",
                "sector": "반도체",
                "market": "KOSPI",
            },
        )
        assert resp.status_code == 422

    async def test_requires_auth(self, client: AsyncClient) -> None:
        """미인증 요청 거부."""
        resp = await client.post(
            "/api/v1/settings/universe",
            json={
                "pool": "pool_a",
                "symbol": "005930",
                "name": "삼성전자",
                "sector": "반도체",
                "market": "KOSPI",
            },
        )
        assert resp.status_code in (401, 403)


class TestRemoveUniverseStock:
    """DELETE /api/v1/settings/universe/{id} 테스트."""

    async def test_delete_stock(self, auth_client: AsyncClient, db: AsyncSession) -> None:
        """종목 삭제 성공 → 204."""
        stock = _make_stock()
        db.add(stock)
        await db.flush()
        stock_id = stock.id

        resp = await auth_client.delete(f"/api/v1/settings/universe/{stock_id}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_404(self, auth_client: AsyncClient) -> None:
        """존재하지 않는 ID → 404."""
        fake_id = uuid.uuid4()
        resp = await auth_client.delete(f"/api/v1/settings/universe/{fake_id}")
        assert resp.status_code == 404

    async def test_requires_auth(self, client: AsyncClient) -> None:
        """미인증 요청 거부."""
        fake_id = uuid.uuid4()
        resp = await client.delete(f"/api/v1/settings/universe/{fake_id}")
        assert resp.status_code in (401, 403)
