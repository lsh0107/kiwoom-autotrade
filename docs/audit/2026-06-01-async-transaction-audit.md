# Long-lived AsyncSession Transaction Audit (2026-06-01)

> PR #495/#496 (realtime WebSocket transaction leak HOTFIX) 의 후속 audit.
> 코드 변경 0. 진단 보고만. 같은 패턴 (broker_credentials / orders / trade_logs / strategies row lock 유발) 이 다른 long-lived 경로에 있는지 확인.

## 1. 범위

- WebSocket endpoint
- live_trader / process_manager
- reconciler
- background task (BackgroundTasks / asyncio.create_task)
- broker token refresh / save 경로
- scheduler (APScheduler)
- 위 경로에서 사용되는 핵심 row: `broker_credentials`, `orders`, `trade_logs`, `strategies`, `strategy_configs`

## 2. 정책

| 정책 | 적용 |
|---|---|
| broker / order / live_trader 동작 변경 | 금지 |
| fake fallback 도입 | 금지 |
| 본 PR 에서 코드 변경 | 0 (진단만) |
| 후속 수정은 별도 PR | 권장 (위험 등급별) |

## 3. 위험 등급

- **P0** — 현재 운영에서 leak 가능. 별도 수정 PR 권장.
- **P1** — 미래 변경에 따라 leak 가능. 가드 추가 권장.
- **P2** — 현재 leak 아님. 일관성 / 방어적 개선 후보.

## 4. 경로별 진단

### 4.1 WebSocket — `src/api/v1/realtime.py::market_websocket`

| 항목 | 값 |
|---|---|
| session 수명 | `db=Depends(get_db)` → WebSocket 종료 시까지 long-lived |
| 핵심 row | `broker_credentials` (SELECT + UPDATE), `orders` (SELECT + UPDATE) |
| HOTFIX 적용 | ✅ PR #495 (SELECT 후 commit, `_get_token()` 후 commit/rollback) |
| `on_order_exec` 콜백 | 자체 `db.commit()` / `rollback()` 사용 — OK |
| `on_tick` 콜백 | DB 미사용 — OK |
| 등급 | ✅ 해소 |

### 4.2 token refresh/save — `src/broker/token_store.py` + `src/broker/kiwoom.py::ensure_token`

| 항목 | 값 |
|---|---|
| `token_store.save()` 내부 | `await db.flush()` 만. **`commit()` 안 함** (호출자 책임) |
| `token_store.get_or_refresh_token()` | SELECT(load) + UPDATE(save) 호출. commit 책임 호출자 |
| `KiwoomClient.ensure_token()` | line 220~ — `self._db` 있으면 `get_or_refresh_token` 호출. 자체 commit 없음. **호출자가 commit 안 하면 leak** |
| 직접 호출자 | `src/api/v1/realtime.py::_get_token` (✅ HOTFIX 후 commit), `KiwoomClient._request` 내부 (각 endpoint 의 단일 request 당 호출 — endpoint 가 commit 책임) |
| 등급 | **P1** |

**P1 사유**: 현재 호출자 (realtime / account.py / 기타 endpoint) 의 commit 의무가 암묵적. 새로운 호출자가 들어올 때 commit 빠뜨릴 가능성 큼. **§6 의 설계안** 으로 short-lived session 옵션 도입 권장.

### 4.3 background task — `src/api/v1/bot.py::_start_bg`

| 항목 | 값 |
|---|---|
| 진입 | `request.app.state._start_task = asyncio.create_task(_start_bg())` |
| session 수명 | `async with async_session_factory() as session:` (factory) → block 종료 시 close |
| 호출 대상 | `TradingProcessManager.start(session)` → `_launch_process(session)` → `_run_screening` + `_build_args_from_db` + `subprocess` |
| DB 사용 | SELECT(StrategyConfig) only. UPDATE/INSERT 없음 |
| commit | 명시 없음 — async with 종료 시 SQLAlchemy AsyncSession 의 default 정리 (rollback) |
| 등급 | **P2** |

**P2 사유**: 현재 SELECT-only 라 leak 없음 (SELECT 만 으로는 row lock 점유 안 함). 단, 미래에 process_manager 가 UPDATE 를 도입하면 즉시 leak 위험. 명시 commit/rollback 가드 추가 권장.

### 4.4 scheduler — `src/config/scheduler.py::_run_active_strategies`

| 항목 | 값 |
|---|---|
| 진입 | APScheduler cron trigger |
| session 수명 | `async with async_session_factory() as db:` → block 종료 시 close |
| DB 사용 | SELECT(Strategy) + `engine.run_analysis(..., db=db, ...)` 위임 |
| KiwoomClient | `settings.kiwoom_app_key` 사용 — **DB BrokerCredential 무관** (`db=` 안 받음) |
| broker_credentials lock 위험 | ❌ 없음 |
| 등급 | **P2** (engine.run_analysis 내부에서 commit 누락 시 분석 시간 동안 다른 row lock 가능 — 별도 audit) |

### 4.5 short_swing_reconciler — `src/trading/short_swing_reconciler.py::reconcile_short_swing_positions`

| 항목 | 값 |
|---|---|
| session 수명 | 외부에서 주입 (`db: AsyncSession`) |
| DB 사용 | SELECT(Order) 다회 + UPDATE |
| commit | line 270 `await db.commit()` ✅ 명시 |
| 등급 | ✅ 정상 |

### 4.6 cross_momentum_rebalance — `src/trading/cross_momentum_rebalance.py` line 793 부근

| 항목 | 값 |
|---|---|
| session 생성 | `gate_db = async_session_factory()` (context manager 미사용 — 객체 직접 호출) |
| 정리 | except 분기에서 `await gate_db.close()` 명시 |
| 정상 종료 | 그 이후 코드 (Phase 1 SELL) 까지 살아 있음. 명시 close 추가 확인 필요 (해당 try/finally 블록 끝) |
| 등급 | **P1** |

**P1 사유**: `async_session_factory()` 를 `async with` 없이 호출하면 finally 보장 없이 close. 코드 흐름 중 예외 발생 시 session leak 가능. 핵심 row UPDATE 가 그 안에서 일어나면 lock 점유 위험. 별도 audit 시 finally 정리 / context manager 전환 권장.

### 4.7 다른 WebSocket endpoint

| 항목 | 값 |
|---|---|
| 검색 결과 | `src/api/v1/realtime.py` (1 개) + `src/broker/realtime.py` (라이브러리) 만 |
| 추가 WebSocket endpoint | ❌ 없음 |
| 등급 | ✅ |

## 5. 핵심 row 사용처 요약

| 테이블 | SELECT 위치 | UPDATE 위치 | leak 위험 |
|---|---|---|---|
| `broker_credentials` | `realtime.py`, `settings.py`, `deps.py`, `token_store.py` | `token_store.save()` | **P1** (token_store 호출자 commit 의무 암묵) |
| `orders` | `realtime.py`, `short_swing_cancel.py`, `order_service.py`, `short_swing_reconciler.py` | (각 모듈) | ✅ 호출자별 명시 commit 확인 (위 §4) |
| `trade_logs` | 검색 결과 0건 (SELECT) | (별도 audit 필요 시) | — |
| `strategies` | `scheduler.py`, `bot.py` | (검색 결과 없음 — 별도 확인) | ✅ |

## 6. 설계안 — short-lived session 기반 token refresh

### 6.1 동기

현재 `token_store.save()` 의 commit 책임이 호출자에게 있음. realtime.py HOTFIX 처럼 호출자마다 명시 commit 을 추가하는 방식은 다음 호출자가 빠뜨리기 쉬움. **token UPDATE 의 transaction lifecycle 을 호출자 무관하게 자기 self-contained** 로 만드는 게 항구적.

### 6.2 옵션 A — `token_store` 에 short-lived session 헬퍼 추가

`src/broker/token_store.py` 에 신규 함수:

```python
from src.config.database import async_session_factory

async def get_or_refresh_token_isolated(
    credential_id: uuid.UUID,
    authenticate_fn: Callable[[], Awaitable[TokenInfo]],
) -> str:
    """호출자의 session 과 무관하게 short-lived session 으로 토큰 조회/저장.

    호출자가 long-lived AsyncSession 을 들고 있더라도 broker_credentials
    UPDATE 트랜잭션은 본 함수 안에서 commit 후 close → row lock 즉시 해소.
    """
    async with async_session_factory() as isolated_db:
        token = await get_or_refresh_token(credential_id, isolated_db, authenticate_fn)
        await isolated_db.commit()
        return token
```

호출자 변경:
- `KiwoomClient.ensure_token()` 가 `self._db` 가 있어도 위 isolated 함수 사용
- realtime.py 의 `_get_token` 콜백은 별도 commit 불필요 (단, 호환성 유지)

장점:
- 호출자 무관하게 broker_credentials transaction lifecycle 자체 완결
- 기존 commit 호출은 no-op (이미 commit 됨) — 회귀 0
- realtime.py 의 HOTFIX commit 라인은 유지해도 무해 (방어 차원)

단점:
- session factory 의존 — `src/broker/token_store.py` 가 `src/config/database` 를 import (현재는 안 함). 의존성 단방향 검토 필요
- 매 token 조회마다 새 connection (pool 에서 빌림) — 성능 영향 작음 (token 캐시 히트 시 SELECT 1번 + commit)

### 6.3 옵션 B — `KiwoomClient` 에 `session_factory` 주입

`KiwoomClient.__init__` 에 `db` 대신 `session_factory: Callable[[], AsyncSession]` 받기. ensure_token 내부에서 session 매번 생성/정리.

장점:
- 모든 호출자에서 일관
- 호출자의 session 과 완전 분리

단점:
- KiwoomClient 의 시그니처 변경 (큰 변경) — broker 동작 정책 부합 여부 사용자 결정
- 모든 호출자 (realtime / account / 기타) 마이그레이션 필요

### 6.4 추천

**옵션 A** (token_store 에 isolated 헬퍼 추가). KiwoomClient 시그니처 변경 없음, 호출자 무관 안전, 회귀 위험 최소.

## 7. 후속 별도 PR 후보 (사용자 결정)

| # | 작업 | 등급 | 범위 |
|---|---|---|---|
| 1 | `token_store.get_or_refresh_token_isolated` 추가 (§6.4) + `KiwoomClient.ensure_token` 가 isolated 우선 사용 | P1 | broker token 경로만, 시그니처 호환 |
| 2 | `cross_momentum_rebalance` 의 `async_session_factory()` 직접 호출을 `async with` 로 전환 (finally 보장) | P1 | trading 모듈 (broker 동작 변경 아님 — session lifecycle 만) |
| 3 | `bot.py::_start_bg` 의 `async with` 블록에 명시 `commit/rollback` 가드 | P2 | 미래 leak 예방 |
| 4 | `engine.run_analysis` (scheduler 안) 의 session 사용 audit | P2 | 분석 모듈 별도 |
| 5 | 정기 모니터링: `pg_stat_activity` 에서 `idle in transaction` 지속 시간 임계 초과 시 알림 | P2 | 운영 점검 |

## 8. 진단에 사용한 명령 / 코드 위치 (재현용)

```bash
# 좀비 세션 탐색 (재현)
docker exec kiwoom-autotrade-postgres-1 psql -U kiwoom -d kiwoom_trade -c "
SELECT pid, state, wait_event_type, wait_event,
       (now() - xact_start) AS xact_age,
       substring(query, 1, 100) AS query_head
FROM pg_stat_activity
WHERE datname = 'kiwoom_trade'
  AND state = 'idle in transaction'
ORDER BY xact_start NULLS LAST;"

# row lock 보유자
docker exec kiwoom-autotrade-postgres-1 psql -U kiwoom -d kiwoom_trade -c "
SELECT l.pid, l.mode, l.granted, c.relname, a.state
FROM pg_locks l
JOIN pg_class c ON c.oid = l.relation
LEFT JOIN pg_stat_activity a ON a.pid = l.pid
WHERE c.relname IN ('broker_credentials','orders','trade_logs','strategies')
  AND l.granted = true;"
```

검토 위치:
- `src/api/v1/realtime.py::market_websocket` (HOTFIX 적용)
- `src/broker/token_store.py::save / get_or_refresh_token` (commit 의무 암묵)
- `src/broker/kiwoom.py::ensure_token` line 220 부근
- `src/trading/process_manager.py::start`
- `src/config/scheduler.py::_run_active_strategies`
- `src/trading/cross_momentum_rebalance.py` line 793 부근
- `src/api/v1/bot.py::_start_bg` line 336

## 9. 결론

- **현재 운영 P0 risk 없음**. PR #495 HOTFIX 로 알려진 leak 해소.
- **P1 risk 2건**: `token_store` commit 의무 암묵 (§4.2), `cross_momentum_rebalance` session factory 미관리 (§4.6).
- **P2 risk 3건**: `bot.py _start_bg`, `engine.run_analysis`, 정기 모니터링.
- **권장**: §6 옵션 A (short-lived isolated token refresh) 로 P1 의 token 부분 해소. 코드 진입은 별도 PR + 사용자 OK.
- 본 audit 범위 외: `trade_logs` (검색 결과 select 0건), 다른 background task 의 row UPDATE 패턴 (필요 시 별도 audit).
