"""FastAPI 애플리케이션 팩토리."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config.logging import setup_logging
from src.config.settings import get_settings
from src.utils.exceptions import AppError

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """앱 시작/종료 이벤트."""
    settings = get_settings()
    setup_logging(debug=settings.debug)

    await logger.ainfo(
        "앱 시작",
        mock_trading=settings.is_mock_trading,
        debug=settings.debug,
    )
    yield
    await logger.ainfo("앱 종료")


def create_app() -> FastAPI:
    """FastAPI 앱 생성."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 에러 핸들러
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        """커스텀 예외 → JSON 응답."""
        status_map: dict[str, int] = {
            "AUTH_ERROR": 401,
            "INVALID_CREDENTIALS": 401,
            "INVALID_TOKEN": 401,
            "TOKEN_EXPIRED": 401,
            "INVITE_REQUIRED": 401,
            "INVITE_USED": 401,
            "INVITE_EXPIRED": 401,
            "ACCOUNT_DISABLED": 403,
            "INSUFFICIENT_PERMISSION": 403,
            "NOT_FOUND": 404,
            "DUPLICATE": 409,
            "BROKER_RATE_LIMIT": 429,
            "LLM_RATE_LIMIT": 429,
            "ORDER_VALIDATION_ERROR": 422,
        }
        status_code = status_map.get(exc.code, 400)
        return JSONResponse(
            status_code=status_code,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        """FastAPI HTTPException → 일관된 JSON 포맷."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": f"HTTP_{exc.status_code}", "message": str(exc.detail)},
        )

    # 헬스체크
    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        """헬스체크 엔드포인트."""
        return {
            "status": "ok",
            "version": "0.1.0",
            "trading_mode": "mock" if settings.is_mock_trading else "real",
        }

    # API 라우터 등록
    from src.api.v1.router import v1_router

    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
