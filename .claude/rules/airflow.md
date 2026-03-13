# Airflow DAG 작성 규칙

## 버전
- Apache Airflow 3.1.8
- Python 3.12

## 디렉토리 구조

```
airflow/
├── dags/       # DAG 정의 (오케스트레이션만, 로직 0줄)
├── plugins/    # 비즈니스 로직 (Airflow 자동 sys.path)
└── tests/      # 테스트
```

## DAG 작성 패턴
- TaskFlow API 사용 (`@dag`, `@task` 데코레이터)
- import: `from airflow.sdk import dag, task, Asset`
- Airflow import는 파일 상단, **비즈니스 로직 import는 `@task` 함수 안**
  - Scheduler가 30초마다 DAG 파일을 파싱 — 상단 import는 매번 실행됨
  - 무거운 라이브러리(opendartreader, pykrx 등)는 task 안에서 lazy import
- 모든 DAG에 `tags` 필수
- `catchup=False` 기본
- `start_date`: 고정 날짜 + `timezone.utc`

## Asset (구 Dataset)
- DAG 간 데이터 의존성: `Asset("premarket_data")`
- 생산: `@task(outlets=[asset])`
- 소비: `@dag(schedule=[asset])`

## 에러 핸들링
- `default_args`: `retries=2`, `retry_delay=5min`
- `on_failure_callback`: Telegram 알림
- `execution_timeout`: 30min

## 테스트
- `plugins/` 로직: 순수 pytest (Airflow 의존 없음)
- DAG 구조: DagBag 검증 (import, 순환, 태그)
- 실행: `cd airflow && uv run pytest tests/`
