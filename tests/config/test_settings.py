"""애플리케이션 설정 테스트."""

import pytest
from src.config.settings import Settings, get_settings


class TestSettingsDefaults:
    """Settings 기본값 테스트."""

    def test_settings_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """기본값 검증."""
        # 환경변수 없이 기본값으로 생성
        settings = Settings()

        assert settings.app_name == "키움 자동매매"
        assert settings.debug is False
        assert settings.jwt_algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30
        assert settings.refresh_token_expire_days == 7
        assert settings.kiwoom_account_product_code == "01"

    def test_settings_mock_trading_default(self) -> None:
        """is_mock_trading 기본값은 True."""
        settings = Settings()

        assert settings.is_mock_trading is True

    def test_settings_parse_bool_string_true(self) -> None:
        """is_mock_trading 문자열 'true' → True 변환."""
        settings = Settings(is_mock_trading="true")  # type: ignore[arg-type]
        assert settings.is_mock_trading is True

    def test_settings_parse_bool_string_false(self) -> None:
        """is_mock_trading 문자열 'false' → False 변환."""
        settings = Settings(is_mock_trading="false")  # type: ignore[arg-type]
        assert settings.is_mock_trading is False

    def test_settings_parse_bool_string_yes(self) -> None:
        """is_mock_trading 문자열 'yes' → True 변환."""
        settings = Settings(is_mock_trading="yes")  # type: ignore[arg-type]
        assert settings.is_mock_trading is True

    def test_settings_parse_bool_string_1(self) -> None:
        """is_mock_trading 문자열 '1' → True 변환."""
        settings = Settings(is_mock_trading="1")  # type: ignore[arg-type]
        assert settings.is_mock_trading is True


class TestSettingsProperties:
    """Settings 속성 테스트."""

    def test_kiwoom_base_url_mock(self) -> None:
        """모의투자 URL 반환."""
        settings = Settings(is_mock_trading=True)
        assert settings.kiwoom_base_url == "https://mockapi.kiwoom.com"

    def test_kiwoom_base_url_real(self) -> None:
        """실투자 URL 반환."""
        settings = Settings(is_mock_trading=False)
        assert settings.kiwoom_base_url == "https://api.kiwoom.com"

    def test_kiwoom_app_key_mock(self) -> None:
        """모의투자 앱 키 반환."""
        settings = Settings(
            kiwoom_mock_app_key="mock_key",
            kiwoom_real_app_key="real_key",
            is_mock_trading=True,
        )
        assert settings.kiwoom_app_key == "mock_key"

    def test_kiwoom_app_key_real(self) -> None:
        """실투자 앱 키 반환."""
        settings = Settings(
            kiwoom_mock_app_key="mock_key",
            kiwoom_real_app_key="real_key",
            is_mock_trading=False,
        )
        assert settings.kiwoom_app_key == "real_key"

    def test_kiwoom_app_secret_mock(self) -> None:
        """모의투자 앱 시크릿 반환."""
        settings = Settings(
            kiwoom_mock_app_secret="mock_secret",
            kiwoom_real_app_secret="real_secret",
            is_mock_trading=True,
        )
        assert settings.kiwoom_app_secret == "mock_secret"

    def test_kiwoom_account_no_mock(self) -> None:
        """모의투자 계좌번호 반환."""
        settings = Settings(
            kiwoom_mock_account_no="1234567890",
            kiwoom_real_account_no="0987654321",
            is_mock_trading=True,
        )
        assert settings.kiwoom_account_no == "1234567890"

    def test_cors_origins_single(self) -> None:
        """단일 CORS 오리진 파싱."""
        settings = Settings(cors_allowed_origins="http://localhost:3000")
        assert settings.cors_origins == ["http://localhost:3000"]

    def test_cors_origins_multiple(self) -> None:
        """복수 CORS 오리진 파싱 (쉼표 구분)."""
        settings = Settings(cors_allowed_origins="http://localhost:3000, https://example.com")
        assert settings.cors_origins == ["http://localhost:3000", "https://example.com"]


class TestGetSettings:
    """get_settings 함수 테스트."""

    def test_get_settings_returns_settings(self) -> None:
        """Settings 인스턴스 반환."""
        settings = get_settings()
        assert isinstance(settings, Settings)
