"""시세 조회 API 테스트."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import Quote
from src.models.broker import BrokerCredential
from src.models.daily_screening_cache import DailyScreeningCache
from src.models.stock import Stock
from src.models.user import User


@pytest.fixture
def _mock_kiwoom_client() -> AsyncMock:
    """_create_kiwoom_client를 패치한 KiwoomClient 모킹."""
    mock_client = AsyncMock()
    mock_client.get_quote.return_value = Quote(
        symbol="005930",
        name="삼성전자",
        price=70000,
        change=1000,
        change_pct=1.45,
        volume=10000000,
        high=71000,
        low=69000,
        open=69500,
        prev_close=69000,
    )
    mock_client.close.return_value = None
    return mock_client


@pytest.fixture
async def stock_fixtures(db: AsyncSession) -> list[Stock]:
    """검색 테스트용 종목 마스터 데이터."""
    stocks = [
        Stock(
            symbol="005930",
            name="삼성전자",
            market="KOSPI",
            sector="전기전자",
            is_active=True,
        ),
        Stock(
            symbol="000660",
            name="SK하이닉스",
            market="KOSPI",
            sector="전기전자",
            is_active=True,
        ),
        Stock(
            symbol="035420",
            name="NAVER",
            market="KOSPI",
            sector="서비스업",
            is_active=True,
        ),
        Stock(
            symbol="999999",
            name="비활성종목",
            market="KOSPI",
            sector="기타",
            is_active=False,
        ),
    ]
    db.add_all(stocks)
    await db.commit()
    return stocks


@pytest.fixture
async def screening_fixtures(db: AsyncSession) -> list[DailyScreeningCache]:
    """Top 종목 테스트용 스크리닝 캐시 데이터."""
    today = datetime.date(2026, 5, 11)
    yesterday = datetime.date(2026, 5, 10)
    rows = [
        # 오늘 날짜 momentum_daily, rank 1~2
        DailyScreeningCache(
            date=today,
            profile="momentum_daily",
            symbol="005930",
            name="삼성전자",
            sector="전기전자",
            rank=1,
            passed=True,
            close=70000,
            vol_ratio=2.5,
        ),
        DailyScreeningCache(
            date=today,
            profile="momentum_daily",
            symbol="000660",
            name="SK하이닉스",
            sector="전기전자",
            rank=2,
            passed=True,
            close=120000,
            vol_ratio=1.8,
        ),
        # 오늘 날짜 다른 프로파일
        DailyScreeningCache(
            date=today,
            profile="breakout",
            symbol="035420",
            name="NAVER",
            sector="서비스업",
            rank=1,
            passed=True,
            close=200000,
            vol_ratio=3.0,
        ),
        # 어제 날짜 (최신 아님)
        DailyScreeningCache(
            date=yesterday,
            profile="momentum_daily",
            symbol="005930",
            name="삼성전자",
            sector="전기전자",
            rank=1,
            passed=True,
            close=69000,
            vol_ratio=1.5,
        ),
        # 오늘 날짜이지만 미통과
        DailyScreeningCache(
            date=today,
            profile="momentum_daily",
            symbol="035420",
            name="NAVER",
            sector="서비스업",
            rank=0,
            passed=False,
            close=200000,
            vol_ratio=0.5,
        ),
    ]
    db.add_all(rows)
    await db.commit()
    return rows


class TestGetQuote:
    """시세 조회 테스트."""

    async def test_get_quote(
        self,
        auth_client: AsyncClient,
        test_user: User,
        broker_credential: BrokerCredential,
        _mock_kiwoom_client: AsyncMock,
    ) -> None:
        """인증된 사용자가 시세를 조회하면 200 응답."""
        with patch(
            "src.api.v1.market._create_kiwoom_client",
            return_value=_mock_kiwoom_client,
        ):
            resp = await auth_client.get("/api/v1/market/quote/005930")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "005930"
        assert data["name"] == "삼성전자"
        assert data["price"] == 70000
        assert data["change"] == 1000
        assert data["volume"] == 10000000

    async def test_get_quote_no_credential(
        self,
        auth_client: AsyncClient,
        test_user: User,
    ) -> None:
        """자격증명 없으면 422 (NO_CREDENTIALS)."""
        resp = await auth_client.get("/api/v1/market/quote/005930")
        assert resp.status_code == 422
        assert resp.json()["error"] == "NO_CREDENTIALS"


class TestMarketUnauthenticated:
    """미인증 시세 조회 테스트."""

    async def test_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 시세 조회 → 401."""
        resp = await client.get("/api/v1/market/quote/005930")
        assert resp.status_code == 401


class TestSearchStocks:
    """종목 검색 API 테스트."""

    async def test_search_korean_name(
        self,
        auth_client: AsyncClient,
        stock_fixtures: list[Stock],
    ) -> None:
        """한글 종목명 부분 일치 검색."""
        resp = await auth_client.get("/api/v1/market/search?q=삼성")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "005930"
        assert data[0]["name"] == "삼성전자"
        assert data[0]["market"] == "KOSPI"
        assert data[0]["sector"] == "전기전자"

    async def test_search_symbol_prefix(
        self,
        auth_client: AsyncClient,
        stock_fixtures: list[Stock],
    ) -> None:
        """종목코드 prefix 검색."""
        resp = await auth_client.get("/api/v1/market/search?q=005")
        assert resp.status_code == 200
        data = resp.json()
        symbols = [d["symbol"] for d in data]
        assert "005930" in symbols

    async def test_search_empty_q_returns_empty(
        self,
        auth_client: AsyncClient,
        stock_fixtures: list[Stock],
    ) -> None:
        """빈 q → 빈 리스트 반환."""
        resp = await auth_client.get("/api/v1/market/search?q=")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_search_no_q_returns_empty(
        self,
        auth_client: AsyncClient,
        stock_fixtures: list[Stock],
    ) -> None:
        """q 파라미터 생략 → 빈 리스트 반환."""
        resp = await auth_client.get("/api/v1/market/search")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_search_limit(
        self,
        auth_client: AsyncClient,
        stock_fixtures: list[Stock],
    ) -> None:
        """limit=1 이면 결과 최대 1개."""
        resp = await auth_client.get("/api/v1/market/search?q=전자&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

    async def test_search_inactive_excluded(
        self,
        auth_client: AsyncClient,
        stock_fixtures: list[Stock],
    ) -> None:
        """is_active=False 종목은 검색 결과에서 제외."""
        resp = await auth_client.get("/api/v1/market/search?q=비활성")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_search_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 → 401."""
        resp = await client.get("/api/v1/market/search?q=삼성")
        assert resp.status_code == 401


class TestTopStocks:
    """스크리닝 Top 종목 API 테스트."""

    async def test_top_returns_latest_date(
        self,
        auth_client: AsyncClient,
        screening_fixtures: list[DailyScreeningCache],
    ) -> None:
        """최신 날짜 기준 passed=True 종목을 rank 오름차순으로 반환한다."""
        resp = await auth_client.get("/api/v1/market/top?profile=momentum_daily")
        assert resp.status_code == 200
        data = resp.json()
        # 오늘 날짜 momentum_daily 통과 종목 2개
        assert len(data) == 2
        assert data[0]["symbol"] == "005930"
        assert data[0]["rank"] == 1
        assert data[1]["symbol"] == "000660"
        assert data[1]["rank"] == 2

    async def test_top_response_fields(
        self,
        auth_client: AsyncClient,
        screening_fixtures: list[DailyScreeningCache],
    ) -> None:
        """응답 필드 구조 검증."""
        resp = await auth_client.get("/api/v1/market/top?profile=momentum_daily&limit=1")
        assert resp.status_code == 200
        item = resp.json()[0]
        assert "symbol" in item
        assert "name" in item
        assert "rank" in item
        assert "close" in item
        assert "vol_ratio" in item
        assert "sector" in item

    async def test_top_empty_cache_returns_empty(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """캐시 데이터 없을 때 빈 리스트 반환 (404 아님)."""
        resp = await auth_client.get("/api/v1/market/top?profile=momentum_daily")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_top_profile_filter(
        self,
        auth_client: AsyncClient,
        screening_fixtures: list[DailyScreeningCache],
    ) -> None:
        """profile 파라미터로 다른 프로파일 종목이 섞이지 않는다."""
        resp = await auth_client.get("/api/v1/market/top?profile=breakout")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "035420"

    async def test_top_limit(
        self,
        auth_client: AsyncClient,
        screening_fixtures: list[DailyScreeningCache],
    ) -> None:
        """limit=1 이면 1개만 반환."""
        resp = await auth_client.get("/api/v1/market/top?profile=momentum_daily&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_top_unauthenticated(self, client: AsyncClient) -> None:
        """미인증 시 → 401."""
        resp = await client.get("/api/v1/market/top")
        assert resp.status_code == 401
