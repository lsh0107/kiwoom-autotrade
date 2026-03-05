"""애플리케이션 설정 (Pydantic BaseSettings)."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수 기반 설정."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 앱 ──────────────────────────────────────
    app_name: str = "키움 자동매매"
    debug: bool = False

    # ── DB ──────────────────────────────────────
    database_url: str = "postgresql+asyncpg://kiwoom:password@localhost:5432/kiwoom_trade"

    # ── 키움증권 모의투자 ───────────────────────
    kiwoom_mock_app_key: str = ""
    kiwoom_mock_app_secret: str = ""
    kiwoom_mock_account_no: str = ""

    # ── 키움증권 실투자 ─────────────────────────
    kiwoom_real_app_key: str = ""
    kiwoom_real_app_secret: str = ""
    kiwoom_real_account_no: str = ""

    # ── 거래 모드 ───────────────────────────────
    is_mock_trading: bool = True
    kiwoom_account_product_code: str = "01"

    # ── JWT ─────────────────────────────────────
    jwt_secret_key: str = "change_me"  # noqa: S105
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── 암호화 (AES-256) ───────────────────────
    encryption_key: str = "change_me"

    # ── CORS ────────────────────────────────────
    cors_allowed_origins: str = "http://localhost:3000"

    # ── LLM ─────────────────────────────────────
    llm_primary_provider: str = "openai"
    llm_fallback_provider: str = "anthropic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-20250514"
    max_daily_llm_cost_usd: float = 5.0

    # ── DART 공시 ───────────────────────────────
    dart_api_key: str = ""

    # ── 알림 ────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Deprecated: API 라우터/스케줄러는 DB 자격증명(BrokerCredential)을 사용.
    # 아래 프로퍼티는 라이브 테스트 스크립트/초기 셋업에서만 사용. 향후 제거 예정.
    @property
    def kiwoom_base_url(self) -> str:
        """현재 거래 모드에 따른 키움 API URL. (deprecated — DB 자격증명 사용 권장)"""
        if self.is_mock_trading:
            return "https://mockapi.kiwoom.com"
        return "https://api.kiwoom.com"

    @property
    def kiwoom_app_key(self) -> str:
        """현재 모드의 앱 키. (deprecated — DB 자격증명 사용 권장)"""
        return self.kiwoom_mock_app_key if self.is_mock_trading else self.kiwoom_real_app_key

    @property
    def kiwoom_app_secret(self) -> str:
        """현재 모드의 앱 시크릿. (deprecated — DB 자격증명 사용 권장)"""
        return self.kiwoom_mock_app_secret if self.is_mock_trading else self.kiwoom_real_app_secret

    @property
    def kiwoom_account_no(self) -> str:
        """현재 모드의 계좌번호. (deprecated — DB 자격증명 사용 권장)"""
        return self.kiwoom_mock_account_no if self.is_mock_trading else self.kiwoom_real_account_no

    @property
    def cors_origins(self) -> list[str]:
        """CORS 허용 오리진 목록."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",")]

    @field_validator("is_mock_trading", mode="before")
    @classmethod
    def parse_bool(cls, v: object) -> bool:
        """문자열 'true'/'false'를 bool로 변환."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


def get_settings() -> Settings:
    """설정 싱글톤 반환."""
    return Settings()
