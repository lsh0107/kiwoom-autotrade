"""APScheduler 장 시간 스케줄 관리."""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from src.ai.engine import get_engine
from src.broker.kiwoom import KiwoomClient
from src.config.database import async_session_factory
from src.config.settings import get_settings
from src.models.strategy import Strategy, StrategyStatus

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler()


async def _run_active_strategies() -> None:
    """활성 전략 실행."""
    settings = get_settings()
    engine = get_engine()

    async with async_session_factory() as db:
        result = await db.execute(
            select(Strategy).where(
                Strategy.status == StrategyStatus.ACTIVE,
                Strategy.is_auto_trading.is_(True),
            )
        )
        strategies = result.scalars().all()

        if not strategies:
            return

        for strategy in strategies:
            try:
                # 사용자별 브로커 클라이언트 (설정에서)
                broker_client = KiwoomClient(
                    base_url=settings.kiwoom_base_url,
                    app_key=settings.kiwoom_app_key,
                    app_secret=settings.kiwoom_app_secret,
                    account_no=settings.kiwoom_account_no,
                    is_mock=settings.is_mock_trading,
                )

                signals = await engine.run_analysis(
                    strategy=strategy,
                    broker_client=broker_client,
                    db=db,
                )

                await logger.ainfo(
                    "전략 분석 완료",
                    strategy_id=str(strategy.id),
                    signal_count=len(signals),
                )

                await broker_client.close()

            except Exception:
                await logger.aexception(
                    "전략 실행 실패",
                    strategy_id=str(strategy.id),
                )


def setup_scheduler() -> AsyncIOScheduler:
    """스케줄러 설정 (장 시간 기반)."""
    # 프리마켓 분석 (08:50)
    scheduler.add_job(
        _run_active_strategies,
        CronTrigger(hour=8, minute=50, timezone="Asia/Seoul"),
        id="pre_market",
        name="프리마켓 분석",
    )

    # 개장 직후 (09:05)
    scheduler.add_job(
        _run_active_strategies,
        CronTrigger(hour=9, minute=5, timezone="Asia/Seoul"),
        id="market_open",
        name="개장 직후 분석",
    )

    # 정규장 30분 간격 (09:30~15:00)
    scheduler.add_job(
        _run_active_strategies,
        CronTrigger(
            hour="9-14",
            minute="0,30",
            timezone="Asia/Seoul",
        ),
        id="regular_market",
        name="정규장 정기 분석",
    )

    # 마감 전 (15:15)
    scheduler.add_job(
        _run_active_strategies,
        CronTrigger(hour=15, minute=15, timezone="Asia/Seoul"),
        id="market_close",
        name="마감 전 분석",
    )

    return scheduler
