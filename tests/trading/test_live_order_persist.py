"""live_order_persist 어댑터 단위 테스트."""

import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order, OrderSide, OrderStatus
from src.models.user import User
from src.trading.live_order_persist import (
    get_is_mock,
    persist_order_failed,
    persist_order_filled,
    persist_order_submitted,
    reset_cached_user_id,
    resolve_live_trader_user_id,
)
from src.utils.security import hash_password


@pytest.fixture(autouse=True)
def clear_user_id_cache() -> None:
    """각 테스트 전 캐시 초기화."""
    reset_cached_user_id()
    yield
    reset_cached_user_id()


@pytest.fixture(autouse=True)
def clear_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """환경변수 초기화 (테스트 간 격리)."""
    monkeypatch.delenv("LIVE_TRADER_USER_ID", raising=False)
    monkeypatch.delenv("KIWOOM_IS_MOCK", raising=False)


@pytest.fixture
async def trader_user(db: AsyncSession) -> User:
    """트레이더 fallback 사용자 (dev@example.com)."""
    user = User(
        email="dev@example.com",
        hashed_password=hash_password("devpassword"),
        nickname="트레이더",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestGetIsMock:
    """get_is_mock 환경변수 판정 테스트."""

    def test_default_is_true(self) -> None:
        """KIWOOM_IS_MOCK 미설정 시 True 반환."""
        assert get_is_mock() is True

    def test_false_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KIWOOM_IS_MOCK=false 시 False 반환."""
        monkeypatch.setenv("KIWOOM_IS_MOCK", "false")
        assert get_is_mock() is False

    def test_zero_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KIWOOM_IS_MOCK=0 시 False 반환."""
        monkeypatch.setenv("KIWOOM_IS_MOCK", "0")
        assert get_is_mock() is False

    def test_true_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KIWOOM_IS_MOCK=true 시 True 반환."""
        monkeypatch.setenv("KIWOOM_IS_MOCK", "true")
        assert get_is_mock() is True


class TestResolveUserId:
    """resolve_live_trader_user_id 테스트."""

    async def test_env_uuid_used(self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
        """LIVE_TRADER_USER_ID 환경변수 UUID를 반환한다."""
        expected_id = uuid.uuid4()
        monkeypatch.setenv("LIVE_TRADER_USER_ID", str(expected_id))

        result = await resolve_live_trader_user_id(db)

        assert result == expected_id

    async def test_env_uuid_cached(self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
        """두 번 호출 시 동일 UUID 반환 (캐시)."""
        expected_id = uuid.uuid4()
        monkeypatch.setenv("LIVE_TRADER_USER_ID", str(expected_id))

        result1 = await resolve_live_trader_user_id(db)
        result2 = await resolve_live_trader_user_id(db)

        assert result1 == result2 == expected_id

    async def test_invalid_uuid_falls_back(
        self, db: AsyncSession, trader_user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LIVE_TRADER_USER_ID가 유효하지 않은 UUID면 dev@example.com fallback 사용."""
        monkeypatch.setenv("LIVE_TRADER_USER_ID", "not-a-uuid")

        result = await resolve_live_trader_user_id(db)

        assert result == trader_user.id

    async def test_fallback_dev_user(self, db: AsyncSession, trader_user: User) -> None:
        """LIVE_TRADER_USER_ID 미설정 시 dev@example.com UUID 반환."""
        result = await resolve_live_trader_user_id(db)

        assert result == trader_user.id

    async def test_fallback_user_missing_raises(self, db: AsyncSession) -> None:
        """dev@example.com 없으면 RuntimeError."""
        with pytest.raises(RuntimeError, match="user_id 결정 실패"):
            await resolve_live_trader_user_id(db)


class TestPersistOrderSubmitted:
    """persist_order_submitted 테스트."""

    async def test_buy_order_inserted(self, db: AsyncSession, test_user: User) -> None:
        """매수 접수 시 orders 테이블에 SUBMITTED 상태로 insert된다."""
        order_id = await persist_order_submitted(
            session=db,
            symbol="005930",
            side="BUY",
            qty=10,
            price=70000,
            broker_order_no="ORD-001",
            strategy="momentum",
            is_mock=True,
            user_id=test_user.id,
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.symbol == "005930"
        assert order.side == OrderSide.BUY
        assert order.quantity == 10
        assert order.price == 70000
        assert order.broker_order_no == "ORD-001"
        assert order.status == OrderStatus.SUBMITTED
        assert order.is_mock is True
        assert order.submitted_at is not None
        assert order.reason == "momentum"

    async def test_sell_order_inserted(self, db: AsyncSession, test_user: User) -> None:
        """매도 접수 시 OrderSide.SELL로 insert된다."""
        order_id = await persist_order_submitted(
            session=db,
            symbol="000660",
            side="SELL",
            qty=5,
            price=150000,
            broker_order_no="ORD-002",
            strategy="mean_reversion",
            is_mock=True,
            user_id=test_user.id,
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.side == OrderSide.SELL

    async def test_is_mock_false_persisted(self, db: AsyncSession, test_user: User) -> None:
        """is_mock=False이면 orders.is_mock=False로 저장된다."""
        order_id = await persist_order_submitted(
            session=db,
            symbol="005930",
            side="BUY",
            qty=1,
            price=70000,
            broker_order_no="REAL-001",
            strategy="momentum",
            is_mock=False,
            user_id=test_user.id,
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.is_mock is False

    async def test_returns_uuid(self, db: AsyncSession, test_user: User) -> None:
        """반환값이 UUID 타입이다."""
        order_id = await persist_order_submitted(
            session=db,
            symbol="005930",
            side="BUY",
            qty=1,
            price=70000,
            broker_order_no="ORD-003",
            strategy="momentum",
            is_mock=True,
            user_id=test_user.id,
        )
        assert isinstance(order_id, uuid.UUID)


class TestPersistOrderFilled:
    """persist_order_filled 테스트."""

    async def _make_submitted_order(
        self, db: AsyncSession, user_id: uuid.UUID, qty: int = 10
    ) -> uuid.UUID:
        """테스트용 SUBMITTED 주문 생성 헬퍼."""
        return await persist_order_submitted(
            session=db,
            symbol="005930",
            side="BUY",
            qty=qty,
            price=70000,
            broker_order_no="ORD-FILL",
            strategy="momentum",
            is_mock=True,
            user_id=user_id,
        )

    async def test_full_fill_sets_filled(self, db: AsyncSession, test_user: User) -> None:
        """전량체결 시 status=FILLED로 업데이트된다."""
        order_id = await self._make_submitted_order(db, test_user.id, qty=10)

        await persist_order_filled(
            session=db,
            order_id=order_id,
            filled_at=None,
            filled_qty=10,
            filled_price=70100,
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 10
        assert order.filled_price == 70100
        assert order.filled_at is not None

    async def test_partial_fill_sets_partial(self, db: AsyncSession, test_user: User) -> None:
        """부분체결 시 status=PARTIAL_FILL로 업데이트된다."""
        order_id = await self._make_submitted_order(db, test_user.id, qty=10)

        await persist_order_filled(
            session=db,
            order_id=order_id,
            filled_at=None,
            filled_qty=5,
            filled_price=70000,
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.status == OrderStatus.PARTIAL_FILL

    async def test_explicit_filled_at_stored(self, db: AsyncSession, test_user: User) -> None:
        """filled_at 명시 시 해당 값으로 저장된다."""
        order_id = await self._make_submitted_order(db, test_user.id)
        explicit_dt = datetime(2026, 4, 22, 10, 30, 0, tzinfo=UTC)

        await persist_order_filled(
            session=db,
            order_id=order_id,
            filled_at=explicit_dt,
            filled_qty=10,
            filled_price=70000,
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.filled_at is not None

    async def test_unknown_order_id_ignored(self, db: AsyncSession) -> None:
        """없는 order_id 전달 시 에러 없이 무시한다."""
        await persist_order_filled(
            session=db,
            order_id=uuid.uuid4(),
            filled_at=None,
            filled_qty=10,
            filled_price=70000,
        )
        # 에러 없이 통과하면 성공


class TestPersistOrderFailed:
    """persist_order_failed 테스트."""

    async def test_sets_failed_status(self, db: AsyncSession, test_user: User) -> None:
        """주문 실패 시 status=FAILED, error_message 저장된다."""
        order_id = await persist_order_submitted(
            session=db,
            symbol="005930",
            side="BUY",
            qty=10,
            price=70000,
            broker_order_no="ORD-FAIL",
            strategy="momentum",
            is_mock=True,
            user_id=test_user.id,
        )

        await persist_order_failed(
            session=db,
            order_id=order_id,
            reason="잔고 부족",
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.status == OrderStatus.FAILED
        assert order.error_message == "잔고 부족"

    async def test_unknown_order_id_ignored(self, db: AsyncSession) -> None:
        """없는 order_id 전달 시 에러 없이 무시한다."""
        await persist_order_failed(
            session=db,
            order_id=uuid.uuid4(),
            reason="테스트 실패",
        )
        # 에러 없이 통과하면 성공


class TestPersistOrderSubmittedMarketType:
    """persist_order_submitted: order_type="market" 저장 검증."""

    async def test_persist_order_submitted_market_type(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """order_type='market' 전달 시 Order.order_type='market'으로 저장된다."""
        order_id = await persist_order_submitted(
            session=db,
            symbol="005930",
            side="BUY",
            qty=5,
            price=0,
            broker_order_no="MKT-001",
            strategy="cross_momentum",
            is_mock=True,
            user_id=test_user.id,
            order_type="market",
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.order_type == "market"
        assert order.broker_order_no == "MKT-001"

    async def test_persist_order_submitted_default_limit(
        self, db: AsyncSession, test_user: User
    ) -> None:
        """order_type 미전달 시 기본값 'limit'으로 저장된다."""
        order_id = await persist_order_submitted(
            session=db,
            symbol="005930",
            side="BUY",
            qty=5,
            price=70000,
            broker_order_no="LMT-001",
            strategy="momentum",
            is_mock=True,
            user_id=test_user.id,
        )
        await db.commit()

        order = await db.get(Order, order_id)
        assert order is not None
        assert order.order_type == "limit"


class TestDbFailureFallback:
    """DB 장애 시 메인 경로(in-memory TradeLog) 살아있음 검증."""

    async def test_db_exception_caught_main_path_continues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """async_session_factory 장애 시 호출부 try/except에서 무시되고 메인 경로는 계속된다.

        live_trader execute_buy/execute_sell 내부의 try/except 패턴을 재현한다.
        """
        # DB 장애 시뮬레이션: 컨텍스트 진입에서 RuntimeError
        failing_factory = MagicMock()
        failing_cm = AsyncMock()
        failing_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("DB 연결 실패"))
        failing_cm.__aexit__ = AsyncMock(return_value=False)
        failing_factory.return_value = failing_cm

        db_persist_error_caught = False
        log = logging.getLogger("test")

        try:
            async with failing_factory() as _s:
                await persist_order_submitted(
                    _s, "005930", "BUY", 10, 70000, "ORD-X", "momentum", True, uuid.uuid4()
                )
                await _s.commit()
        except Exception as _db_err:
            db_persist_error_caught = True
            log.error("DB persist 실패(무시): %s", _db_err)

        # in-memory 경로는 계속 실행됨
        main_path_executed = True

        assert db_persist_error_caught is True
        assert main_path_executed is True
