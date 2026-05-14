# Short Swing Strategy Implementation Brief

이 문서는 현재 자동매매 시스템을 `cross_momentum` 월간 리밸런스 중심에서, 실제 사용자가 원하는 단타/중단타 목적에 맞는 `short_swing` 전략으로 재구성하기 위한 구현 지시서다.

목표는 "좋아 보이는 전략 설명"이 아니라, Claude가 이 문서를 보고 바로 PR 단위로 구현할 수 있게 만드는 것이다.

## 0. 현재 문제

현재 시스템은 전략 이름, UI, 설정, 실제 자동매매 엔진이 서로 다른 방향을 가리키고 있다.

- `/strategy` 화면은 52주 고점, 거래량, 손절, 익절, 강제청산 등 단타/돌파 전략처럼 보인다.
- 실제 자동매매 트리거는 `ACTIVE_STRATEGY=cross_momentum`이면 월말 14:55 크로스섹션 모멘텀 리밸런스다.
- `strategy_config`의 `volume_ratio`, `entry_end_time`, `stop_loss`, `take_profit`은 단타/스크리닝 계열 값인데, `cross_momentum` 핵심 파라미터와 직접 연결되지 않는다.
- 현재 `cross_momentum`은 코드상 `top20%`, `n_positions=40`, `vol_filter=False`, `trend_filter=False`로 고정되어 있다.
- 현재 계좌 규모에서 40종목 분산은 너무 잘게 쪼개진다.
- 사용자는 초단타보다 짧은 스윙, 즉 2~10거래일 보유 후 손절/익절/트레일링/시간청산하는 자동매매를 원한다.

결론: `cross_momentum`은 장기/월간 리밸런스 전략으로 남기고, 메인 자동매매 전략은 `short_swing`으로 별도 구현해야 한다.

## 1. 전략 정의

전략명: `short_swing`

성격:

- 일봉 기반 후보 생성
- 다음 거래일 장중 조건 충족 시 진입
- 2~10거래일 보유
- 손절, 익절, 트레일링, 최대 보유일로 청산
- 최대 3~5종목 집중
- 하루 신규 진입 1~2개 제한

비목표:

- 호가 초단타가 아니다.
- 시장가 난사 전략이 아니다.
- LLM이 종목을 직접 찍는 전략이 아니다.
- 월말 40종목 리밸런스 전략이 아니다.

## 2. 기본 파라미터

초기 기본값은 현재 계좌 규모와 운영 안전성을 기준으로 보수적으로 둔다.

```json
{
  "short_swing_enabled": true,
  "max_positions": 5,
  "max_daily_new_positions": 2,
  "cash_buffer_pct": 0.15,
  "min_order_amount": 500000,
  "entry_start_time": "09:20",
  "entry_end_time": "13:00",
  "stop_loss": -0.02,
  "take_profit": 0.04,
  "trailing_armed_pct": 0.03,
  "trailing_stop_pct": -0.015,
  "max_holding_days": 7,
  "min_price": 1000,
  "min_avg_trading_value": 3000000000,
  "avoid_gap_up_pct": 0.08,
  "avoid_intraday_rise_pct": 0.15,
  "pullback_min_pct": -0.10,
  "pullback_max_pct": -0.03,
  "market_ma_period": 20,
  "stock_ma_short": 20,
  "stock_ma_long": 60,
  "candidate_limit": 20,
  "watchlist_limit": 20
}
```

파라미터 의미:

| Key | 의미 |
| --- | --- |
| `max_positions` | 전체 동시 보유 종목 수 |
| `max_daily_new_positions` | 하루 신규 매수 최대 수 |
| `cash_buffer_pct` | 현금으로 남길 비율 |
| `min_order_amount` | 이 금액 미만 주문 금지 |
| `entry_start_time` | 신규 진입 시작 시각 |
| `entry_end_time` | 신규 진입 종료 시각 |
| `stop_loss` | 매수가 대비 손절률 |
| `take_profit` | 매수가 대비 기본 익절률 |
| `trailing_armed_pct` | 트레일링 활성화 수익률 |
| `trailing_stop_pct` | 고점 대비 트레일링 청산률 |
| `max_holding_days` | 최대 보유 거래일 수 |
| `min_avg_trading_value` | 최근 평균 거래대금 최소값 |
| `avoid_gap_up_pct` | 시초 갭상승 회피 기준 |
| `avoid_intraday_rise_pct` | 당일 과열 추격 회피 기준 |
| `pullback_min_pct` | 60일 고점 대비 최대 눌림 |
| `pullback_max_pct` | 60일 고점 대비 최소 눌림 |

주의:

- `stop_loss`와 `trailing_stop_pct`는 하락률이므로 음수로 저장한다.
- UI에서 양수로 입력받을 수는 있으나 API 저장 단계에서 음수로 정규화해야 한다.
- 내부 계산은 부호 규칙을 통일한다.

## 3. ACTIVE_STRATEGY 추가

파일: `src/config/active_strategy.py`

추가:

```python
class ActiveStrategy(StrEnum):
    CROSS_MOMENTUM = "cross_momentum"
    MULTI_REGIME = "multi_regime"
    SHORT_SWING = "short_swing"
    NONE = "none"
```

운영 환경:

```env
ACTIVE_STRATEGY=short_swing
```

기대 동작:

- `ACTIVE_STRATEGY=short_swing`일 때만 short swing 자동 진입/청산 job이 주문을 낸다.
- `cross_momentum` job과 동시에 자동 주문을 내면 안 된다.
- 수동 `/trade` 주문은 기존처럼 독립 동작해야 한다.

## 4. 후보 생성

후보 생성은 장마감 후 수행한다. 장중에 전체 유니버스를 계속 훑지 않는다.

권장 파일:

- `src/screening/short_swing_screener.py`
- `tests/screening/test_short_swing_screener.py`

실행 시각:

- 일봉 데이터 수집 완료 후
- 예: 15:50 또는 Airflow daily candle DAG 완료 이후

유니버스:

- KOSPI/KOSDAQ 거래대금 상위 100~300
- 관리종목 제외
- 투자주의/환기/정리매매 제외 가능하면 제외
- ETF/ETN/스팩/우선주 제외
- 현재가 1,000원 미만 제외
- 최근 20일 평균 거래대금 30억 원 미만 제외

필수 계산값:

- 종가
- 20일 이동평균
- 60일 이동평균
- 60일 고가
- 60일 고가 대비 현재 눌림률
- 20일 평균 거래대금
- 당일 거래대금
- 최근 5거래일 수익률

후보 필터:

```text
close > MA20
close > MA60
drawdown_from_60d_high between -10% and -3%
avg_trading_value_20d >= min_avg_trading_value
today_return < +15%
price >= min_price
```

점수 예시:

```text
score =
  +25 if close > MA20
  +20 if close > MA60
  +20 if drawdown_from_60d_high between -10% and -3%
  +15 if trading_value_today > avg_trading_value_20d * 1.2
  +10 if return_5d between 0% and 12%
  +10 if KOSPI or KOSDAQ is above MA20
```

저장 결과는 상위 `candidate_limit`개만 다음날 감시 대상으로 쓴다.

## 5. 데이터 모델

새 테이블을 권장한다.

### 5.1 short_swing_candidates

목적: 장마감 후 생성된 다음 거래일 감시 후보 저장.

필드:

| Field | Type | 설명 |
| --- | --- | --- |
| `id` | UUID | PK |
| `trade_date` | date | 후보 생성 기준일 |
| `symbol` | str | 종목코드 |
| `name` | str | 종목명 |
| `close` | int | 기준일 종가 |
| `ma20` | float | 20일 이동평균 |
| `ma60` | float | 60일 이동평균 |
| `high_60d` | int | 60일 고가 |
| `drawdown_from_high` | float | 고점 대비 눌림률 |
| `trading_value` | int | 당일 거래대금 |
| `avg_trading_value_20d` | int | 20일 평균 거래대금 |
| `return_5d` | float | 5일 수익률 |
| `score` | float | 후보 점수 |
| `reason_json` | JSON | 통과 사유 |
| `created_at` | datetime | 생성 시각 |

제약:

- `(trade_date, symbol)` unique.

### 5.2 short_swing_positions

목적: short swing 전략이 관리하는 포지션 상태 저장.

필드:

| Field | Type | 설명 |
| --- | --- | --- |
| `id` | UUID | PK |
| `symbol` | str | 종목코드 |
| `name` | str | 종목명 |
| `entry_date` | date | 진입일 |
| `entry_time` | datetime | 진입시각 |
| `entry_price` | int | 평균 진입가 |
| `quantity` | int | 보유 수량 |
| `highest_price_since_entry` | int | 진입 후 최고가 |
| `stop_price` | int | 손절 가격 |
| `take_profit_price` | int | 익절 가격 |
| `trailing_armed` | bool | 트레일링 활성 여부 |
| `max_holding_until` | date | 최대 보유 종료일 |
| `status` | str | open, closing, closed |
| `exit_reason` | str | 청산 사유 |
| `created_at` | datetime | 생성시각 |
| `updated_at` | datetime | 수정시각 |

제약:

- `status='open'`인 같은 `symbol` 중복 금지.
- 수동 보유 종목과 자동 포지션을 구분해야 하므로 `strategy='short_swing'` 개념을 반드시 기록한다.

## 6. 장중 진입 로직

권장 파일:

- `src/trading/short_swing.py`
- `tests/trading/test_short_swing.py`

실행 시각:

- 09:20~13:00
- 1분 또는 5분 주기
- 감시 대상은 전일 후보 상위 `watchlist_limit`개만

신규 매수 금지 조건:

```text
ACTIVE_STRATEGY != short_swing
kill switch active
현재 보유 포지션 수 >= max_positions
오늘 신규 진입 수 >= max_daily_new_positions
available_cash <= min_order_amount
KOSPI와 KOSDAQ 둘 다 MA20 아래
이미 보유 중인 종목
pending buy order 존재
시초 갭상승률 > avoid_gap_up_pct
당일 상승률 > avoid_intraday_rise_pct
```

최소 진입 조건:

```text
전일 고가 돌파
현재가 > VWAP
현재가가 당일 과열 제한 이내
거래대금/거래량이 평균 대비 증가
```

진입 조건은 처음에는 단순해야 한다. 너무 많은 조건을 한 번에 넣으면 디버깅이 어렵다.

초기 구현식:

```text
entry_signal =
  current_price > previous_day_high
  and current_price > intraday_vwap
  and gap_up_pct <= avoid_gap_up_pct
  and intraday_rise_pct <= avoid_intraday_rise_pct
```

주문 방식:

- 초기에는 지정가 권장.
- 주문 가격은 현재가 또는 매도1호가 기반.
- 시장가 매수는 별도 feature flag 없이는 금지.
- 미체결 주문은 일정 시간 뒤 취소 또는 재가격해야 한다.

수량 계산:

```text
usable_cash = available_cash * (1 - cash_buffer_pct)
remaining_slots = max_positions - current_open_positions
target_position_value = usable_cash / remaining_slots
target_position_value = max(min_order_amount, target_position_value)
target_position_value = min(target_position_value, available_cash * (1 - cash_buffer_pct))
quantity = floor(target_position_value / order_price)
```

예외:

- `quantity <= 0`이면 주문하지 않는다.
- `target_position_value < min_order_amount`이면 주문하지 않는다.
- 주문 직전 `available_cash`와 kill switch를 다시 확인한다.

## 7. 청산 로직

청산은 신규 진입보다 더 중요하다.

실행 시각:

- 09:20~15:10
- 1분 또는 5분 주기
- open position만 검사

청산 조건:

```text
현재가 <= entry_price * (1 + stop_loss)
현재가 >= entry_price * (1 + take_profit)
현재가 >= entry_price * (1 + trailing_armed_pct) -> trailing_armed = true
trailing_armed and 현재가 <= highest_price_since_entry * (1 + trailing_stop_pct)
보유 거래일수 >= max_holding_days
종가 기준 close < MA20 -> 다음날 청산 후보
kill switch active -> 청산 또는 신규매수 정지 정책 적용
```

초기 구현은 전량 매도만 한다. 부분익절은 후속 PR로 미룬다.

청산 사유:

- `stop_loss`
- `take_profit`
- `trailing_stop`
- `max_holding_days`
- `ma20_breakdown`
- `kill_switch`
- `manual`

주문 후:

- 주문 이벤트를 기존 주문/거래 이력에 기록한다.
- broker 실패 시 `order_failed` 이벤트를 기록한다.
- 포지션 상태는 체결 확인 후 `closed`로 바꾼다.

## 8. 스케줄

권장 운영 흐름:

```text
15:40
  daily candle update 완료 확인

15:50
  short_swing 후보 생성

09:20~13:00
  후보 상위 10~20개 감시
  조건 충족 시 신규 매수

09:20~15:10
  보유 포지션 손절/익절/트레일링 관리

15:10
  시간청산/MA 이탈/리스크 청산 확인

15:20
  미체결 주문 취소
```

기존 `src/config/scheduler.py`의 `_run_active_strategies`는 Strategy 테이블 + AI engine 중심이라 short_swing에 그대로 얹기 어렵다.

권장:

- short_swing 전용 scheduler job을 만든다.
- entry check, exit check, candidate generation을 분리한다.
- Airflow가 일봉 수집을 책임지고 있다면 후보 생성은 Airflow DAG 뒤에 연결한다.

## 9. API

권장 파일:

- `src/api/v1/short_swing.py`

라우터:

```text
GET  /api/v1/short-swing/status
GET  /api/v1/short-swing/candidates?date=YYYY-MM-DD
POST /api/v1/short-swing/screen
GET  /api/v1/short-swing/positions
POST /api/v1/short-swing/run-entry-check
POST /api/v1/short-swing/run-exit-check
```

초기에는 admin only로 제한한다.

응답 예시:

```json
{
  "active_strategy": "short_swing",
  "enabled": true,
  "next_candidate_screen_at": "15:50",
  "entry_window": "09:20-13:00",
  "open_positions": 2,
  "max_positions": 5,
  "today_new_positions": 1,
  "max_daily_new_positions": 2,
  "kill_switch_active": false
}
```

## 10. UI

`/strategy`는 `ACTIVE_STRATEGY`별로 실제 전략 화면을 다르게 보여줘야 한다.

`ACTIVE_STRATEGY=short_swing`이면 표시할 정보:

- 전략명: Short Swing
- 보유기간: 2~10거래일
- 신규 진입 시간: 09:20~13:00
- 최대 보유 종목: 5
- 하루 신규 진입: 2
- 손절: -2%
- 익절: +4%
- 트레일링: +3% 이후 고점 대비 -1.5%
- 최대 보유일: 7거래일
- 다음 후보 생성 시간
- 오늘 후보 리스트
- 현재 보유 포지션
- 각 포지션의 청산 기준
- 오늘 주문/체결/실패 이력

금지:

- `short_swing` 활성 상태에서 `cross_momentum` 월말 리밸런스 정보를 메인 전략처럼 보여주지 말 것.
- `cross_momentum` 파라미터와 `short_swing` 파라미터를 같은 흐름도에 섞지 말 것.
- 실제 자동매매에 사용되지 않는 `strategy_config` 값을 "반영 중"처럼 보여주지 말 것.

`/strategy-config`:

- `short_swing` 설정 섹션을 별도로 둔다.
- 손절/익절/트레일링 부호 규칙을 명확히 표시한다.
- 저장 후 실제 scheduler/engine이 읽는 값과 동일한 source of truth를 써야 한다.

## 11. 안전장치

필수:

- mock mode 기본.
- real trading gate 통과 전 실전 주문 금지.
- kill switch 확인.
- 하루 최대 주문 수 제한.
- 하루 최대 손실 제한.
- 미체결 주문 중복 방지.
- 같은 종목 중복 매수 방지.
- 주문 전 `available_cash` 재조회.
- 주문 후 trade history 기록.
- broker 실패 시 `order_failed` 이벤트 기록.
- `POSTGRES_PASSWORD` fail-fast 정책 유지.

주문 전 체크리스트:

```text
1. ACTIVE_STRATEGY == short_swing
2. broker credential active
3. is_mock or real trading gate passed
4. kill switch inactive
5. symbol not already held by short_swing
6. no pending buy order for symbol
7. current open positions < max_positions
8. today new positions < max_daily_new_positions
9. available_cash enough
10. quantity > 0
```

## 12. 테스트 요구사항

### 12.1 후보 생성 테스트

파일:

- `tests/screening/test_short_swing_screener.py`

케이스:

- MA20 아래 종목 제외.
- MA60 아래 종목 제외.
- 60일 고점 대비 눌림률 범위 밖 제외.
- 거래대금 부족 제외.
- 당일 과열 종목 제외.
- 가격 1,000원 미만 제외.
- 점수 계산 및 정렬 확인.
- 같은 날짜 같은 종목 중복 저장 방지.

### 12.2 진입 테스트

파일:

- `tests/trading/test_short_swing.py`

케이스:

- `ACTIVE_STRATEGY != short_swing`이면 주문 안 함.
- 시장 필터 fail이면 주문 안 함.
- kill switch active면 주문 안 함.
- `max_positions` 초과 시 주문 안 함.
- `max_daily_new_positions` 초과 시 주문 안 함.
- 갭상승 과열이면 주문 안 함.
- 당일 상승 과열이면 주문 안 함.
- 이미 보유 중이면 주문 안 함.
- pending buy order 있으면 주문 안 함.
- 전일 고가 돌파 + VWAP 위면 주문 생성.
- `quantity <= 0`이면 주문 안 함.

### 12.3 청산 테스트

케이스:

- stop loss 발동.
- take profit 발동.
- trailing armed 전에는 trailing stop 미발동.
- trailing armed 후 trailing stop 발동.
- max holding days 발동.
- MA20 이탈 청산 후보 처리.
- broker 실패 시 `order_failed` 기록.

### 12.4 회귀 테스트

케이스:

- `/trade` 수동 주문 영향 없음.
- `/bot` trade history 표시 유지.
- `/dashboard` balance 표시 유지.
- 기존 kill switch 동작 유지.
- `cross_momentum`은 `ACTIVE_STRATEGY=cross_momentum`일 때만 동작.

## 13. 구현 순서

PR 1: config/model/screener

- `ActiveStrategy.SHORT_SWING` 추가.
- short_swing config 정의.
- `short_swing_candidates` 모델 및 migration.
- 후보 생성 로직 구현.
- 후보 생성 테스트.

PR 2: entry engine

- 장중 entry checker 구현.
- 자금관리/수량계산 구현.
- 중복 주문/보유 제한 구현.
- mock broker 기반 주문 생성 테스트.

PR 3: exit engine

- `short_swing_positions` 모델 및 migration.
- stop/take/trailing/max holding 청산 구현.
- 청산 테스트.

PR 4: API/UI

- `/api/v1/short-swing/*` API 구현.
- `/strategy`를 ACTIVE_STRATEGY별로 분기.
- `short_swing` status/candidates/positions 표시.
- `/strategy-config`에 short_swing 설정 섹션 추가.

PR 5: scheduler/operations

- candidate generation job 연결.
- entry/exit check job 연결.
- dry-run 로그 정리.
- mock mode 1주 운영 검증.

## 14. 검증 기준

기능 검증:

- 장마감 후 후보가 생성된다.
- 다음날 장중 조건 충족 시 mock 주문이 생성된다.
- 주문 실패 시 실패 사유가 이력에 남는다.
- 보유 포지션이 stop/take/trailing/max holding 조건으로 청산된다.
- UI가 실제 활성 전략과 같은 내용을 보여준다.

운영 검증:

- `ACTIVE_STRATEGY=none`이면 자동 주문 없음.
- `ACTIVE_STRATEGY=cross_momentum`이면 short_swing 주문 없음.
- `ACTIVE_STRATEGY=short_swing`이면 cross_momentum 주문 없음.
- mock mode에서 최소 1주 dry-run 후 실전 검토.

실전 전환 조건:

- mock mode에서 주문 생성/실패/체결/청산 이력 정상.
- 중복 주문 0건.
- kill switch 오작동 0건.
- UI와 API 상태 불일치 0건.
- 수동 주문 경로 회귀 없음.

## 15. Claude 작업 시 주의

- 단번에 전체 구현하지 말고 PR 단위로 쪼갤 것.
- `cross_momentum`을 지우지 말 것. 별도 전략으로 남길 것.
- 기존 `/trade`, `/bot`, `/dashboard` 동작을 깨지 말 것.
- 실전 주문 경로는 mock 검증 전까지 열지 말 것.
- UI는 실제 engine/config가 읽는 값만 표시할 것.
- 손절/익절 부호 규칙을 반드시 테스트로 고정할 것.
- 금융 거래 시스템이므로 fail-open 금지. 불확실하면 주문하지 않는 쪽으로 처리할 것.

## 16. 요약

`short_swing`은 현재 사용 목적에 맞는 메인 자동매매 전략이다.

핵심 구조:

```text
장마감 후보 생성
-> 다음날 후보만 감시
-> 09:20~13:00 조건 충족 시 소수 종목 매수
-> 손절/익절/트레일링/보유일수로 청산
-> UI/API/스케줄러가 같은 전략 상태를 보여줌
```

현재 `cross_momentum`은 월간 리밸런스 전략이므로 짧은 스윙 자동매매 메인 전략으로 쓰지 않는다.
