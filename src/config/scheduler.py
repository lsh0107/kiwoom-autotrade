"""APScheduler 장 시간 스케줄 관리."""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from src.ai.engine import get_engine
from src.broker.constants import MOCK_BASE_URL, REAL_BASE_URL
from src.broker.kiwoom import KiwoomClient
from src.config.database import async_session_factory
from src.models.broker import BrokerCredential
from src.models.strategy import Strategy, StrategyStatus
from src.utils.crypto import decrypt

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler()


async def _run_active_strategies() -> None:
    """활성 전략 실행."""
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
                # 전략 소유자의 활성 자격증명 조회
                cred_result = await db.execute(
                    select(BrokerCredential).where(
                        BrokerCredential.user_id == strategy.user_id,
                        BrokerCredential.is_active.is_(True),
                    )
                )
                cred = cred_result.scalar_one_or_none()
                if not cred:
                    await logger.awarning(
                        "전략 실행 불가: 활성 자격증명 없음",
                        strategy_id=str(strategy.id),
                        user_id=str(strategy.user_id),
                    )
                    continue

                base_url = MOCK_BASE_URL if cred.is_mock else REAL_BASE_URL
                broker_client = KiwoomClient(
                    base_url=base_url,
                    app_key=decrypt(cred.encrypted_app_key),
                    app_secret=decrypt(cred.encrypted_app_secret),
                    is_mock=cred.is_mock,
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
