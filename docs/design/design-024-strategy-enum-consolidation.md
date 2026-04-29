---
name: design-024-strategy-enum-consolidation
description: ACTIVE_STRATEGY enum 단일화 + default poll_cycle 가드. 두 boolean (USE_MULTI_REGIME / USE_CROSS_MOMENTUM) 폐기.
type: design
status: 활성 — 즉시 enum-only 갈아끼움 완료, 모의 4주 관찰 시작 가능
created: 2026-04-29
depends_on:
  - design-013-multi-regime-strategy
  - design-021-cross-sectional-momentum
  - design-022-cross-momentum-live-adapter
  - design-023-cross-momentum-hardening
related:
  - src/config/active_strategy.py
  - scripts/live_trader.py
  - src/trading/cross_momentum_rebalance.py
  - .env.example
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-29 | ADR-024 신규: ACTIVE_STRATEGY enum 통합 + default poll_cycle 가드 결정 |
| 2026-04-29 | 즉시 enum-only 갈아끼움 (호환 코드 없음). 1874 회귀 PASS |
| 2026-04-29 | `.env` 갱신 (USE_* 삭제, ACTIVE_STRATEGY=cross_momentum 추가). 모의 4주 관찰 진입 |

---

# Design 024: ACTIVE_STRATEGY enum 통합 + default loop 가드 (ADR-024)

## 1. 배경

### 1-1. 두 boolean의 invalid state 위험
ADR-022(`USE_CROSS_MOMENTUM`)와 ADR-013(`USE_MULTI_REGIME`)이 별개 boolean으로 도입되며, 둘 동시 ON이라는 invalid 조합이 표현 가능했음. 이를 막기 위해 `validate_cross_momentum_exclusivity`가 부팅 시 `SystemExit(1)`로 차단했지만:
- 검증 코드 자체가 부담 (단일 enum이면 불필요)
- 사용자 실수 가능성 잔존 (실제 2026-04-29에 `.env` 양쪽 ON으로 부팅 실패 발생)
- 기존 boolean 검증 테스트 3개가 ADR-022 테스트 영역에 잔존

### 1-2. default poll_cycle 누락 (치명적)
ADR-022 어댑터가 `_check_monthly_rebalance`만 추가하고 `poll_cycle` (default single-asset 매매)는 그대로 둠 →

`USE_CROSS_MOMENTUM=true` 설정해도 매 5분 polling cycle에서 **ADR-016 폐기 5분봉 모멘텀 매매가 동시 진행**되는 구조.
- ADR-016 폐기 사유: 왕복비용 0.53% × 일 5거래 = 일 -2.65% 비용
- 결과: cross-momentum 모의 4주 관찰 = default 손실 매매에 묻혀 평가 불가능

이건 ADR-022 설계 단계의 누락 — **모의 진입 직전에 발견.**

### 1-3. ADR-022/023 미해결 부채
- `USE_*` 환경변수 직접 참조 라인이 live_trader.py / cross_momentum_rebalance.py에 산재
- `_is_multi_regime_enabled`, `_is_cross_momentum_enabled` 두 함수 분리
- 의미상 "활성 전략 1개"인데 코드는 "두 독립 flag"로 표현

## 2. 결정

### 2-1. 단일 enum 도입
```python
class ActiveStrategy(StrEnum):
    CROSS_MOMENTUM = "cross_momentum"
    MULTI_REGIME = "multi_regime"
    NONE = "none"
```

- 환경변수: `ACTIVE_STRATEGY` (기본값 `none`)
- invalid 값은 `none`으로 폴백 (시스템 idle = 안전 default)
- whitespace/대소문자 무관 (`.strip().lower()`)

### 2-2. 기존 두 boolean flag 폐기 (호환 X)
- `USE_CROSS_MOMENTUM`, `USE_MULTI_REGIME` 환경변수 **즉시 무시**
- `validate_cross_momentum_exclusivity` 함수 + 호출 전부 삭제
- `_is_multi_regime_enabled` 함수 삭제, 호출처는 `get_active_strategy() == MULTI_REGIME`로 교체
- `_is_cross_momentum_enabled` 함수는 시그니처 유지하되 내부 로직만 enum 사용

호환 코드 추가 X — invalid state representable 문제를 점진 마이그레이션이 아닌 즉시 갈아끼움으로 해소.

### 2-3. default poll_cycle 가드
`run_trading_loop`(line 1962)에 strategy_mode 분기:
```python
strategy_mode = get_active_strategy()
if strategy_mode == ActiveStrategy.CROSS_MOMENTUM:
    await _check_monthly_rebalance(...)  # 월말만
elif strategy_mode == ActiveStrategy.MULTI_REGIME:
    await poll_cycle(...)  # 기존 동작
else:  # NONE
    log.info("ACTIVE_STRATEGY=none — 매매 비활성")
```

### 2-4. WS 모드 가드
`run_trading_loop_ws`은 tick 기반 매수/매도라 별도 가드. main에서 args.mode 분기 시 ACTIVE_STRATEGY != MULTI_REGIME이면 WS → polling 강제 전환:
```python
if args.mode == "ws" and active != ActiveStrategy.MULTI_REGIME:
    args.mode = "polling"  # default tick 매매 차단
```

## 3. 데이터 흐름

| 모드 | 매매 활성 항목 |
|------|----------------|
| `cross_momentum` | 매월 마지막 영업일 14:55 monthly rebalance만. polling/WS tick 매매 모두 비활성 |
| `multi_regime` | 기존 5분 polling (multi-regime 분배) — ADR-013 walk-forward 미통과로 운영 비추 |
| `none` | 모든 매매 비활성 (시스템 idle, kill_switch 모니터만) |

## 4. .env 변경

기존:
```
USE_CROSS_MOMENTUM=true
USE_MULTI_REGIME=false
```

신규:
```
ACTIVE_STRATEGY=cross_momentum
```

`.env.example`도 동일하게 갱신 (기존 `USE_*` 라인은 .env.example에 없었음).

## 5. 테스트

| 영역 | 결과 |
|------|------|
| `tests/config/test_active_strategy.py` (신규) | 8 PASS — 기본값/유효값/대소문자/whitespace/잘못된값/빈값 |
| `tests/scripts/test_live_trader_multi_regime.py` (갱신) | 58 PASS — TestMultiRegimeFlag 클래스 ACTIVE_STRATEGY 기반으로 재작성 |
| `tests/trading/test_cross_momentum_rebalance.py` (갱신) | exclusivity 테스트 3개 삭제, monkeypatch USE_* → ACTIVE_STRATEGY |
| `tests/trading/test_cross_momentum_rebalance_t2.py` (갱신) | monkeypatch USE_CROSS_MOMENTUM → ACTIVE_STRATEGY |
| 전체 회귀 | **1874 PASS** (1872+신규 8 - 폐기 6) |
| ruff/mypy | clean |

## 6. 마이그레이션 결정 근거: 점진 vs 즉시

### 점진 (deprecation warning + 호환 라인 유지)
- 장점: 기존 사용자 환경 무중단
- 단점: 호환 코드 부담 + invalid state 표현 가능성 잔존 + 다음 정리 ADR 필요

### 즉시 (호환 X) ← **선택**
- 장점: 코드 정리 1회 완결, invalid state 즉시 불가능
- 단점: 운영 환경 .env 직접 수정 필요 (단일 사용자 환경이라 비용 낮음)

본 프로젝트는 단일 운영자 환경 + 모의 진입 직전 상태라 즉시 마이그레이션 비용이 매우 낮음. 점진 마이그레이션의 호환 코드 부채가 즉시 갈아끼움의 일회성 .env 수정보다 큼.

## 7. 운영 변경

### 모의 진입
- 사용자: `.env`에 `ACTIVE_STRATEGY=cross_momentum` 설정 (기존 USE_* 라인 삭제)
- 리드: `docker compose restart backend` + JWT 생성 + `POST /api/v1/bot/trading/start`
- 부팅 로그에서 `ACTIVE_STRATEGY=cross_momentum` 확인
- 다음 trigger: **2026-05-29 (금) 14:55**

### 모드 전환
- multi-regime 검증 시: `.env`에서 `ACTIVE_STRATEGY=multi_regime`로 변경 후 재기동
- 정지: `ACTIVE_STRATEGY=none` 또는 trading/stop API

## 8. 후속 작업 (별도 ADR 후보)

본 ADR 범위가 아닌 후속 정리:

| 항목 | 설명 |
|------|------|
| `LIVE_TRADER_USER_ID` 환경변수 제거 | design-014 임시 처방 — dev user 자동 시드 + email fallback 정정으로 대체 (ADR-014 후속) |
| `t2_pending` DB 영속화 | ADR-023 follow-up TODO 1번. 재기동 후 손실 방지 |
| 매년 12월 KRX 캘린더 갱신 절차 | ADR-023 follow-up TODO 2번 |
| 임시공휴일 자동 동기화 | ADR-023 follow-up TODO 3번. Airflow DAG 후보 |

## 9. 교차 참조

- design-013: USE_MULTI_REGIME → ActiveStrategy.MULTI_REGIME으로 매핑
- design-021: cross-momentum walk-forward V2 PASS — 본 ADR로 운영 활성
- design-022: monthly rebalance 어댑터 — 본 ADR로 default poll_cycle 차단
- design-023: 견고화 (rate limit / T+2 / 공휴일) — 본 ADR로 운영 가드 추가
- operations/strategy-redesign-rollout: 모의 진입 절차 ACTIVE_STRATEGY enum 기반으로 갱신
