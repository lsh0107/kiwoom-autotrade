"""DB strategy_config → 전략 파라미터 로더.

live_trader 시작 시 DB에서 최신 파라미터를 읽어
MomentumParams / MeanReversionParams 객체를 구성한다.

우선순위: CLI 인자 > DB > 코드 기본값
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backtest.strategy import MomentumParams
from src.strategy.mean_reversion import MeanReversionParams

logger = structlog.get_logger("config.strategy_loader")

# DB key → MomentumParams 필드 매핑
_MOMENTUM_KEY_MAP: dict[str, str] = {
    "volume_ratio": "volume_ratio",
    "stop_loss": "stop_loss",
    "take_profit": "take_profit",
    "entry_start_time": "entry_start_time",
    "entry_end_time": "entry_end_time",
    "max_positions": "max_positions",
    "atr_stop_mult": "atr_stop_multiplier",
    "atr_tp_mult": "atr_tp_multiplier",
    "slippage_pct": "slippage_pct",
}

# DB key → MeanReversionParams 필드 매핑
_MR_KEY_MAP: dict[str, str] = {
    "mr_rsi_oversold": "rsi_oversold",
    "mr_rsi_overbought": "rsi_overbought",
    "mr_bb_std": "bb_std",
    "mr_volume_ratio": "volume_ratio",
    "mr_stop_loss": "stop_loss",
    "mr_take_profit": "take_profit",
    "mr_max_positions": "max_positions",
    "mr_slippage_pct": "slippage_pct",
}

# DB key → 전역 상수 매핑 (live_trader 전역 변수용)
GLOBAL_KEYS: set[str] = {
    "atr_stop_mult",
    "atr_tp_mult",
    "gap_risk_threshold",
    "max_holding_days",
}


async def load_all_config(db: AsyncSession) -> dict[str, object]:
    """DB strategy_config 테이블에서 전체 파라미터를 로드한다.

    Returns:
        {key: value} 딕셔너리. value는 JSONB 저장 값 그대로.
    """
    from src.models.strategy_config import StrategyConfig

    result = await db.execute(select(StrategyConfig))
    rows = result.scalars().all()
    config: dict[str, object] = {row.key: row.value for row in rows}
    logger.info("DB strategy_config 로드 완료", count=len(config))
    return config


async def load_all_config_raw(database_url: str) -> dict[str, object]:
    """SQLAlchemy 세션 없이 raw connection으로 strategy_config를 로드한다.

    live_trader처럼 FastAPI 외부에서 실행될 때 사용.

    Args:
        database_url: PostgreSQL 접속 URL (asyncpg)

    Returns:
        {key: value} 딕셔너리
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.models.strategy_config import StrategyConfig

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(select(StrategyConfig.key, StrategyConfig.value))
            config = {row.key: row.value for row in result}
    finally:
        await engine.dispose()

    logger.info("DB strategy_config 로드 완료 (raw)", count=len(config))
    return config


def build_momentum_params(
    db_config: dict[str, object],
    cli_overrides: dict[str, object] | None = None,
) -> MomentumParams:
    """DB config + CLI 오버라이드로 MomentumParams 구성.

    우선순위: CLI > DB > 코드 기본값

    Args:
        db_config: load_all_config() 결과
        cli_overrides: CLI에서 명시적으로 지정된 값 (None이면 DB/기본값 사용)

    Returns:
        MomentumParams 인스턴스
    """
    overrides = cli_overrides or {}
    kwargs: dict[str, Any] = {}

    for db_key, field_name in _MOMENTUM_KEY_MAP.items():
        # CLI > DB > 코드 기본값
        if field_name in overrides:
            kwargs[field_name] = overrides[field_name]
        elif db_key in db_config:
            kwargs[field_name] = _extract_value(db_config[db_key])
        # else: 코드 기본값 사용

    # entry_start_time 형식 변환: "09:05" → "09:05" (HH:MM)
    if "entry_start_time" in kwargs and isinstance(kwargs["entry_start_time"], str):
        val = str(kwargs["entry_start_time"]).replace(":", "")
        if len(val) == 4:
            kwargs["entry_start_time"] = f"{val[:2]}:{val[2:]}"
    if "entry_end_time" in kwargs and isinstance(kwargs["entry_end_time"], str):
        val = str(kwargs["entry_end_time"]).replace(":", "")
        if len(val) == 4:
            kwargs["entry_end_time"] = f"{val[:2]}:{val[2:]}"

    params = MomentumParams(**kwargs)
    logger.info(
        "MomentumParams 구성 완료",
        volume_ratio=params.volume_ratio,
        stop_loss=params.stop_loss,
        take_profit=params.take_profit,
    )
    return params


def build_mr_params(
    db_config: dict[str, object],
    cli_overrides: dict[str, object] | None = None,
) -> MeanReversionParams:
    """DB config + CLI 오버라이드로 MeanReversionParams 구성.

    Args:
        db_config: load_all_config() 결과
        cli_overrides: CLI에서 명시적으로 지정된 값

    Returns:
        MeanReversionParams 인스턴스
    """
    overrides = cli_overrides or {}
    kwargs: dict[str, Any] = {}

    for db_key, field_name in _MR_KEY_MAP.items():
        if field_name in overrides:
            kwargs[field_name] = overrides[field_name]
        elif db_key in db_config:
            kwargs[field_name] = _extract_value(db_config[db_key])

    params = MeanReversionParams(**kwargs)
    logger.info(
        "MeanReversionParams 구성 완료",
        rsi_oversold=params.rsi_oversold,
        stop_loss=params.stop_loss,
        take_profit=params.take_profit,
    )
    return params


def extract_globals(db_config: dict[str, object]) -> dict[str, object]:
    """DB config에서 전역 상수 값을 추출한다.

    Returns:
        {"atr_stop_mult": 1.5, "atr_tp_mult": 3.0, ...}
    """
    result = {}
    for key in GLOBAL_KEYS:
        if key in db_config:
            result[key] = _extract_value(db_config[key])
    return result


def _extract_value(val: object) -> object:
    """JSONB 저장 값에서 실제 값을 추출한다.

    DB에서 JSONB로 저장된 값은 {"value": 1.5} 또는 1.5 형태일 수 있다.
    """
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val
