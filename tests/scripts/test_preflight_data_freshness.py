"""preflight_data_freshness CLI 단위 테스트 (PR A)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from scripts import preflight_data_freshness as pf


class TestResolveCutoff:
    """as_of 가 영업일/휴장일일 때 cutoff 결정 로직."""

    def test_business_day_returns_self(self) -> None:
        # 2026-06-16 (화) 영업일
        assert pf._resolve_cutoff(date(2026, 6, 16)) == date(2026, 6, 16)

    def test_saturday_falls_back_to_friday(self) -> None:
        # 2026-06-13 (토) → 2026-06-12 (금)
        assert pf._resolve_cutoff(date(2026, 6, 13)) == date(2026, 6, 12)


class TestFreshnessResultDecisions:
    """FreshnessResult 의 pass/fail 판정."""

    def _make(
        self,
        *,
        max_date: date | None,
        fresh: int,
        size: int,
        min_cov: float,
        cutoff: date = date(2026, 6, 16),
    ) -> pf.FreshnessResult:
        return pf.FreshnessResult(
            as_of=date(2026, 6, 16),
            cutoff=cutoff,
            max_date=max_date,
            universe_size=size,
            fresh_count=fresh,
            coverage=(fresh / size) if size else 0.0,
            min_coverage=min_cov,
        )

    def test_pass_when_fresh_and_coverage_met(self) -> None:
        r = self._make(max_date=date(2026, 6, 16), fresh=170, size=176, min_cov=0.85)
        assert r.passed is True

    def test_fail_when_max_date_stale(self) -> None:
        r = self._make(max_date=date(2026, 5, 8), fresh=0, size=176, min_cov=0.85)
        assert r.max_date_pass is False
        assert r.passed is False

    def test_fail_when_coverage_low(self) -> None:
        r = self._make(max_date=date(2026, 6, 16), fresh=50, size=176, min_cov=0.85)
        assert r.max_date_pass is True
        assert r.coverage_pass is False
        assert r.passed is False

    def test_fail_when_max_date_null(self) -> None:
        r = self._make(max_date=None, fresh=0, size=176, min_cov=0.85)
        assert r.passed is False


class TestMainExitCode:
    """main() 종료 코드: 0=PASS, 1=FAIL, 2=환경 오류."""

    def test_main_returns_zero_on_pass(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = pf.FreshnessResult(
            as_of=date(2026, 6, 16),
            cutoff=date(2026, 6, 16),
            max_date=date(2026, 6, 16),
            universe_size=176,
            fresh_count=170,
            coverage=170 / 176,
            min_coverage=0.85,
        )
        with (
            patch.object(pf, "_check_freshness", return_value=fake),
            patch(
                "src.strategy.cross_momentum_universe.get_universe",
                return_value=["005930"] * 176,
            ),
        ):
            code = pf.main(["--as-of", "2026-06-16", "--min-coverage", "0.85"])
        assert code == 0
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_main_returns_one_on_stale(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = pf.FreshnessResult(
            as_of=date(2026, 6, 16),
            cutoff=date(2026, 6, 16),
            max_date=date(2026, 5, 8),
            universe_size=176,
            fresh_count=0,
            coverage=0.0,
            min_coverage=0.85,
        )
        with (
            patch.object(pf, "_check_freshness", return_value=fake),
            patch(
                "src.strategy.cross_momentum_universe.get_universe",
                return_value=["005930"] * 176,
            ),
        ):
            code = pf.main(["--as-of", "2026-06-16"])
        assert code == 1
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "max_date stale" in out

    def test_main_returns_two_on_db_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch.object(pf, "_check_freshness", side_effect=RuntimeError("db down")),
            patch(
                "src.strategy.cross_momentum_universe.get_universe",
                return_value=["005930"] * 176,
            ),
        ):
            code = pf.main(["--as-of", "2026-06-16"])
        assert code == 2
        err = capsys.readouterr().err
        assert "DB 조회 실패" in err
