"""CrossMomentumParams + 4개 함수 단위 테스트."""

from __future__ import annotations

import pytest

from src.broker.schemas import DailyPrice
from src.strategy.cross_momentum import (
    CrossMomentumParams,
    apply_trend_filter,
    apply_vol_filter,
    compute_momentum_score,
    select_portfolio,
)

# ── 테스트 픽스처 헬퍼 ─────────────────────────────────────────────────────────


def _daily(date: str, close: int, volume: int = 1000) -> DailyPrice:
    return DailyPrice(date=date, open=close, high=close, low=close, close=close, volume=volume)


def _make_trending_up(n: int, start_close: int = 10000, pct: float = 0.005) -> list[DailyPrice]:
    """매일 pct씩 상승하는 일봉 생성 (날짜: 20200101부터 n일)."""
    result: list[DailyPrice] = []
    price = start_close
    for i in range(n):
        year = 2020 + i // 365
        day_of_year = i % 365
        month = day_of_year // 30 + 1
        day = day_of_year % 30 + 1
        date = f"{year}{month:02d}{day:02d}"
        result.append(_daily(date, int(price)))
        price *= 1 + pct
    return result


def _make_flat(n: int, close: int = 10000) -> list[DailyPrice]:
    """종가 고정 일봉 생성."""
    result: list[DailyPrice] = []
    for i in range(n):
        year = 2020 + i // 365
        day_of_year = i % 365
        month = day_of_year // 30 + 1
        day = day_of_year % 30 + 1
        date = f"{year}{month:02d}{day:02d}"
        result.append(_daily(date, close))
    return result


# ── CrossMomentumParams ────────────────────────────────────────────────────────


class TestCrossMomentumParams:
    """파라미터 기본값 및 속성 검증."""

    def test_defaults(self) -> None:
        p = CrossMomentumParams()
        assert p.formation_months == 12
        assert p.skip_months == 1
        assert p.vol_window == 252
        assert p.vol_percentile == pytest.approx(50.0)
        assert p.trend_window == 200
        assert p.top_decile == pytest.approx(0.1)
        assert p.use_vol_filter is True
        assert p.use_trend_filter is True
        assert p.slippage_pct == pytest.approx(0.0015)
        assert p.commission_rate == pytest.approx(0.00015)
        assert p.tax_rate == pytest.approx(0.0023)

    def test_formation_days_property(self) -> None:
        """formation_days = formation_months × 21."""
        p = CrossMomentumParams(formation_months=12)
        assert p.formation_days == 252

    def test_skip_days_property(self) -> None:
        """skip_days = skip_months × 21."""
        p = CrossMomentumParams(skip_months=1)
        assert p.skip_days == 21

    def test_min_history_days(self) -> None:
        """min_history_days = formation + skip + 10."""
        p = CrossMomentumParams()
        assert p.min_history_days == 252 + 21 + 10

    def test_label_full_filters(self) -> None:
        p = CrossMomentumParams(top_decile=0.1, use_vol_filter=True, use_trend_filter=True)
        assert "10pct" in p.label()
        assert "vol" in p.label()
        assert "trend" in p.label()

    def test_label_no_filters(self) -> None:
        p = CrossMomentumParams(top_decile=0.2, use_vol_filter=False, use_trend_filter=False)
        assert "20pct" in p.label()
        assert "novol" in p.label()
        assert "notrend" in p.label()

    def test_to_dict_roundtrip(self) -> None:
        p = CrossMomentumParams(top_decile=0.2, use_vol_filter=False)
        d = p.to_dict()
        assert d["top_decile"] == pytest.approx(0.2)
        assert d["use_vol_filter"] is False
        assert d["formation_months"] == 12


# ── compute_momentum_score ─────────────────────────────────────────────────────


class TestComputeMomentumScore:
    """12-1 month momentum score 계산 검증."""

    def test_insufficient_data_returns_none(self) -> None:
        """데이터 부족 → None."""
        params = CrossMomentumParams()
        daily = _make_flat(n=params.formation_days)  # skip_days 분 부족
        result = compute_momentum_score(daily, params)
        assert result is None

    def test_exact_required_data_returns_score(self) -> None:
        """최소 필요 데이터 충족 → 유효한 점수."""
        params = CrossMomentumParams()
        required = params.formation_days + params.skip_days + 1
        daily = _make_flat(n=required, close=10000)
        # 평탄 → 수익률 0
        result = compute_momentum_score(daily, params)
        assert result == pytest.approx(0.0)

    def test_positive_trend_positive_score(self) -> None:
        """상승 추세 → 양수 점수."""
        params = CrossMomentumParams()
        n = params.formation_days + params.skip_days + 10
        daily = _make_trending_up(n=n, start_close=10000, pct=0.005)
        result = compute_momentum_score(daily, params)
        assert result is not None
        assert result > 0

    def test_known_values(self) -> None:
        """알려진 가격으로 정확한 점수 검증 (look-ahead 방지 포함)."""
        params = CrossMomentumParams(formation_months=1, skip_months=1)
        # formation_days=21, skip_days=21 → required=43
        # daily[0..20] = formation_start 구간, daily[21] = formation_end, daily[22..42] = skip 구간
        # score = daily[21].close / daily[0].close - 1
        n = params.formation_days + params.skip_days + 1  # 43
        daily = _make_flat(n=n, close=10000)
        # formation_start index = n - skip_days - 1 - formation_days = 43 - 22 - 21 = 0
        # formation_end index = n - skip_days - 1 = 43 - 22 = 21
        # score = daily[21].close / daily[0].close - 1 = 0
        result = compute_momentum_score(daily, params)
        assert result == pytest.approx(0.0)

    def test_skip_period_excluded_from_score(self) -> None:
        """skip 기간 가격 변동은 점수에 영향 없음 (look-ahead 방지 핵심)."""
        params = CrossMomentumParams(formation_months=1, skip_months=1)
        n = params.formation_days + params.skip_days + 1  # 43

        # 기준선: flat
        daily_flat = _make_flat(n=n, close=10000)
        score_flat = compute_momentum_score(daily_flat, params)

        # skip 기간(마지막 21개 바)만 가격을 2배로 변경해도 점수 불변
        daily_modified = list(daily_flat)
        for idx in range(n - params.skip_days, n):
            daily_modified[idx] = _daily(daily_flat[idx].date, close=20000)

        score_modified = compute_momentum_score(daily_modified, params)
        assert score_flat == pytest.approx(score_modified)  # type: ignore[arg-type]

    def test_zero_start_price_returns_none(self) -> None:
        """시작 가격 0 → None."""
        params = CrossMomentumParams(formation_months=1, skip_months=1)
        n = params.formation_days + params.skip_days + 1
        daily = _make_flat(n=n, close=10000)
        # formation_start 가격을 0으로 설정
        start_idx = n - params.skip_days - params.formation_days - 1
        daily[start_idx] = _daily(daily[start_idx].date, close=0)
        result = compute_momentum_score(daily, params)
        assert result is None


# ── apply_vol_filter ───────────────────────────────────────────────────────────


class TestApplyVolFilter:
    """변동성 하위 50% 필터 검증."""

    def _make_vol_universe(self) -> dict[str, list[DailyPrice]]:
        """변동성이 다른 두 종목 유니버스 생성.
        - low_vol: 미미한 변동
        - high_vol: 큰 변동
        """
        params = CrossMomentumParams()
        n = params.vol_window + 5

        # 저변동성: 가격 거의 불변
        low_vol = []
        for i in range(n):
            price = 10000 + (i % 2)  # 10000, 10001, 10000, ...
            low_vol.append(_daily(f"2022{i + 1:04d}", price))

        # 고변동성: 큰 폭 등락
        high_vol = []
        for i in range(n):
            price = 10000 + (1000 if i % 2 == 0 else -1000)
            high_vol.append(_daily(f"2022{i + 1:04d}", price))

        return {"low": low_vol, "high": high_vol}

    def test_low_vol_passes(self) -> None:
        """저변동성 종목은 하위 50% 필터 통과."""
        universe = self._make_vol_universe()
        params = CrossMomentumParams(vol_percentile=50.0)
        passing = apply_vol_filter(universe, params)
        assert "low" in passing

    def test_high_vol_filtered(self) -> None:
        """고변동성 종목은 하위 50% 필터에서 제거."""
        universe = self._make_vol_universe()
        params = CrossMomentumParams(vol_percentile=50.0)
        passing = apply_vol_filter(universe, params)
        assert "high" not in passing

    def test_insufficient_data_excluded(self) -> None:
        """데이터 부족 종목은 자동 제외."""
        params = CrossMomentumParams()
        universe = {"short": _make_flat(n=10, close=10000)}
        passing = apply_vol_filter(universe, params)
        # 데이터 부족 → 빈 집합
        assert "short" not in passing

    def test_empty_universe_returns_empty_set(self) -> None:
        """빈 유니버스 → 빈 집합."""
        params = CrossMomentumParams()
        passing = apply_vol_filter({}, params)
        assert passing == set()

    def test_all_same_vol_all_pass_at_100pct(self) -> None:
        """100% 기준 → 전체 통과."""
        params = CrossMomentumParams(vol_percentile=100.0)
        n = params.vol_window + 5
        universe = {
            "a": _make_flat(n, 10000),
            "b": _make_flat(n, 20000),
        }
        passing = apply_vol_filter(universe, params)
        assert "a" in passing
        assert "b" in passing


# ── apply_trend_filter ─────────────────────────────────────────────────────────


class TestApplyTrendFilter:
    """200일 이평 위 추세 필터 검증."""

    def test_uptrend_passes(self) -> None:
        """상승 추세 (현재가 > MA200) → 통과."""
        params = CrossMomentumParams(trend_window=5)  # 테스트용 단축 윈도우
        n = params.trend_window + 5
        # 전반부 낮은 가격 → MA 낮음, 후반부 높은 가격 → 현재가 > MA
        daily: list[DailyPrice] = []
        for i in range(n - 3):
            daily.append(_daily(f"2022{i + 1:04d}", 10000))
        for i in range(3):
            daily.append(_daily(f"2022{n - 3 + i:04d}", 20000))  # 현재가 높음

        passing = apply_trend_filter({"A": daily}, params)
        assert "A" in passing

    def test_downtrend_filtered(self) -> None:
        """하락 추세 (현재가 < MA200) → 제거."""
        params = CrossMomentumParams(trend_window=5)
        n = params.trend_window + 5
        # 전반부 높은 가격 → MA 높음, 후반부 낮은 가격 → 현재가 < MA
        daily: list[DailyPrice] = []
        for i in range(n - 3):
            daily.append(_daily(f"2022{i + 1:04d}", 20000))
        for i in range(3):
            daily.append(_daily(f"2022{n - 3 + i:04d}", 10000))  # 현재가 낮음

        passing = apply_trend_filter({"A": daily}, params)
        assert "A" not in passing

    def test_insufficient_data_excluded(self) -> None:
        """데이터 부족 → 제외."""
        params = CrossMomentumParams(trend_window=200)
        universe = {"short": _make_flat(n=10, close=10000)}
        passing = apply_trend_filter(universe, params)
        assert "short" not in passing

    def test_empty_universe_returns_empty_set(self) -> None:
        params = CrossMomentumParams()
        assert apply_trend_filter({}, params) == set()


# ── select_portfolio ───────────────────────────────────────────────────────────


class TestSelectPortfolio:
    """상위 데실 포트폴리오 선택 검증."""

    def test_top_10pct_of_10_symbols(self) -> None:
        """10종목 중 상위 10% → 1종목."""
        params = CrossMomentumParams(top_decile=0.1)
        symbols = [f"stock{i:02d}" for i in range(10)]
        scores = {s: float(i) for i, s in enumerate(symbols)}  # stock09 최고
        portfolio = select_portfolio(symbols, scores, params)
        assert len(portfolio) == 1
        assert portfolio[0] == "stock09"

    def test_top_20pct_of_10_symbols(self) -> None:
        """10종목 중 상위 20% → 2종목."""
        params = CrossMomentumParams(top_decile=0.2)
        symbols = [f"stock{i:02d}" for i in range(10)]
        scores = {s: float(i) for i, s in enumerate(symbols)}
        portfolio = select_portfolio(symbols, scores, params)
        assert len(portfolio) == 2
        assert portfolio[0] == "stock09"  # 최고 점수
        assert portfolio[1] == "stock08"

    def test_descending_order(self) -> None:
        """모멘텀 점수 내림차순 정렬."""
        params = CrossMomentumParams(top_decile=0.5)
        symbols = ["A", "B", "C", "D"]
        scores = {"A": 0.1, "B": 0.5, "C": 0.3, "D": 0.2}
        portfolio = select_portfolio(symbols, scores, params)
        assert portfolio[0] == "B"
        assert portfolio[1] == "C"

    def test_minimum_one_stock(self) -> None:
        """최소 1종목 보장 (top_decile × n < 1 일 때)."""
        params = CrossMomentumParams(top_decile=0.01)  # 1% → 1종목 미만
        symbols = ["A", "B"]
        scores = {"A": 0.5, "B": 0.3}
        portfolio = select_portfolio(symbols, scores, params)
        assert len(portfolio) >= 1

    def test_symbol_not_in_scores_excluded(self) -> None:
        """scores에 없는 종목은 제외."""
        params = CrossMomentumParams(top_decile=1.0)
        symbols = ["A", "B", "C"]
        scores = {"A": 0.5, "B": 0.3}  # C 없음
        portfolio = select_portfolio(symbols, scores, params)
        assert "C" not in portfolio

    def test_empty_candidates_returns_empty(self) -> None:
        """후보 없음 → 빈 리스트."""
        params = CrossMomentumParams()
        portfolio = select_portfolio([], {}, params)
        assert portfolio == []
