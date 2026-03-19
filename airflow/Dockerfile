FROM apache/airflow:3.1.8-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

USER airflow

# uv 설치
RUN pip install --no-cache-dir uv

# 데이터 수집 라이브러리 설치 (airflow 그룹)
# Airflow 자체는 베이스 이미지에 포함, 추가 라이브러리만 설치
# pip install 로 /home/airflow/.local 에 설치
RUN pip install --no-cache-dir \
    opendartreader \
    pykrx \
    fredapi \
    yfinance \
    anthropic \
    openai \
    google-generativeai \
    psycopg2-binary
