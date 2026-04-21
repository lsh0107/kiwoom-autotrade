---
name: design-011-daily-candle-caching
description: 일봉 DB 캐싱으로 스크리닝/live_trader 초기화 가속
type: design
status: 활성 (PR 1~4 구현)
created: 2026-04-21
related:
  - scripts/screen_symbols.py
  - scripts/live_trader.py
  - src/models/daily_candle.py
  - airflow/dags/postmarket/daily_candle_collection.py
  - src/trading/daily_candle_store.py
---

# Design 011: 일봉 DB 캐싱 구조

## 1. 배경
2026-04-21 장중 live_trader 26분 hang. 원인: screen_symbols/live_trader가 종목마다 52주 고가/평균거래량 계산 위해 4~6개월치 일봉을 키움 `ka10086`에서 페이징 로드. HTTP 429 빈발. 100종목 = 20~30분.

## 2. 목표
- DB 조회로 전환 → 밀리초 단위.
- 100종목 초기화 30초 이내.
- Airflow pykrx로 장 마감 후 일괄 수집.
- Feature flag 점진 적용.

## 3. 아키텍처
- `daily_candles` 테이블: (symbol, date) 복합 PK, OHLCV + volume + source.
- Airflow DAG `postmarket/daily_candle_collection.py`: KST 18:00 pykrx 수집.
- `DailyCandleStore`: MarketContext 스타일 조회 + 키움 fallback.
- Feature flag: `USE_DB_DAILY_CANDLES=false` 기본.

## 4. PR 쪼개기
1. 모델 + Alembic migration (런타임 영향 0)
2. Airflow DAG + backfill 스크립트
3. DailyCandleStore + 테스트
4. live_trader/screen_symbols 리팩토링 (flag off 기본)
5. (수동) flag on

## 5. 롤백
PR별 revert. Feature flag는 env만 false로 원복.

상세: (agent 재량, 필요 시 확장)
