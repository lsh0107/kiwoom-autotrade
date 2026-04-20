"""MarketContext 브릿지 모듈 테스트."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from src.trading.market_context import MarketContext
from src.trading.market_regime import MarketRegime, detect_regime


class TestMarketContextDefaults:
    """초기화 및 기본값 테스트."""

    def test_default_vkospi(self) -> None:
        """초기화 직후 VKOSPI는 기본값 25.0을 반환한다."""
        ctx = MarketContext()
        assert ctx.get_vkospi() == 25.0

    def test_default_kospi_above_ma12(self) -> None:
        """초기화 직후 kospi_above_ma12는 기본값 True를 반환한다."""
        ctx = MarketContext()
        assert ctx.get_kospi_above_ma12() is True

    def test_is_cache_stale_initial(self) -> None:
        """갱신 전(미갱신 상태)에는 is_cache_stale()이 True를 반환한다."""
        ctx = MarketContext()
        assert ctx.is_cache_stale() is True

    def test_no_database_url(self) -> None:
        """database_url=None이면 DB 조회 없이 기본값만 반환한다."""
        ctx = MarketContext(database_url=None)
        assert ctx.get_vkospi() == MarketContext.DEFAULT_VKOSPI
        assert ctx.get_kospi_above_ma12() == MarketContext.DEFAULT_KOSPI_ABOVE_MA12


class TestMarketContextRefresh:
    """refresh() 동작 테스트."""

    async def test_refresh_no_database_url_does_nothing(self) -> None:
        """database_url이 없으면 refresh()는 캐시를 갱신하지 않는다."""
        ctx = MarketContext(database_url=None)
        await ctx.refresh()
        # DB URL 없으면 _last_refresh_monotonic이 0 그대로 → stale
        assert ctx.is_cache_stale() is True

    async def test_refresh_success_updates_vkospi(self) -> None:
        """DB 조회 성공 시 VKOSPI 값이 갱신된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        async def mock_fetch() -> None:
            ctx._vkospi = 32.5
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        assert ctx.get_vkospi() == pytest.approx(32.5)

    async def test_refresh_success_updates_kospi_above_ma12(self) -> None:
        """DB 조회 성공 시 kospi_above_ma12 값이 갱신된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        async def mock_fetch() -> None:
            ctx._kospi_above_ma12 = False
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        assert ctx.get_kospi_above_ma12() is False

    async def test_refresh_success_clears_stale(self) -> None:
        """DB 조회 성공 후 is_cache_stale()은 False를 반환한다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        async def mock_fetch() -> None:
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        assert ctx.is_cache_stale() is False

    async def test_refresh_failure_keeps_previous_values(self) -> None:
        """DB 조회 실패 시 이전 캐시 값(기본값)이 유지된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        with patch.object(
            ctx, "_fetch_from_db", new=AsyncMock(side_effect=Exception("DB 연결 오류"))
        ):
            await ctx.refresh()

        # 기본값 그대로 유지
        assert ctx.get_vkospi() == MarketContext.DEFAULT_VKOSPI
        assert ctx.get_kospi_above_ma12() == MarketContext.DEFAULT_KOSPI_ABOVE_MA12

    async def test_refresh_failure_keeps_stale(self) -> None:
        """DB 조회 실패 시 is_cache_stale()은 True를 유지한다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=Exception("타임아웃"))):
            await ctx.refresh()

        assert ctx.is_cache_stale() is True

    async def test_refresh_failure_after_success_keeps_cached_value(self) -> None:
        """갱신 성공 후 재갱신 실패 시 이전 캐시 값이 유지된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        # 1차: 성공 (VKOSPI=28.0)
        async def mock_fetch_success() -> None:
            ctx._vkospi = 28.0
            ctx._kospi_above_ma12 = True
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch_success)):
            await ctx.refresh()

        assert ctx.get_vkospi() == pytest.approx(28.0)

        # 2차: 실패
        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=Exception("연결 끊김"))):
            await ctx.refresh()

        # 2차 실패에도 1차 성공 값(28.0) 유지
        assert ctx.get_vkospi() == pytest.approx(28.0)


class TestMarketContextTTL:
    """TTL 캐시 만료 테스트."""

    def test_is_cache_stale_before_ttl(self) -> None:
        """TTL 이내에는 is_cache_stale()이 False를 반환한다."""
        ctx = MarketContext(ttl_seconds=3600)
        # 직접 갱신 시각 설정
        ctx._last_refresh_monotonic = time.monotonic()
        assert ctx.is_cache_stale() is False

    def test_is_cache_stale_after_ttl(self) -> None:
        """TTL 경과 후에는 is_cache_stale()이 True를 반환한다."""
        ctx = MarketContext(ttl_seconds=10)
        # TTL보다 훨씬 과거 시각으로 설정
        ctx._last_refresh_monotonic = time.monotonic() - 3600
        assert ctx.is_cache_stale() is True

    def test_custom_ttl_honored(self) -> None:
        """커스텀 TTL 값이 적용된다."""
        ctx = MarketContext(ttl_seconds=60)
        ctx._last_refresh_monotonic = time.monotonic() - 30  # 30초 경과 (TTL 60초 이내)
        assert ctx.is_cache_stale() is False

        ctx2 = MarketContext(ttl_seconds=20)
        ctx2._last_refresh_monotonic = time.monotonic() - 30  # 30초 경과 (TTL 20초 초과)
        assert ctx2.is_cache_stale() is True


class TestMarketContextDetectRegimeIntegration:
    """MarketContext + detect_regime 통합 시나리오 테스트."""

    async def test_crisis_regime_from_db(self) -> None:
        """DB에서 고공포(VKOSPI>30) + KOSPI 약세 조회 시 CRISIS 레짐 판단."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        async def mock_fetch() -> None:
            ctx._vkospi = 42.0
            ctx._kospi_above_ma12 = False
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        regime = detect_regime(
            vkospi=ctx.get_vkospi(),
            kospi_above_ma12=ctx.get_kospi_above_ma12(),
        )
        assert regime == MarketRegime.CRISIS

    async def test_aggressive_regime_from_db(self) -> None:
        """DB에서 저공포(VKOSPI<20) + KOSPI 강세 조회 시 AGGRESSIVE 레짐 판단."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        async def mock_fetch() -> None:
            ctx._vkospi = 15.0
            ctx._kospi_above_ma12 = True
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        regime = detect_regime(
            vkospi=ctx.get_vkospi(),
            kospi_above_ma12=ctx.get_kospi_above_ma12(),
        )
        assert regime == MarketRegime.AGGRESSIVE

    async def test_fallback_gives_neutral_regime(self) -> None:
        """DB 조회 실패(is_cache_stale=True) 시 기본값(VKOSPI=25, bull=True) → NEUTRAL 레짐."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=Exception("DB 오류"))):
            await ctx.refresh()

        # is_cache_stale=True → 기본값 사용
        assert ctx.is_cache_stale() is True
        regime = detect_regime(
            vkospi=ctx.get_vkospi(),
            kospi_above_ma12=ctx.get_kospi_above_ma12(),
        )
        assert regime == MarketRegime.NEUTRAL

    async def test_multiple_refreshes_update_regime(self) -> None:
        """여러 번 refresh() 시 최신 값으로 레짐이 갱신된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        # 1차: AGGRESSIVE 상태
        async def mock_fetch_1() -> None:
            ctx._vkospi = 15.0
            ctx._kospi_above_ma12 = True
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch_1)):
            await ctx.refresh()

        assert (
            detect_regime(ctx.get_vkospi(), ctx.get_kospi_above_ma12()) == MarketRegime.AGGRESSIVE
        )

        # 2차: CRISIS로 전환
        async def mock_fetch_2() -> None:
            ctx._vkospi = 38.0
            ctx._kospi_above_ma12 = False
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch_2)):
            await ctx.refresh()

        assert detect_regime(ctx.get_vkospi(), ctx.get_kospi_above_ma12()) == MarketRegime.CRISIS


class TestMarketContextFlowDefaults:
    """수급/테마 캐시 기본값 테스트."""

    def test_default_investor_flow_empty(self) -> None:
        """초기화 직후 investor_flow는 빈 딕셔너리."""
        ctx = MarketContext()
        assert ctx.get_investor_flow() == {}

    def test_default_stock_investor_flows_empty(self) -> None:
        """초기화 직후 stock_investor_flows는 빈 딕셔너리."""
        ctx = MarketContext()
        assert ctx.get_stock_investor_flows() == {}

    def test_default_theme_scores_empty(self) -> None:
        """초기화 직후 theme_scores는 빈 딕셔너리."""
        ctx = MarketContext()
        assert ctx.get_theme_scores() == {}

    def test_no_database_url_keeps_empty_defaults(self) -> None:
        """database_url=None이면 수급/테마 기본값(빈 딕셔너리) 유지."""
        ctx = MarketContext(database_url=None)
        assert ctx.get_investor_flow() == {}
        assert ctx.get_stock_investor_flows() == {}
        assert ctx.get_theme_scores() == {}


class TestMarketContextFlowRefresh:
    """수급/테마 refresh() 동작 테스트."""

    async def test_refresh_updates_investor_flow(self) -> None:
        """DB 조회 성공 시 investor_flow가 갱신된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")
        expected = {
            "foreign": 1_000_000_000,
            "institution": 500_000_000,
            "individual": -1_500_000_000,
        }

        async def mock_fetch() -> None:
            ctx._investor_flow = expected.copy()
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        assert ctx.get_investor_flow() == expected

    async def test_refresh_updates_stock_investor_flows(self) -> None:
        """DB 조회 성공 시 stock_investor_flows가 갱신된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")
        expected = {
            "005930": {"foreign": 300_000_000, "institution": 100_000_000},
            "000660": {"foreign": 200_000_000, "institution": 50_000_000},
        }

        async def mock_fetch() -> None:
            ctx._stock_investor_flows = expected.copy()
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        assert ctx.get_stock_investor_flows() == expected

    async def test_refresh_updates_theme_scores(self) -> None:
        """DB 조회 성공 시 theme_scores가 갱신된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")
        expected: dict[str, float] = {"반도체": 0.9, "AI": 0.8, "2차전지": 0.5}

        async def mock_fetch() -> None:
            ctx._theme_scores = expected.copy()
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        assert ctx.get_theme_scores() == expected

    async def test_refresh_failure_keeps_empty_defaults(self) -> None:
        """DB 조회 실패 시 수급/테마 기본값(빈 딕셔너리) 유지."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=Exception("DB 오류"))):
            await ctx.refresh()

        assert ctx.get_investor_flow() == {}
        assert ctx.get_stock_investor_flows() == {}
        assert ctx.get_theme_scores() == {}

    async def test_refresh_failure_after_success_keeps_cached_flow(self) -> None:
        """갱신 성공 후 재갱신 실패 시 수급 캐시 값 유지."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")
        prev_flow = {"foreign": 500_000_000, "institution": 200_000_000}

        # 1차: 성공
        async def mock_fetch_success() -> None:
            ctx._investor_flow = prev_flow.copy()
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch_success)):
            await ctx.refresh()

        assert ctx.get_investor_flow() == prev_flow

        # 2차: 실패 → 이전 값 유지
        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=Exception("연결 끊김"))):
            await ctx.refresh()

        assert ctx.get_investor_flow() == prev_flow

    async def test_apply_vkospi_none_value_keeps_default(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """VKOSPI 수집 실패 페이로드(value=None, available=False)는 기본값을 유지한다.

        live_20260420.log 121회 TypeError 재현 방지 (_apply_vkospi None 가드).
        """
        ctx = MarketContext()
        with caplog.at_level("WARNING"):
            ctx._apply_vkospi({"value": None, "available": False, "reason": "collect_failed"})

        assert ctx.get_vkospi() == MarketContext.DEFAULT_VKOSPI
        assert any("VKOSPI" in rec.message for rec in caplog.records)

    async def test_apply_vkospi_value_none_without_available(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """available 플래그 없이 value만 None인 경우도 방어한다."""
        ctx = MarketContext()
        ctx._vkospi = 30.0  # 이전 캐시 값
        with caplog.at_level("WARNING"):
            ctx._apply_vkospi({"value": None})

        # 이전 캐시 값 유지
        assert ctx.get_vkospi() == pytest.approx(30.0)

    async def test_apply_vkospi_normal_value(self) -> None:
        """정상 페이로드는 기존과 동일하게 캐스팅된다."""
        ctx = MarketContext()
        ctx._apply_vkospi({"value": 27.5, "change": 0.3})
        assert ctx.get_vkospi() == pytest.approx(27.5)

    async def test_apply_vkospi_non_dict_payload(self, caplog: pytest.LogCaptureFixture) -> None:
        """dict가 아닌 페이로드는 경고 후 무시."""
        ctx = MarketContext()
        with caplog.at_level("WARNING"):
            ctx._apply_vkospi("not a dict")
        assert ctx.get_vkospi() == MarketContext.DEFAULT_VKOSPI

    async def test_apply_kospi_regime_none_above_ma12_keeps_default(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """kospi_regime above_ma12=None 페이로드는 기본값을 유지한다."""
        ctx = MarketContext()
        with caplog.at_level("WARNING"):
            ctx._apply_kospi_regime({"above_ma12": None})

        assert ctx.get_kospi_above_ma12() == MarketContext.DEFAULT_KOSPI_ABOVE_MA12
        assert any("KOSPI" in rec.message for rec in caplog.records)

    async def test_apply_kospi_regime_missing_key(self, caplog: pytest.LogCaptureFixture) -> None:
        """kospi_regime에 above_ma12 키 자체가 없어도 기본값 유지."""
        ctx = MarketContext()
        with caplog.at_level("WARNING"):
            ctx._apply_kospi_regime({"kospi_close": 2500.0})

        assert ctx.get_kospi_above_ma12() == MarketContext.DEFAULT_KOSPI_ABOVE_MA12

    async def test_apply_kospi_regime_unavailable_keeps_default(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """kospi_regime available=False 페이로드는 기본값 유지."""
        ctx = MarketContext()
        with caplog.at_level("WARNING"):
            ctx._apply_kospi_regime({"above_ma12": None, "available": False, "reason": "no_data"})

        assert ctx.get_kospi_above_ma12() == MarketContext.DEFAULT_KOSPI_ABOVE_MA12

    async def test_apply_kospi_regime_normal_value(self) -> None:
        """정상 페이로드는 bool 캐스팅된다."""
        ctx = MarketContext()
        ctx._apply_kospi_regime({"above_ma12": False, "kospi_close": 2400.0, "ma12": 2500.0})
        assert ctx.get_kospi_above_ma12() is False

    async def test_apply_investor_flow_empty_dict_keeps_previous(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """investor_flow 빈 딕셔너리는 기존 캐시 유지."""
        ctx = MarketContext()
        prev = {"foreign": 1_000_000}
        ctx._investor_flow = prev.copy()

        with caplog.at_level("WARNING"):
            ctx._apply_investor_flow({})

        assert ctx.get_investor_flow() == prev

    async def test_apply_stock_investor_flows_empty_dict_keeps_previous(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """stock_investor_flows 빈 딕셔너리는 기존 캐시 유지."""
        ctx = MarketContext()
        prev = {"005930": {"foreign": 300_000_000}}
        ctx._stock_investor_flows = prev.copy()

        with caplog.at_level("WARNING"):
            ctx._apply_stock_investor_flows({})

        assert ctx.get_stock_investor_flows() == prev

    async def test_apply_stock_investor_flows_unavailable(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """stock_investor_flows available=False 페이로드는 기존 캐시 유지."""
        ctx = MarketContext()
        prev = {"005930": {"foreign": 300_000_000}}
        ctx._stock_investor_flows = prev.copy()

        with caplog.at_level("WARNING"):
            ctx._apply_stock_investor_flows({"available": False, "reason": "collect_failed"})

        # available=False는 체크에서 먼저 걸리므로 이전 값 유지
        assert ctx.get_stock_investor_flows() == prev

    async def test_apply_theme_scores_none_keeps_previous(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """theme_scores가 None이면 기존 캐시 유지."""
        ctx = MarketContext()
        prev = {"반도체": 0.8}
        ctx._theme_scores = prev.copy()

        with caplog.at_level("WARNING"):
            ctx._apply_theme_scores(None)

        assert ctx.get_theme_scores() == prev

    async def test_apply_theme_scores_non_dict_keeps_previous(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """theme_scores가 dict가 아니면 기존 캐시 유지."""
        ctx = MarketContext()
        prev = {"반도체": 0.8}
        ctx._theme_scores = prev.copy()

        with caplog.at_level("WARNING"):
            ctx._apply_theme_scores(["not", "a", "dict"])

        assert ctx.get_theme_scores() == prev

    async def test_refresh_updates_all_fields_together(self) -> None:
        """모든 캐시 필드(VKOSPI, KOSPI, 수급, 테마)가 함께 갱신된다."""
        ctx = MarketContext(database_url="postgresql+asyncpg://test/db")

        async def mock_fetch() -> None:
            ctx._vkospi = 22.0
            ctx._kospi_above_ma12 = True
            ctx._investor_flow = {"foreign": 1_000_000}
            ctx._stock_investor_flows = {"005930": {"foreign": 200_000_000}}
            ctx._theme_scores = {"반도체": 0.8}
            ctx._last_refresh_monotonic = time.monotonic()

        with patch.object(ctx, "_fetch_from_db", new=AsyncMock(side_effect=mock_fetch)):
            await ctx.refresh()

        assert ctx.get_vkospi() == pytest.approx(22.0)
        assert ctx.get_kospi_above_ma12() is True
        assert ctx.get_investor_flow()["foreign"] == 1_000_000
        assert ctx.get_stock_investor_flows()["005930"]["foreign"] == 200_000_000
        assert ctx.get_theme_scores()["반도체"] == pytest.approx(0.8)
        assert ctx.is_cache_stale() is False
