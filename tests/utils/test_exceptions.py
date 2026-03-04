"""커스텀 예외 계층 테스트."""

from src.utils.exceptions import (
    AIError,
    AppError,
    AuthError,
    BrokerAuthError,
    BrokerError,
    BrokerRateLimitError,
    DataError,
    DuplicateError,
    InsufficientPermissionError,
    InvalidCredentialsError,
    InvalidTokenError,
    KillSwitchError,
    LLMRateLimitError,
    MarketClosedError,
    NotFoundError,
    OrderError,
    OrderValidationError,
    TokenExpiredError,
    TradingError,
)


class TestAppError:
    """AppError 기본 예외 테스트."""

    def test_default(self) -> None:
        """기본 메시지/코드."""
        err = AppError()
        assert err.message == ""
        assert err.code == "APP_ERROR"
        assert str(err) == ""

    def test_custom(self) -> None:
        """커스텀 메시지/코드."""
        err = AppError("커스텀 에러", "CUSTOM")
        assert err.message == "커스텀 에러"
        assert err.code == "CUSTOM"


class TestAuthError:
    """인증 관련 예외 테스트."""

    def test_auth_error(self) -> None:
        """AuthError 기본값."""
        err = AuthError()
        assert err.message == "인증 실패"
        assert err.code == "AUTH_ERROR"
        assert isinstance(err, AppError)

    def test_invalid_credentials(self) -> None:
        """InvalidCredentialsError 메시지/코드."""
        err = InvalidCredentialsError()
        assert err.message == "이메일 또는 비밀번호가 올바르지 않습니다"
        assert err.code == "INVALID_CREDENTIALS"
        assert isinstance(err, AuthError)

    def test_invalid_token(self) -> None:
        """InvalidTokenError 메시지/코드."""
        err = InvalidTokenError()
        assert err.message == "유효하지 않은 토큰입니다"
        assert err.code == "INVALID_TOKEN"
        assert isinstance(err, AuthError)

    def test_token_expired(self) -> None:
        """TokenExpiredError 메시지/코드."""
        err = TokenExpiredError()
        assert err.message == "토큰이 만료되었습니다"
        assert err.code == "TOKEN_EXPIRED"
        assert isinstance(err, AuthError)

    def test_insufficient_permission(self) -> None:
        """InsufficientPermissionError 메시지/코드."""
        err = InsufficientPermissionError()
        assert err.message == "권한이 부족합니다"
        assert err.code == "INSUFFICIENT_PERMISSION"
        assert isinstance(err, AuthError)


class TestBrokerError:
    """브로커 관련 예외 테스트."""

    def test_broker_error(self) -> None:
        """BrokerError 기본값."""
        err = BrokerError()
        assert err.message == "브로커 API 오류"
        assert err.code == "BROKER_ERROR"
        assert isinstance(err, AppError)

    def test_broker_auth_error(self) -> None:
        """BrokerAuthError 메시지/코드."""
        err = BrokerAuthError()
        assert err.message == "브로커 인증 실패"
        assert err.code == "BROKER_AUTH_ERROR"
        assert isinstance(err, BrokerError)

    def test_broker_auth_error_custom_message(self) -> None:
        """BrokerAuthError 커스텀 메시지."""
        err = BrokerAuthError("토큰 발급 실패")
        assert err.message == "토큰 발급 실패"
        assert err.code == "BROKER_AUTH_ERROR"

    def test_broker_rate_limit(self) -> None:
        """BrokerRateLimitError 메시지/코드."""
        err = BrokerRateLimitError()
        assert err.message == "API 요청 한도 초과"
        assert err.code == "BROKER_RATE_LIMIT"
        assert isinstance(err, BrokerError)


class TestOrderError:
    """주문 관련 예외 테스트."""

    def test_order_error(self) -> None:
        """OrderError 기본값."""
        err = OrderError()
        assert err.message == "주문 오류"
        assert err.code == "ORDER_ERROR"
        assert isinstance(err, AppError)

    def test_order_validation_error(self) -> None:
        """OrderValidationError 메시지/코드."""
        err = OrderValidationError()
        assert err.message == "주문 검증 실패"
        assert err.code == "ORDER_VALIDATION_ERROR"
        assert isinstance(err, OrderError)

    def test_order_validation_error_custom(self) -> None:
        """OrderValidationError 커스텀 메시지."""
        err = OrderValidationError("수량 초과")
        assert err.message == "수량 초과"

    def test_kill_switch_error(self) -> None:
        """KillSwitchError 메시지/코드/레벨."""
        err = KillSwitchError()
        assert err.message == "킬스위치 발동"
        assert err.code == "KILL_SWITCH_L1"
        assert err.level == 1

    def test_kill_switch_error_level2(self) -> None:
        """KillSwitchError 레벨 2."""
        err = KillSwitchError("전략 손실 초과", level=2)
        assert err.message == "전략 손실 초과"
        assert err.code == "KILL_SWITCH_L2"
        assert err.level == 2

    def test_kill_switch_error_level3(self) -> None:
        """KillSwitchError 레벨 3."""
        err = KillSwitchError(level=3)
        assert err.code == "KILL_SWITCH_L3"
        assert err.level == 3


class TestTradingError:
    """트레이딩 관련 예외 테스트."""

    def test_trading_error(self) -> None:
        """TradingError 기본값."""
        err = TradingError()
        assert err.message == "트레이딩 오류"
        assert err.code == "TRADING_ERROR"
        assert isinstance(err, AppError)

    def test_market_closed(self) -> None:
        """MarketClosedError 메시지/코드."""
        err = MarketClosedError()
        assert err.message == "현재 장 운영시간이 아닙니다"
        assert err.code == "MARKET_CLOSED"
        assert isinstance(err, TradingError)


class TestAIError:
    """AI/LLM 관련 예외 테스트."""

    def test_ai_error(self) -> None:
        """AIError 기본값."""
        err = AIError()
        assert err.message == "AI 처리 오류"
        assert err.code == "AI_ERROR"
        assert isinstance(err, AppError)

    def test_llm_rate_limit(self) -> None:
        """LLMRateLimitError 메시지/코드."""
        err = LLMRateLimitError()
        assert err.message == "LLM 일일 비용 한도 초과"
        assert err.code == "LLM_RATE_LIMIT"
        assert isinstance(err, AIError)


class TestDataError:
    """데이터 관련 예외 테스트."""

    def test_data_error(self) -> None:
        """DataError 기본값."""
        err = DataError()
        assert err.message == "데이터 오류"
        assert err.code == "DATA_ERROR"
        assert isinstance(err, AppError)

    def test_not_found_error(self) -> None:
        """NotFoundError 메시지/코드."""
        err = NotFoundError("사용자")
        assert err.message == "사용자을(를) 찾을 수 없습니다"
        assert err.code == "NOT_FOUND"
        assert isinstance(err, AppError)

    def test_not_found_error_default(self) -> None:
        """NotFoundError 기본 리소스명."""
        err = NotFoundError()
        assert err.message == "리소스을(를) 찾을 수 없습니다"

    def test_duplicate_error(self) -> None:
        """DuplicateError 메시지/코드."""
        err = DuplicateError("이메일")
        assert err.message == "이미 존재하는 이메일입니다"
        assert err.code == "DUPLICATE"
        assert isinstance(err, AppError)

    def test_duplicate_error_default(self) -> None:
        """DuplicateError 기본 리소스명."""
        err = DuplicateError()
        assert err.message == "이미 존재하는 리소스입니다"


class TestExceptionHierarchy:
    """예외 상속 계층 테스트."""

    def test_all_inherit_from_app_error(self) -> None:
        """모든 예외가 AppError를 상속하는지 확인."""
        exceptions = [
            AuthError(),
            InvalidCredentialsError(),
            InvalidTokenError(),
            TokenExpiredError(),
            InsufficientPermissionError(),
            BrokerError(),
            BrokerAuthError(),
            BrokerRateLimitError(),
            OrderError(),
            OrderValidationError(),
            KillSwitchError(),
            TradingError(),
            MarketClosedError(),
            AIError(),
            LLMRateLimitError(),
            DataError(),
            NotFoundError(),
            DuplicateError(),
        ]
        for exc in exceptions:
            assert isinstance(exc, AppError), f"{type(exc).__name__}이 AppError를 상속하지 않음"
            assert isinstance(exc, Exception)
