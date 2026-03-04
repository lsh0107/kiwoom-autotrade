"""structlog 로깅 설정 테스트."""

from unittest.mock import patch

from src.config.logging import get_logger, setup_logging


class TestSetupLogging:
    """setup_logging 함수 테스트."""

    @patch("src.config.logging.logging.basicConfig")
    @patch("src.config.logging.structlog.configure")
    def test_setup_logging_default(self, mock_configure: object, mock_basic: object) -> None:
        """기본 설정(debug=False) 호출 확인."""
        setup_logging(debug=False)

        mock_basic.assert_called_once()  # type: ignore[attr-defined]
        mock_configure.assert_called_once()  # type: ignore[attr-defined]

        # basicConfig에 INFO 레벨 전달 확인
        call_kwargs = mock_basic.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["level"] == 20  # logging.INFO = 20

    @patch("src.config.logging.logging.basicConfig")
    @patch("src.config.logging.structlog.configure")
    def test_setup_logging_debug(self, mock_configure: object, mock_basic: object) -> None:
        """debug=True 설정 시 DEBUG 레벨."""
        setup_logging(debug=True)

        call_kwargs = mock_basic.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["level"] == 10  # logging.DEBUG = 10


class TestGetLogger:
    """get_logger 함수 테스트."""

    def test_get_logger(self) -> None:
        """이름 지정 로거 반환 확인."""
        logger = get_logger("test.module")

        assert logger is not None
        # structlog.get_logger는 바인딩 가능한 로거를 반환
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_get_logger_different_names(self) -> None:
        """다른 이름으로 다른 로거 반환."""
        logger1 = get_logger("module.a")
        logger2 = get_logger("module.b")

        assert logger1 is not None
        assert logger2 is not None
