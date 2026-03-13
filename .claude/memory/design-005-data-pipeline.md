# Phase 3 데이터+AI 파이프라인 설계

> **상태**: 활성 — 3-DB~3-7 구현 완료, 3-8 텔레그램 양방향 대기
> **갱신**: 2026-03-14

## 1. 목표

장전/장후 자동 데이터 수집 → LLM 분석 → 전략 파라미터 미세 조정.
로컬 Airflow로 개발/테스트, 나중에 EKS 배포.

## 2. 프로젝트 구조

```
kiwoom-autotrade/
├── src/                        # FastAPI 백엔드 (기존)
├── airflow/                    # Airflow 파이프라인 (신규)
│   ├── dags/                   # 오케스트레이션만 — 로직 0줄
│   │   ├── premarket/
│   │   │   ├── data_collection.py    # 장전 데이터 수집
│   │   │   └── llm_briefing.py       # LLM 브리핑 생성
│   │   ├── postmarket/
│   │   │   ├── trade_review.py       # 장후 매매 리뷰
│   │   │   └── param_adjustment.py   # 파라미터 조정 제안
│   │   └── periodic/
│   │       ├── news_collection.py    # 뉴스 수집 (1~2시간)
│   │       └── macro_weekly.py       # 거시경제 주간 수집
│   │
│   ├── plugins/                # 비즈니스 로직 (Airflow 표준 sys.path 자동 추가)
│   │   ├── collectors/         # 데이터 수집 모듈
│   │   │   ├── __init__.py
│   │   │   ├── dart.py         # DART 공시/재무
│   │   │   ├── krx.py          # pykrx 주가/투자자
│   │   │   ├── fred.py         # FRED VIX/금리/환율
│   │   │   ├── ecos.py         # 한국은행 거시경제
│   │   │   ├── news.py         # 네이버 뉴스 검색
│   │   │   ├── overseas.py     # yfinance 해외지수
│   │   │   └── storage.py      # 데이터 저장
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── briefing.py     # 장전 브리핑 생성
│   │   │   └── review.py       # 장후 리뷰 분석
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   ├── param_tuner.py  # 파라미터 조정 제안
│   │   │   └── sentiment.py    # 뉴스 감성 분석
│   │   └── callbacks/
│   │       ├── __init__.py
│   │       └── telegram.py     # 실패/완료 알림
│   │
│   ├── tests/
│   │   ├── dags/
│   │   │   └── test_dag_integrity.py   # DAG import/순환 검증
│   │   ├── collectors/
│   │   │   ├── test_collectors.py
│   │   │   ├── test_overseas.py
│   │   │   ├── test_storage.py
│   │   │   └── test_news.py
│   │   └── analysis/
│   │       └── test_sentiment.py
│   │
│   ├── Dockerfile              # apache/airflow:3.1.8 기반 커스텀 이미지
│   ├── docker-compose.yml      # Airflow 로컬 실행
│   └── .env.example
│
├── scripts/                    # 기존 스크립트 (live_trader 등)
└── tests/                      # 기존 테스트
```

### 핵심 원칙
- `dags/` = import + task 연결만. 비즈니스 로직 0줄.
- `plugins/` = 순수 Python. Airflow 없이 pytest로 테스트 가능. Airflow가 자동으로 sys.path에 추가.
- `src/` 재활용: plugins/에서 기존 src/ 패키지 import (PYTHONPATH 설정)

## 3. 데이터 소스 확정

### Tier 1 — 즉시 구현 (공식 API, 무료, 안정)

| 소스 | 라이브러리 | 데이터 | DAG | 스케줄 |
|------|-----------|-------|-----|--------|
| DART | `opendartreader` | 공시, 재무제표 | premarket/data_collection | 08:00 |
| pykrx | `pykrx` | OHLCV, 투자자 매매 | postmarket/trade_review | 16:00 |
| FRED | `fredapi` | VIX, 미국 금리, 환율, WTI | premarket/data_collection | 08:00 |
| ECOS | `requests` | 기준금리, 거시경제 | periodic/macro_weekly | 월 08:00 |

### Tier 2 — 조건부 (모니터링 필요)

| 소스 | 라이브러리 | 데이터 | DAG | 스케줄 |
|------|-----------|-------|-----|--------|
| yfinance | `yfinance` | 해외지수 실시간 | premarket/data_collection | 08:00 |
| 네이버 뉴스 | `requests` | 종목 뉴스 | periodic/news_collection | 2시간 |

### 제외
텔레그램 채널, Google Trends, 증권사 리포트, Alpha Vantage 무료, 카카오, Reddit/StockTwits.
상세: `research-data-sources-phase3.md`

## 4. DAG 설계

### DAG 1: premarket_data_collection (장전 데이터 수집)

```
스케줄: 0 8 * * 1-5 (평일 08:00)
catchup: False

[fetch_dart_disclosures] → \
[fetch_fred_macro]       → → [store_premarket_data] → Dataset("premarket_data")
[fetch_overseas_index]   → /
```

- 3개 수집 태스크 병렬 실행
- 결과를 통합 저장 후 Dataset 트리거
- 실패 시 Telegram 알림 + 2회 재시도 (5분 간격)

### DAG 2: llm_briefing (LLM 브리핑)

```
스케줄: Dataset("premarket_data") 트리거 (08:30~09:00 예상)
catchup: False

[load_premarket_data] → [generate_briefing] → [send_telegram_briefing]
                                             → [adjust_entry_weights]
```

- premarket_data 완료 시 자동 트리거 (Dataset-aware)
- LLM에 DART 공시 + 해외지수 + VIX/금리 전달
- 산출물: 테마 스코어, 진입 가중치 ±20% 조정, 위험 종목 플래그
- 텔레그램으로 요약 전송

### DAG 3: news_collection (뉴스 수집)

```
스케줄: 0 */2 9-15 * * 1-5 (장중 2시간 간격)
catchup: False

[search_naver_news] → [extract_sentiment] → [store_news_data]
```

- 유니버스 종목명 키워드로 네이버 뉴스 검색
- 감성 분석 (긍정/부정/중립)
- 일 25,000건 한도 내 운영

### DAG 4: postmarket_trade_review (장후 리뷰)

```
스케줄: 30 15 * * 1-5 (평일 15:30)
catchup: False

[fetch_krx_data]     → \
[load_trade_history]  → → [llm_review] → [suggest_params] → [send_report]
[load_news_sentiment] → /
```

- pykrx로 당일 주가/투자자 데이터 수집
- 당일 매매 기록 + 뉴스 감성 + 시장 데이터 → LLM 분석
- 파라미터 조정 제안 (SL/TP 승수, 진입 필터 등)
- 사용자 텔레그램으로 리뷰 리포트 전송

### DAG 5: macro_weekly (거시경제 주간)

```
스케줄: 0 8 * * 1 (월요일 08:00)
catchup: False

[fetch_ecos_rates] → [fetch_fred_weekly] → [store_macro_data]
```

- ECOS 기준금리 + FRED 주간 지표
- 주간 매크로 트렌드 요약

## 5. DAG 코드 패턴 (TaskFlow API)

```python
# dags/premarket/data_collection.py
from __future__ import annotations

from datetime import timedelta

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

from callbacks.telegram import on_failure_telegram


@dag(
    dag_id="premarket_data_collection",
    schedule="0 8 * * 1-5",
    start_date=days_ago(1),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_telegram,
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["premarket", "data", "tier1"],
)
def premarket_data_collection():
    @task()
    def fetch_dart() -> dict:
        from collectors.dart import collect_disclosures
        return collect_disclosures()

    @task()
    def fetch_fred() -> dict:
        from collectors.fred import collect_macro
        return collect_macro()

    @task()
    def fetch_overseas() -> dict:
        from collectors.overseas import collect_indices
        return collect_indices()

    @task(outlets=[premarket_dataset])
    def store(dart: dict, fred: dict, overseas: dict) -> None:
        from collectors import store_premarket
        store_premarket(dart, fred, overseas)

    store(fetch_dart(), fetch_fred(), fetch_overseas())

premarket_data_collection()
```

## 6. 로컬 개발 환경

```yaml
# airflow/docker-compose.yml (실제 구현)
services:
  airflow:
    build:
      context: ..
      dockerfile: airflow/Dockerfile
    env_file: .env
    volumes:
      - ./dags:/opt/airflow/dags
      - ./plugins:/opt/airflow/plugins
      - ../src:/opt/airflow/src        # 기존 src/ 재활용
    ports:
      - "8080:8080"
    environment:
      - PYTHONPATH=/opt/airflow/src
      - AIRFLOW__CORE__LOAD_EXAMPLES=false
```

- Docker 이미지: `apache/airflow:3.1.8-python3.12` (Dockerfile 기반 빌드)
- apache-airflow는 Docker 이미지에 포함. pyproject.toml `airflow` 그룹은 수집 라이브러리만 (`opendartreader`, `pykrx`, `yfinance`, `fredapi`)
- `requirements.txt`는 삭제됨 (uv + pyproject.toml로 통합)

## 7. 테스트 전략

```python
# airflow/tests/dags/test_dag_integrity.py
from airflow.models import DagBag

def test_no_import_errors():
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    assert len(dagbag.import_errors) == 0

def test_all_dags_have_tags():
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    for dag_id, dag in dagbag.dags.items():
        assert dag.tags, f"{dag_id} has no tags"
```

- `plugins/` 로직: 순수 pytest (Airflow 의존 없음)
- DAG 구조: DagBag 검증 (import, 순환, 태그)
- 통합: `dag.test()` (Airflow 3.x+)
- 실행: `cd airflow && uv run pytest tests/`

## 8. 에러 핸들링

| 수준 | 전략 |
|------|------|
| Task | retries=2, retry_delay=5min, exponential_backoff |
| DAG | execution_timeout=30min |
| 알림 | on_failure_callback → Telegram (기존 봇 재활용) |
| Rate Limit | 수집기마다 sleep 간격 내장 (DART 0.1s, pykrx 1.5s, 네이버 0.5s) |

## 9. 시크릿 관리

```bash
# .env (로컬)
AIRFLOW_VAR_DART_API_KEY=xxx
AIRFLOW_VAR_FRED_API_KEY=xxx
AIRFLOW_VAR_NAVER_CLIENT_ID=xxx
AIRFLOW_VAR_NAVER_CLIENT_SECRET=xxx
AIRFLOW_CONN_KIWOOM_DB=postgresql://...

# EKS 배포 시: AWS Secrets Manager + External Secrets Operator
```

## 10. 구현 순서

| 단계 | 내용 | 의존성 | 상태 | 담당 |
|------|------|--------|------|------|
| **3-1** | Airflow 로컬 환경 구축 | 없음 | ✅ PR #147 | data-eng |
| **3-2** | Tier 1 수집기 (DART, pykrx, FRED, ECOS) | 3-1 | ✅ PR #147 | data-eng |
| **3-3** | 장전 데이터 수집 DAG + overseas + storage | 3-2 | ✅ PR #149 | data-eng |
| **3-5** | 뉴스 수집 파이프라인 (네이버 뉴스 + 감성 분류) | 3-1 | ✅ PR #149 | data-eng |
| **3-DB** | DB 테이블 + 전략 설정 API + kill switch 리팩토링 | 3-3, 3-5 | ✅ 구현 완료 | backend |
| **3-4** | LLM 브리핑 (Claude/GPT/Gemini fallback) | 3-DB | ✅ 구현 완료 | data-eng |
| **3-6** | 장후 매매 리뷰 DAG | 3-DB, 3-5 | ✅ 구현 완료 | data-eng |
| **3-7** | 파라미터 자동 조정 제안 + 승인 흐름 | 3-6 | ✅ 구현 완료 | backend + data-eng + frontend |
| **3-8** | 텔레그램 양방향 통신 | 3-4 | ⬜ 다음 | — |

## 10-1. 3-DB 상세 — DB 테이블 + 전략 설정 + Kill Switch

### 신규 테이블 (alembic 마이그레이션)

| 테이블 | 주요 컬럼 | 용도 |
|--------|----------|------|
| `market_data` | id, category, date, data(JSONB), collected_at | 수집 데이터 통합 |
| `news_articles` | id, keyword, title, url, description, sentiment, published_at, collected_at | 뉴스 + 감성 |
| `strategy_config` | id, key, value(JSONB), description, updated_at, updated_by | 전략 파라미터 |

### strategy_config 초기 데이터 (DB, 사용자 조정 가능)

| key | 기본값 | 설명 |
|-----|--------|------|
| atr_stop_mult | 1.5 | ATR 손절 승수 |
| atr_tp_mult | 3.0 | ATR 익절 승수 |
| volume_ratio | 1.5 | 거래량 배수 |
| entry_start_time | "09:05" | 진입 시작 |
| entry_end_time | "13:00" | 진입 마감 |
| max_holding_days | 5 | 스윙 최대 보유일 |
| gap_risk_threshold | -0.03 | 갭다운 손절 기준 |
| take_profit | 0.015 | 고정 익절 |
| stop_loss | -0.005 | 고정 손절 |
| max_positions | 3 | 최대 동시 포지션 |

### CONST 유지 (코드 고정, DB 안 넣음)

- MIN_ATR_PCT (0.0035), MIN_STOP_PCT (0.005), MIN_TP_PCT (0.010)
- FORCE_CLOSE_HHMM ("1515")
- 거래세 (0.0020), 수수료 (0.00015)
- DRAWDOWN_STOP_BUY_PCT (-2%), DRAWDOWN_FORCE_CLOSE_PCT (-3%)

### Kill Switch 리팩토링

| 현재 | 변경 |
|------|------|
| kill_switch.py (drawdown 관리) | DrawdownGuard로 rename |
| — | KillSwitch 신규 — soft_stop() + hard_stop() |

- **Soft stop**: 신규 매수 중단, 보유분은 전략대로 청산
- **Hard stop**: 즉시 전량 시장가 청산 + 매매 중단 (확인 필수)

### API 엔드포인트

| method | path | 용도 |
|--------|------|------|
| GET | /api/v1/settings/strategy | 전략 파라미터 조회 |
| PUT | /api/v1/settings/strategy | 전략 파라미터 수정 |
| POST | /api/v1/trading/soft-stop | 매매 중단 |
| POST | /api/v1/trading/hard-stop | 긴급 청산 |

## 10-2. 3-4 상세 — LLM 브리핑

### LLM 클라이언트 (3 provider fallback)

| 순위 | provider | 라이브러리 |
|------|----------|-----------|
| 1 | Claude | anthropic |
| 2 | GPT | openai |
| 3 | Gemini | google-generativeai |

- `airflow/plugins/llm/client.py` — 통합 클라이언트 (순회 + fallback)
- `airflow/plugins/llm/briefing.py` — 수집 데이터 → LLM → 테마 스코어 + 진입 가중치
- 결과: DB 저장 + 텔레그램 전송

## 10-3. 3-6/3-7 상세 — 장후 리뷰 + 파라미터 제안

- `airflow/plugins/llm/review.py` — 매매 기록 + 시장 + 뉴스 → LLM 분석
- `airflow/plugins/analysis/param_tuner.py` — LLM 결과 → 파라미터 조정 제안
- 제안은 DB 저장 → 웹에서 승인/거부 → 승인 시 strategy_config 업데이트
- `GET /api/v1/settings/strategy/suggestions` — 미승인 제안 목록
- `POST /api/v1/settings/strategy/suggestions/{id}/approve` — 승인

## 10-4. 팀 분배 (병렬 가능 기준)

| 에이전트 | 작업 | 파일 범위 |
|----------|------|----------|
| **backend** | 3-DB (모델+마이그레이션+API) + kill switch 리팩토링 | src/, alembic/, tests/backend |
| **data-eng** | 수집기 DB 전환 + LLM 클라이언트 + 브리핑/리뷰 | airflow/plugins/, airflow/dags/, airflow/tests/ |
| **frontend** | 전략 설정 UI + kill switch 버튼 + 제안 승인 UI | frontend/src/ |

backend + data-eng 병렬 (파일 안 겹침). frontend는 backend API 완성 후.

### Phase 3 완료 후 → 인프라 정리

| 단계 | 내용 |
|------|------|
| **INF-1** | Docker Compose 통합 (백엔드 + 프론트 + DB + Airflow) |
| **INF-2** | EKS 배포 (kiwoom-infra 레포, Terraform + ArgoCD) |
| **INF-3** | CI/CD 연결 (build-push.yml → ECR → ArgoCD) |

## 11. 필요 API 키

| 서비스 | 발급처 | 비용 |
|--------|--------|------|
| DART | opendart.fss.or.kr | 무료 |
| FRED | fred.stlouisfed.org | 무료 |
| ECOS | ecos.bok.or.kr | 무료 |
| 네이버 검색 | developers.naver.com | 무료 |

## 12. 한국 증시 커스텀 Timetable

공휴일/휴장일 스킵을 위해 Airflow 커스텀 Timetable 구현:
- 기존 `scripts/korean_holidays.py` 재활용
- 토/일 + 법정 공휴일 + 대체공휴일 제외
