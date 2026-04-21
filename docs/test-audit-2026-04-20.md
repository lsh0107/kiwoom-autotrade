# 테스트 감사 보고서 (2026-04-20)

> T5-B 후속 감사. PR #236에서 boilerplate 48개 제거 완료 이후, 나머지 약 97개의
> 저품질 테스트를 카테고리별로 분류하고 단계적 정리 계획을 제시한다.

## 1. 현황 집계

| 항목 | 값 |
|------|-----|
| 테스트 파일 수 | 72 |
| 총 테스트 함수 수 (`def test_`) | 1,155 |
| `pytest --collect-only` 집계 | 1,205 (parametrize 포함) |
| 테스트 총 LoC | 18,870 |
| 보호 가드레일 | 커버리지 85%+ 유지 (MANDATORY) |

### Mock 사용량 Top 15 (implementation coupling 위험 지표)

```
tests/test_live_trader.py              193
tests/broker/test_realtime.py           78
tests/trading/test_process_manager.py   67
tests/ai/test_llm_clients.py            36
tests/notification/test_telegram.py     34
tests/scripts/test_live_trader_swing.py 22
tests/api/test_bot_process.py           21
tests/trading/test_market_context.py    20
tests/api/test_realtime.py              20
tests/ai/test_data_collectors.py        20
tests/ai/llm/test_gemini_client.py      19
tests/broker/test_ws_contract.py        18
tests/backtest/test_data_fetcher.py     14
tests/ai/test_manager.py                14
tests/utils/test_time.py                13
```

### `assert_called*` 사용량 Top (호출 상세 검증)

```
tests/test_live_trader.py        13
tests/ai/test_manager.py         13
tests/broker/test_token_store.py  8
tests/broker/test_realtime.py     7
tests/scripts/test_live_trader_swing.py 5
```

---

## 2. 문제 카테고리 분류

### 2.1 Redundant (중복 — 삭제/병합)

동일 행동을 여러 파일/위치에서 중복 검증.

| 파일 | 라인 | 테스트 | 중복 대상 | 처리 |
|------|------|--------|----------|------|
| `tests/broker/test_ws_contract.py` | 51 | `test_login_request_matches_spec` | `test_realtime.py::test_login_sends_trnm_login` (L270) | **병합** → contract만 유지 |
| `tests/broker/test_ws_contract.py` | 72 | `test_bearer_prefix_stripped_before_send` | `test_realtime.py::test_login_strips_bearer_prefix` (L282) | **삭제 (contract 쪽)** 또는 중복 제거 |
| `tests/broker/test_ws_contract.py` | 92 | `test_login_success_returns_true` | `test_realtime.py::test_login_returns_true_on_success` (L296) | **삭제** (realtime에서 이미 검증) |
| `tests/broker/test_ws_contract.py` | 115-194 | 6개 subscribe_*_matches_spec | `test_realtime.py::test_subscribe_*` (L336~415) | **병합** → contract만 유지하고 realtime은 제거 |
| `tests/broker/test_ws_contract.py` | 220 | `test_unsubscribe_has_no_refresh_field` | `test_realtime.py::test_unsubscribe_has_no_refresh_field` (L443) | **삭제** (realtime 쪽) |
| `tests/broker/test_ws_contract.py` | 173 | `test_subscribe_is_flat_not_nested` | `test_realtime.py::test_subscribe_is_flat_not_nested` (L405) | **삭제** (realtime 쪽) |
| `tests/broker/test_ws_contract.py` | 350 | `test_ping_triggers_pong_response` | `test_realtime.py::test_ping_triggers_pong_response` (L475) | **삭제** (realtime 쪽) |
| `tests/broker/test_realtime.py` | 1015, 1036, 1078, 1126 | `test_creation_with_required_fields`, `test_creation_with_all_fields` (4x) | Pydantic 모델 생성 boilerplate | **통합** → 단일 parametrize 테스트 |
| `tests/broker/test_realtime.py` | 1050, 1094, 1140 | `test_raw_field_defaults_to_empty_dict` (3x) | 동일 패턴 반복 | **통합** → parametrize |
| `tests/broker/test_realtime.py` | 1060, 1067, 1107, 1152 | `test_negative_*_raises_validation_error` (4x) | 동일 Pydantic 검증 | **통합** → parametrize |
| `tests/backtest/test_strategy.py` | 222, 257 | `test_zero_entry_price` (2회) | 동일 이름 | **확인 후 병합** |
| `tests/trading/test_market_regime.py` | 22, 30, 34 | `test_*_at_boundary` 3개 | 경계값 개별 테스트 | **병합** → parametrize |

**예상 제거량: ~18개**

### 2.2 Implementation Coupling (내부 구현 상세 의존 — 리팩토링)

동작이 아닌 "어떻게" 호출되는지를 assert. 리팩토링 시 부러짐.

| 파일 | 라인 | 문제 | 처리 |
|------|------|------|------|
| `tests/ai/test_manager.py` | 95, 108, 136, 137, 200, 218, 219, 235, 285, 286, 287, 301, 320 | `mock_*.complete.assert_called_once()` 13회 — fallback 체인이 특정 순서로 호출되는지 만 검증. 실제 반환값/fallback 동작은 검증 안 됨 | **재작성** → 반환값/결과 기반으로 전환. 예: 1차 실패 시 2차 반환값이 최종 결과와 같은지 |
| `tests/broker/test_token_store.py` | 62, 108, 109, 110 | `mock_decrypt.assert_called_once_with(...)`, `db.execute.assert_called_once()`, `db.flush.assert_called_once()` — ORM 내부 호출 방식 검증 | **재작성** → 저장 후 `load_token`으로 회복 가능한지 (round-trip) 검증 |
| `tests/trading/test_process_manager.py` | 82, 117, 175, 196, 215, 263 | `mock_result.scalars.return_value.all.return_value = ...` 체인 깊이 3+. SQLAlchemy 내부 체인을 고스란히 재현 | **리팩토링** → pytest-postgresql 또는 `AsyncSession` fake fixture로 ORM-level 검증 |
| `tests/scripts/test_live_trader_swing.py` | 188, 250, 335 | `mock_sell.assert_called_once()` — gap-risk/holding-limit 발생 시 `sell()` 함수가 호출되는지만 검증 | **재작성** → 실제 포지션 상태 변화 검증 (position dict 제거 확인 등) |
| `tests/test_live_trader.py` | 1238, 1367 | `mock_poll_loop.assert_called_once()`, `mock_update_drawdown.assert_called_once()` | **재작성** → 상태(TradingState) 변화로 검증 |
| `tests/notification/test_telegram.py` | (34 mocks) | TelegramClient 내부 send 호출만 검증 | **리팩토링** → fake transport로 대체 |
| `tests/api/test_bot_process.py` | (21 mocks) | 프로세스 시작 후 `popen.assert_called_with(...)` 패턴 | **리팩토링** → API 응답 status/logs로 검증 |

**예상 정리량: ~22개 재작성, ~6개 삭제**

### 2.3 Mock-Everything (실제 로직 검증 없음 — 통합/삭제)

외부 의존성뿐 아니라 SUT 내부까지 mock해 "실제 로직이 실행되지 않는" 테스트.

| 파일 | 라인 | 문제 | 처리 |
|------|------|------|------|
| `tests/test_live_trader.py` | 418~800대 | `async def test_entry_signal_triggers_buy` 류 — `trade_state`, `client`, 지표, 전략 판단까지 전부 mock. 결국 "mock이 올바르게 설정되었는지"만 검증 | **통합 스타일로 전환** → 실제 `MomentumParams` + 실제 `check_entry` + mocked `client`만. 또는 `tests/integration/` 디렉토리로 이동 |
| `tests/trading/test_market_context.py` | 272, 290, 307 | `test_refresh_updates_*` — DB 응답 값을 직접 mock하고, 같은 값이 state에 들어갔는지 assert (identity test) | **삭제 또는 재작성** → 실제 model 변환 로직 검증 |
| `tests/ai/test_data_collectors.py` | (20 mocks) | 외부 API 전체 mock 후 반환 파싱 검증 | **통합 테스트로 이동** (respx 기반) |
| `tests/trading/test_process_manager.py` | 151, 158, 205, 223, 233 | DB 설정 로드 테스트 — DB 전체 mock, 반환값을 assert. 실제 ORM 쿼리/매핑 미검증 | **재작성** → pytest-postgresql로 진짜 쿼리 실행, 또는 일부는 삭제 |
| `tests/backtest/test_data_fetcher.py` | (14 mocks) | 키움 API 응답 전체 mock 후 parsing 검증 | **유지 가능** (respx로 스위치) 또는 통합 테스트로 이동 |

**예상 정리량: ~25개 재작성 또는 이동, ~8개 삭제**

### 2.4 Useless Assertion (유효하지 않은 검증)

`assert True`, mock 반환값 그대로 검증, 타입 존재만 확인하는 테스트.

| 파일 | 라인 | 문제 | 처리 |
|------|------|------|------|
| `tests/strategy/test_base.py` | 29, 33 | `test_momentum_has_name`, `test_mean_reversion_has_name` — `strategy.name is not None`만 검증 | **삭제** (Pydantic 필드 검증과 중복) |
| `tests/strategy/test_base.py` | 19, 24, 37, 44 | `test_*_implements_protocol`, `test_check_entry_returns_bool` — isinstance/타입 힌트만 검증 | **삭제** (mypy가 이미 보장) |
| `tests/ai/test_models.py` | 13, 24, 120 | `test_create_with_required_fields`, `test_create_with_all_fields` — Pydantic 모델 생성 및 필드 접근 | **통합** → 하나의 parametrize로 단축 또는 삭제 |
| `tests/backtest/test_engine.py` | 180 | `test_result_has_params` — dataclass 필드 존재 검증 | **삭제** |
| `tests/backtest/test_mr_engine.py` | 139, 321 | `test_result_has_mr_params`, `test_metrics_fields_present` | **삭제** (dataclass 필드 검증은 무의미) |
| `tests/trading/test_market_regime.py` | 289, 294 | `test_string_equality`, `test_all_values_defined` (enum) | **삭제** (Python enum 기본 동작) |
| `tests/trading/test_market_regime.py` | 148, 153 | `test_all_regimes_have_allocation`, `test_allocation_sums_to_one` | 이건 **유지** (비즈니스 불변식) |
| `tests/strategy/test_flow_signal.py` | 13~213 (여러 개) | 개별 입력값에 대한 기계적 검증 (`test_both_buying_returns_positive`, `test_both_selling_returns_negative` 등) | **통합** → parametrize로 단축 |

**예상 제거량: ~18개**

---

## 3. 통합 요약

| 카테고리 | 삭제 | 재작성 | 병합/parametrize | 합계(축소) |
|----------|------|--------|-------------------|-----------|
| Redundant | 10 | 0 | 8 | 18 |
| Implementation coupling | 6 | 22 | 0 | 6 (순감) |
| Mock-everything | 8 | 25 | 0 | 8 (순감) |
| Useless assertion | 13 | 0 | 5 | 18 |
| **합계** | **37** | **47** | **13** | **~50 순감 + ~47 리팩토링** |

> 목표: 제거/병합 중심으로 약 60~70개 순감(부채 해소), 실제 로직 검증 강화 47개.

---

## 4. 분할 PR 계획

각 PR마다:
- 커버리지 85%+ 유지 확인 (`uv run pytest --cov=src --cov-report=term-missing`)
- `claude` 기준 분기 → feat 브랜치 push → `dev` PR(squash) → `main` PR(merge commit)
- 세션 기록(`sessions/YYYY-MM-DD.md`)

### PR 1 (본 PR): 감사 문서만 (코드 변경 0)
- `docs/test-audit-2026-04-20.md` 신규

### PR 2: broker 영역 정리 (10~18개)
대상 파일:
- `tests/broker/test_ws_contract.py` ↔ `tests/broker/test_realtime.py` 중복 통합 (contract가 계약/realtime이 구현 테스트 역할 명확화)
- `tests/broker/test_realtime.py` L1015~1160 Pydantic 모델 boilerplate parametrize
- `tests/broker/test_token_store.py` assert_called 기반 테스트 → round-trip 검증으로 재작성

브랜치: `test/cleanup-broker-1`

### PR 3: strategy 영역 정리 (10~15개) ✅ 완료
대상:
- `tests/strategy/test_base.py` protocol/name 검증 삭제 (5개 제거), `check_exit_signal` 래퍼 behavior 테스트 3개 신규 추가
- `tests/strategy/test_flow_signal.py` 개별 값 테스트 parametrize 통합 (14개 → 3개 parametrized)

브랜치: `test/cleanup-strategy-1`
결과: 104 → 99 테스트 (-5), strategy 모듈 커버리지 96.48% 유지, 전체 커버리지 90.54%

### PR 4: trading 영역 정리 (15~20개)  **[완료: test/cleanup-trading-1, 2026-04-20]**
대상:
- `tests/trading/test_market_regime.py` enum/boundary 테스트 정리
- `tests/trading/test_market_context.py` mock-everything 재작성
- `tests/trading/test_process_manager.py` 깊은 mock 체인 리팩토링 (일부는 삭제)
- 제외: `tests/test_live_trader.py` (T5-C 별도 PR)

결과:
- `test_market_regime.py`: 경계값 테스트 11개 → 단일 `test_regime_matrix` parametrize (10 cases), `TestMarketRegimeEnum` 클래스 삭제 (2 tests — Python enum 기본 동작)
- `test_market_context.py`: identity test(직접 `ctx._* = value`) 9개 → `_apply_*` 메서드 경로 기반 통합 테스트로 재작성. 실제 Airflow 페이로드 변환 로직 검증
- `test_process_manager.py`: `_FakeAsyncSession` fake fixture 도입 → SQLAlchemy chain mock 깊이 3+ (`scalars.return_value.all.return_value`) 8개 호출 완전 제거, implementation coupling 해소
- items 235 → 233 (-2), 전체 1274 tests 통과, 전체 coverage **90.64%** 유지

브랜치: `test/cleanup-trading-1`

### PR 5: ai 영역 정리 (완료)
대상:
- `tests/ai/test_manager.py` assert_called_once 13회 → 반환값/비용 기반 재작성, mode/chain parametrize
- `tests/ai/test_models.py` Pydantic boilerplate parametrize 통합 (13 → 13, 3 테스트 함수로 압축)
- `tests/backtest/test_engine.py` · `test_mr_engine.py` dataclass 필드 존재 테스트 삭제 → 후속 작업(T5-C)으로 이동

브랜치: `test/cleanup-ai-1`
status: **완료 (2026-04-20)**. 테스트 수 156 유지, 커버리지 93.49% 유지, `assert_called_*` 13 → 0 (순수 `call_count` 1회 사용).

> 5개 PR 제한. `tests/test_live_trader.py`는 범위가 커서 별도 후속 작업(T5-C)으로 분리.

### PR 6: test_live_trader 정리 (T5-C) **[완료: test/cleanup-live-trader, 2026-04-21]**
대상: `tests/test_live_trader.py` 단일 파일

결과:
- def test_ 함수 수: 111 → 79 (-32)
- mock/Mock/patch 참조: 421 → 393 (-28)
- `assert_called*` 사용: 7 → 4 (-3)
- LoC: 2,644 → 2,561 (-83)
- 실제 테스트 항목: 111 → 108 (-3, parametrize 확장 후 최종)
- 전체 테스트 수: 1,285 → 1,282 통과
- 전체 src 커버리지: **90.66% 유지**
- `scripts/live_trader.py` 모듈 커버리지: 52% 유지(변화 없음)

주요 변경:
- **Parametrize 통합**: `TestSafeInt`(4→1), `TestBuildStrategies`(4→2), `TestCalcTimeRatio`(7→1), `TestRegimeCapitalAllocation`(5→2), `TestUpdateRiskAfterTrade`(5→1), `TestThemeBoostIntegration`(7→3), `TestFlowSignalIntegration`(6→3), `TestExecuteBuy`(4→3, strategy parametrize)
- **Useless assertion 삭제**: `TestDualStopLoss`의 Python `max()` 동작 검증 2개 삭제(남은 2개는 `max_loss_pct` 기본/커스텀 통합 1개로 축약), `TestDataclasses` LivePosition 2개 통합
- **Mock-only 테스트 삭제**: `TestRunTradingLoopWs.test_main_ws_fallback_to_polling` — SUT 호출 없이 mock 자체만 검증(useless) 삭제
- **Implementation coupling 재작성**: `test_kill_switch_force_close_after_sell` — `mock_force_close.assert_called_once()` 대신 `state.positions == {}` 상태 기반 검증으로 전환 (실제 `force_close_all` 실행 경로 커버)
- **소소한 cleanup**: kill_switch stop_buy 테스트의 잉여 `assert_called_once()` 제거, `test_rescreened_default_empty` + `test_rescreened_tracking` 병합, `test_buy_quantity_zero`의 `assert_not_called` → `await_count == 0`로 전환

WS/주문/포지션 핵심 행동 테스트는 전부 보존됨.

---

## 5. 우선순위 근거

1. **broker**가 최우선: `test_realtime.py` 와 `test_ws_contract.py`의 **명시적 중복**(동일 이름 테스트 여러 개)이 가장 제거 효과 큼 + 파일 LoC 1,164/373
2. **strategy** 그 다음: `test_flow_signal.py`는 테스트 당 3~5줄의 기계적 반복. parametrize 효과 큼
3. **trading**은 mock-everything / deep mock chain 위험. 재작성 리스크 있어 중간 순위
4. **ai**는 fallback 체인 검증이 이미 `test_manager.py`에 집중되어 있어 재작성 범위 명확

## 6. 안전장치

- 각 PR마다 `uv run pytest tests/ --cov=src --cov-report=term-missing` 결과 첨부
- 커버리지 85% 미만 시 즉시 롤백 (또는 삭제 대신 유지로 계획 조정)
- 동일 소스 파일을 건드리는 PR이 동시에 열리지 않도록 순차 진행
- 각 PR 독립 롤백 가능 (병합 순서 무관)
