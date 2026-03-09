"""커스텀 예외 계층."""


class AppError(Exception):
    """애플리케이션 기본 예외."""

    def __init__(self, message: str = "", code: str = "APP_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


# ── 인증 ──────────────────────────────────────────────


class AuthError(AppError):
    """인증 관련 예외."""

    def __init__(self, message: str = "인증 실패", code: str = "AUTH_ERROR") -> None:
        super().__init__(message, code)


class InvalidCredentialsError(AuthError):
    """잘못된 자격증명."""

    def __init__(self) -> None:
        super().__init__("이메일 또는 비밀번호가 올바르지 않습니다", "INVALID_CREDENTIALS")


class InvalidTokenError(AuthError):
    """유효하지 않은 토큰."""

    def __init__(self) -> None:
        super().__init__("유효하지 않은 토큰입니다", "INVALID_TOKEN")


class TokenExpiredError(AuthError):
    """만료된 토큰."""

    def __init__(self) -> None:
        super().__init__("토큰이 만료되었습니다", "TOKEN_EXPIRED")


class InsufficientPermissionError(AuthError):
    """권한 부족."""

    def __init__(self) -> None:
        super().__init__("권한이 부족합니다", "INSUFFICIENT_PERMISSION")


# ── 브로커 ────────────────────────────────────────────


class BrokerError(AppError):
    """증권사 API 관련 예외."""

    def __init__(self, message: str = "브로커 API 오류", code: str = "BROKER_ERROR") -> None:
        super().__init__(message, code)


class BrokerAuthError(BrokerError):
    """브로커 인증 실패."""

    def __init__(self, message: str = "브로커 인증 실패") -> None:
        super().__init__(message, "BROKER_AUTH_ERROR")


class BrokerRateLimitError(BrokerError):
    """브로커 요청 제한 초과."""

    def __init__(self) -> None:
        super().__init__("API 요청 한도 초과", "BROKER_RATE_LIMIT")


# ── 주문 ──────────────────────────────────────────────


class OrderError(AppError):
    """주문 관련 예외."""

    def __init__(self, message: str = "주문 오류", code: str = "ORDER_ERROR") -> None:
        super().__init__(message, code)


class OrderValidationError(OrderError):
    """주문 검증 실패."""

    def __init__(self, message: str = "주문 검증 실패") -> None:
        super().__init__(message, "ORDER_VALIDATION_ERROR")


class KillSwitchError(OrderError):
    """킬스위치 발동."""

    def __init__(self, message: str = "킬스위치 발동", level: int = 1) -> None:
        self.level = level
        super().__init__(message, f"KILL_SWITCH_L{level}")


# ── 트레이딩 ──────────────────────────────────────────


class TradingError(AppError):
    """트레이딩 관련 예외."""

    def __init__(self, message: str = "트레이딩 오류", code: str = "TRADING_ERROR") -> None:
        super().__init__(message, code)


class MarketClosedError(TradingError):
    """장 운영시간 외."""

    def __init__(self) -> None:
        super().__init__("현재 장 운영시간이 아닙니다", "MARKET_CLOSED")


# ── AI / LLM ─────────────────────────────────────────


class AIError(AppError):
    """AI/LLM 관련 예외."""

    def __init__(self, message: str = "AI 처리 오류", code: str = "AI_ERROR") -> None:
        super().__init__(message, code)


class LLMRateLimitError(AIError):
    """LLM 비용/요청 한도 초과."""

    def __init__(self, message: str = "LLM 일일 비용 한도 초과") -> None:
        super().__init__(message, "LLM_RATE_LIMIT")


# ── 데이터 ────────────────────────────────────────────


class DataError(AppError):
    """데이터 관련 예외."""

    def __init__(self, message: str = "데이터 오류", code: str = "DATA_ERROR") -> None:
        super().__init__(message, code)


class NotFoundError(AppError):
    """리소스 없음."""

    def __init__(self, resource: str = "리소스") -> None:
        super().__init__(f"{resource}을(를) 찾을 수 없습니다", "NOT_FOUND")


class CredentialNotFoundError(AppError):
    """브로커 자격증명 없음."""

    def __init__(self) -> None:
        super().__init__(
            "브로커 API 키가 등록되지 않았습니다. 설정에서 API 키를 등록해주세요.",
            "NO_CREDENTIALS",
        )


class DuplicateError(AppError):
    """중복 리소스."""

    def __init__(self, resource: str = "리소스") -> None:
        super().__init__(f"이미 존재하는 {resource}입니다", "DUPLICATE")
