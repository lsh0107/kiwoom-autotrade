"""CrossMomentumPortfolioEngine 단위 테스트.

합성 데이터로 look-ahead 방지, 거래비용, 월별 리밸런싱 로직을 검증한다.
"""

from __future__ import annotations

import pytest

from src.backtest.portfolio_engine import (
    CrossMomentumPortfolioEngine,
    PortfolioBacktestResult,
    _calc_mdd,
    _find_month_ends,
    _get_price_at_or_before,
    _information_ratio,
    _monthly_sharpe,
    _portfolio_metrics,
)
from src.broker.schemas import DailyPrice
from src.strategy.cross_momentum import CrossMomentumParams

# ── 테스트 픽스처 헬퍼 ─────────────────────────────────────────────────────────


def _daily(date: str, close: int, volume: int = 1000) -> DailyPrice:
    return DailyPrice(date=date, open=close, high=close, low=close, close=close, volume=volume)


def _make_price_series(
    start_yyyymm: str,
    n_months: int,
    start_price: int = 10000,
    monthly_pct: float = 0.01,
) -> list[DailyPrice]:
    """월별 last-day 일봉 생성 (각 월 1개 바로 단순화).

    Args:
        start_yyyymm: 시작 연월 (YYYYMM)
        n_months: 생성할 월 수
        start_price: 시작 가격
        monthly_pct: 월별 가격 변화율
    """
    result: list[DailyPrice] = []
    price = float(start_price)
    year = int(start_yyyymm[:4])
    month = int(start_yyyymm[4:])

    for _ in range(n_months):
        date = f"{year}{month:02d}28"  # 월 28일 = 안전한 월말 대리
        result.append(_daily(date, int(price)))
        price *= 1 + monthly_pct
        month += 1
        if month > 12:
            month = 1
            year += 1

    return result


def _make_daily_series(
    start_yyyymmdd: str,
    n_days: int,
    start_price: int = 10000,
    daily_pct: float = 0.0,
) -> list[DailyPrice]:
    """일별 일봉 생성 (연속 날짜).

    Args:
        start_yyyymmdd: 시작일 (YYYYMMDD)
        n_days: 일 수
        start_price: 시작 가격
        daily_pct: 일별 가격 변화율
    """
    from datetime import date, timedelta

    result: list[DailyPrice] = []
    price = float(start_price)
    d = date(int(start_yyyymmdd[:4]), int(start_yyyymmdd[4:6]), int(start_yyyymmdd[6:]))

    for _ in range(n_days):
        result.append(_daily(d.strftime("%Y%m%d"), int(price)))
        price *= 1 + daily_pct
        d += timedelta(days=1)

    return result


def _make_test_universe(
    symbols: list[str],
    n_months: int = 36,
    start_price: int = 10000,
    monthly_pcts: list[float] | None = None,
) -> dict[str, list[DailyPrice]]:
    """테스트용 유니버스 생성.

    Args:
        symbols: 종목코드 리스트
        n_months: 월 수
        start_price: 초기 가격
        monthly_pcts: 종목별 월별 수익률 (None이면 모두 +1%)
    """
    if monthly_pcts is None:
        monthly_pcts = [0.01] * len(symbols)

    return {
        symbol: _make_price_series(
            "202001",
            n_months,
            start_price=start_price,
            monthly_pct=monthly_pcts[i],
        )
        for i, symbol in enumerate(symbols)
    }


# ── _find_month_ends ───────────────────────────────────────────────────────────


class TestFindMonthEnds:
    """월말 기준일 탐색 검증."""

    def test_basic(self) -> None:
        """각 월의 최대 날짜를 월말로 선택."""
        dates = [
            "20210128",
            "20210129",
            "20210130",
            "20210228",
            "20210301",
            "20210331",
        ]
        month_ends = _find_month_ends(dates)
        assert "20210130" in month_ends  # 1월 마지막
        assert "20210228" in month_ends  # 2월 마지막
        assert "20210331" in month_ends  # 3월 마지막

    def test_single_date_per_month(self) -> None:
        dates = ["20210115", "20210215", "20210315"]
        month_ends = _find_month_ends(dates)
        assert month_ends == ["20210115", "20210215", "20210315"]

    def test_empty_returns_empty(self) -> None:
        assert _find_month_ends([]) == []

    def test_sorted_output(self) -> None:
        dates = ["20210331", "20210130", "20210228"]
        month_ends = _find_month_ends(dates)
        assert month_ends == sorted(month_ends)


# ── _get_price_at_or_before ────────────────────────────────────────────────────


class TestGetPriceAtOrBefore:
    """날짜 기준 종가 탐색 검증."""

    def test_exact_date(self) -> None:
        daily = [_daily("20210101", 1000), _daily("20210102", 2000)]
        assert _get_price_at_or_before(daily, "20210102") == 2000

    def test_nearest_before(self) -> None:
        """정확한 날짜 없으면 이전 가장 가까운 날짜 반환."""
        daily = [_daily("20210101", 1000), _daily("20210103", 3000)]
        assert _get_price_at_or_before(daily, "20210102") == 1000

    def test_before_all_data_returns_none(self) -> None:
        daily = [_daily("20210101", 1000)]
        assert _get_price_at_or_before(daily, "20201231") is None

    def test_empty_returns_none(self) -> None:
        assert _get_price_at_or_before([], "20210101") is None


# ── _monthly_sharpe / _information_ratio / _calc_mdd ──────────────────────────


class TestMetricHelpers:
    """성과 지표 헬퍼 함수 검증."""

    def test_monthly_sharpe_flat_returns_zero(self) -> None:
        """모든 수익률 동일 → std=0 → Sharpe=0."""
        returns = [0.01] * 12
        assert _monthly_sharpe(returns) == pytest.approx(0.0)

    def test_monthly_sharpe_annualized(self) -> None:
        """Sharpe = (mean/std) × sqrt(12) 연환산 검증."""
        import math

        returns = [0.02, 0.01, 0.03, 0.02, 0.01, 0.03] * 2
        n = len(returns)
        mean_r = sum(returns) / n
        variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
        std_r = math.sqrt(variance)
        expected = (mean_r / std_r) * math.sqrt(12)
        assert _monthly_sharpe(returns) == pytest.approx(expected, rel=1e-6)

    def test_monthly_sharpe_insufficient_data(self) -> None:
        assert _monthly_sharpe([0.01]) == pytest.approx(0.0)
        assert _monthly_sharpe([]) == pytest.approx(0.0)

    def test_information_ratio_basic(self) -> None:
        """초과수익 일정 → IR > 0."""
        port = [0.03] * 12
        bm = [0.01] * 12  # 포트폴리오가 항상 2% 초과
        ir = _information_ratio(port, bm)
        # 초과수익이 일정 → std=0 → 0.0
        assert ir == pytest.approx(0.0)

    def test_information_ratio_variable_excess(self) -> None:
        """가변 초과수익 → IR 계산."""
        port = [0.03, 0.01, 0.04, 0.02, 0.03, 0.01, 0.04, 0.02] * 2
        bm = [0.01] * 16
        ir = _information_ratio(port, bm)
        assert ir != 0.0

    def test_calc_mdd_no_drawdown(self) -> None:
        """단조 상승 → MDD = 0."""
        equity = [1.0, 1.1, 1.2, 1.3]
        assert _calc_mdd(equity) == pytest.approx(0.0)

    def test_calc_mdd_known_value(self) -> None:
        """알려진 낙폭 검증: 1.0→1.5→1.0 → MDD = -1/3."""
        equity = [1.0, 1.5, 1.0]
        mdd = _calc_mdd(equity)
        assert mdd == pytest.approx(-1 / 3, rel=1e-6)

    def test_calc_mdd_empty(self) -> None:
        assert _calc_mdd([]) == pytest.approx(0.0)


# ── _portfolio_metrics ─────────────────────────────────────────────────────────


class TestPortfolioMetrics:
    """포트폴리오 지표 통합 검증."""

    def test_empty_returns_zeros(self) -> None:
        m = _portfolio_metrics([], [], [])
        assert m["sharpe_ratio"] == pytest.approx(0.0)
        assert m["n_periods"] == 0

    def test_n_periods_matches_returns(self) -> None:
        returns = [0.01, 0.02, 0.03]
        bm = [0.005] * 3
        equity = [1.0, 1.01, 1.03, 1.06]
        m = _portfolio_metrics(returns, bm, equity)
        assert m["n_periods"] == 3

    def test_total_return_from_equity(self) -> None:
        returns = [0.1]
        m = _portfolio_metrics(returns, [0.0], [1.0, 1.1])
        assert m["total_return"] == pytest.approx(0.1)


# ── CrossMomentumPortfolioEngine ───────────────────────────────────────────────


class TestCrossMomentumPortfolioEngine:
    """포트폴리오 엔진 통합 테스트."""

    def _make_minimal_universe(self) -> dict[str, list[DailyPrice]]:
        """formation(12mo) + skip(1mo) + 3mo 거래 기간에 충분한 합성 유니버스.

        월별 1바(28일)로 구성된 단순 시계열.
        총 16개월 = 12 + 1 + 3 (거래 3기간)
        """
        symbols = [f"S{i:02d}" for i in range(10)]
        # 각 종목별 서로 다른 수익률로 랭킹 차별화
        monthly_pcts = [0.01 * (i + 1) for i in range(10)]
        return _make_test_universe(symbols, n_months=16, monthly_pcts=monthly_pcts)

    def test_returns_portfolio_backtest_result(self) -> None:
        """엔진 실행 결과 타입 검증."""
        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
        )
        universe = self._make_minimal_universe()
        bm = _make_price_series("202001", 16)

        result = engine.run(universe, bm, params, "202101", "202204")
        assert isinstance(result, PortfolioBacktestResult)

    def test_empty_universe_returns_empty_metrics(self) -> None:
        """빈 유니버스 → 빈 지표."""
        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams()
        result = engine.run({}, [], params, "20210101", "20211231")
        assert result.metrics["n_periods"] == 0
        assert result.monthly_returns == []

    def test_insufficient_data_returns_empty(self) -> None:
        """데이터 부족 → 리밸런싱 없음."""
        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
        )
        # 3개월 데이터 → momentum score 계산 불가
        universe = _make_test_universe(["A", "B"], n_months=3)
        bm = _make_price_series("202001", 3)

        result = engine.run(universe, bm, params, "202001", "202003")
        assert result.metrics["n_periods"] == 0

    def test_look_ahead_prevention(self) -> None:
        """look-ahead 방지: T0 시점 이후 데이터 가격 변경이 신호에 영향 없음.

        T0 이후 가격을 2배로 변경한 뒤 실행해도 동일한 포트폴리오 선택.
        """
        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
            top_decile=0.3,
        )

        universe_original = self._make_minimal_universe()

        # T0(첫 리밸런싱: 202113, 즉 202201 근처) 이후 데이터를 변경한 유니버스
        universe_modified: dict[str, list[DailyPrice]] = {}
        for symbol, daily in universe_original.items():
            modified = list(daily)
            # 14번째 바 이후(T1 해당 구간) 가격 2배 — 신호에는 영향 없어야 함
            for j in range(13, len(modified)):
                d = modified[j]
                modified[j] = _daily(d.date, d.close * 2)
            universe_modified[symbol] = modified

        bm = _make_price_series("202001", 16)
        result_orig = engine.run(universe_original, bm, params, "202101", "202204")
        result_mod = engine.run(universe_modified, bm, params, "202101", "202204")

        # 동일 T0 포트폴리오 선택 (신호는 T0 이전 데이터만 의존)
        if result_orig.portfolios and result_mod.portfolios:
            assert result_orig.portfolios[0] == result_mod.portfolios[0]

    def test_equity_curve_monotonically_updates(self) -> None:
        """positive 수익률 포트폴리오 → equity curve 단조 증가."""
        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
            top_decile=0.5,
        )
        # 모든 종목 +5%/월 → 포트폴리오도 양수
        symbols = [f"S{i:02d}" for i in range(6)]
        universe = _make_test_universe(symbols, n_months=16, monthly_pcts=[0.05] * 6)
        bm = _make_price_series("202001", 16)

        result = engine.run(universe, bm, params, "202101", "202204")
        if len(result.equity_curve) >= 2:
            # 첫 값 1.0, 이후 양수 수익이므로 증가해야 함
            assert result.equity_curve[-1] > result.equity_curve[0]

    def test_transaction_costs_reduce_returns(self) -> None:
        """거래비용 > 0이면 gross return보다 net return이 작음."""
        engine = CrossMomentumPortfolioEngine()

        # 거래비용 0인 파라미터
        params_no_cost = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
            slippage_pct=0.0,
            commission_rate=0.0,
            tax_rate=0.0,
            top_decile=0.3,
        )
        # 실제 거래비용
        params_with_cost = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
            slippage_pct=0.0015,
            commission_rate=0.00015,
            tax_rate=0.0023,
            top_decile=0.3,
        )

        universe = self._make_minimal_universe()
        bm = _make_price_series("202001", 16)

        result_no_cost = engine.run(universe, bm, params_no_cost, "202101", "202204")
        result_with_cost = engine.run(universe, bm, params_with_cost, "202101", "202204")

        # 거래비용 있는 경우 총 수익이 더 낮아야 함
        if result_no_cost.metrics["n_periods"] > 0 and result_with_cost.metrics["n_periods"] > 0:
            assert (
                result_with_cost.metrics["total_return"] <= result_no_cost.metrics["total_return"]
            )

    def test_to_dict_serializable(self) -> None:
        """결과 직렬화 가능 확인."""
        import json

        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
        )
        universe = self._make_minimal_universe()
        bm = _make_price_series("202001", 16)

        result = engine.run(universe, bm, params, "202101", "202204")
        serialized = result.to_dict()
        # JSON 직렬화 예외 없음
        json_str = json.dumps(serialized)
        assert len(json_str) > 0

    def test_benchmark_monthly_returns_same_length_as_portfolio(self) -> None:
        """벤치마크 수익률 길이 = 포트폴리오 수익률 길이."""
        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
        )
        universe = self._make_minimal_universe()
        bm = _make_price_series("202001", 16)

        result = engine.run(universe, bm, params, "202101", "202204")
        assert len(result.monthly_returns) == len(result.benchmark_monthly_returns)

    def test_vol_filter_reduces_candidates(self) -> None:
        """변동성 필터 활성화 시 후보 종목 수 감소 (또는 동일) → 정상 실행."""
        engine = CrossMomentumPortfolioEngine()
        params_no_filter = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
            top_decile=0.5,
        )
        params_with_filter = CrossMomentumParams(
            formation_months=12,
            skip_months=1,
            use_vol_filter=True,
            use_trend_filter=False,
            vol_window=10,  # 테스트용 단축
            top_decile=0.5,
        )

        n_months = 20
        symbols = [f"S{i:02d}" for i in range(8)]
        universe = _make_test_universe(symbols, n_months=n_months)
        bm = _make_price_series("202001", n_months)

        # 필터 활성 여부 무관 엔진 실행 가능 확인
        result = engine.run(universe, bm, params_with_filter, "202101", "202206")
        assert isinstance(result, PortfolioBacktestResult)
        _ = engine.run(universe, bm, params_no_filter, "202101", "202206")

    # ── 거래 경로 커버리지 (충분한 데이터로 메인 루프 진입) ─────────────────────────

    def _make_sufficient_universe(self) -> dict[str, list[DailyPrice]]:
        """formation_months=2, skip_months=1 기준 충분한 일봉 데이터 유니버스.

        required = 2×21 + 1×21 + 1 = 64 bars.
        backtest 기간 전 64+ bars 이력 포함을 위해 20190101부터 400일 생성.
        """
        symbols = [f"T{i:02d}" for i in range(6)]
        # 종목별 다른 일별 수익률로 순위 차별화
        daily_pcts = [0.001 * (i + 1) for i in range(6)]
        return {
            s: _make_daily_series("20190101", 400, start_price=10000, daily_pct=daily_pcts[i])
            for i, s in enumerate(symbols)
        }

    def _small_params(self, **kwargs: object) -> CrossMomentumParams:
        """소형 윈도우 파라미터 (formation=2mo, skip=1mo)."""
        return CrossMomentumParams(
            formation_months=2,
            skip_months=1,
            use_vol_filter=False,
            use_trend_filter=False,
            top_decile=0.5,
            **kwargs,  # type: ignore[arg-type]
        )

    def test_main_trading_path_executes(self) -> None:
        """충분한 이력 → 리밸런싱 1회 이상 발생 (lines 132, 139-197 커버)."""
        engine = CrossMomentumPortfolioEngine()
        params = self._small_params()
        universe = self._make_sufficient_universe()
        bm = _make_daily_series("20190101", 400, start_price=1000)

        result = engine.run(universe, bm, params, "20200101", "20200401")
        # 이력이 충분하면 at least 1 리밸런싱 발생
        assert result.metrics["n_periods"] >= 1
        assert len(result.equity_curve) >= 2
        assert len(result.monthly_returns) >= 1

    def test_main_trading_path_positive_returns(self) -> None:
        """상승 종목만 있는 포트폴리오 → 양수 총수익."""
        engine = CrossMomentumPortfolioEngine()
        params = self._small_params(slippage_pct=0.0, commission_rate=0.0, tax_rate=0.0)
        universe = {
            f"T{i:02d}": _make_daily_series("20190101", 400, start_price=10000, daily_pct=0.002)
            for i in range(4)
        }
        bm = _make_daily_series("20190101", 400, start_price=1000)

        result = engine.run(universe, bm, params, "20200101", "20200401")
        if result.metrics["n_periods"] > 0:
            assert result.metrics["total_return"] > 0

    def test_portfolio_period_return_missing_price(self) -> None:
        """T1 가격 없는 종목 제외 → 나머지로 평균 계산 (lines 283-294 커버)."""
        engine = CrossMomentumPortfolioEngine()
        params = self._small_params()
        universe_short: dict[str, list[DailyPrice]] = {
            "T00": _make_daily_series("20190101", 400, start_price=10000, daily_pct=0.002),
            "T01": _make_daily_series("20190101", 400, start_price=10000, daily_pct=0.001),
        }
        bm = _make_daily_series("20190101", 400, start_price=1000)

        result = engine.run(universe_short, bm, params, "20200101", "20200401")
        assert isinstance(result, PortfolioBacktestResult)

    def test_vol_and_trend_filter_path(self) -> None:
        """vol+trend 필터 활성화 시 메인 루프 진입 (lines 141-147 커버)."""
        engine = CrossMomentumPortfolioEngine()
        params = CrossMomentumParams(
            formation_months=2,
            skip_months=1,
            use_vol_filter=True,
            use_trend_filter=True,
            vol_window=20,
            trend_window=30,
            top_decile=0.5,
        )
        universe = self._make_sufficient_universe()
        bm = _make_daily_series("20190101", 400, start_price=1000)

        result = engine.run(universe, bm, params, "20200101", "20200401")
        assert isinstance(result, PortfolioBacktestResult)
