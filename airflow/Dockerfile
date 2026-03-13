FROM apache/airflow:3.1.8-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

USER airflow

# 데이터 수집 라이브러리 설치 (Poetry airflow 그룹)
# Airflow 자체는 베이스 이미지에 포함, 추가 라이브러리만 설치
RUN pip install --no-cache-dir poetry
COPY --chown=airflow:root pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false && \
    poetry install --only airflow --no-root --no-interaction
