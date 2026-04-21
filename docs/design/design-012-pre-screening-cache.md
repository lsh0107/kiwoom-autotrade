---
name: design-012-pre-screening-cache
description: 장 마감 후 Airflow가 스크리닝까지 수행, DB에 저장하여 live_trader 0~10초 초기화
type: design
status: 활성 (PR 1~4 구현)
created: 2026-04-21
depends_on:
  - design-011-daily-candle-caching (PR 1~4 머지 완료)
related:
  - scripts/screen_symbols.py
  - scripts/live_trader.py
  - src/trading/process_manager.py
  - src/models/daily_candle.py
  - src/trading/daily_candle_store.py
  - airflow/dags/postmarket/daily_candle_collection.py
feature_flag: USE_PRESCREEN_CACHE  # 기본 false
---

# Design 012: 사전 스크리닝 캐시

## 1. 배경
Design 011 (PR #287~#294)로 일봉 DB 캐싱을 도입해 `live_trader` 초기화가 30초 수준으로 단축됐다.
여전히 스크리닝 조건(52주 고가/평균거래량/볼륨 비율 등) 계산은 `live_trader` 시작 시점에 종목 수만큼 반복 수행된다.
100 종목 기준 약 20~30초가 소요되며 매번 동일한 마감 시점 데이터로 같은 결과를 재계산한다.

## 2. 목표
- **사전 스크리닝**: 장 마감 후 Airflow가 일봉 수집 → 스크리닝까지 한번에 처리.
- **DB 저장**: 스크리닝 결과 전체(통과/미통과 + 계산 지표)를 날짜/프로파일 단위로 보관.
- **0~10초 초기화**: `live_trader`는 당일 캐시 테이블 1회 조회로 통과 리스트를 얻는다.
- **점진 적용**: Feature flag `USE_PRESCREEN_CACHE=false` 기본. cache miss/stale 시 기존 subprocess 폴백.

## 3. 아키텍처

```
장 마감 (15:30 KST)
  │
  ▼
[Airflow] postmarket/daily_candle_collection
  ├─ pykrx OHLCV 수집
  └─ DailyCandle upsert ──▶ Asset("daily_candle_collection")
                                 │
                                 ▼ (Asset trigger)
[Airflow] postmarket/daily_screening  (신규 PR 3)
  ├─ params = load_screening_params(profile)
  ├─ results = compute_screening(params, DailyCandleStore)   # PR 2
  └─ DailyScreeningCacheStore.upsert_many(results)           # PR 1/2
                                 │
                                 ▼ Asset("daily_screening_ready")

다음 거래일 09:00 (live_trader 시작)
  process_manager._run_screening()  (PR 4)
    if USE_PRESCREEN_CACHE:
        rows = load_screened_from_db(today_kst(), profile)
        if rows:  return rows
    # fallback: 기존 subprocess(screen_symbols.py)
```

## 4. 데이터 모델

`daily_screening_cache` (PR 1)
- 복합 PK: `(date, profile, symbol)`
- `profile`: `momentum_breakout` 기본. 다중 프로파일 대비 구분자.
- `passed`: 스크리닝 통과 여부 (True/False 모두 저장해 디버깅/분석에 사용).
- `rank`: 통과 종목의 점수 순위.
- 계산 지표: `price_ratio`, `vol_ratio`, `bonus_score`, `close`, `high_52w`, `volume`, `avg_volume`.
- 파라미터 스냅샷: `threshold`, `volume_ratio_param`, `min_stocks_param` (재현성).
- `run_id`: Airflow DAG run_id (감사/추적).
- Index: `(date, profile, rank)`, `(date, passed)`.

## 5. PR 쪼개기

| PR | 내용 | 런타임 영향 |
|----|------|-------------|
| 1 | `DailyScreeningCache` 모델 + `013_daily_screening_cache` 마이그레이션 + 설계 문서 | 0 |
| 2 | 스크리닝 엔진 모듈화 (`src/screening/engine.py`) + `DailyScreeningCacheStore` + `screen_symbols.py` 얇은 래퍼화 | 0 (회귀 스냅샷 유지) |
| 3 | Airflow DAG `postmarket/daily_screening.py` + backfill 스크립트 | 0 (장 마감 후) |
| 4 | `process_manager` + `live_trader` cache-miss 폴백 분기, `USE_PRESCREEN_CACHE` flag (기본 off) | flag on일 때만 |

각 PR는 독립 revertable. PR 1~3 머지 후에도 flag off 상태이므로 프로덕션 경로는 변하지 않는다.

## 6. Feature flag 전략
- `.env`에 `USE_PRESCREEN_CACHE=false` 기본.
- `live_trader --from-prescreen-cache` 인자 제공 → 수동 전환 가능.
- 캐시 miss/stale (같은 날짜 데이터 부재) → subprocess 폴백 + 경고 로그.

## 7. 롤백
- PR 4만 revert하면 flag 경로 제거 → 기존 subprocess 동작.
- PR 3 DAG pause → Airflow UI에서 즉시.
- PR 1~2는 테이블/모듈만 추가이므로 런타임 영향 없음.

## 8. 테스트 전략
- 모델 테스트: insert / upsert (ON CONFLICT DO UPDATE, 복합 PK) / 날짜·프로파일별 조회.
- 엔진 테스트: 기존 `screen_symbols` 스냅샷 테스트 회귀.
- DAG 테스트: DagBag 파싱 + Asset 토폴로지.
- flag on/off 경로 분기: cache hit / cache miss / stale 시나리오.

## 9. 의존
- Design 011 (PR #287~#294 머지 완료): `DailyCandle` 테이블과 `DailyCandleStore` 존재.

## 10. 관련 문서
- `.claude/rules/airflow.md` — Airflow DAG 컨벤션.
- `.claude/rules/python.md` — Python/테스트 규칙.
