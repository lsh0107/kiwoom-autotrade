"""Short Swing 스크리너 테스트.

문서 12.1 — 8개 케이스:
1. MA20 아래 종목 제외
2. MA60 아래 종목 제외
3. 눌림률 범위 밖 제외
4. 거래대금 부족 제외
5. 당일 과열 제외 (today_return >= +15%)
6. 가격 1,000원 미만 제외
7. 점수 계산 및 정렬
8. (trade_date, symbol) 중복 저장 방지
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_candle import DailyCandle
from src.models.short_swing import ShortSwingCandidate
from src.models.stock import Stock
from src.screening.short_swing_screener import run_short_swing_screening


def _make_stock(symbol: str, name: str) -> Stock:
    """테스트 종목 마스터 생성."""
    return Stock(symbol=symbol, name=name, market="KOSPI", sector="테스트")


def _make_candles(
    symbol: str,
    trade_date: date,
    *,
    close: int = 50000,
    high: int = 55000,
    volume: int = 200000,
    n_days: int = 65,
    close_trend: float = 0.0,
    high_peak_offset: int | None = None,
) -> list[DailyCandle]:
    """테스트용 일봉 시퀀스 생성.

    Args:
        symbol: 종목 코드.
        trade_date: 기준일 (마지막 캔들 날짜).
        close: 기준일 종가.
        high: 기준일 고가 (고정 또는 peak 조정).
        volume: 거래량.
        n_days: 생성할 캔들 수.
        close_trend: 일별 종가 변동 비율 (과거→현재 증가).
        high_peak_offset: 고가 피크를 넣을 거래일 전 오프셋 (60일 내).
    """
    candles = []
    for i in range(n_days):
        d = trade_date - timedelta(days=n_days - 1 - i)
        # 과거에서 현재로 점진적 변동
        day_close = int(close * (1 - close_trend * (n_days - 1 - i)))
        day_high = max(day_close, high)

        # 특정 오프셋에 고점 피크 설정
        if high_peak_offset is not None and i == (n_days - 1 - high_peak_offset):
            day_high = int(close * 1.15)  # 고점 +15%

        candles.append(
            DailyCandle(
                symbol=symbol,
                date=d,
                open=day_close - 500,
                high=day_high,
                low=day_close - 1000,
                close=day_close,
                volume=volume,
                source="test",
            )
        )
    return candles


def _passing_candles(
    symbol: str,
    trade_date: date,
    *,
    close: int = 50000,
    volume: int = 200000,
) -> list[DailyCandle]:
    """모든 필터를 통과하는 '이상적인' 캔들 세트.

    - close > MA20, close > MA60 (기준일 종가를 약간 높게)
    - drawdown: 고점 대비 -3% ~ -10% 범위 (high만 spike, close 유지)
    - 거래대금 30억 이상 (50000 * 200000 = 100억)
    - today_return < 15%
    - price >= 1000
    """
    candles = []
    n_days = 65
    base_close = int(close * 0.995)  # 과거 종가는 기준일보다 약간 낮게
    for i in range(n_days):
        d = trade_date - timedelta(days=n_days - 1 - i)
        day_close = base_close
        day_high = base_close + 500

        # 40일 전에 고가만 spike → drawdown 범위 확보 (close는 유지)
        if i == (n_days - 1 - 40):
            day_high = int(close * 1.08)

        # 기준일(마지막 캔들)은 원래 close 사용
        if i == n_days - 1:
            day_close = close
            day_high = close + 500

        candles.append(
            DailyCandle(
                symbol=symbol,
                date=d,
                open=day_close - 200,
                high=day_high,
                low=day_close - 500,
                close=day_close,
                volume=volume,
                source="test",
            )
        )
    return candles


# ── 기준 날짜 ──
_TRADE_DATE = date(2026, 5, 14)


class TestMA20Filter:
    """MA20 아래 종목 제외."""

    async def test_below_ma20_excluded(self, db: AsyncSession) -> None:
        """종가 < MA20 → 후보 탈락."""
        symbol = "000010"
        db.add(_make_stock(symbol, "MA20실패"))

        # 최근 20일은 종가 50000, 기준일만 종가 40000 (< MA20)
        candles = _passing_candles(symbol, _TRADE_DATE, close=50000)
        candles[-1] = DailyCandle(
            symbol=symbol,
            date=_TRADE_DATE,
            open=49000,
            high=50000,
            low=39000,
            close=40000,  # MA20 ≈ 50000 → 40000 < 50000
            volume=200000,
            source="test",
        )
        db.add_all(candles)
        await db.flush()

        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result) == 0


class TestMA60Filter:
    """MA60 아래 종목 제외."""

    async def test_below_ma60_excluded(self, db: AsyncSession) -> None:
        """종가 < MA60 → 후보 탈락."""
        symbol = "000020"
        db.add(_make_stock(symbol, "MA60실패"))

        # MA60을 높게 만들기: 과거 캔들은 80000, 기준일은 50000
        candles = []
        n_days = 65
        for i in range(n_days):
            d = _TRADE_DATE - timedelta(days=n_days - 1 - i)
            day_close = 80000 if i < n_days - 5 else 50000

            candles.append(
                DailyCandle(
                    symbol=symbol,
                    date=d,
                    open=day_close - 200,
                    high=day_close + 500,
                    low=day_close - 500,
                    close=day_close,
                    volume=200000,
                    source="test",
                )
            )
        db.add_all(candles)
        await db.flush()

        # close=50000, MA60 ≈ (60*80000+5*50000)/65 ≈ 77692 → 50000 < 77692
        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result) == 0


class TestPullbackFilter:
    """눌림률 범위 밖 제외."""

    async def test_drawdown_too_deep_excluded(self, db: AsyncSession) -> None:
        """눌림률 < -10% → 제외."""
        symbol = "000030"
        db.add(_make_stock(symbol, "눌림과다"))

        # 60일 고점 = 60000, 현재가 = 50000 → drawdown = -16.7% (< -10%)
        candles = _passing_candles(symbol, _TRADE_DATE, close=50000)
        # 40일 전 고점을 훨씬 높게
        idx = len(candles) - 1 - 40
        candles[idx] = DailyCandle(
            symbol=symbol,
            date=candles[idx].date,
            open=59000,
            high=60000,
            low=58000,
            close=60000,
            volume=200000,
            source="test",
        )
        db.add_all(candles)
        await db.flush()

        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result) == 0

    async def test_drawdown_too_shallow_excluded(self, db: AsyncSession) -> None:
        """눌림률 > -3% (거의 안 빠짐) → 제외."""
        symbol = "000031"
        db.add(_make_stock(symbol, "눌림부족"))

        # flat candles → drawdown ≈ 0% (not in -10% ~ -3%)
        candles = _make_candles(symbol, _TRADE_DATE, close=50000, high=50500, volume=200000)
        db.add_all(candles)
        await db.flush()

        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result) == 0


class TestTradingValueFilter:
    """거래대금 부족 제외."""

    async def test_low_trading_value_excluded(self, db: AsyncSession) -> None:
        """20일 평균 거래대금 < 30억 → 제외."""
        symbol = "000040"
        db.add(_make_stock(symbol, "거래대금부족"))

        # 거래량 적어 거래대금 미달: 50000 * 10000 = 5억
        candles = _passing_candles(symbol, _TRADE_DATE, close=50000, volume=10000)
        db.add_all(candles)
        await db.flush()

        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result) == 0


class TestOverheatFilter:
    """당일 과열 제외."""

    async def test_today_return_over_15pct_excluded(self, db: AsyncSession) -> None:
        """당일 수익률 >= 15% → 제외."""
        symbol = "000050"
        db.add(_make_stock(symbol, "당일과열"))

        candles = _passing_candles(symbol, _TRADE_DATE, close=50000)
        # 기준일만 급등: 전일 대비 +20%
        prev_close = candles[-2].close  # ~50000
        hot_close = int(prev_close * 1.20)
        candles[-1] = DailyCandle(
            symbol=symbol,
            date=_TRADE_DATE,
            open=prev_close + 1000,
            high=hot_close + 1000,
            low=prev_close,
            close=hot_close,
            volume=200000,
            source="test",
        )
        db.add_all(candles)
        await db.flush()

        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result) == 0


class TestMinPriceFilter:
    """가격 1,000원 미만 제외."""

    async def test_low_price_excluded(self, db: AsyncSession) -> None:
        """종가 < 1000 → 제외."""
        symbol = "000060"
        db.add(_make_stock(symbol, "저가주"))

        candles = _passing_candles(symbol, _TRADE_DATE, close=800, volume=5000000)
        db.add_all(candles)
        await db.flush()

        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result) == 0


class TestScoring:
    """점수 계산 및 정렬."""

    async def test_score_and_sort(self, db: AsyncSession) -> None:
        """통과 종목이 score 내림차순으로 저장된다."""
        symbols = ["100010", "100020", "100030"]
        for sym in symbols:
            db.add(_make_stock(sym, f"종목_{sym}"))

        # 종목 A: 거래대금 급증 → +15점 보너스
        candles_a = _passing_candles("100010", _TRADE_DATE, close=50000, volume=200000)
        # 기준일 거래량 대폭 증가
        candles_a[-1] = DailyCandle(
            symbol="100010",
            date=_TRADE_DATE,
            open=49800,
            high=50500,
            low=49500,
            close=50000,
            volume=800000,  # 거래대금 = 50000 * 800000 = 400억 (>> 평균 100억 * 1.2)
            source="test",
        )
        db.add_all(candles_a)

        # 종목 B: 기본 통과 (거래대금 보통)
        candles_b = _passing_candles("100020", _TRADE_DATE, close=50000, volume=200000)
        db.add_all(candles_b)

        # 종목 C: 기본 통과 + 5일 수익률 음수 → return_5d 보너스 없음
        candles_c = _passing_candles("100030", _TRADE_DATE, close=50000, volume=200000)
        # 5일 전 종가를 현재보다 높게 → 5일 수익률 음수
        candles_c[-6] = DailyCandle(
            symbol="100030",
            date=candles_c[-6].date,
            open=55000,
            high=56000,
            low=54000,
            close=55000,
            volume=200000,
            source="test",
        )
        db.add_all(candles_c)
        await db.flush()

        result = await run_short_swing_screening(db, _TRADE_DATE, universe_source=symbols)

        assert len(result) >= 2
        # 점수가 높은 순서로 정렬되었는지 확인
        scores = [c.score for c in result]
        assert scores == sorted(scores, reverse=True)
        # A(거래대금 급증 보너스)가 최상위
        assert result[0].symbol == "100010"


class TestIdempotency:
    """(trade_date, symbol) 중복 저장 방지."""

    async def test_rerun_replaces_candidates(self, db: AsyncSession) -> None:
        """같은 날짜 재실행 시 기존 후보를 교체한다."""
        symbol = "200010"
        db.add(_make_stock(symbol, "멱등테스트"))

        candles = _passing_candles(symbol, _TRADE_DATE, close=50000, volume=200000)
        db.add_all(candles)
        await db.flush()

        # 1차 실행
        result1 = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result1) == 1

        # 2차 실행 (같은 날짜)
        result2 = await run_short_swing_screening(db, _TRADE_DATE, universe_source=[symbol])
        assert len(result2) == 1

        # DB에 해당 날짜 1건만 존재
        stmt = select(ShortSwingCandidate).where(
            ShortSwingCandidate.trade_date == _TRADE_DATE,
            ShortSwingCandidate.symbol == symbol,
        )
        rows = (await db.execute(stmt)).scalars().all()
        assert len(rows) == 1
