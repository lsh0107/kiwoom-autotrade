"""API v1 라우터 통합."""

from fastapi import APIRouter

from src.api.v1.account import router as account_router
from src.api.v1.admin import router as admin_router
from src.api.v1.auth import router as auth_router
from src.api.v1.bot import router as bot_router
from src.api.v1.market import router as market_router
from src.api.v1.orders import router as orders_router
from src.api.v1.realtime import router as realtime_router
from src.api.v1.results import router as results_router
from src.api.v1.settings import router as settings_router

v1_router = APIRouter()

v1_router.include_router(auth_router)
v1_router.include_router(admin_router)
v1_router.include_router(settings_router)
v1_router.include_router(market_router)
v1_router.include_router(account_router)
v1_router.include_router(orders_router)
v1_router.include_router(bot_router)
v1_router.include_router(results_router)
v1_router.include_router(realtime_router)
