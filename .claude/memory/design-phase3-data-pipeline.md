# Phase 3 데이터+AI 파이프라인 설계

> **상태**: 설계 확정, 구현 진행 중 (Tier 1 수집기 + 기본 DAG 완료)
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

| 단계 | 내용 | 의존성 |
|------|------|--------|
| **3-1** | Airflow 로컬 환경 구축 (docker-compose + 빈 DAG) | 없음 |
| **3-2** | Tier 1 수집기 구현 (DART, pykrx, FRED, ECOS) | 3-1 |
| **3-3** | premarket_data_collection DAG | 3-2 |
| **3-4** | LLM 브리핑 서비스 (MarketBriefing) | 3-3 |
| **3-5** | 뉴스 수집 파이프라인 (네이버 뉴스) | 3-1 |
| **3-6** | 장후 매매 리뷰 DAG | 3-2, 3-5 |
| **3-7** | 파라미터 자동 조정 제안 | 3-6 |
| **3-8** | 텔레그램 양방향 통신 | 3-4 |

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
