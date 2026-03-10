"""전략 모듈 테스트."""

import pytest
from src.backtest.strategy import (
    MomentumParams,
    Position,
    calc_trade_pnl,
    check_entry_signal,
    check_exit_signal,
    extract_time_from_bar,
)
from src.broker.schemas import MinutePrice


class TestMomentumParams:
    """MomentumParams 기본값 테스트."""

    def test_default_values(self) -> None:
        """기본 파라미터가 올바르게 설정되는지 확인."""
        params = MomentumParams()
        assert params.volume_ratio == 1.5
        assert params.stop_loss == -0.005
        assert params.take_profit == 0.010
        assert params.trailing_stop is False
        assert params.max_positions == 3
        assert params.high_52w_threshold == 0.80
        assert params.force_close_time == "14:30"
        assert params.commission_rate == 0.00015
        assert params.tax_rate == 0.0018

    def test_custom_values(self) -> None:
        """커스텀 파라미터 설정."""
        params = MomentumParams(volume_ratio=2.0, stop_loss=-0.01)
        assert params.volume_ratio == 2.0
        assert params.stop_loss == -0.01


class TestCheckEntrySignal:
    """진입 신호 테스트."""

    def test_entry_signal_true(self) -> None:
        """진입 조건 충족 시 True."""
        params = MomentumParams()
        result = check_entry_signal(
            current_price=10000,
            high_52w=10000,
            current_volume=1500,
            avg_volume=1000,
            params=params,
        )
        assert result is True

    def test_entry_signal_price_below_threshold(self) -> None:
        """52주 신고가 대비 threshold 미만이면 False."""
        params = MomentumParams()
        result = check_entry_signal(
            current_price=7000,
            high_52w=10000,
            current_volume=1500,
            avg_volume=1000,
            params=params,
        )
        assert result is False

    def test_entry_signal_volume_insufficient(self) -> None:
        """거래량 부족 시 False."""
        params = MomentumParams()
        result = check_entry_signal(
            current_price=10000,
            high_52w=10000,
            current_volume=1000,
            avg_volume=1000,
            params=params,
        )
        assert result is False

    def test_entry_signal_zero_high(self) -> None:
        """52주 최고가가 0이면 False."""
        params = MomentumParams()
        assert check_entry_signal(10000, 0, 1500, 1000, params) is False

    def test_entry_signal_zero_avg_volume(self) -> None:
        """평균 거래량이 0이면 False."""
        params = MomentumParams()
        assert check_entry_signal(10000, 10000, 1500, 0, params) is False

    def test_entry_signal_at_threshold_boundary(self) -> None:
        """정확히 95% 경계에서 True."""
        params = MomentumParams(high_52w_threshold=0.95)
        result = check_entry_signal(
            current_price=9500,
            high_52w=10000,
            current_volume=1500,
            avg_volume=1000,
            params=params,
        )
        assert result is True

    def test_entry_signal_just_below_threshold(self) -> None:
        """95% 바로 아래에서 False."""
        params = MomentumParams(high_52w_threshold=0.95)
        result = check_entry_signal(
            current_price=9499,
            high_52w=10000,
            current_volume=1500,
            avg_volume=1000,
            params=params,
        )
        assert result is False


class TestCheckExitSignal:
    """청산 신호 테스트."""

    def test_stop_loss(self) -> None:
        """손절가 도달 시 stop_loss."""
        params = MomentumParams(stop_loss=-0.005)
        result = check_exit_signal(10000, 9940, "100000", params)
        assert result == "stop_loss"

    def test_take_profit(self) -> None:
        """익절가 도달 시 take_profit."""
        params = MomentumParams(take_profit=0.01)
        result = check_exit_signal(10000, 10110, "100000", params)
        assert result == "take_profit"

    def test_force_close(self) -> None:
        """강제 청산 시각 도달 시 force_close."""
        params = MomentumParams(force_close_time="14:30")
        result = check_exit_signal(10000, 10005, "143000", params)
        assert result == "force_close"

    def test_no_exit(self) -> None:
        """청산 조건 미충족 시 None."""
        params = MomentumParams()
        result = check_exit_signal(10000, 10005, "100000", params)
        assert result is None

    def test_zero_entry_price(self) -> None:
        """진입가가 0이면 None."""
        params = MomentumParams()
        assert check_exit_signal(0, 10000, "100000", params) is None

    def test_force_close_exactly_at_time(self) -> None:
        """정확히 14:30에 강제 청산."""
        params = MomentumParams(force_close_time="14:30")
        result = check_exit_signal(10000, 10005, "1430", params)
        assert result == "force_close"

    def test_stop_loss_priority_over_force_close(self) -> None:
        """손절과 강제 청산이 동시에 발생하면 손절 우선."""
        params = MomentumParams(stop_loss=-0.005, force_close_time="14:30")
        result = check_exit_signal(10000, 9940, "143000", params)
        assert result == "stop_loss"


class TestCalcTradePnl:
    """거래 손익률 계산 테스트."""

    def test_positive_pnl(self) -> None:
        """수익 거래 손익률 계산."""
        params = MomentumParams()
        pnl = calc_trade_pnl(10000, 10100, params)
        # 1% 수익 - 0.21% 비용 = 약 0.79%
        assert pnl == pytest.approx(0.01 - 0.00015 * 2 - 0.0018, abs=1e-6)

    def test_negative_pnl(self) -> None:
        """손실 거래 손익률 계산."""
        params = MomentumParams()
        pnl = calc_trade_pnl(10000, 9950, params)
        expected = -0.005 - 0.00015 * 2 - 0.0018
        assert pnl == pytest.approx(expected, abs=1e-6)

    def test_zero_entry_price(self) -> None:
        """진입가 0이면 0.0 반환."""
        params = MomentumParams()
        assert calc_trade_pnl(0, 10000, params) == 0.0

    def test_break_even_still_has_cost(self) -> None:
        """동일 가격이어도 거래비용만큼 손실."""
        params = MomentumParams()
        pnl = calc_trade_pnl(10000, 10000, params)
        expected_cost = -(0.00015 * 2 + 0.0018)
        assert pnl == pytest.approx(expected_cost, abs=1e-6)


class TestExtractTimeFromBar:
    """시간 추출 테스트."""

    def test_full_datetime(self) -> None:
        """YYYYMMDDHHMMSS에서 HHMMSS 추출."""
        bar = MinutePrice(
            datetime="20250101093000",
            open=100,
            high=110,
            low=90,
            close=105,
            volume=1000,
        )
        assert extract_time_from_bar(bar) == "093000"

    def test_time_only(self) -> None:
        """HHMMSS 형식은 그대로."""
        bar = MinutePrice(
            datetime="093000",
            open=100,
            high=110,
            low=90,
            close=105,
            volume=1000,
        )
        assert extract_time_from_bar(bar) == "093000"


class TestCheckExitSignalEdgeCases:
    """청산 신호 엣지케이스 테스트."""

    def test_exact_stop_loss_boundary(self) -> None:
        """정확히 -0.5% 경계에서 손절 발동."""
        params = MomentumParams(stop_loss=-0.005)
        # 10000 → 9950 = -0.5% 정확히
        result = check_exit_signal(10000, 9950, "100000", params)
        assert result == "stop_loss"

    def test_just_above_stop_loss(self) -> None:
        """손절가 바로 위에서는 청산 안 됨."""
        params = MomentumParams(stop_loss=-0.005)
        # 10000 → 9951 = -0.49%
        result = check_exit_signal(10000, 9951, "100000", params)
        assert result is None

    def test_take_profit_priority_over_force_close(self) -> None:
        """익절과 강제 청산 동시 발생 시 익절 우선."""
        params = MomentumParams(take_profit=0.01, force_close_time="14:30")
        # 10000 → 10110 (1.1% > 1%) + 시각 14:30
        result = check_exit_signal(10000, 10110, "143000", params)
        assert result == "take_profit"

    def test_negative_entry_price(self) -> None:
        """진입가 음수면 None."""
        params = MomentumParams()
        assert check_exit_signal(-100, 10000, "100000", params) is None


class TestExtractTimeEdgeCases:
    """시간 추출 엣지케이스 테스트."""

    def test_intermediate_length(self) -> None:
        """14자리도 6자리도 아닌 경우 그대로 반환."""
        bar = MinutePrice(
            datetime="0930",
            open=100,
            high=110,
            low=90,
            close=105,
            volume=1000,
        )
        assert extract_time_from_bar(bar) == "0930"


class TestPosition:
    """Position 데이터클래스 테스트."""

    def test_create_position(self) -> None:
        """포지션 생성."""
        pos = Position(symbol="005930", entry_time="20250101093000", entry_price=70000)
        assert pos.symbol == "005930"
        assert pos.entry_time == "20250101093000"
        assert pos.entry_price == 70000
