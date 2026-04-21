"""일봉 캐시 조회 모듈.

Design 011 PR 3. daily_candles 테이블에서 종목별 일봉을 조회해
live_trader/screen_symbols의 52주 고가·평균거래량 계산 비용을 제거한다.

동작 모드:
    use_db=False (기본): 항상 키움 API 폴백. 기존 동작 유지.
    use_db=True: DB 우선 조회 → 데이터 부족(< 20 bars) 시 키움 API 폴백.

Feature flag:
    USE_DB_DAILY_CANDLES 환경변수 (기본 false).

캐시:
    프로세스 내 dict 캐시. (symbol, lookback_days) 기준.
    flush_cache()로 수동 무효화 가능.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_MIN_BARS_THRESHOLD = 20


def _env_truthy(value: str | None) -> bool:
    """환경변수 문자열을 bool 해석."""
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


class DailyCandleStore:
    """일봉 DB 우선 조회 + 키움 API 폴백.

    MarketContext와 유사한 lazy DB 접근 패턴. 조회 결과는 프로세스 캐시에
    저장되어 같은 사이클 내 재호출 비용을 없앤다.

    Attributes:
        use_db: DB 우선 조회 활성화 여부. False면 항상 키움 API 폴백.
    """

    def __init__(
        self,
        database_url: str | None = None,
        *,
        use_db: bool | None = None,
    ) -> None:
        """DailyCandleStore 초기화.

        Args:
            database_url: PostgreSQL asyncpg 접속 URL. None이면 항상 폴백.
            use_db: 명시적 DB 사용 스위치. None이면 `USE_DB_DAILY_CANDLES`
                환경변수(기본 false) 읽음.
        """
        self._database_url = database_url
        if use_db is None:
            use_db = _env_truthy(os.environ.get("USE_DB_DAILY_CANDLES"))
        self.use_db: bool = bool(use_db) and database_url is not None
        self._cache: dict[tuple[str, int], list[Any]] = {}

    def flush_cache(self) -> None:
        """프로세스 내 캐시 초기화."""
        self._cache.clear()

    # ── 내부 DB 조회 ──────────────────────────────────────

    async def _fetch_from_db(
        self,
        symbol: str,
        lookback_days: int,
    ) -> list[Any]:
        """daily_candles에서 날짜 내림차순 → 오름차순 정렬 반환."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from src.broker.schemas import DailyPrice
        from src.models.daily_candle import DailyCandle

        assert self._database_url is not None
        engine = create_async_engine(self._database_url, pool_pre_ping=True)
        session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        from_date = datetime.now(tz=UTC).date() - timedelta(days=lookback_days)
        try:
            async with session_factory() as session:
                rows = (
                    (
                        await session.execute(
                            select(DailyCandle)
                            .where(
                                DailyCandle.symbol == symbol,
                                DailyCandle.date >= from_date,
                            )
                            .order_by(DailyCandle.date.asc())
                        )
                    )
                    .scalars()
                    .all()
                )

            bars: list[Any] = [
                DailyPrice(
                    date=r.date.strftime("%Y%m%d"),
                    open=int(r.open),
                    high=int(r.high),
                    low=int(r.low),
                    close=int(r.close),
                    volume=int(r.volume),
                )
                for r in rows
            ]
            return bars
        finally:
            await engine.dispose()

    # ── 공용 조회 API ─────────────────────────────────────

    async def get_daily_prices(
        self,
        symbol: str,
        *,
        lookback_days: int = 260,
        kiwoom_client: Any = None,
    ) -> list[Any]:
        """종목의 최근 N일치 일봉 반환.

        Args:
            symbol: 6자리 종목 코드.
            lookback_days: 오늘 기준 과거 일수 (기본 260 = 약 52주 거래일).
            kiwoom_client: 키움 fallback 용 KiwoomClient. None이면 폴백 불가.

        Returns:
            DailyPrice 리스트 (날짜 오름차순). 조회 실패 시 빈 리스트.
        """
        cache_key = (symbol, lookback_days)
        if cache_key in self._cache:
            return self._cache[cache_key]

        bars: list[Any] = []
        if self.use_db:
            try:
                bars = await self._fetch_from_db(symbol, lookback_days)
            except Exception as exc:
                log.warning("[%s] daily_candles 조회 실패 → 폴백: %s", symbol, exc)
                bars = []

            if len(bars) >= _MIN_BARS_THRESHOLD:
                self._cache[cache_key] = bars
                return bars
            log.info(
                "[%s] DB 일봉 %d개(임계 %d 미만) → 키움 폴백",
                symbol,
                len(bars),
                _MIN_BARS_THRESHOLD,
            )

        # 폴백 경로: 키움 API (use_db=False 또는 DB 데이터 부족)
        if kiwoom_client is not None:
            bars = await self._fetch_from_kiwoom(kiwoom_client, symbol)
        self._cache[cache_key] = bars
        return bars

    async def _fetch_from_kiwoom(
        self,
        client: Any,
        symbol: str,
    ) -> list[Any]:
        """키움 ka10086 페이징 폴백.

        live_trader.load_daily_context 로직의 단일 종목 버전.
        """
        import asyncio

        from src.broker.constants import API_IDS, DEFAULT_EXCHANGE, ENDPOINTS
        from src.broker.schemas import DailyPrice, to_kiwoom_symbol

        stk_cd = to_kiwoom_symbol(symbol, DEFAULT_EXCHANGE)
        qry_dt = datetime.now(tz=UTC).strftime("%Y%m%d")

        all_raw: list[dict] = []
        for _page in range(13):
            try:
                data = await client._request(
                    ENDPOINTS["market"],
                    API_IDS["daily_price"],
                    json_body={"stk_cd": stk_cd, "qry_dt": qry_dt, "indc_tp": "0"},
                )
            except Exception as exc:
                log.warning("[%s] 키움 폴백 에러: %s", symbol, exc)
                break
            items = data.get("daly_stkpc", [])
            if not items:
                break
            all_raw.extend(items)
            last_date = items[-1].get("date", "")
            if not last_date:
                break
            qry_dt = last_date
            await asyncio.sleep(0.5)

        bars: list[Any] = []
        for r in all_raw:
            try:
                bars.append(
                    DailyPrice(
                        date=r.get("date", ""),
                        open=_safe_int(r.get("open_pric", 0)),
                        high=_safe_int(r.get("high_pric", 0)),
                        low=_safe_int(r.get("low_pric", 0)),
                        close=_safe_int(r.get("close_pric", r.get("cur_prc", 0))),
                        volume=_safe_int(r.get("trde_qty", 0)),
                    )
                )
            except (ValueError, TypeError):
                continue
        bars.sort(key=lambda x: x.date)
        return bars

    async def get_daily_context(
        self,
        symbols: list[str],
        *,
        kiwoom_client: Any = None,
        lookback_days: int = 260,
    ) -> tuple[dict[str, list[Any]], dict[str, dict]]:
        """여러 종목의 일봉/컨텍스트 일괄 반환.

        live_trader.load_daily_context와 동일한 반환 타입.

        Returns:
            (daily_prices, daily_context)
            - daily_prices: {symbol: list[DailyPrice]}
            - daily_context: {symbol: {"high_52w": int, "avg_volume": int}}
        """
        daily_prices: dict[str, list[Any]] = {}
        daily_context: dict[str, dict] = {}

        for symbol in symbols:
            bars = await self.get_daily_prices(
                symbol,
                lookback_days=lookback_days,
                kiwoom_client=kiwoom_client,
            )
            if not bars:
                log.warning("[%s] 일봉 없음 — 스킵", symbol)
                continue
            daily_prices[symbol] = bars
            high_52w = max(b.high for b in bars)
            recent = bars[-20:] if len(bars) >= 20 else bars
            avg_volume = sum(b.volume for b in recent) // len(recent) if recent else 0
            daily_context[symbol] = {"high_52w": high_52w, "avg_volume": avg_volume}

        return daily_prices, daily_context


def _safe_int(value: Any) -> int:
    """문자열/숫자를 안전하게 int로 변환 (음수 부호 허용)."""
    if value is None:
        return 0
    s = str(value).strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0
