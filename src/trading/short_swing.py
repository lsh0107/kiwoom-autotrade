"""Short Swing 장중 진입 엔진.

설계 문서 6절 — 09:20~13:00 후보 감시, 진입 조건 충족 시 지정가 매수.
9개 신규 매수 금지 조건 + 진입 신호 + 수량 계산.
"""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.schemas import AccountBalance, Quote
from src.config.active_strategy import ActiveStrategy, get_active_strategy
from src.models.order import Order, OrderSide, OrderStatus
from src.models.short_swing import ShortSwingCandidate
from src.trading.kill_switch import KillSwitchStatus
from src.trading.kill_switch import kill_switch as ks
from src.trading.order_service import CreateOrderParams, create_order, submit_order
from src.utils.time import KST

if TYPE_CHECKING:
    from src.broker.base import BrokerClient

logger = structlog.get_logger("trading.short_swing")

# ── 파라미터 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ShortSwingParams:
    """short_swing 전략 파라미터.

    strategy_config 테이블의 short_swing.* 키에서 로드.
    """

    short_swing_enabled: bool = True
    max_positions: int = 5
    max_daily_new_positions: int = 2
    cash_buffer_pct: float = 0.15
    min_order_amount: int = 500_000
    entry_start_time: str = "09:20"
    entry_end_time: str = "13:00"
    stop_loss: float = -0.02
    take_profit: float = 0.04
    trailing_armed_pct: float = 0.03
    trailing_stop_pct: float = -0.015
    max_holding_days: int = 7
    min_price: int = 1000
    min_avg_trading_value: int = 3_000_000_000
    avoid_gap_up_pct: float = 0.08
    avoid_intraday_rise_pct: float = 0.15
    pullback_min_pct: float = -0.10
    pullback_max_pct: float = -0.03
    market_ma_period: int = 20
    stock_ma_short: int = 20
    stock_ma_long: int = 60
    candidate_limit: int = 20
    watchlist_limit: int = 20


# ── DB 로더 ───────────────────────────────────────────────────────────────────

_SHORT_SWING_PREFIX = "short_swing."


async def load_short_swing_params(db: AsyncSession) -> ShortSwingParams:
    """strategy_config에서 short_swing.* 키를 읽어 ShortSwingParams 를 반환한다.

    누락 키는 dataclass 기본값 사용. DB 조회 실패 시에도 기본값.

    Args:
        db: 비동기 DB 세션.

    Returns:
        ShortSwingParams 인스턴스.
    """
    defaults = ShortSwingParams()

    try:
        result = await db.execute(
            text("SELECT key, value FROM strategy_config WHERE key LIKE 'short_swing.%'"),
        )
        rows = result.fetchall()
    except Exception as exc:
        await logger.awarning("short_swing config 로드 실패, 기본값 사용", error=str(exc))
        return defaults

    config: dict[str, object] = {}
    for row in rows:
        short_key = row[0].removeprefix(_SHORT_SWING_PREFIX)
        val = row[1]
        # JSONB → Python 자동 변환이 안 되는 드라이버 대비
        if isinstance(val, str):
            import json as _json

            with contextlib.suppress(ValueError, TypeError):
                val = _json.loads(val)
        config[short_key] = val

    kwargs: dict[str, object] = {}
    for fld in ShortSwingParams.__dataclass_fields__:
        if fld in config:
            kwargs[fld] = config[fld]

    return ShortSwingParams(**kwargs)  # type: ignore[arg-type]


# ── 진입 결과 ─────────────────────────────────────────────────────────────────


@dataclass
class EntryResult:
    """한 번의 run_entry_check 실행 결과."""

    checked: int = 0
    ordered: int = 0
    skipped: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    would_order: list[dict[str, object]] = field(default_factory=list)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _parse_time(hhmm: str) -> time:
    """HH:MM 문자열을 time 객체로 변환."""
    parts = hhmm.split(":")
    return time(int(parts[0]), int(parts[1]))


async def _count_today_new_entries(db: AsyncSession, user_id: object, today: date) -> int:
    """오늘 short_swing 신규 매수 주문 수."""
    today_start = datetime(today.year, today.month, today.day, tzinfo=KST)
    result = await db.execute(
        select(func.count(Order.id)).where(
            Order.user_id == user_id,
            Order.side == OrderSide.BUY,
            Order.reason == "short_swing",
            Order.created_at >= today_start,
            Order.status.notin_([OrderStatus.FAILED, OrderStatus.REJECTED, OrderStatus.CANCELLED]),
        )
    )
    return result.scalar() or 0


async def _has_pending_buy(db: AsyncSession, user_id: object, symbol: str) -> bool:
    """해당 종목에 미체결 매수 주문이 있는지."""
    result = await db.execute(
        select(func.count(Order.id)).where(
            Order.user_id == user_id,
            Order.symbol == symbol,
            Order.side == OrderSide.BUY,
            Order.status.in_([OrderStatus.CREATED, OrderStatus.SUBMITTED, OrderStatus.ACCEPTED]),
        )
    )
    return (result.scalar() or 0) > 0


def _is_held(holdings: list[object], symbol: str) -> bool:
    """보유 종목인지 확인. holdings는 Holding 리스트."""
    return any(getattr(h, "symbol", None) == symbol for h in holdings)


async def calculate_intraday_vwap(
    client: BrokerClient,
    symbol: str,
    today: date,
) -> float | None:
    """당일 분봉 데이터로 장중 VWAP 계산.

    VWAP = sum(typical_price * volume) / sum(volume)
    typical_price = (high + low + close) / 3

    분봉 fetch 불가 시 None 반환 (fail-closed: 신호 미발동).

    Args:
        client: 브로커 클라이언트 (get_minute_price 지원 필요).
        symbol: 종목 코드.
        today: 당일 날짜.

    Returns:
        VWAP 값 또는 데이터 부족 시 None.
    """
    if not hasattr(client, "get_minute_price"):
        await logger.adebug("VWAP 스킵: get_minute_price 미지원", symbol=symbol)
        return None

    try:
        today_str = today.strftime("%Y%m%d")
        minutes = await client.get_minute_price(symbol, interval=5, base_dt=today_str)
    except Exception as exc:
        await logger.awarning("VWAP 분봉 조회 실패", symbol=symbol, error=str(exc))
        return None

    if not minutes:
        await logger.adebug("VWAP 스킵: 분봉 데이터 없음", symbol=symbol)
        return None

    # 당일 분봉만 필터링 후 VWAP 계산
    total_tp_vol = 0.0
    total_vol = 0
    for m in minutes:
        if m.datetime.startswith(today_str):
            typical_price = (m.high + m.low + m.close) / 3.0
            total_tp_vol += typical_price * m.volume
            total_vol += m.volume

    if total_vol == 0:
        await logger.adebug("VWAP 스킵: 누적 거래량 0", symbol=symbol)
        return None

    return total_tp_vol / total_vol


# ── 메인 진입점 ───────────────────────────────────────────────────────────────


async def run_entry_check(
    db: AsyncSession,
    client: BrokerClient,
    *,
    user_id: object,
    now: datetime | None = None,
    dry_run: bool = False,
) -> EntryResult:
    """Short swing 장중 진입 체크 — 후보 순회 → 조건 판정 → 지정가 매수.

    Args:
        db: 비동기 DB 세션.
        client: 브로커 클라이언트 (get_quote, place_order, get_balance).
        user_id: 트레이더 UUID.
        now: 현재 시각 주입 (테스트용). None이면 실제 KST.
        dry_run: True이면 주문 생성/브로커 호출 skip, would_order 반환.

    Returns:
        EntryResult: 체크/주문/스킵/에러 요약.
    """
    result = EntryResult()

    if now is None:
        from src.utils.time import now_kst

        now = now_kst()

    # ── 글로벌 가드 (전 종목 공통) ────────────────────────────────────────

    # 1) ACTIVE_STRATEGY
    if get_active_strategy() != ActiveStrategy.SHORT_SWING:
        await logger.ainfo("SKIP: ACTIVE_STRATEGY != short_swing")
        result.skipped.append({"reason": "active_strategy_mismatch"})
        return result

    # 2) 파라미터 로드
    params = await load_short_swing_params(db)

    if not params.short_swing_enabled:
        await logger.ainfo("SKIP: short_swing_enabled=False")
        result.skipped.append({"reason": "short_swing_disabled"})
        return result

    # 3) 시간 가드
    entry_start = _parse_time(params.entry_start_time)
    entry_end = _parse_time(params.entry_end_time)
    current_time = now.time()
    if not (entry_start <= current_time <= entry_end):
        await logger.ainfo(
            "SKIP: 진입 시간 외",
            current=current_time.isoformat(),
            window=f"{params.entry_start_time}~{params.entry_end_time}",
        )
        result.skipped.append({"reason": "outside_entry_window"})
        return result

    # 4) Kill switch
    import uuid as _uuid

    uid = _uuid.UUID(str(user_id))
    ks_status = ks.get_status(uid)
    if ks_status != KillSwitchStatus.NORMAL:
        await logger.awarning("SKIP: kill_switch active", status=ks_status.value)
        result.skipped.append({"reason": "kill_switch_active"})
        return result

    # 5) 잔고 조회
    balance: AccountBalance = await client.get_balance()
    holdings = balance.holdings

    # 6) 보유 포지션 수 (short_swing 제한은 전체 보유 기준)
    current_positions = len(holdings)
    if current_positions >= params.max_positions:
        await logger.ainfo(
            "SKIP: max_positions 도달",
            current=current_positions,
            max=params.max_positions,
        )
        result.skipped.append({"reason": "max_positions_reached"})
        return result

    # 7) 오늘 신규 진입 수
    today = now.date()
    today_new = await _count_today_new_entries(db, user_id, today)
    if today_new >= params.max_daily_new_positions:
        await logger.ainfo(
            "SKIP: max_daily_new_positions 도달",
            today_new=today_new,
            max=params.max_daily_new_positions,
        )
        result.skipped.append({"reason": "max_daily_new_positions_reached"})
        return result

    # 8) 가용 현금
    available_cash = balance.available_cash
    if available_cash <= params.min_order_amount:
        await logger.ainfo(
            "SKIP: 현금 부족",
            available=available_cash,
            min_order=params.min_order_amount,
        )
        result.skipped.append({"reason": "insufficient_cash"})
        return result

    # ── 후보 로드 ─────────────────────────────────────────────────────────
    # 전일 후보 상위 watchlist_limit개 (trade_date <= today 로 최근 것 사용)
    candidates_query = (
        select(ShortSwingCandidate)
        .where(ShortSwingCandidate.trade_date <= today)
        .order_by(ShortSwingCandidate.trade_date.desc(), ShortSwingCandidate.score.desc())
        .limit(params.watchlist_limit)
    )
    candidates_result = await db.execute(candidates_query)
    candidates = list(candidates_result.scalars().all())

    if not candidates:
        await logger.ainfo("SKIP: 후보 없음")
        result.skipped.append({"reason": "no_candidates"})
        return result

    # ── 종목별 진입 판정 ──────────────────────────────────────────────────

    for cand in candidates:
        result.checked += 1

        # 주문 상한 재확인 (루프 중 주문 성공으로 증가 가능)
        if today_new >= params.max_daily_new_positions:
            break
        if current_positions >= params.max_positions:
            break

        symbol = cand.symbol
        symbol_name = cand.name

        # 이미 보유 중
        if _is_held(holdings, symbol):
            await logger.adebug("SKIP(종목): 이미 보유", symbol=symbol)
            result.skipped.append({"symbol": symbol, "reason": "already_held"})
            continue

        # pending buy order 존재
        if await _has_pending_buy(db, user_id, symbol):
            await logger.adebug("SKIP(종목): pending buy", symbol=symbol)
            result.skipped.append({"symbol": symbol, "reason": "pending_buy_exists"})
            continue

        # 시세 조회
        try:
            quote: Quote = await client.get_quote(symbol)
        except Exception as exc:
            await logger.awarning("시세 조회 실패", symbol=symbol, error=str(exc))
            result.errors.append({"symbol": symbol, "error": str(exc)})
            continue

        current_price = quote.price
        prev_close = quote.prev_close
        open_price = quote.open

        # 시초 갭상승률
        gap_up_pct = (open_price - prev_close) / prev_close if prev_close > 0 else 0.0

        if gap_up_pct > params.avoid_gap_up_pct:
            await logger.adebug(
                "SKIP(종목): 갭상승 과열",
                symbol=symbol,
                gap_up_pct=round(gap_up_pct, 4),
            )
            result.skipped.append({"symbol": symbol, "reason": "gap_up_exceeded"})
            continue

        # 당일 상승률
        intraday_rise_pct = (current_price - prev_close) / prev_close if prev_close > 0 else 0.0

        if intraday_rise_pct > params.avoid_intraday_rise_pct:
            await logger.adebug(
                "SKIP(종목): 당일 과열",
                symbol=symbol,
                intraday_rise_pct=round(intraday_rise_pct, 4),
            )
            result.skipped.append({"symbol": symbol, "reason": "intraday_rise_exceeded"})
            continue

        # ── 진입 신호 ────────────────────────────────────────────────────

        # 전일 고가: 후보 테이블의 prev_day_high 사용. NULL이면 신호 미발동.
        if cand.prev_day_high is None:
            await logger.adebug(
                "SKIP(종목): prev_day_high 없음 (데이터 미확보)",
                symbol=symbol,
            )
            result.skipped.append({"symbol": symbol, "reason": "prev_day_high_missing"})
            continue

        previous_day_high = cand.prev_day_high

        # 장중 VWAP: 분봉 데이터 기반 실계산. 실패 시 신호 미발동 (fail-closed).
        intraday_vwap = await calculate_intraday_vwap(client, symbol, today)
        if intraday_vwap is None:
            await logger.adebug(
                "SKIP(종목): VWAP 데이터 미확보",
                symbol=symbol,
            )
            result.skipped.append({"symbol": symbol, "reason": "vwap_unavailable"})
            continue

        entry_signal = (
            current_price > previous_day_high
            and current_price >= intraday_vwap
            and gap_up_pct <= params.avoid_gap_up_pct
            and intraday_rise_pct <= params.avoid_intraday_rise_pct
        )

        if not entry_signal:
            await logger.adebug(
                "SKIP(종목): 진입 신호 미충족",
                symbol=symbol,
                current_price=current_price,
                prev_day_high=previous_day_high,
                vwap=round(intraday_vwap, 2),
            )
            result.skipped.append({"symbol": symbol, "reason": "no_entry_signal"})
            continue

        # ── 수량 계산 ────────────────────────────────────────────────────
        remaining_slots = params.max_positions - current_positions
        if remaining_slots <= 0:
            break

        usable_cash = available_cash * (1 - params.cash_buffer_pct)
        target_value = usable_cash / remaining_slots
        target_value = max(params.min_order_amount, target_value)
        target_value = min(target_value, usable_cash)

        if target_value < params.min_order_amount:
            await logger.adebug(
                "SKIP(종목): target_value < min_order_amount",
                symbol=symbol,
                target_value=int(target_value),
            )
            result.skipped.append({"symbol": symbol, "reason": "target_value_below_min"})
            continue

        order_price = current_price
        quantity = math.floor(target_value / order_price)

        if quantity <= 0:
            await logger.adebug("SKIP(종목): quantity=0", symbol=symbol)
            result.skipped.append({"symbol": symbol, "reason": "zero_quantity"})
            continue

        # ── dry_run: 주문 없이 결과만 수집 ─────────────────────────────
        if dry_run:
            result.would_order.append(
                {
                    "symbol": symbol,
                    "name": symbol_name,
                    "price": order_price,
                    "quantity": quantity,
                }
            )
            today_new += 1
            current_positions += 1
            available_cash -= order_price * quantity
            continue

        # ── 주문 직전 재확인 ─────────────────────────────────────────────
        # 가용현금 재조회
        try:
            balance_recheck: AccountBalance = await client.get_balance()
            available_cash = balance_recheck.available_cash
        except Exception:
            await logger.awarning("잔고 재조회 실패, 기존 잔고 사용", symbol=symbol)

        order_amount = order_price * quantity
        if order_amount > available_cash:
            await logger.adebug(
                "SKIP(종목): 재조회 현금 부족",
                symbol=symbol,
                order_amount=order_amount,
                available_cash=available_cash,
            )
            result.skipped.append({"symbol": symbol, "reason": "insufficient_cash_recheck"})
            continue

        # kill switch 재확인
        ks_recheck = ks.get_status(uid)
        if ks_recheck != KillSwitchStatus.NORMAL:
            await logger.awarning("SKIP(종목): kill_switch 재확인 active", symbol=symbol)
            result.skipped.append({"symbol": symbol, "reason": "kill_switch_recheck"})
            break

        # ── drawdown guard ───────────────────────────────────────────────
        try:
            from src.trading.drawdown_guard import run_all_checks

            await run_all_checks(
                user_id=uid,
                symbol=symbol,
                side="buy",
                price=order_price,
                quantity=quantity,
                db=db,
                prev_close=prev_close,
                check_market_hours=False,  # 시간 가드는 위에서 처리
            )
        except Exception as exc:
            await logger.awarning(
                "SKIP(종목): drawdown_guard 차단",
                symbol=symbol,
                error=str(exc),
            )
            result.skipped.append({"symbol": symbol, "reason": f"drawdown_guard: {exc}"})
            continue

        # ── 지정가 주문 생성 ─────────────────────────────────────────────
        try:
            order_params = CreateOrderParams(
                user_id=uid,
                symbol=symbol,
                symbol_name=symbol_name,
                side=OrderSide.BUY,
                price=order_price,
                quantity=quantity,
                reason="short_swing",
                is_mock=client._is_mock if hasattr(client, "_is_mock") else True,
                prev_close=prev_close,
                check_market_hours=False,  # 이미 시간 가드 통과
            )
            order = await create_order(db=db, params=order_params)
        except Exception as exc:
            await logger.aerror(
                "주문 생성 실패",
                symbol=symbol,
                error=str(exc),
            )
            result.errors.append({"symbol": symbol, "error": f"create_order: {exc}"})
            continue

        # 브로커 주문 제출
        try:
            from src.broker.schemas import OrderRequest, OrderSideEnum

            broker_req = OrderRequest(
                symbol=symbol,
                side=OrderSideEnum.BUY,
                price=order_price,
                quantity=quantity,
            )
            broker_resp = await client.place_order(broker_req)
            await submit_order(db=db, order=order, broker_response=broker_resp)
        except Exception as exc:
            await logger.aerror(
                "브로커 주문 제출 실패",
                symbol=symbol,
                error=str(exc),
            )
            result.errors.append({"symbol": symbol, "error": f"submit_order: {exc}"})
            # order_failed 이벤트는 submit_order 내부에서 기록됨
            continue

        # ── short_swing_positions row 생성 (PENDING_ENTRY) ──────────────
        try:
            from src.models.short_swing import PositionStatus, ShortSwingPosition
            from src.utils.krx_calendar import add_business_days

            position = ShortSwingPosition(
                user_id=uid,
                symbol=symbol,
                name=symbol_name,
                entry_date=today,
                entry_time=now,
                entry_price=order_price,
                quantity=quantity,
                highest_price_since_entry=order_price,
                stop_price=math.floor(order_price * (1 + params.stop_loss)),
                take_profit_price=math.floor(order_price * (1 + params.take_profit)),
                trailing_armed=False,
                max_holding_until=add_business_days(today, params.max_holding_days),
                status=PositionStatus.PENDING_ENTRY,
                entry_order_id=order.id,
            )
            db.add(position)
        except Exception as exc:
            await logger.aerror(
                "position 생성 실패 (주문은 성공)",
                symbol=symbol,
                error=str(exc),
            )

        await db.commit()

        await logger.ainfo(
            "short_swing 매수 주문 성공",
            symbol=symbol,
            price=order_price,
            quantity=quantity,
            order_id=str(order.id),
        )

        result.ordered += 1
        today_new += 1
        current_positions += 1
        # 가용현금 차감 (다음 종목 수량 계산에 반영)
        available_cash -= order_amount

    return result
