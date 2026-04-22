---
name: design-009-market-context-integration
description: MarketContext 수급/테마 getter를 live_trader 매매 판단에 단계적 통합
type: design
status: 활성 (PR A · PR B · PR C 완료)
created: 2026-04-20
---

## 상태 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-22 | stocks.theme NULL 이슈 발견 → PR #321로 백필 완료. ThemeBoost 정상 동작 복원. |

# Design 009: MarketContext 수급/테마 통합 (FlowSignal + ThemeDetector)

## 1. 배경

- Airflow 수집 파이프라인(`market_data.investor_trading`, `market_data.stock_investor_flow`, `llm_briefings.theme_scores`)이 이미 DB에 축적 중.
- `src/trading/market_context.py`의 `MarketContext`는 5개 getter(`get_vkospi`, `get_kospi_above_ma12`, `get_investor_flow`, `get_stock_investor_flows`, `get_theme_scores`)를 제공하지만, `scripts/live_trader.py`는 VKOSPI/KOSPI 레짐만 소비하고 있음.
- `src/strategy/flow_signal.py`(`FlowSignal`), `src/strategy/theme_detector.py`(`ThemeDetector`)는 단위 테스트만 존재하고 `live_trader`에서 import 0회 → 사실상 dead code.

## 2. 목표

매매 판단에 수급·테마 시그널을 점진적으로 반영하되, 금융 거래 시스템 특성상 **관찰 → 가산점 → 전면 적용**의 단계를 거친다. 모든 신규 로직은 **feature flag 기본 OFF**로 보호되어 플래그만 끄면 즉시 원복된다.

### 비목표 (현 단계에서 다루지 않음)
- **백테스트 엔진 적용**: `src/backtest/engine.py`, `src/backtest/mr_engine.py`의 수급/테마 반영은 본 설계 범위에서 제외. 라이브 데이터(시점별 DB 스냅샷)가 아닌 일별 저장소로 재설계가 필요하므로 별도 설계서에서 다룬다. 라이브 선반영.
- `FlowSignal` / `ThemeDetector`의 시그니처 변경: 사용만 추가하고 모듈 내부 로직은 변경 금지.

## 3. 단계적 배포 계획

### PR A — observe-only (본 PR)

- `_refresh_regime()`, main 블록 초기 `market_ctx.refresh()` 직후 `_log_market_context_observation()` 호출.
- 로그 3줄: 시장 수급 / 테마 상위 5 / 감시 종목 수급 매칭 수.
- **매매 판단 경로 변경 0** → 완전 무영향, 데이터 오작동(빈 dict, 테마 점수 타입 이상 등) 조기 감지용.
- 테마 점수는 상위 5개 key + 점수만 로그. 원문 전체 dump 금지(보안 정책).

### PR B — `USE_FLOW_SIGNAL` (구현 완료, 본 PR)

환경변수 `USE_FLOW_SIGNAL=true` 시 `FlowSignal`을 진입 조건에 반영.

적용 대상: **모멘텀 전략만** (`poll_cycle` / WS `handle_tick` 내 `strat.name == "momentum"` 분기).
평균회귀 전략은 수급 역행성이 있어 기본 반영 안 함.

판정 수식(구현):
```
if not _is_flow_signal_enabled():
    return False  # flag off — 기존 경로 100%
flow = FlowSignal(market_flow=market_ctx.get_investor_flow(),
                  stock_flows=market_ctx.get_stock_investor_flows())
score = flow.score(symbol)
if score <= FLOW_SIGNAL_BEARISH_THRESHOLD (-0.2):
    block entry   # 진입 차단 + 로그
```

- 가산점 로직은 본 PR 미포함 — 향후 `confidence` 체계 도입 시 확장 예정.
- MarketContext None, investor_flow 빈 dict, FlowSignal 예외 시 **차단 안 함**(기존 경로 유지) — feature-flag 안전장치.
- 기본값: `USE_FLOW_SIGNAL=false` → 기존 경로 그대로.

### PR C — `USE_THEME_BOOST` (구현 완료, 본 PR)

환경변수 `USE_THEME_BOOST=true` 시 `ThemeDetector.get_theme_score(symbol)`가 낮은 종목(cold)의 모멘텀 진입을 차단. 기존 `confidence` 체계가 없어 "가산점"은 상대적으로 구현 — **hot/중립 테마 통과, cold(< 0.3) 차단** = 사실상 핫 테마 가산 효과.

판정 수식(구현):
```
if not _is_theme_boost_enabled():
    return False  # flag off — 기존 경로 100%
theme_scores = market_ctx.get_theme_scores()
sector_map = _build_sector_map(symbols)  # SECTOR_MAP(symbol→sector)의 역변환
detector = ThemeDetector(theme_scores=theme_scores, sector_map=sector_map)
if detector.get_theme_score(symbol) < THEME_COLD_THRESHOLD (0.3):
    block entry   # 진입 차단
```

- `_build_sector_map(symbols)`: `scripts.screen_symbols.get_sector()`를 사용해 감시 유니버스의 symbol→sector을 sector→[symbols]로 역변환.
- 모멘텀에만 적용(평균회귀는 테마 무관 기술적 진입이라 제외).
- 안전장치: MarketContext None / 빈 theme_scores / 미분류 종목이 많은 경우 다수가 차단되지 않도록 — theme_scores 빈 dict면 차단 **안 함**(데이터 부재 시 기존 경로).
- 기본값: `USE_THEME_BOOST=false`.

### 주의 — 가산점 미구현

기존 전략은 `confidence`/`score` 기반이 아닌 boolean 진입 신호이므로, PR C는 "가산점" 대신 "cold 차단"을 선택. `confidence` 체계 도입 후 가산점 재검토.

## 4. feature flag 기본 OFF 이유

- 라이브 매매에 즉시 로직 변경 금지(금융 리스크).
- Airflow DB 데이터의 스키마/빈도/신뢰도를 관찰 로그로 최소 1주일 이상 모니터링 후 활성화.
- 활성화 실패 시 플래그 off만으로 즉시 롤백 가능 → 코드 제거 PR 불필요.

## 5. 활성화 절차

1. PR A 머지 후 1주일 라이브 운영 — observe 로그로 데이터 건전성 확인.
2. 빈 dict / 타입 이상 발생 빈도 0이면 PR B 머지 → 스테이징에서 `USE_FLOW_SIGNAL=true` 24시간 드라이런.
3. 이상 없으면 프로덕션 활성화. 이상 발견 시 플래그 off로 롤백.
4. 동일 절차로 PR C(`USE_THEME_BOOST`).

## 6. 롤백 절차

- 코드 원복 PR 불필요. 환경변수만 제거/false로 돌리면 원복.
- 긴급 시 .env 수정 후 live_trader 프로세스 재시작(systemd/docker restart).

## 7. 관련 파일

- 수정: `scripts/live_trader.py` (observe 로그 주입)
- 참조: `src/trading/market_context.py` (getter 호출만, 수정 없음)
- 참조: `src/strategy/flow_signal.py`, `src/strategy/theme_detector.py` (PR B/C에서 import만 추가)
- 테스트: `tests/test_live_trader.py` (observe 로그 유닛 케이스)

## 8. 보안

- theme_scores 로그 시 원문 dump 금지 — 상위 5개 key+score만.
- DB 연결 문자열, PAT, 토큰은 로그 0(기존 `MarketContext` 정책 유지).
