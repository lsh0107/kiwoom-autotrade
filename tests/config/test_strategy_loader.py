"""strategy_loader 테스트."""

from src.config.strategy_loader import (
    _extract_value,
    build_momentum_params,
    build_mr_params,
    extract_globals,
)


class TestExtractValue:
    """JSONB 값 추출 테스트."""

    def test_dict_with_value_key(self) -> None:
        """{"value": 1.5} → 1.5."""
        assert _extract_value({"value": 1.5}) == 1.5

    def test_plain_value(self) -> None:
        """직접 값이면 그대로 반환."""
        assert _extract_value(1.5) == 1.5
        assert _extract_value("09:05") == "09:05"

    def test_dict_without_value_key(self) -> None:
        """value 키 없는 dict은 그대로."""
        d = {"min": 0, "max": 10}
        assert _extract_value(d) == d


class TestBuildMomentumParams:
    """MomentumParams 구성 테스트."""

    def test_empty_config_uses_defaults(self) -> None:
        """빈 DB config → 코드 기본값."""
        params = build_momentum_params({})
        assert params.volume_ratio == 0.7  # v3.0 기본값
        assert params.stop_loss == -0.01
        assert params.take_profit == 0.025

    def test_db_config_overrides_defaults(self) -> None:
        """DB 값이 기본값을 오버라이드."""
        db_config = {
            "volume_ratio": 1.2,
            "stop_loss": -0.005,
            "take_profit": 0.03,
        }
        params = build_momentum_params(db_config)
        assert params.volume_ratio == 1.2
        assert params.stop_loss == -0.005
        assert params.take_profit == 0.03

    def test_cli_overrides_db(self) -> None:
        """CLI가 DB보다 우선."""
        db_config = {"volume_ratio": 1.2}
        cli = {"volume_ratio": 0.5}
        params = build_momentum_params(db_config, cli)
        assert params.volume_ratio == 0.5

    def test_jsonb_wrapped_value(self) -> None:
        """JSONB {"value": ...} 형식 처리."""
        db_config = {"volume_ratio": {"value": 0.9}}
        params = build_momentum_params(db_config)
        assert params.volume_ratio == 0.9

    def test_entry_time_format_conversion(self) -> None:
        """HHMM → HH:MM 변환."""
        db_config = {
            "entry_start_time": "0905",
            "entry_end_time": "1400",
        }
        params = build_momentum_params(db_config)
        assert params.entry_start_time == "09:05"
        assert params.entry_end_time == "14:00"

    def test_entry_time_already_formatted(self) -> None:
        """이미 HH:MM이면 그대로."""
        db_config = {"entry_start_time": "09:05"}
        params = build_momentum_params(db_config)
        assert params.entry_start_time == "09:05"

    def test_atr_mult_maps_to_correct_field(self) -> None:
        """atr_stop_mult → atr_stop_multiplier."""
        db_config = {"atr_stop_mult": 1.5, "atr_tp_mult": 3.0}
        params = build_momentum_params(db_config)
        assert params.atr_stop_multiplier == 1.5
        assert params.atr_tp_multiplier == 3.0


class TestBuildMrParams:
    """MeanReversionParams 구성 테스트."""

    def test_empty_config_uses_defaults(self) -> None:
        """빈 config → 기본값."""
        params = build_mr_params({})
        assert params.rsi_oversold == 35.0
        assert params.stop_loss == -0.025

    def test_db_config_overrides(self) -> None:
        """DB 값 오버라이드."""
        db_config = {
            "mr_rsi_oversold": 30.0,
            "mr_stop_loss": -0.03,
        }
        params = build_mr_params(db_config)
        assert params.rsi_oversold == 30.0
        assert params.stop_loss == -0.03

    def test_cli_overrides_db(self) -> None:
        """CLI > DB."""
        db_config = {"mr_rsi_oversold": 30.0}
        cli = {"rsi_oversold": 25.0}
        params = build_mr_params(db_config, cli)
        assert params.rsi_oversold == 25.0


class TestExtractGlobals:
    """전역 상수 추출 테스트."""

    def test_extracts_known_keys(self) -> None:
        """알려진 키만 추출."""
        db_config = {
            "atr_stop_mult": 1.5,
            "atr_tp_mult": 3.0,
            "gap_risk_threshold": -0.03,
            "max_holding_days": 5,
            "volume_ratio": 0.7,  # 전역이 아닌 키
        }
        result = extract_globals(db_config)
        assert result["atr_stop_mult"] == 1.5
        assert result["gap_risk_threshold"] == -0.03
        assert "volume_ratio" not in result

    def test_empty_config(self) -> None:
        """빈 config → 빈 결과."""
        assert extract_globals({}) == {}
