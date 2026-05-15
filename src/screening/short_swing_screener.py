"""Short Swing 전략 후보 생성 스크리너.

장마감 후 일봉 데이터 기반으로 다음 거래일 진입 감시 후보를 생성한다.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_candle import DailyCandle
from src.models.short_swing import ShortSwingCandidate
from src.models.stock import Stock

logger = logging.getLogger(__name__)

# 스크리너 기본 파라미터 (strategy_config 연동 전 하드코딩 fallback)
_DEFAULT_UNIVERSE_SIZE = 300
_DEFAULT_MIN_PRICE = 1000
_DEFAULT_MIN_AVG_TRADING_VALUE = 3_000_000_000
_DEFAULT_PULLBACK_MIN_PCT = -0.10
_DEFAULT_PULLBACK_MAX_PCT = -0.03
_DEFAULT_AVOID_INTRADAY_RISE_PCT = 0.15
_DEFAULT_CANDIDATE_LIMIT = 20
_MA_SHORT = 20
_MA_LONG = 60


async def _load_strategy_config(db: AsyncSession) -> dict[str, object]:
    """strategy_config 테이블에서 short_swing.* 키를 읽어 dict 반환."""
    from src.models.strategy_config import StrategyConfig

    stmt = select(StrategyConfig.key, StrategyConfig.value).where(
        StrategyConfig.key.like("short_swing.%")
    )
    rows = (await db.execute(stmt)).all()
    cfg: dict[str, object] = {}
    for key, value in rows:
        short_key = key.removeprefix("short_swing.")
        cfg[short_key] = value
    return cfg


async def _build_universe(
    db: AsyncSession,
    trade_date: date_type,
    *,
    universe_size: int = _DEFAULT_UNIVERSE_SIZE,
    min_price: int = _DEFAULT_MIN_PRICE,
) -> list[str]:
    """거래대금 상위 N 종목 심볼 목록 반환.

    관리종목/우선주 등 분류 데이터가 없으므로 가격 하한 필터만 적용.
    TODO: 관리종목/투자주의/ETF/ETN/스팩/우선주 제외 필터 추가.

    Args:
        db: DB 세션.
        trade_date: 기준일.
        universe_size: 거래대금 상위 종목 수.
        min_price: 최소 주가.

    Returns:
        심볼 목록 (거래대금 내림차순).
    """
    stmt = (
        select(DailyCandle.symbol)
        .where(
            DailyCandle.date == trade_date,
            DailyCandle.close >= min_price,
        )
        .order_by((DailyCandle.close * DailyCandle.volume).desc())
        .limit(universe_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _load_candles(
    db: AsyncSession,
    symbols: list[str],
    trade_date: date_type,
    lookback: int = _MA_LONG,
) -> dict[str, list[DailyCandle]]:
    """종목별 최근 lookback 거래일 캔들 로드.

    Args:
        db: DB 세션.
        symbols: 종목 코드 목록.
        trade_date: 기준일 (포함).
        lookback: 과거 조회 거래일 수.

    Returns:
        {symbol: [candle, ...]} — 날짜 오름차순.
    """
    start_date = trade_date - timedelta(days=lookback * 2)  # 영업일 보정 여유
    stmt = (
        select(DailyCandle)
        .where(
            DailyCandle.symbol.in_(symbols),
            DailyCandle.date >= start_date,
            DailyCandle.date <= trade_date,
        )
        .order_by(DailyCandle.symbol, DailyCandle.date)
    )
    result = await db.execute(stmt)
    candles_by_symbol: dict[str, list[DailyCandle]] = {}
    for candle in result.scalars().all():
        candles_by_symbol.setdefault(candle.symbol, []).append(candle)
    return candles_by_symbol


async def _load_stock_names(
    db: AsyncSession,
    symbols: list[str],
) -> dict[str, str]:
    """종목 코드 → 종목명 매핑.

    Args:
        db: DB 세션.
        symbols: 종목 코드 목록.

    Returns:
        {symbol: name}.
    """
    stmt = select(Stock.symbol, Stock.name).where(Stock.symbol.in_(symbols))
    result = await db.execute(stmt)
    return dict(result.all())


def _calc_metrics(candles: list[DailyCandle]) -> dict | None:
    """단일 종목의 캔들 리스트로부터 스크리닝 지표를 계산한다.

    Args:
        candles: 날짜 오름차순 캔들 목록 (최소 _MA_LONG개 필요).

    Returns:
        지표 dict 또는 데이터 부족 시 None.
    """
    if len(candles) < _MA_SHORT:
        return None

    latest = candles[-1]
    close = latest.close

    # MA20
    recent_20 = candles[-_MA_SHORT:]
    ma20 = sum(c.close for c in recent_20) / _MA_SHORT

    # MA60 (데이터 부족 시 가용한 만큼)
    recent_60 = candles[-_MA_LONG:]
    ma60 = sum(c.close for c in recent_60) / len(recent_60)

    # 60일 고가
    high_60d = max(c.high for c in recent_60)

    # 60일 고점 대비 눌림률
    drawdown = (close - high_60d) / high_60d if high_60d > 0 else 0.0

    # 20일 평균 거래대금
    avg_tv_20d = sum(c.close * c.volume for c in recent_20) // _MA_SHORT

    # 당일 거래대금
    trading_value = close * latest.volume

    # 5일 수익률
    if len(candles) >= 6:
        close_5d_ago = candles[-6].close
        return_5d = (close - close_5d_ago) / close_5d_ago if close_5d_ago > 0 else 0.0
    else:
        return_5d = 0.0

    # 당일 수익률 (전일 대비)
    if len(candles) >= 2:
        prev_close = candles[-2].close
        today_return = (close - prev_close) / prev_close if prev_close > 0 else 0.0
    else:
        today_return = 0.0

    return {
        "close": close,
        "prev_day_high": latest.high,
        "ma20": ma20,
        "ma60": ma60,
        "high_60d": high_60d,
        "drawdown": drawdown,
        "avg_trading_value_20d": avg_tv_20d,
        "trading_value": trading_value,
        "return_5d": return_5d,
        "today_return": today_return,
    }


def _apply_filters(
    metrics: dict,
    *,
    min_avg_trading_value: int = _DEFAULT_MIN_AVG_TRADING_VALUE,
    pullback_min_pct: float = _DEFAULT_PULLBACK_MIN_PCT,
    pullback_max_pct: float = _DEFAULT_PULLBACK_MAX_PCT,
    avoid_intraday_rise_pct: float = _DEFAULT_AVOID_INTRADAY_RISE_PCT,
    min_price: int = _DEFAULT_MIN_PRICE,
) -> tuple[bool, dict[str, bool]]:
    """6개 필터 조건 적용.

    Args:
        metrics: _calc_metrics 결과.

    Returns:
        (통과 여부, {조건명: 통과여부} 상세).
    """
    checks = {
        "close_above_ma20": metrics["close"] > metrics["ma20"],
        "close_above_ma60": metrics["close"] > metrics["ma60"],
        "drawdown_in_range": pullback_min_pct <= metrics["drawdown"] <= pullback_max_pct,
        "avg_trading_value_ok": metrics["avg_trading_value_20d"] >= min_avg_trading_value,
        "not_overheated": metrics["today_return"] < avoid_intraday_rise_pct,
        "price_above_min": metrics["close"] >= min_price,
    }
    return all(checks.values()), checks


def _calc_score(
    metrics: dict,
    filter_details: dict[str, bool],
) -> float:
    """후보 점수 계산 (최대 100).

    Args:
        metrics: _calc_metrics 결과.
        filter_details: _apply_filters 상세.

    Returns:
        점수 (0~100).
    """
    score = 0.0

    # +25: close > MA20
    if filter_details.get("close_above_ma20"):
        score += 25.0

    # +20: close > MA60
    if filter_details.get("close_above_ma60"):
        score += 20.0

    # +20: 눌림률 범위 내
    if filter_details.get("drawdown_in_range"):
        score += 20.0

    # +15: 당일 거래대금 > 20일 평균 * 1.2
    if metrics["trading_value"] > metrics["avg_trading_value_20d"] * 1.2:
        score += 15.0

    # +10: 5일 수익률 0~12%
    if 0.0 <= metrics["return_5d"] <= 0.12:
        score += 10.0

    # +10: 시장 지수 MA20 위 (데이터 미확보 — 0점 고정)
    # TODO: KOSPI/KOSDAQ 지수 또는 ETF(069500/229200) MA20 비교 추가

    return score


async def run_short_swing_screening(
    db: AsyncSession,
    trade_date: date_type,
    *,
    universe_source: list[str] | None = None,
) -> list[ShortSwingCandidate]:
    """Short Swing 후보 생성 메인 진입점.

    Args:
        db: 비동기 DB 세션.
        trade_date: 스크리닝 기준일.
        universe_source: 외부 유니버스 (테스트용). None이면 자동 생성.

    Returns:
        저장된 ShortSwingCandidate 목록 (score 내림차순).
    """
    cfg = await _load_strategy_config(db)

    min_price = int(cfg.get("min_price", _DEFAULT_MIN_PRICE))
    min_avg_tv = int(cfg.get("min_avg_trading_value", _DEFAULT_MIN_AVG_TRADING_VALUE))
    pullback_min = float(cfg.get("pullback_min_pct", _DEFAULT_PULLBACK_MIN_PCT))
    pullback_max = float(cfg.get("pullback_max_pct", _DEFAULT_PULLBACK_MAX_PCT))
    avoid_rise = float(cfg.get("avoid_intraday_rise_pct", _DEFAULT_AVOID_INTRADAY_RISE_PCT))
    candidate_limit = int(cfg.get("candidate_limit", _DEFAULT_CANDIDATE_LIMIT))

    # 1. 유니버스 구성
    if universe_source is not None:
        symbols = universe_source
    else:
        symbols = await _build_universe(db, trade_date, min_price=min_price)

    if not symbols:
        logger.warning("short_swing_screener: 유니버스 0종목 — 스크리닝 스킵")
        return []

    # 2. 캔들 로드
    candles_map = await _load_candles(db, symbols, trade_date)

    # 3. 종목명 로드
    stock_names = await _load_stock_names(db, list(candles_map.keys()))

    # 4. 종목별 지표 계산 + 필터 + 점수
    scored: list[dict] = []
    for symbol, candles in candles_map.items():
        metrics = _calc_metrics(candles)
        if metrics is None:
            continue

        passed, details = _apply_filters(
            metrics,
            min_avg_trading_value=min_avg_tv,
            pullback_min_pct=pullback_min,
            pullback_max_pct=pullback_max,
            avoid_intraday_rise_pct=avoid_rise,
            min_price=min_price,
        )
        if not passed:
            continue

        score = _calc_score(metrics, details)
        scored.append(
            {
                "symbol": symbol,
                "name": stock_names.get(symbol, symbol),
                "metrics": metrics,
                "filter_details": details,
                "score": score,
            }
        )

    # 5. 점수 내림차순 → 상위 candidate_limit
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:candidate_limit]

    # 6. 기존 해당 날짜 후보 삭제 → 일괄 insert (멱등)
    await db.execute(
        delete(ShortSwingCandidate).where(ShortSwingCandidate.trade_date == trade_date)
    )

    candidates: list[ShortSwingCandidate] = []
    for item in top:
        m = item["metrics"]
        candidate = ShortSwingCandidate(
            trade_date=trade_date,
            symbol=item["symbol"],
            name=item["name"],
            close=m["close"],
            prev_day_high=m["prev_day_high"],
            ma20=m["ma20"],
            ma60=m["ma60"],
            high_60d=m["high_60d"],
            drawdown_from_high=m["drawdown"],
            trading_value=m["trading_value"],
            avg_trading_value_20d=m["avg_trading_value_20d"],
            return_5d=m["return_5d"],
            score=item["score"],
            reason_json={
                "filters": item["filter_details"],
                "trading_value_surge": m["trading_value"] > m["avg_trading_value_20d"] * 1.2,
                "return_5d_in_range": 0.0 <= m["return_5d"] <= 0.12,
            },
        )
        db.add(candidate)
        candidates.append(candidate)

    await db.flush()
    logger.info(
        "short_swing_screener: %d/%d 종목 통과, %d 후보 저장 (date=%s)",
        len(scored),
        len(candles_map),
        len(candidates),
        trade_date,
    )
    return candidates
