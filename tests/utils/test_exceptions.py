"""커스텀 예외 계층 테스트."""

import pytest

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


# ── 파라메트릭: 기본값 메시지/코드 검증 ──────────────────────────────


@pytest.mark.parametrize(
    ("exc_cls", "expected_message", "expected_code"),
    [
        (AuthError, "인증 실패", "AUTH_ERROR"),
        (
            InvalidCredentialsError,
            "이메일 또는 비밀번호가 올바르지 않습니다",
            "INVALID_CREDENTIALS",
        ),
        (InvalidTokenError, "유효하지 않은 토큰입니다", "INVALID_TOKEN"),
        (TokenExpiredError, "토큰이 만료되었습니다", "TOKEN_EXPIRED"),
        (InsufficientPermissionError, "권한이 부족합니다", "INSUFFICIENT_PERMISSION"),
        (BrokerError, "브로커 API 오류", "BROKER_ERROR"),
        (BrokerAuthError, "브로커 인증 실패", "BROKER_AUTH_ERROR"),
        (BrokerRateLimitError, "API 요청 한도 초과", "BROKER_RATE_LIMIT"),
        (OrderError, "주문 오류", "ORDER_ERROR"),
        (OrderValidationError, "주문 검증 실패", "ORDER_VALIDATION_ERROR"),
        (TradingError, "트레이딩 오류", "TRADING_ERROR"),
        (MarketClosedError, "현재 장 운영시간이 아닙니다", "MARKET_CLOSED"),
        (AIError, "AI 처리 오류", "AI_ERROR"),
        (LLMRateLimitError, "LLM 일일 비용 한도 초과", "LLM_RATE_LIMIT"),
        (DataError, "데이터 오류", "DATA_ERROR"),
    ],
)
def test_exception_defaults(
    exc_cls: type[AppError],
    expected_message: str,
    expected_code: str,
) -> None:
    """예외 클래스별 기본 메시지·코드 검증."""
    err = exc_cls()
    assert err.message == expected_message
    assert err.code == expected_code
    assert isinstance(err, AppError)


class TestKillSwitchError:
    """KillSwitchError 레벨별 동작 테스트 (특수 케이스)."""

    def test_default_level1(self) -> None:
        """기본값: 레벨 1."""
        err = KillSwitchError()
        assert err.message == "킬스위치 발동"
        assert err.code == "KILL_SWITCH_L1"
        assert err.level == 1

    def test_level2(self) -> None:
        """레벨 2."""
        err = KillSwitchError("전략 손실 초과", level=2)
        assert err.code == "KILL_SWITCH_L2"
        assert err.level == 2

    def test_level3(self) -> None:
        """레벨 3."""
        err = KillSwitchError(level=3)
        assert err.code == "KILL_SWITCH_L3"
        assert err.level == 3


class TestCustomMessageOverride:
    """커스텀 메시지 오버라이드 테스트."""

    def test_broker_auth_error_custom_message(self) -> None:
        """BrokerAuthError 커스텀 메시지."""
        err = BrokerAuthError("토큰 발급 실패")
        assert err.message == "토큰 발급 실패"
        assert err.code == "BROKER_AUTH_ERROR"

    def test_order_validation_error_custom_message(self) -> None:
        """OrderValidationError 커스텀 메시지."""
        err = OrderValidationError("수량 초과")
        assert err.message == "수량 초과"


class TestResourceErrors:
    """리소스명을 인자로 받는 예외 테스트."""

    def test_not_found_with_resource(self) -> None:
        """NotFoundError 특정 리소스."""
        err = NotFoundError("사용자")
        assert err.message == "사용자을(를) 찾을 수 없습니다"
        assert err.code == "NOT_FOUND"

    def test_not_found_default(self) -> None:
        """NotFoundError 기본 리소스명."""
        err = NotFoundError()
        assert err.message == "리소스을(를) 찾을 수 없습니다"

    def test_duplicate_with_resource(self) -> None:
        """DuplicateError 특정 리소스."""
        err = DuplicateError("이메일")
        assert err.message == "이미 존재하는 이메일입니다"
        assert err.code == "DUPLICATE"

    def test_duplicate_default(self) -> None:
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
