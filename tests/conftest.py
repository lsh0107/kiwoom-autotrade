"""공통 테스트 fixture."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.config.database import get_db
from src.models.base import Base
from src.models.broker import BrokerCredential
from src.models.user import User, UserRole
from src.utils.crypto import encrypt
from src.utils.jwt import create_access_token
from src.utils.security import hash_password

# 테스트용 인메모리 SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """테스트 DB 초기화."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """테스트 DB 세션."""
    async with test_session_factory() as session:
        yield session


@pytest.fixture
def app(db: AsyncSession) -> FastAPI:
    """테스트용 FastAPI 앱."""
    from src.main import create_app

    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """테스트 HTTP 클라이언트."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """테스트 사용자."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        nickname="테스터",
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    """관리자 테스트 사용자."""
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpassword123"),
        nickname="관리자",
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
def auth_client(client: AsyncClient, test_user: User) -> AsyncClient:
    """인증된 테스트 클라이언트."""
    token = create_access_token(test_user.id)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    """관리자 인증 테스트 클라이언트."""
    token = create_access_token(admin_user.id)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def mock_broker() -> AsyncMock:
    """모의 브로커 클라이언트."""
    from src.broker.schemas import AccountBalance, BrokerOrderResponse, Holding, Quote

    broker = AsyncMock()
    broker.authenticate.return_value = None
    broker.get_quote.return_value = Quote(
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
    broker.get_balance.return_value = AccountBalance(
        total_eval=10000000,
        total_profit=500000,
        total_profit_pct=5.26,
        available_cash=5000000,
        holdings=[
            Holding(
                symbol="005930",
                name="삼성전자",
                quantity=10,
                avg_price=65000,
                current_price=70000,
                eval_amount=700000,
                profit=50000,
                profit_pct=7.69,
            )
        ],
    )
    broker.place_order.return_value = BrokerOrderResponse(
        order_no="00001",
        symbol="005930",
        side="buy",
        price=70000,
        quantity=10,
        status="submitted",
        message="주문 접수",
    )
    return broker


@pytest.fixture
async def broker_credential(db: AsyncSession, test_user: User) -> BrokerCredential:
    """테스트용 브로커 자격증명."""
    cred = BrokerCredential(
        user_id=test_user.id,
        broker_name="kiwoom",
        encrypted_app_key=encrypt("test_app_key"),
        encrypted_app_secret=encrypt("test_app_secret"),
        account_no="1234567890",
        is_mock=True,
        is_active=True,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred
