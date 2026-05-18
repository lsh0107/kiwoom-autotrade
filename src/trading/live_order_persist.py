"""live_trader → orders/trade_logs DB persist 어댑터 (ADR-014).

live_trader의 in-memory TradeLog와 독립적으로 동작하는 그림자 persist 레이어.
session을 주입받아 사용하며, 호출자는 DB 실패 시 try/except로 무시한다.
메인 매매 경로는 이 모듈의 실패와 무관하게 유지된다.
"""

import os
import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order, OrderSide, OrderStatus
from src.models.user import User
from src.utils.time import now_kst

logger = structlog.get_logger(__name__)

# 환경변수로 지정한 트레이더 user_id (프로세스 수명 동안 캐시)
_cached_user_id: uuid.UUID | None = None
_FALLBACK_EMAIL = "dev@example.com"


def get_is_mock() -> bool:
    """KIWOOM_IS_MOCK 환경변수로 모의투자 여부 판정 (기본 True).

    Returns:
        True이면 모의투자, False이면 실거래.
    """
    return os.environ.get("KIWOOM_IS_MOCK", "true").lower() not in ("false", "0", "no")


async def resolve_live_trader_user_id(db: AsyncSession) -> uuid.UUID:
    """트레이더 user_id 결정 (캐시 우선).

    1순위: LIVE_TRADER_USER_ID 환경변수 UUID
    2순위: dev@example.com 사용자의 UUID (fallback)

    Args:
        db: 비동기 DB 세션 (fallback 사용자 조회용)

    Returns:
        결정된 user_id UUID

    Raises:
        RuntimeError: LIVE_TRADER_USER_ID 미설정 + fallback 사용자 없음
    """
    global _cached_user_id
    if _cached_user_id is not None:
        return _cached_user_id

    env_val = os.environ.get("LIVE_TRADER_USER_ID", "").strip()
    if env_val:
        try:
            _cached_user_id = uuid.UUID(env_val)
            logger.info("live_trader user_id 환경변수 사용", user_id=str(_cached_user_id))
            return _cached_user_id
        except ValueError:
            logger.warning("LIVE_TRADER_USER_ID UUID 파싱 실패, fallback 진행", raw=env_val)

    result = await db.execute(select(User).where(User.email == _FALLBACK_EMAIL))
    user = result.scalar_one_or_none()
    if user is None:
        raise RuntimeError(
            f"live_trader user_id 결정 실패: "
            f"LIVE_TRADER_USER_ID 미설정 + {_FALLBACK_EMAIL} 사용자 없음"
        )
    _cached_user_id = user.id
    logger.info(
        "live_trader user_id fallback 사용",
        email=_FALLBACK_EMAIL,
        user_id=str(_cached_user_id),
    )
    return _cached_user_id


def reset_cached_user_id() -> None:
    """캐시된 user_id 초기화 (테스트용).

    프로덕션에서는 호출하지 않는다.
    """
    global _cached_user_id
    _cached_user_id = None


async def persist_order_submitted(
    session: AsyncSession,
    symbol: str,
    side: str,
    qty: int,
    price: int,
    broker_order_no: str,
    strategy: str,
    is_mock: bool,
    user_id: uuid.UUID,
    *,
    order_type: str = "limit",
) -> uuid.UUID:
    """매수/매도 접수 직후 orders 테이블에 SUBMITTED 상태로 insert.

    session.flush()만 수행하며, commit은 호출자 책임이다.

    Args:
        session: 비동기 DB 세션
        symbol: 종목코드
        side: 매수/매도 구분 ("BUY" | "SELL")
        qty: 주문 수량
        price: 주문 가격 (시장가 주문이면 0)
        broker_order_no: 브로커 주문번호
        strategy: 전략 이름 ("momentum" | "mean_reversion" 등)
        is_mock: 모의투자 여부
        user_id: 트레이더 사용자 UUID
        order_type: 주문 유형 ("limit" | "market"). 기본값 "limit" (backward compatible).

    Returns:
        생성된 Order UUID
    """
    order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
    order = Order(
        user_id=user_id,
        symbol=symbol,
        side=order_side,
        order_type=order_type,
        price=price,
        quantity=qty,
        filled_quantity=0,
        status=OrderStatus.SUBMITTED,
        broker_order_no=broker_order_no,
        is_mock=is_mock,
        submitted_at=now_kst(),
        reason=strategy,
    )
    session.add(order)
    await session.flush()

    logger.info(
        "persist_order_submitted",
        order_id=str(order.id),
        symbol=symbol,
        side=side,
        qty=qty,
        order_type=order_type,
        broker_order_no=broker_order_no,
        is_mock=is_mock,
    )
    return order.id


async def persist_order_filled(
    session: AsyncSession,
    order_id: uuid.UUID,
    filled_at: datetime | None,
    filled_qty: int,
    filled_price: int,
) -> None:
    """체결 이벤트 시 orders 상태를 FILLED 또는 PARTIAL_FILL로 업데이트.

    부분체결(filled_qty < order.quantity)이면 PARTIAL_FILL, 전량체결이면 FILLED.
    session.flush 없이 변경사항만 설정하며, commit은 호출자 책임이다.

    Args:
        session: 비동기 DB 세션
        order_id: 대상 Order UUID (persist_order_submitted 반환값)
        filled_at: 체결 시각. None이면 now_kst() 사용
        filled_qty: 체결 수량
        filled_price: 체결 가격
    """
    order = await session.get(Order, order_id)
    if order is None:
        logger.warning("persist_order_filled: 주문 없음", order_id=str(order_id))
        return

    order.filled_quantity = filled_qty
    order.filled_price = filled_price
    order.filled_at = filled_at or now_kst()
    order.status = OrderStatus.FILLED if filled_qty >= order.quantity else OrderStatus.PARTIAL_FILL

    logger.info(
        "persist_order_filled",
        order_id=str(order_id),
        filled_qty=filled_qty,
        filled_price=filled_price,
        status=order.status,
    )


async def persist_order_failed(
    session: AsyncSession,
    order_id: uuid.UUID,
    reason: str,
) -> None:
    """주문 실패 시 orders 상태를 FAILED로 업데이트.

    commit은 호출자 책임이다.

    Args:
        session: 비동기 DB 세션
        order_id: 대상 Order UUID
        reason: 실패 사유
    """
    order = await session.get(Order, order_id)
    if order is None:
        logger.warning("persist_order_failed: 주문 없음", order_id=str(order_id))
        return

    order.status = OrderStatus.FAILED
    order.error_message = reason

    logger.info("persist_order_failed", order_id=str(order_id), reason=reason)
