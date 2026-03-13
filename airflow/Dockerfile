FROM apache/airflow:2.9.0-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

USER airflow

# Poetry 설치 + airflow 그룹 의존성 설치
RUN pip install --no-cache-dir poetry
COPY --chown=airflow:root pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false && \
    poetry install --only airflow --no-root --no-interaction
