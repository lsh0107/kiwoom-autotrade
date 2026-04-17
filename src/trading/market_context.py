"""시장 컨텍스트 브릿지 모듈.

Airflow가 수집한 market_data / llm_briefings 테이블에서 최신 데이터를
live_trader가 읽어 장중 레짐 및 수급/테마 판단에 활용하는 브릿지 역할을 한다.

캐시:
    TTL 기반(기본 30분). 만료 시 DB 재조회, 실패 시 이전 캐시 값 유지.

폴백:
    database_url 없거나 DB 조회 실패 시 기본값(VKOSPI=25.0, kospi_above_ma12=True,
    investor_flow={}, stock_investor_flows={}, theme_scores={})
    또는 직전 캐시 값을 유지한다. 이때 is_cache_stale()은 True를 반환하여
    호출자가 환경변수 폴백을 감지할 수 있다.

데이터 형식 (Airflow 수집 기준):
    category="vkospi"             → data={"value": float, "change": float, ...}
    category="kospi_regime"       → data={"kospi_close": float, "ma12": float, "above_ma12": bool}
    category="investor_trading"    → {"foreign": float, "institution": float, "individual": float}
    category="stock_investor_flow" → {"005930": {"foreign": float, "institution": float}, ...}
    llm_briefings 테이블          → theme_scores={"반도체": 0.8, "AI": 0.9, ...}
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

# market_data 카테고리 상수
_CATEGORY_VKOSPI = "vkospi"
_CATEGORY_KOSPI_REGIME = "kospi_regime"
_CATEGORY_INVESTOR_TRADING = "investor_trading"
_CATEGORY_STOCK_INVESTOR_FLOW = "stock_investor_flow"


class MarketContext:
    """시장 데이터 캐시 — Airflow DB → live_trader 브릿지.

    Airflow 수집 market_data / llm_briefings 테이블에서 VKOSPI, KOSPI 12이평,
    시장 수급, 종목별 수급, LLM 테마 점수를 읽어 레짐·시그널 판단에 필요한
    최신 값을 제공한다.

    TTL(기본 30분) 기반 캐싱으로 매 사이클마다 DB를 쿼리하지 않는다.
    DB 조회 실패 시 이전 캐시 값(또는 초기 기본값)을 유지하며 예외를 삼킨다.

    Attributes:
        DEFAULT_VKOSPI: DB 조회 전 또는 실패 시 사용할 VKOSPI 기본값 (25.0 = NEUTRAL 경계)
        DEFAULT_KOSPI_ABOVE_MA12: DB 조회 전 또는 실패 시 사용할 KOSPI 이평 위치 기본값 (True)
    """

    DEFAULT_VKOSPI: float = 25.0
    DEFAULT_KOSPI_ABOVE_MA12: bool = True

    def __init__(
        self,
        database_url: str | None = None,
        ttl_seconds: int = 1800,
    ) -> None:
        """MarketContext 초기화.

        Args:
            database_url: PostgreSQL asyncpg 접속 URL.
                None이면 DB 조회 없이 기본값만 반환한다.
            ttl_seconds: 캐시 유효시간 (초). 기본 1800초(30분).
        """
        self._database_url = database_url
        self._ttl_seconds = ttl_seconds
        self._vkospi: float = self.DEFAULT_VKOSPI
        self._kospi_above_ma12: bool = self.DEFAULT_KOSPI_ABOVE_MA12
        # 수급/테마 캐시 — 기본값 빈 딕셔너리
        self._investor_flow: dict = {}
        self._stock_investor_flows: dict = {}
        self._theme_scores: dict[str, float] = {}
        # 마지막 갱신 성공 시각 (monotonic clock). 0.0 = 미갱신.
        self._last_refresh_monotonic: float = 0.0

    # ── 조회 인터페이스 ────────────────────────────────────

    def get_vkospi(self) -> float:
        """캐시된 VKOSPI 값을 반환한다.

        Returns:
            최신 VKOSPI 값. DB 갱신 전이면 기본값 25.0.
        """
        return self._vkospi

    def get_kospi_above_ma12(self) -> bool:
        """KOSPI 현재가 > 12개월 이동평균 여부를 반환한다.

        Returns:
            True면 KOSPI 상승 추세(이평선 위), False면 하락 추세.
            DB 갱신 전이면 기본값 True.
        """
        return self._kospi_above_ma12

    def get_investor_flow(self) -> dict:
        """캐시된 시장 전체 수급 데이터를 반환한다.

        Returns:
            시장 수급 딕셔너리. 예: {"foreign": 1e9, "institution": 5e8, "individual": -1.5e9}.
            DB 갱신 전이면 빈 딕셔너리.
        """
        return self._investor_flow

    def get_stock_investor_flows(self) -> dict:
        """캐시된 종목별 수급 데이터를 반환한다.

        Returns:
            종목별 수급 딕셔너리. 예: {"005930": {"foreign": 3e8, "institution": 1e8}}.
            DB 갱신 전이면 빈 딕셔너리.
        """
        return self._stock_investor_flows

    def get_theme_scores(self) -> dict[str, float]:
        """캐시된 LLM 테마 점수를 반환한다.

        Returns:
            테마별 점수 딕셔너리. 예: {"반도체": 0.8, "AI": 0.9}.
            DB 갱신 전이면 빈 딕셔너리.
        """
        return self._theme_scores

    def is_cache_stale(self) -> bool:
        """캐시 만료 여부를 확인한다.

        TTL 경과 여부로 판단한다.
        최초 refresh 성공 전(미갱신 상태)은 항상 True를 반환하여
        호출자가 환경변수 폴백을 시도할 수 있게 한다.

        Returns:
            TTL 초과 또는 미갱신 상태이면 True.
        """
        return time.monotonic() - self._last_refresh_monotonic > self._ttl_seconds

    # ── 갱신 ──────────────────────────────────────────────

    async def refresh(self) -> None:
        """DB에서 최신 시장 데이터를 조회해 캐시를 갱신한다.

        DB 접근 실패 시 이전 캐시 값(또는 기본값)을 유지하며 예외를 삼킨다.
        갱신 성공 시 is_cache_stale()은 False를 반환한다.
        database_url이 없으면 아무것도 하지 않는다.
        """
        if not self._database_url:
            log.debug("MarketContext: database_url 없음 — 기본값 유지")
            return

        try:
            await self._fetch_from_db()
            log.info(
                "MarketContext 갱신 완료: VKOSPI=%.1f, KOSPI>12이평=%s, 테마수=%d",
                self._vkospi,
                self._kospi_above_ma12,
                len(self._theme_scores),
            )
        except Exception:
            log.warning("MarketContext DB 조회 실패 — 이전 캐시 값 유지", exc_info=True)

    # ── 내부 DB 조회 ──────────────────────────────────────

    async def _fetch_from_db(self) -> None:
        """market_data / llm_briefings 테이블에서 최신 레코드를 조회한다.

        ORM select를 사용하며, 각 카테고리별 최신 date 레코드 1건씩 조회한다.
        값이 없으면 기존 캐시 값을 유지한다.

        Raises:
            Exception: DB 연결 또는 쿼리 실패 시. 호출자(refresh)가 처리한다.
        """
        # lazy import: live_trader 외부(Airflow 스케줄러 등) 실행 시 무거운 패키지 지연 로드
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from src.models.llm_briefing import LLMBriefing
        from src.models.market_data import MarketData

        assert self._database_url is not None  # refresh()에서 None 체크 후 호출 보장
        engine = create_async_engine(self._database_url, pool_pre_ping=True)
        session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        try:
            async with session_factory() as session:
                # 최신 VKOSPI 조회 (날짜 내림차순 1건)
                vkospi_row: MarketData | None = await session.scalar(
                    select(MarketData)
                    .where(MarketData.category == _CATEGORY_VKOSPI)
                    .order_by(MarketData.date.desc())
                    .limit(1)
                )
                if vkospi_row is not None:
                    self._vkospi = float(vkospi_row.data["value"])

                # 최신 KOSPI 레짐 조회 (날짜 내림차순 1건)
                kospi_row: MarketData | None = await session.scalar(
                    select(MarketData)
                    .where(MarketData.category == _CATEGORY_KOSPI_REGIME)
                    .order_by(MarketData.date.desc())
                    .limit(1)
                )
                if kospi_row is not None:
                    self._kospi_above_ma12 = bool(kospi_row.data["above_ma12"])

                # 최신 시장 수급 조회 (날짜 내림차순 1건)
                investor_row: MarketData | None = await session.scalar(
                    select(MarketData)
                    .where(MarketData.category == _CATEGORY_INVESTOR_TRADING)
                    .order_by(MarketData.date.desc())
                    .limit(1)
                )
                if investor_row is not None:
                    self._investor_flow = dict(investor_row.data)

                # 최신 종목별 수급 조회 (날짜 내림차순 1건)
                stock_flow_row: MarketData | None = await session.scalar(
                    select(MarketData)
                    .where(MarketData.category == _CATEGORY_STOCK_INVESTOR_FLOW)
                    .order_by(MarketData.date.desc())
                    .limit(1)
                )
                if stock_flow_row is not None:
                    self._stock_investor_flows = dict(stock_flow_row.data)

                # 최신 LLM 테마 점수 조회 (날짜 내림차순 1건)
                llm_row: LLMBriefing | None = await session.scalar(
                    select(LLMBriefing).order_by(LLMBriefing.date.desc()).limit(1)
                )
                if llm_row is not None:
                    self._theme_scores = dict(llm_row.theme_scores)

            # 전체 조회 성공 시 마지막 갱신 시각 갱신
            self._last_refresh_monotonic = time.monotonic()
        finally:
            await engine.dispose()
