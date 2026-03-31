"""슬리피지 모델 테스트."""

from src.backtest.slippage import apply_slippage


class TestApplySlippage:
    """apply_slippage 함수 테스트."""

    def test_zero_slippage_returns_original(self) -> None:
        """슬리피지 0이면 원래 가격 반환."""
        assert apply_slippage(10000, "BUY", 0.0) == 10000
        assert apply_slippage(10000, "SELL", 0.0) == 10000

    def test_buy_slippage_increases_price(self) -> None:
        """BUY 시 슬리피지는 가격을 올린다 (불리한 방향)."""
        result = apply_slippage(10000, "BUY", 0.001)
        assert result == 10010  # +0.1%

    def test_sell_slippage_decreases_price(self) -> None:
        """SELL 시 슬리피지는 가격을 내린다 (불리한 방향)."""
        result = apply_slippage(10000, "SELL", 0.001)
        assert result == 9990  # -0.1%

    def test_larger_slippage(self) -> None:
        """큰 슬리피지 비율 테스트."""
        assert apply_slippage(10000, "BUY", 0.005) == 10050  # +0.5%
        assert apply_slippage(10000, "SELL", 0.005) == 9950  # -0.5%

    def test_volatility_factor_adds_slippage(self) -> None:
        """변동성 계수가 슬리피지를 추가한다."""
        # bar range = 10200 - 9800 = 400, range_pct = 400/10000 = 4%
        # extra = 4% * 0.1 = 0.4%
        # total = 0.1% + 0.4% = 0.5%
        result = apply_slippage(
            10000,
            "BUY",
            0.001,
            bar_high=10200,
            bar_low=9800,
            volatility_factor=0.1,
        )
        assert result == 10050  # +0.5%

    def test_volatility_factor_only(self) -> None:
        """고정 슬리피지 0, 변동성만 적용."""
        result = apply_slippage(
            10000,
            "SELL",
            0.0,
            bar_high=10200,
            bar_low=9800,
            volatility_factor=0.1,
        )
        assert result == 9960  # -0.4%

    def test_no_bar_data_volatility_ignored(self) -> None:
        """봉 데이터 없으면 변동성 무시."""
        result = apply_slippage(10000, "BUY", 0.001, volatility_factor=0.1)
        assert result == 10010  # 고정 슬리피지만 적용

    def test_roundtrip_cost(self) -> None:
        """왕복 거래 시 슬리피지 비용 확인."""
        entry = apply_slippage(10000, "BUY", 0.001)  # 10010
        exit_ = apply_slippage(10000, "SELL", 0.001)  # 9990
        # 왕복 손실 = (10010 - 9990) / 10000 = 0.2%
        roundtrip_cost = (entry - exit_) / 10000
        assert abs(roundtrip_cost - 0.002) < 1e-6
