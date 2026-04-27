"""tests/backtest/test_walk_forward.py — Walk-forward 검증 모듈 단위 테스트."""

from __future__ import annotations

import json

from src.backtest.walk_forward import (
    WalkForwardSummary,
    create_walk_forward_windows,
    run_walk_forward,
)
from src.broker.schemas import DailyPrice
from src.strategy.momentum_daily import DailyMomentumParams

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def make_daily(i: int, price: int = 10_000) -> DailyPrice:
    """인덱스 i 기반 DailyPrice 생성 (날짜 고유 보장)."""
    year = 2023 + i // 250
    day_in_year = i % 250
    month = day_in_year // 21 + 1
    day = day_in_year % 21 + 1
    return DailyPrice(
        date=f"{year}{min(month, 12):02d}{min(day, 28):02d}",
        open=price,
        high=price + 100,
        low=price - 100,
        close=price,
        volume=1_000_000,
    )


def make_series(n: int, price: int = 10_000) -> list[DailyPrice]:
    return [make_daily(i, price) for i in range(n)]


# ── create_walk_forward_windows ───────────────────────────────────────────────


class TestCreateWalkForwardWindows:
    def test_basic_window_count(self) -> None:
        """충분한 데이터 → 최소 1개 이상 윈도우 생성."""
        windows = create_walk_forward_windows(n_bars=300, train_months=6, test_months=2)
        assert len(windows) >= 1

    def test_train_size_correct(self) -> None:
        """train 구간 크기 = 6 × 21 = 126."""
        windows = create_walk_forward_windows(n_bars=300, train_months=6, test_months=2)
        for w in windows:
            assert w.train_end - w.train_start == 6 * 21

    def test_oos_windows_non_overlapping(self) -> None:
        """OOS 구간은 서로 겹치지 않아야 함."""
        windows = create_walk_forward_windows(n_bars=500, train_months=6, test_months=2)
        for i in range(1, len(windows)):
            assert windows[i].test_start >= windows[i - 1].test_end

    def test_insufficient_data_returns_empty(self) -> None:
        """데이터 부족 → 빈 리스트."""
        windows = create_walk_forward_windows(n_bars=50, train_months=6, test_months=2)
        assert windows == []

    def test_window_ids_sequential(self) -> None:
        """window_id가 0부터 순차 증가."""
        windows = create_walk_forward_windows(n_bars=400, train_months=6, test_months=2)
        for i, w in enumerate(windows):
            assert w.window_id == i

    def test_test_end_within_bounds(self) -> None:
        """test_end가 n_bars 초과하지 않음."""
        n = 300
        windows = create_walk_forward_windows(n_bars=n, train_months=6, test_months=2)
        for w in windows:
            assert w.test_end <= n


# ── run_walk_forward ──────────────────────────────────────────────────────────


class TestRunWalkForward:
    def _params(self) -> DailyMomentumParams:
        return DailyMomentumParams(lookback=10, use_kospi_filter=False)

    def test_returns_walk_forward_summary(self) -> None:
        """WalkForwardSummary 반환 확인."""
        data = make_series(400)
        result = run_walk_forward("TEST", data, self._params())
        assert isinstance(result, WalkForwardSummary)
        assert result.symbol == "TEST"

    def test_insufficient_data_returns_empty_windows(self) -> None:
        """데이터 부족 → windows 비어있음."""
        data = make_series(50)
        result = run_walk_forward("TEST", data, self._params())
        assert result.windows == []

    def test_windows_populated(self) -> None:
        """충분한 데이터 → windows 1개 이상."""
        data = make_series(400)
        result = run_walk_forward("TEST", data, self._params())
        assert len(result.windows) >= 1

    def test_metrics_are_dicts(self) -> None:
        """각 윈도우의 in_sample_metrics, oos_metrics가 dict 타입."""
        data = make_series(400)
        result = run_walk_forward("TEST", data, self._params())
        for w in result.windows:
            assert isinstance(w.in_sample_metrics, dict)
            assert isinstance(w.oos_metrics, dict)

    def test_to_dict_json_serializable(self) -> None:
        """to_dict() 결과가 JSON 직렬화 가능."""
        data = make_series(400)
        result = run_walk_forward("TEST", data, self._params())
        d = result.to_dict()
        # 예외 없이 직렬화되어야 함
        json.dumps(d)

    def test_to_dict_keys(self) -> None:
        """to_dict() 필수 키 포함 확인."""
        data = make_series(400)
        result = run_walk_forward("TEST", data, self._params())
        d = result.to_dict()
        required = {
            "symbol",
            "avg_oos_sharpe",
            "avg_oos_win_rate",
            "avg_oos_mdd",
            "avg_sharpe_degradation",
            "params",
            "windows",
        }
        assert required.issubset(d.keys())

    def test_summary_metrics_are_floats(self) -> None:
        """요약 메트릭이 float 타입."""
        data = make_series(400)
        result = run_walk_forward("TEST", data, self._params())
        assert isinstance(result.avg_oos_sharpe, float)
        assert isinstance(result.avg_oos_win_rate, float)
        assert isinstance(result.avg_oos_mdd, float)
        assert isinstance(result.avg_sharpe_degradation, float)


# ── WalkForwardSummary 속성 ───────────────────────────────────────────────────


class TestWalkForwardSummaryProperties:
    def test_empty_windows_returns_zero_averages(self) -> None:
        """windows 없으면 평균 = 0.0."""
        params = DailyMomentumParams()
        summary = WalkForwardSummary(symbol="TEST", params=params)
        assert summary.avg_oos_sharpe == 0.0
        assert summary.avg_oos_win_rate == 0.0
        assert summary.avg_oos_mdd == 0.0
        assert summary.avg_sharpe_degradation == 0.0

    def test_sharpe_degradation_zero_when_is_sharpe_zero(self) -> None:
        """in_sample Sharpe = 0 → degradation = 0.0 (ZeroDivision 방지)."""
        from src.backtest.walk_forward import WalkForwardResult

        params = DailyMomentumParams()
        wf = WalkForwardResult(
            window_id=0,
            in_sample_metrics={"sharpe_ratio": 0.0},
            oos_metrics={"sharpe_ratio": 0.5},
            params=params,
        )
        assert wf.sharpe_degradation == 0.0

    def test_sharpe_degradation_computed(self) -> None:
        """OOS Sharpe / IS Sharpe 계산 확인."""
        from src.backtest.walk_forward import WalkForwardResult

        params = DailyMomentumParams()
        wf = WalkForwardResult(
            window_id=0,
            in_sample_metrics={"sharpe_ratio": 2.0},
            oos_metrics={"sharpe_ratio": 1.0},
            params=params,
        )
        assert abs(wf.sharpe_degradation - 0.5) < 1e-9
