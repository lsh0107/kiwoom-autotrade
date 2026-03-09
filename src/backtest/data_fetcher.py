"""백테스트 데이터 수집 모듈.

키움 REST API를 통해 일봉/분봉 데이터를 수집한다.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.broker.kiwoom import KiwoomClient
    from src.broker.schemas import DailyPrice, MinutePrice

logger = structlog.get_logger("backtest.data_fetcher")

# 키움 API 연속조회 간 대기 시간 (초)
_REQUEST_DELAY: float = 0.25


async def fetch_daily_data(
    client: KiwoomClient,
    symbol: str,
    start_date: str,
    end_date: str,
) -> list[DailyPrice]:
    """일봉 데이터 수집.

    ka10081 API를 사용하여 기간 내 일봉 데이터를 수집한다.
    API는 기준일자부터 과거 방향으로 데이터를 반환하므로,
    end_date를 기준으로 조회 후 start_date 이전 데이터를 필터링한다.

    Args:
        client: 키움 API 클라이언트
        symbol: 종목코드 (6자리)
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)

    Returns:
        list[DailyPrice]: 일봉 데이터 (날짜 오름차순)
    """
    all_data: list[DailyPrice] = []

    data = await client.get_daily_chart(symbol, base_dt=end_date)
    for item in data:
        if start_date <= item.date <= end_date:
            all_data.append(item)

    # API는 시간 역순으로 반환하므로 오름차순 정렬
    all_data.sort(key=lambda x: x.date)

    logger.info(
        "일봉 데이터 수집 완료",
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        count=len(all_data),
    )

    return all_data


async def fetch_minute_data(
    client: KiwoomClient,
    symbol: str,
    date: str,
    interval: int = 5,
) -> list[MinutePrice]:
    """분봉 데이터 수집.

    ka10080 API를 사용하여 특정 일자의 분봉 데이터를 수집한다.

    Args:
        client: 키움 API 클라이언트
        symbol: 종목코드 (6자리)
        date: 조회 일자 (YYYYMMDD)
        interval: 분봉 간격 (1, 3, 5, 10, 15, 30, 45, 60)

    Returns:
        list[MinutePrice]: 분봉 데이터 (시간 오름차순)
    """
    data = await client.get_minute_price(symbol, interval, base_dt=date)

    # 해당 일자 데이터만 필터링
    filtered = [item for item in data if item.datetime.startswith(date)]

    # API는 시간 역순으로 반환하므로 오름차순 정렬
    filtered.sort(key=lambda x: x.datetime)

    logger.info(
        "분봉 데이터 수집 완료",
        symbol=symbol,
        date=date,
        interval=interval,
        count=len(filtered),
    )

    return filtered


async def fetch_minute_data_multi_day(
    client: KiwoomClient,
    symbol: str,
    dates: list[str],
    interval: int = 5,
) -> list[MinutePrice]:
    """여러 날짜의 분봉 데이터를 순차 수집.

    키움 API rate limit을 고려하여 요청 간 대기 시간을 둔다.

    Args:
        client: 키움 API 클라이언트
        symbol: 종목코드 (6자리)
        dates: 조회 일자 목록 (YYYYMMDD)
        interval: 분봉 간격

    Returns:
        list[MinutePrice]: 전체 분봉 데이터 (시간 오름차순)
    """
    all_data: list[MinutePrice] = []

    for i, date in enumerate(dates):
        day_data = await fetch_minute_data(client, symbol, date, interval)
        all_data.extend(day_data)

        # rate limit 방지 (마지막 요청 제외)
        if i < len(dates) - 1:
            await asyncio.sleep(_REQUEST_DELAY)

    logger.info(
        "멀티데이 분봉 데이터 수집 완료",
        symbol=symbol,
        days=len(dates),
        total_bars=len(all_data),
    )

    return all_data
